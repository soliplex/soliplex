"""Unit tests for 'soliplex.cli.database'.

The commands are driven through Typer's 'CliRunner' against throwaway
SQLite files, because what they do is move real databases: a mocked
alembic would prove nothing about whether one arrives.
"""

from __future__ import annotations

import pathlib

import pytest
import sqlalchemy as sa
import typer

from soliplex import alembic_migrations
from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema
from soliplex.cli import database as cli_database
from soliplex.config import installation as config_installation
from tests._dburi import sqlite_dburi

AGUI = alembic_migrations.AGUI
AUTHZ = alembic_migrations.AUTHZ

_POLICY = config_installation.MigrationPolicy

_BASELINE = "d5009d4f9874"
# A revision no release has: stands in for one belonging to a soliplex
# newer than this tree.
_NEWER = "ffffffffffff"


def _chain_length() -> int:
    """How many revisions the shipped tree holds, which grows over time."""
    return len(alembic_migrations.revision_chain())


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


def _invoke(cli_runner, *args):
    return cli_runner.invoke(cli_database.app, [str(arg) for arg in args])


def _a_status(**kwargs):
    """A 'MigrationStatus' with the boilerplate filled in."""
    kwargs.setdefault("name", AUTHZ)
    kwargs.setdefault("dburi", "sqlite://")
    kwargs.setdefault("policy", None)
    return cli_database.MigrationStatus(**kwargs)


# --------------------------------------------------------------------------
# _redacted
# --------------------------------------------------------------------------
def test__redacted_masks_the_password():
    found = cli_database._redacted("postgresql://owner:swordfish@db/agui")

    assert "swordfish" not in found
    assert "owner" in found


def test__redacted_refuses_to_print_an_unparseable_dburi():
    # Nothing of it is shown: the text that would not parse may still hold
    # the password this is here to keep off a terminal.
    found = cli_database._redacted("postgres, but with a typo")

    assert found == cli_database._UNPARSEABLE_DBURI


# --------------------------------------------------------------------------
# MigrationStatus
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "policy, expected",
    [
        (None, False),
        (_POLICY.EXPLICIT, False),
        (_POLICY.DISABLED, True),
    ],
)
def test_migration_status_disabled(policy, expected):
    status = _a_status(policy=policy)

    assert status.disabled is expected


@pytest.mark.parametrize(
    "state, expected",
    [
        (alembic_migrations.DatabaseState.UNSTAMPED, True),
        (alembic_migrations.DatabaseState.STAMPED, False),
        (alembic_migrations.DatabaseState.EMPTY, False),
        (None, False),
    ],
)
def test_migration_status_unstamped(state, expected):
    status = _a_status(state=state)

    assert status.unstamped is expected


@pytest.mark.parametrize(
    "revision, known, expected",
    [
        (_NEWER, False, True),
        (_BASELINE, True, False),
        # Nothing to be ahead with.
        (None, True, False),
    ],
)
def test_migration_status_downgrade_required(revision, known, expected):
    status = _a_status(revision=revision, known=known)

    assert status.downgrade_required is expected


def test_migration_status_chain_splits_at_the_stamp():
    status = _a_status(
        state=alembic_migrations.DatabaseState.STAMPED,
        revision=_BASELINE,
    )

    applied, pending = status.chain

    assert [entry.revision for entry in applied] == [_BASELINE]
    assert len(pending) == _chain_length() - 1


def test_migration_status_chain_leaves_an_empty_database_all_pending():
    status = _a_status(state=alembic_migrations.DatabaseState.EMPTY)

    applied, pending = status.chain

    assert applied == ()
    assert len(pending) == _chain_length()


@pytest.mark.parametrize(
    "kwargs",
    [
        # Did not open: nothing was read, so nothing can be said.
        {"error": "OperationalError: refused"},
        # Tables, but no version row: which revisions ran is unknowable.
        {"state": alembic_migrations.DatabaseState.UNSTAMPED},
        # Stamped by a newer release: the chain is not in this tree.
        {"revision": _NEWER, "known": False},
    ],
)
def test_migration_status_chain_is_empty_without_a_chain(kwargs):
    status = _a_status(**kwargs)

    found = status.chain

    assert found == ((), ())


# --------------------------------------------------------------------------
# _targets
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "database, expected",
    [
        (None, (AGUI, AUTHZ)),
        (cli_database.Database.AGUI, (AGUI,)),
        (cli_database.Database.AUTHZ, (AUTHZ,)),
    ],
)
def test__targets(database, expected):
    found = cli_database._targets(database)

    assert found == expected


# --------------------------------------------------------------------------
# _status: one probe, reporting rather than raising
# --------------------------------------------------------------------------
def test__status_reads_an_empty_database(write_installation, tmp_path):
    i_config = cli_database._load_config(write_installation())

    found = cli_database._status(i_config, AGUI)

    assert found.state is alembic_migrations.DatabaseState.EMPTY
    assert found.revision is None
    assert found.dburi == sqlite_dburi(tmp_path / "agui.sqlite")


def test__status_reads_a_migrated_database(cli_dburis, write_installation):
    i_config = cli_database._load_config(write_installation())
    alembic_migrations.upgrade(dburis=cli_dburis)

    found = cli_database._status(i_config, AUTHZ)

    assert found.state is alembic_migrations.DatabaseState.STAMPED
    assert found.revision == alembic_migrations.head_revision()
    assert found.known is True


def test__status_reports_a_database_which_will_not_open(
    write_installation, tmp_path
):
    missing = tmp_path / "no-such-directory"
    path = write_installation(
        agui={"migration_dburi": sqlite_dburi(missing / "x.sqlite")}
    )
    i_config = cli_database._load_config(path)

    found = cli_database._status(i_config, AGUI)

    assert found.error.startswith("OperationalError: ")
    assert found.state is None


def test__status_skips_the_probe_when_asked(write_installation, tmp_path):
    # The offline case: an explicit '--sql' range says where the database
    # stands, so it need not be reachable from here at all.
    missing = tmp_path / "no-such-directory"
    path = write_installation(
        authz={"migration_dburi": sqlite_dburi(missing / "x.sqlite")}
    )
    i_config = cli_database._load_config(path)

    found = cli_database._status(i_config, AUTHZ, probe=False)

    assert found.error is None
    assert found.state is None


def test__status_carries_the_configured_policy(write_installation):
    path = write_installation(authz={"migration_policy": "disabled"})
    i_config = cli_database._load_config(path)

    found = cli_database._status(i_config, AUTHZ)

    assert found.policy is _POLICY.DISABLED


# --------------------------------------------------------------------------
# _blocker / _check_movable
# --------------------------------------------------------------------------
def test__blocker_passes_a_movable_database():
    status = _a_status(
        state=alembic_migrations.DatabaseState.EMPTY,
    )

    found = cli_database._blocker(status)

    assert found is None


def test__blocker_reports_a_database_which_did_not_open():
    status = _a_status(error="OperationalError: refused")

    found = cli_database._blocker(status)

    assert isinstance(found, alembic_migrations.DatabaseUnreachable)
    assert found.names == (AUTHZ,)


def test__blocker_reports_an_unstamped_database():
    status = _a_status(state=alembic_migrations.DatabaseState.UNSTAMPED)

    found = cli_database._blocker(status)

    assert isinstance(found, alembic_migrations.UnstampedDatabase)


def test__blocker_reports_a_stamp_from_a_newer_release():
    status = _a_status(revision=_NEWER, known=False)

    found = cli_database._blocker(status)

    assert isinstance(found, alembic_migrations.DowngradeRequired)
    assert found.revision == _NEWER


def test__check_movable_passes_movable_databases():
    statuses = (
        _a_status(name=AGUI, state=alembic_migrations.DatabaseState.EMPTY),
        _a_status(name=AUTHZ, state=alembic_migrations.DatabaseState.EMPTY),
    )

    found = cli_database._check_movable(statuses)

    assert found is None


def test__check_movable_refuses_the_run_for_a_disabled_database():
    # All or nothing, and the disabled one is named: both databases move
    # in one alembic run, so a half-applied upgrade is not on offer.
    statuses = (
        _a_status(name=AGUI, state=alembic_migrations.DatabaseState.EMPTY),
        _a_status(name=AUTHZ, policy=_POLICY.DISABLED),
    )

    with pytest.raises(alembic_migrations.MigrationsDisabled) as exc_info:
        cli_database._check_movable(statuses)

    assert exc_info.value.names == (AUTHZ,)


def test__check_movable_reraises_a_blocker():
    statuses = (_a_status(error="OperationalError: refused"),)

    with pytest.raises(alembic_migrations.DatabaseUnreachable):
        cli_database._check_movable(statuses)


# --------------------------------------------------------------------------
# _reported
# --------------------------------------------------------------------------
def test__reported_passes_a_successful_run_through():
    with cli_database._reported("Cannot upgrade"):
        found = "done"

    assert found == "done"


def test__reported_turns_an_operator_error_into_an_exit(capsys):
    boom = alembic_migrations.MigrationsDisabled([AGUI])

    with pytest.raises(typer.Exit) as exc_info:
        with cli_database._reported("Cannot upgrade"):
            raise boom

    assert exc_info.value.exit_code == 1
    assert "Cannot upgrade" in capsys.readouterr().out


def test__reported_leaves_an_unexpected_error_alone():
    # Not something the operator got wrong, so not something to swallow.
    boom = RuntimeError("a bug")

    with pytest.raises(RuntimeError, match="a bug"):
        with cli_database._reported("Cannot upgrade"):
            raise boom


# --------------------------------------------------------------------------
# _sql_revision
# --------------------------------------------------------------------------
def test__sql_revision_leaves_an_explicit_range_alone():
    status = _a_status(revision=_BASELINE)

    found = cli_database._sql_revision(status, "head:base")

    assert found == "head:base"


def test__sql_revision_starts_from_the_stamp():
    # Without the lower end alembic would replay the whole chain, there
    # being no connection offline for it to read a stamp from.
    status = _a_status(revision=_BASELINE)

    found = cli_database._sql_revision(status, "head")

    assert found == f"{_BASELINE}:head"


def test__sql_revision_starts_from_base_when_nothing_is_stamped():
    status = _a_status(state=alembic_migrations.DatabaseState.EMPTY)

    found = cli_database._sql_revision(status, "head")

    assert found == "base:head"


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------
def test_status_reports_an_empty_installation_as_all_pending(
    write_installation, cli_runner
):
    path = write_installation()

    result = _invoke(cli_runner, "status", path)

    assert result.exit_code == 0
    assert result.output.count("applied: 0") == 2
    assert result.output.count(f"pending: {_chain_length()}") == 2


def test_status_reports_a_migrated_installation_as_current(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()
    alembic_migrations.upgrade(dburis=cli_dburis)

    result = _invoke(cli_runner, "status", path)

    assert result.exit_code == 0
    assert result.output.count(f"applied: {_chain_length()}") == 2
    assert result.output.count("pending: 0") == 2


def test_status_reports_one_database_when_asked(
    write_installation, cli_runner
):
    path = write_installation()

    result = _invoke(cli_runner, "status", path, "--database", "authz")

    assert result.exit_code == 0
    assert "authz" in result.output
    assert "agui" not in result.output


def test_status_shows_the_policy_in_force(
    write_installation, tmp_path, cli_runner
):
    # Configured credential, no policy: 'explicit' is implied, and saying
    # so is the point of printing a policy nobody wrote down.
    path = write_installation(
        agui={"migration_dburi": sqlite_dburi(tmp_path / "agui.sqlite")},
        authz={"migration_policy": "disabled"},
    )

    result = _invoke(cli_runner, "status", path)

    assert "policy: explicit" in result.output
    assert "policy: disabled" in result.output


def test_status_exits_one_for_an_unstamped_database(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()
    _create_all_unstamped(cli_dburis[AGUI], agui_schema.metadata)

    result = _invoke(cli_runner, "status", path)

    assert result.exit_code == 1
    assert "bootstrap" in result.output


def test_status_exits_one_for_a_stamp_from_a_newer_release(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()
    alembic_migrations.upgrade(dburis=cli_dburis)
    _stamp(cli_dburis[AUTHZ], _NEWER)

    result = _invoke(cli_runner, "status", path)

    assert result.exit_code == 1
    assert _NEWER in result.output


def test_status_exits_one_for_a_database_which_will_not_open(
    write_installation, tmp_path, cli_runner
):
    missing = tmp_path / "no-such-directory"
    path = write_installation(
        agui={"migration_dburi": sqlite_dburi(missing / "x.sqlite")}
    )

    result = _invoke(cli_runner, "status", path)

    assert result.exit_code == 1
    assert "did not open" in result.output


# --------------------------------------------------------------------------
# upgrade
# --------------------------------------------------------------------------
def test_upgrade_brings_both_databases_to_head(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()

    result = _invoke(cli_runner, "upgrade", path)

    assert result.exit_code == 0
    head = alembic_migrations.head_revision()
    assert _revision(cli_dburis[AGUI]) == head
    assert _revision(cli_dburis[AUTHZ]) == head


def test_upgrade_to_an_explicit_revision(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()

    result = _invoke(cli_runner, "upgrade", path, "--revision", _BASELINE)

    assert result.exit_code == 0
    assert _revision(cli_dburis[AGUI]) == _BASELINE


def test_upgrade_moves_only_the_named_database(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()

    result = _invoke(cli_runner, "upgrade", path, "-d", "agui")

    assert result.exit_code == 0
    assert _revision(cli_dburis[AGUI]) is not None
    assert _revision(cli_dburis[AUTHZ]) is None


def test_upgrade_uses_the_configured_migration_dburi(
    write_installation, tmp_path, cli_runner
):
    # The whole point of #1378: the credential a migration runs as is not
    # the one the application runs as. Here it simply names another file,
    # which is enough to show which of the two was used.
    owner_db = tmp_path / "agui-as-owner.sqlite"
    path = write_installation(agui={"migration_dburi": sqlite_dburi(owner_db)})

    result = _invoke(cli_runner, "upgrade", path, "-d", "agui")

    assert result.exit_code == 0
    assert _revision(sqlite_dburi(owner_db)) is not None
    assert not (tmp_path / "agui.sqlite").exists()


def test_upgrade_refuses_a_disabled_database(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation(authz={"migration_policy": "disabled"})

    result = _invoke(cli_runner, "upgrade", path)

    assert result.exit_code == 1
    assert "Cannot upgrade" in result.output
    # All or nothing: the database which was not disabled did not move.
    assert _revision(cli_dburis[AGUI]) is None


def test_upgrade_refuses_an_unstamped_database(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()
    _create_all_unstamped(cli_dburis[AUTHZ], authz_schema.metadata)

    result = _invoke(cli_runner, "upgrade", path)

    assert result.exit_code == 1
    assert "bootstrap" in result.output


def test_upgrade_reports_a_revision_the_tree_lacks(
    write_installation, cli_runner
):
    # Alembic's own refusal, reported as a message rather than a traceback.
    path = write_installation()

    result = _invoke(cli_runner, "upgrade", path, "--revision", _NEWER)

    assert result.exit_code == 1
    assert "Cannot upgrade" in result.output


def test_upgrade_sql_writes_the_pending_delta(
    cli_dburis, write_installation, tmp_path, cli_runner, capsys
):
    path = write_installation()
    alembic_migrations.upgrade(_BASELINE, dburis=cli_dburis)

    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = _invoke(cli_runner, "upgrade", path, "--sql")
        written = (pathlib.Path(cwd) / f"{AGUI}.sql").read_text(
            encoding="utf-8"
        )

    assert result.exit_code == 0
    # From the stamp, not from base: the baseline's own DDL is not here.
    assert f"Running upgrade {_BASELINE}" in written
    # And nothing ran: the databases are where they were.
    assert _revision(cli_dburis[AGUI]) == _BASELINE


def test_upgrade_sql_accepts_an_unreachable_database_with_a_range(
    write_installation, tmp_path, cli_runner
):
    # The DBA's case: the databases cannot be reached from here at all, so
    # the operator says where they stand and gets the SQL to hand over.
    missing = tmp_path / "no-such-directory"
    path = write_installation(
        agui={"migration_dburi": sqlite_dburi(missing / "x.sqlite")}
    )

    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = _invoke(
            cli_runner,
            "upgrade",
            path,
            "-d",
            "agui",
            "--sql",
            "--revision",
            f"{_BASELINE}:head",
        )
        written = (pathlib.Path(cwd) / f"{AGUI}.sql").read_text(
            encoding="utf-8"
        )

    assert result.exit_code == 0
    assert f"Running upgrade {_BASELINE}" in written
    assert not missing.exists()


# --------------------------------------------------------------------------
# downgrade
# --------------------------------------------------------------------------
def test_downgrade_moves_both_databases_back(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation()
    alembic_migrations.upgrade(dburis=cli_dburis)

    result = _invoke(cli_runner, "downgrade", path, _BASELINE)

    assert result.exit_code == 0
    assert _revision(cli_dburis[AGUI]) == _BASELINE
    assert _revision(cli_dburis[AUTHZ]) == _BASELINE


def test_downgrade_refuses_a_disabled_database(
    cli_dburis, write_installation, cli_runner
):
    path = write_installation(authz={"migration_policy": "disabled"})
    alembic_migrations.upgrade(dburis=cli_dburis)

    result = _invoke(cli_runner, "downgrade", path, _BASELINE)

    assert result.exit_code == 1
    assert "Cannot downgrade" in result.output
    assert _revision(cli_dburis[AGUI]) != _BASELINE


def test_downgrade_sql_writes_the_delta(
    cli_dburis, write_installation, tmp_path, cli_runner
):
    path = write_installation()
    alembic_migrations.upgrade(dburis=cli_dburis)

    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = _invoke(
            cli_runner, "downgrade", path, _BASELINE, "-d", "authz", "--sql"
        )
        written = (pathlib.Path(cwd) / f"{AUTHZ}.sql").read_text(
            encoding="utf-8"
        )

    assert result.exit_code == 0
    assert f"Running downgrade {alembic_migrations.head_revision()}" in written
    # Nothing ran: the database is still where it was.
    assert _revision(cli_dburis[AUTHZ]) != _BASELINE


def test_downgrade_sql_accepts_an_unreachable_database_with_a_range(
    write_installation, tmp_path, cli_runner
):
    # The escape hatch 'upgrade --sql' offers, on the command most likely
    # to need it: a rollback is planned from somewhere that cannot reach
    # the databases, so the operator names the range and nothing connects.
    missing = tmp_path / "no-such-directory"
    path = write_installation(
        authz={"migration_dburi": sqlite_dburi(missing / "x.sqlite")}
    )
    head = alembic_migrations.head_revision()

    with cli_runner.isolated_filesystem(temp_dir=tmp_path) as cwd:
        result = _invoke(
            cli_runner,
            "downgrade",
            path,
            f"{head}:{_BASELINE}",
            "-d",
            "authz",
            "--sql",
        )
        written = (pathlib.Path(cwd) / f"{AUTHZ}.sql").read_text(
            encoding="utf-8"
        )

    assert result.exit_code == 0
    assert f"Running downgrade {head}" in written
    assert not missing.exists()
