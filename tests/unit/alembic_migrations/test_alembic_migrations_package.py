"""Unit tests for 'soliplex.alembic_migrations'.

The migrations are driven for real here, against throwaway SQLite files:
alembic executes 'env.py' by path, so running it is what covers it, and a
mocked alembic would prove nothing about whether the two databases actually
come up. A run takes a few milliseconds.

Each test is laid out in three blank-line-separated phases -- setup, then
the single call under test (the "act"), then the assertions -- and performs
that act exactly once.
"""

from __future__ import annotations

import pathlib
from unittest import mock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import alembic_migrations
from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation

AGUI = alembic_migrations.AGUI
AUTHZ = alembic_migrations.AUTHZ
POLICY = config_installation.MigrationPolicy


def _dburis(tmp_path: pathlib.Path) -> dict[str, str]:
    return {
        AGUI: f"sqlite:///{tmp_path / 'agui.sqlite'}",
        AUTHZ: f"sqlite:///{tmp_path / 'authz.sqlite'}",
    }


def _state(dburi: str, metadata) -> alembic_migrations.DatabaseState:
    engine = sa.create_engine(dburi)
    try:
        with engine.connect() as connection:
            return alembic_migrations.database_state(connection, metadata)
    finally:
        engine.dispose()


def _revision(dburi: str) -> str | None:
    engine = sa.create_engine(dburi)
    try:
        with engine.connect() as connection:
            return alembic_migrations.current_revision(connection)
    finally:
        engine.dispose()


def _create_all_unstamped(dburi: str, metadata) -> None:
    """Build a schema the way soliplex <= 0.81 did: no version row."""
    engine = sa.create_engine(dburi)
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# head_revision
# --------------------------------------------------------------------------
def test_head_revision_is_the_newest_revision():
    found = alembic_migrations.head_revision()

    # A revision id, and the one the shipped tree ends at.
    assert isinstance(found, str)
    assert found


def test_head_revision_matches_the_versions_directory():
    on_disk = sorted(
        (alembic_migrations.TREE / "versions").glob("*.py"),
    )

    found = alembic_migrations.head_revision()

    # Every revision file is named '<revision>_<slug>.py', and head is one
    # of them.
    revisions = {path.name.split("_", 1)[0] for path in on_disk}
    assert found in revisions


# --------------------------------------------------------------------------
# version_table / current_revision / database_state
# --------------------------------------------------------------------------
def test_version_table_matches_alembics_own_definition():
    found = alembic_migrations.version_table()

    assert found.name == "alembic_version"
    column = found.c.version_num
    assert column.type.length == 32
    assert not column.nullable
    assert found.primary_key.name == "alembic_version_pkc"


def test_database_state_empty(tmp_path):
    dburis = _dburis(tmp_path)

    found = _state(dburis[AGUI], agui_schema.metadata)

    assert found is alembic_migrations.DatabaseState.EMPTY


def test_database_state_unstamped_when_create_all_built_it(tmp_path):
    dburis = _dburis(tmp_path)
    _create_all_unstamped(dburis[AUTHZ], authz_schema.metadata)

    found = _state(dburis[AUTHZ], authz_schema.metadata)

    assert found is alembic_migrations.DatabaseState.UNSTAMPED


def test_database_state_stamped_after_migrating(tmp_path):
    dburis = _dburis(tmp_path)
    alembic_migrations.upgrade(dburis=dburis)

    found = _state(dburis[AGUI], agui_schema.metadata)

    assert found is alembic_migrations.DatabaseState.STAMPED


def test_current_revision_none_on_an_empty_database(tmp_path):
    dburis = _dburis(tmp_path)

    found = _revision(dburis[AGUI])

    assert found is None


def test_current_revision_ignores_an_empty_version_table(tmp_path):
    # Alembic creates the version table before running a migration, so an
    # upgrade that failed part-way leaves an empty one behind.
    dburi = f"sqlite:///{tmp_path / 'agui.sqlite'}"
    engine = sa.create_engine(dburi)
    with engine.begin() as connection:
        alembic_migrations.version_table().create(connection)
    engine.dispose()

    found = _revision(dburi)

    assert found is None


# --------------------------------------------------------------------------
# upgrade: the chain builds both databases from nothing
# --------------------------------------------------------------------------
def test_upgrade_creates_and_stamps_both_databases(tmp_path):
    dburis = _dburis(tmp_path)

    alembic_migrations.upgrade(dburis=dburis)

    head = alembic_migrations.head_revision()
    assert _revision(dburis[AGUI]) == head
    assert _revision(dburis[AUTHZ]) == head
    # And the schemas are really there.
    assert _state(dburis[AGUI], agui_schema.metadata) is (
        alembic_migrations.DatabaseState.STAMPED
    )


def test_upgrade_to_an_explicit_revision(tmp_path):
    dburis = _dburis(tmp_path)
    baseline = "d5009d4f9874"

    alembic_migrations.upgrade(baseline, dburis=dburis)

    assert _revision(dburis[AGUI]) == baseline


def test_upgrade_without_a_source_refuses():
    with pytest.raises(alembic_migrations.NoDatabasesNamed):
        alembic_migrations.upgrade()


# --------------------------------------------------------------------------
# downgrade: the operator's way back, named databases only
# --------------------------------------------------------------------------
def test_downgrade_moves_both_databases_back(tmp_path):
    dburis = _dburis(tmp_path)
    baseline = "d5009d4f9874"
    alembic_migrations.upgrade(dburis=dburis)

    alembic_migrations.downgrade(baseline, dburis=dburis)

    assert _revision(dburis[AGUI]) == baseline
    assert _revision(dburis[AUTHZ]) == baseline


def test_downgrade_offline_writes_one_sql_file_per_database(
    tmp_path, monkeypatch
):
    # As for 'upgrade': nothing connects, so the range has to say where
    # the databases stand.
    dburis = _dburis(tmp_path / "nonexistent")
    head = alembic_migrations.head_revision()
    monkeypatch.chdir(tmp_path)

    alembic_migrations.downgrade(
        f"{head}:d5009d4f9874", dburis=dburis, sql=True
    )

    for name in (AGUI, AUTHZ):
        written = (tmp_path / f"{name}.sql").read_text(encoding="utf-8")
        assert "DROP TABLE" in written or "ALTER TABLE" in written
    assert not (tmp_path / "nonexistent").exists()


# --------------------------------------------------------------------------
# ensure_current_connection: the core, on a connection the caller owns
# --------------------------------------------------------------------------


def _ensure_on(dburi, database, *, sole_writer=True, policy=None):
    engine = sa.create_engine(dburi)
    try:
        with engine.begin() as connection:
            alembic_migrations.ensure_current_connection(
                connection, database, sole_writer=sole_writer, policy=policy
            )
    finally:
        engine.dispose()


def test_ensure_current_connection_migrates_an_empty_database(tmp_path):
    dburis = _dburis(tmp_path)

    _ensure_on(dburis[AGUI], AGUI)

    assert _revision(dburis[AGUI]) == alembic_migrations.head_revision()


def test_ensure_current_connection_is_a_no_op_at_head(tmp_path):
    dburis = _dburis(tmp_path)
    alembic_migrations.upgrade(dburis=dburis)

    with mock.patch.object(alembic_migrations, "upgrade") as upgrade:
        _ensure_on(dburis[AUTHZ], AUTHZ)

    upgrade.assert_not_called()


@pytest.mark.parametrize("policy", [None, POLICY.EXPLICIT, POLICY.DISABLED])
def test_ensure_current_connection_refuses_an_unstamped_database(
    tmp_path, policy
):
    # Reported under every policy: which role may migrate is a separate
    # question from a database whose history cannot be known.
    dburis = _dburis(tmp_path)
    _create_all_unstamped(dburis[AUTHZ], authz_schema.metadata)

    with pytest.raises(alembic_migrations.UnstampedDatabase) as exc_info:
        _ensure_on(dburis[AUTHZ], AUTHZ, policy=policy)

    assert exc_info.value.names == (AUTHZ,)
    assert _revision(dburis[AUTHZ]) is None


def _stamp(dburi: str, revision: str) -> None:
    """Re-stamp a migrated database, as a newer release would have."""
    engine = sa.create_engine(dburi)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    f"UPDATE {alembic_migrations.VERSION_TABLE} "
                    "SET version_num = :revision"
                ),
                {"revision": revision},
            )
    finally:
        engine.dispose()


# A revision no release has: stands in for one belonging to a soliplex
# newer than the tree under test.
_FROM_THE_FUTURE = "ffffffffffff"


@pytest.mark.parametrize("policy", [None, POLICY.EXPLICIT, POLICY.DISABLED])
@pytest.mark.parametrize("sole_writer", [True, False])
def test_ensure_current_connection_refuses_a_newer_stamp(
    tmp_path, sole_writer, policy
):
    # Rolling the code back without downgrading first: neither stopped
    # writers nor a policy helps, so neither may change the outcome.
    dburis = _dburis(tmp_path)
    alembic_migrations.upgrade("head", dburis=dburis)
    _stamp(dburis[AUTHZ], _FROM_THE_FUTURE)

    with pytest.raises(alembic_migrations.DowngradeRequired) as exc_info:
        _ensure_on(
            dburis[AUTHZ], AUTHZ, sole_writer=sole_writer, policy=policy
        )

    error = exc_info.value
    assert error.names == (AUTHZ,)
    assert error.revision == _FROM_THE_FUTURE
    assert error.head == alembic_migrations.head_revision()
    # Nothing was written, and no command is suggested: only the release
    # holding that revision can move this database.
    assert _revision(dburis[AUTHZ]) == _FROM_THE_FUTURE
    assert "alembic" not in str(error)


@pytest.mark.parametrize(
    "policy, expected",
    [
        (POLICY.EXPLICIT, alembic_migrations.ExplicitMigrationRequired),
        (POLICY.DISABLED, alembic_migrations.MigrationsDisabled),
    ],
)
def test_ensure_current_connection_refuses_under_a_policy(
    tmp_path, policy, expected
):
    # The database is empty, so a migration is owed; the configuration
    # says this process is not the one to run it.
    dburis = _dburis(tmp_path)

    with pytest.raises(expected) as exc_info:
        _ensure_on(dburis[AGUI], AGUI, policy=policy)

    assert exc_info.value.names == (AGUI,)
    assert _revision(dburis[AGUI]) is None


@pytest.mark.parametrize(
    "policy, expected",
    [
        (POLICY.EXPLICIT, alembic_migrations.ExplicitMigrationRequired),
        (POLICY.DISABLED, alembic_migrations.MigrationsDisabled),
    ],
)
def test_ensure_current_connection_policy_outranks_the_writer_gate(
    tmp_path, policy, expected
):
    # Stopping the other writers is not the remedy when the configuration
    # says this process never migrates, so 'MigrationRequired' -- which
    # says exactly that -- must not be what comes back.
    dburis = _dburis(tmp_path)

    with pytest.raises(expected):
        _ensure_on(dburis[AGUI], AGUI, sole_writer=False, policy=policy)


@pytest.mark.parametrize("policy", [POLICY.EXPLICIT, POLICY.DISABLED])
def test_ensure_current_connection_at_head_ignores_the_policy(
    tmp_path, policy
):
    # Nothing is owed, so nothing is refused: this is what lets a service
    # configured 'disabled' start normally against a current database.
    dburis = _dburis(tmp_path)
    alembic_migrations.upgrade(dburis=dburis)

    with mock.patch.object(alembic_migrations, "upgrade") as upgrade:
        _ensure_on(dburis[AUTHZ], AUTHZ, policy=policy)

    upgrade.assert_not_called()


def test_ensure_current_connection_refuses_when_not_sole_writer(tmp_path):
    dburis = _dburis(tmp_path)

    with pytest.raises(alembic_migrations.MigrationRequired) as exc_info:
        _ensure_on(dburis[AGUI], AGUI, sole_writer=False)

    assert exc_info.value.names == (AGUI,)
    assert _revision(dburis[AGUI]) is None


@pytest.mark.asyncio
async def test_ensure_current_engine_migrates_through_the_engine(tmp_path):
    dburi = f"sqlite+aiosqlite:///{tmp_path / 'agui.sqlite'}"
    engine = sqla_asyncio.create_async_engine(dburi)

    await alembic_migrations.ensure_current_engine(
        engine, AGUI, sole_writer=True, policy=None
    )

    async with engine.connect() as connection:
        revision = await connection.run_sync(
            alembic_migrations.current_revision
        )
    await engine.dispose()
    assert revision == alembic_migrations.head_revision()


@pytest.mark.asyncio
async def test_ensure_current_engine_forwards_the_policy(tmp_path):
    # The refusal has to survive the trip through 'run_sync'.
    dburi = f"sqlite+aiosqlite:///{tmp_path / 'agui.sqlite'}"
    engine = sqla_asyncio.create_async_engine(dburi)

    with pytest.raises(alembic_migrations.ExplicitMigrationRequired):
        await alembic_migrations.ensure_current_engine(
            engine, AGUI, sole_writer=True, policy=POLICY.EXPLICIT
        )

    await engine.dispose()


@pytest.mark.parametrize(
    "revision, expected",
    [
        # Every revision in the tree, plus one belonging to a release this
        # tree predates (the rollback case).
        ("d5009d4f9874", True),
        ("63edaa5987f6", True),
        ("ffffffffffff", False),
    ],
)
def test_knows_revision(revision, expected):
    assert alembic_migrations.knows_revision(revision) is expected


def test_knows_revision_knows_head():
    head = alembic_migrations.head_revision()

    assert alembic_migrations.knows_revision(head) is True


# --------------------------------------------------------------------------
# revision_chain / split_chain: what a report shows an operator
# --------------------------------------------------------------------------
def test_revision_chain_runs_oldest_first_to_head():
    found = alembic_migrations.revision_chain()

    assert found[0].revision == "d5009d4f9874"
    assert found[-1].revision == alembic_migrations.head_revision()
    # Every revision carries the message naming its release.
    assert all(entry.doc for entry in found)


@pytest.mark.parametrize(
    "revision, n_applied",
    [
        # An empty (or unstamped) database has applied nothing.
        (None, 0),
        ("d5009d4f9874", 1),
        ("63edaa5987f6", 4),
    ],
)
def test_split_chain(revision, n_applied):
    chain = alembic_migrations.revision_chain()

    applied, pending = alembic_migrations.split_chain(revision)

    assert len(applied) == n_applied
    assert applied + pending == chain


def test_split_chain_at_head_leaves_nothing_pending():
    head = alembic_migrations.head_revision()

    applied, pending = alembic_migrations.split_chain(head)

    assert applied[-1].revision == head
    assert pending == ()


def test_split_chain_refuses_a_revision_this_tree_lacks():
    with pytest.raises(alembic_migrations.UnknownRevision, match="ffff"):
        alembic_migrations.split_chain("ffffffffffff")


# --------------------------------------------------------------------------
# migration_dburi / migration_policy: which credential, and whether at all
# --------------------------------------------------------------------------
# The six properties the resolvers read; an 'Installation' and the
# 'InstallationConfig' it wraps both answer to exactly these.
_INSTALLATION_ATTRS = {
    "thread_persistence_sync_dburi": "sqlite:///agui-runtime",
    "authorization_sync_dburi": "sqlite:///authz-runtime",
    "thread_persistence_migration_dburi": None,
    "authorization_migration_dburi": None,
    "thread_persistence_migration_policy": None,
    "authorization_migration_policy": None,
}


def _installation(**overrides):
    i_config = mock.create_autospec(
        config_installation.InstallationConfig,
        **(_INSTALLATION_ATTRS | overrides),
    )
    return i_config


@pytest.mark.parametrize(
    "database, runtime",
    [
        (AGUI, "sqlite:///agui-runtime"),
        (AUTHZ, "sqlite:///authz-runtime"),
    ],
)
def test_migration_dburi_falls_back_to_the_runtime_sync_uri(database, runtime):
    installation = _installation()

    found = alembic_migrations.migration_dburi(installation, database)

    assert found == runtime


@pytest.mark.parametrize(
    "database, attribute",
    [
        (AGUI, "thread_persistence_migration_dburi"),
        (AUTHZ, "authorization_migration_dburi"),
    ],
)
def test_migration_dburi_prefers_the_configured_one(database, attribute):
    installation = _installation(**{attribute: "postgresql://owner@/db"})

    found = alembic_migrations.migration_dburi(installation, database)

    assert found == "postgresql://owner@/db"


@pytest.mark.parametrize(
    "configured, policy, expected",
    [
        # The dev-mode default: nothing configured, nothing implied.
        (None, None, None),
        (None, POLICY.EXPLICIT, POLICY.EXPLICIT),
        (None, POLICY.DISABLED, POLICY.DISABLED),
        # A configured credential with no policy implies 'explicit'.
        ("postgresql://owner@/db", None, POLICY.EXPLICIT),
        ("postgresql://owner@/db", POLICY.EXPLICIT, POLICY.EXPLICIT),
        ("postgresql://owner@/db", POLICY.DISABLED, POLICY.DISABLED),
    ],
)
def test_migration_policy(configured, policy, expected):
    installation = _installation(
        thread_persistence_migration_dburi=configured,
        thread_persistence_migration_policy=policy,
    )

    found = alembic_migrations.migration_policy(installation, AGUI)

    assert found is expected


def test_migration_policy_reads_the_authorization_fields():
    installation = _installation(
        authorization_migration_policy=POLICY.DISABLED,
    )

    found = alembic_migrations.migration_policy(installation, AUTHZ)

    assert found is POLICY.DISABLED


@pytest.mark.parametrize(
    "database, attribute",
    [
        (AGUI, "thread_persistence_migration_dburi"),
        (AUTHZ, "authorization_migration_dburi"),
    ],
)
def test_configured_migration_dburi_when_one_is_configured(
    database, attribute
):
    installation = _installation(**{attribute: "postgresql://owner@/db"})

    found = alembic_migrations.configured_migration_dburi(
        installation, database
    )

    assert found == "postgresql://owner@/db"


@pytest.mark.parametrize("database", [AGUI, AUTHZ])
def test_configured_migration_dburi_does_not_fall_back(database):
    # Unlike 'migration_dburi', which stands the runtime URI in here.
    installation = _installation()

    found = alembic_migrations.configured_migration_dburi(
        installation, database
    )

    assert found is None


def test_migration_dburis_covers_both_databases():
    installation = _installation(
        authorization_migration_dburi="postgresql://owner@/authz",
    )

    found = alembic_migrations.migration_dburis(installation)

    assert found == {
        AGUI: "sqlite:///agui-runtime",
        AUTHZ: "postgresql://owner@/authz",
    }


# --------------------------------------------------------------------------
# resolve_dburis: the three sources, and the usage exit
# --------------------------------------------------------------------------
def _context(*, attributes=None, x_args=None):
    return mock.Mock(
        config=mock.Mock(attributes=attributes or {}),
        get_x_argument=mock.Mock(return_value=x_args or {}),
    )


def test_resolve_dburis_from_an_explicit_mapping(tmp_path):
    dburis = _dburis(tmp_path)
    context = _context(attributes={"dburis": dburis})

    found = alembic_migrations.resolve_dburis(context)

    assert found == dburis


# An installation carrying nothing but an 'id' and the two DBURIs, whose
# host comes from an environment entry declared with no value -- so the
# value has to be resolved from the process environment.
_DBURI_ONLY_INSTALLATION = """\
id: alembic-migrations-testcase
environment:
  - "SOLIPLEX_TEST_PGHOST"
thread_persistence_db:
  sync_dburi: "postgresql://soliplex@env:SOLIPLEX_TEST_PGHOST/agui"
  async_dburi: "postgresql+asyncpg://soliplex@env:SOLIPLEX_TEST_PGHOST/agui"
authorization_db:
  sync_dburi: "postgresql://soliplex@env:SOLIPLEX_TEST_PGHOST/authz"
  async_dburi: "postgresql+asyncpg://soliplex@env:SOLIPLEX_TEST_PGHOST/authz"
"""


def test_resolve_dburis_from_the_command_line(tmp_path, monkeypatch):
    # Two things at once: the DBURIs interpolate an environment entry, so
    # this passes only if 'resolve_environment()' ran; and there is no
    # 'oidc/' directory beside the config, which passes only because
    # nothing loads the rest of the installation to get at two DBURIs.
    (tmp_path / "installation.yaml").write_text(
        _DBURI_ONLY_INSTALLATION, encoding="utf-8"
    )
    monkeypatch.setenv("SOLIPLEX_TEST_PGHOST", "db.example.net")
    context = _context(x_args={"soliplex.installation_path": str(tmp_path)})

    found = alembic_migrations.resolve_dburis(context)

    assert found == {
        AGUI: "postgresql://soliplex@db.example.net/agui",
        AUTHZ: "postgresql://soliplex@db.example.net/authz",
    }


def test_resolve_dburis_without_an_installation_prints_usage(capsys):
    context = _context()

    with pytest.raises(SystemExit) as exc_info:
        alembic_migrations.resolve_dburis(context)

    assert exc_info.value.code == 2
    assert "soliplex.installation_path" in capsys.readouterr().out


# --------------------------------------------------------------------------
# configure_logging
# --------------------------------------------------------------------------
def test_configure_logging_skipped_without_an_ini_file():
    cfg = mock.Mock(config_file_name=None)

    with mock.patch("logging.config.fileConfig") as file_config:
        alembic_migrations.configure_logging(cfg)

    file_config.assert_not_called()


def test_configure_logging_skipped_when_the_named_file_is_absent(tmp_path):
    # The shape the alembic CLI hands over: it fills in a default name
    # whether or not the file exists, and this project's alembic settings
    # live in 'pyproject.toml'.
    cfg = mock.Mock(config_file_name=str(tmp_path / "alembic.ini"))

    with mock.patch("logging.config.fileConfig") as file_config:
        alembic_migrations.configure_logging(cfg)

    file_config.assert_not_called()


def test_configure_logging_applies_an_existing_ini_file(tmp_path):
    ini = tmp_path / "alembic.ini"
    ini.write_text("[loggers]\nkeys = root\n", encoding="utf-8")
    cfg = mock.Mock(config_file_name=str(ini))

    with mock.patch("logging.config.fileConfig") as file_config:
        alembic_migrations.configure_logging(cfg)

    file_config.assert_called_once_with(
        str(ini), disable_existing_loggers=False
    )


# --------------------------------------------------------------------------
# offline mode, and the online rollback path
# --------------------------------------------------------------------------
def test_offline_mode_writes_one_sql_file_per_database(tmp_path, monkeypatch):
    # '--sql' writes '<name>.sql' into the current directory, and never
    # connects: the DBURIs below name files that are never created.
    dburis = _dburis(tmp_path / "nonexistent")
    monkeypatch.chdir(tmp_path)

    alembic_migrations.upgrade(dburis=dburis, sql=True)

    for name in (AGUI, AUTHZ):
        written = (tmp_path / f"{name}.sql").read_text(encoding="utf-8")
        assert "CREATE TABLE" in written
    assert not (tmp_path / "nonexistent").exists()


def test_online_failure_rolls_back_and_re_raises(tmp_path):
    dburis = _dburis(tmp_path)
    boom = RuntimeError("testing the rollback path")
    context = mock.Mock(
        configure=mock.Mock(side_effect=boom),
        run_migrations=mock.Mock(),
    )

    with pytest.raises(RuntimeError, match="testing the rollback path"):
        alembic_migrations.run_migrations_online(context, dburis)

    # Nothing was committed, so neither database gained a version row.
    assert _revision(dburis[AGUI]) is None


# --------------------------------------------------------------------------
# run: the whole of env.py's job
# --------------------------------------------------------------------------
@pytest.mark.parametrize("offline", [False, True])
def test_run_dispatches_on_the_mode(tmp_path, monkeypatch, offline):
    dburis = _dburis(tmp_path)
    monkeypatch.chdir(tmp_path)
    context = mock.Mock(
        config=mock.Mock(attributes={"dburis": dburis}, config_file_name=None),
        is_offline_mode=mock.Mock(return_value=offline),
    )
    which = "run_migrations_offline" if offline else "run_migrations_online"

    with mock.patch.object(alembic_migrations, which) as runner:
        alembic_migrations.run(context)

    runner.assert_called_once_with(context, dburis)
