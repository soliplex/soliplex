from __future__ import annotations

import asyncio
from unittest import mock

import pytest
import sqlalchemy as sa

from soliplex import alembic_migrations
from soliplex.cli import cli_util
from soliplex.cli.audit import databases as audit_databases
from soliplex.config import installation as config_installation

# --------------------------------------------------------------------------
# The 'databases' section: state of the 'agui' / 'authz' pair
# --------------------------------------------------------------------------
_HEAD = "head-revision"


_DB_STATES = alembic_migrations.DatabaseState


_POLICY = config_installation.MigrationPolicy


def _report(**kwargs):
    """A 'DatabaseReport' with the boilerplate filled in."""
    kwargs.setdefault("name", cli_util.AUTHZ)
    kwargs.setdefault("dburi", "sqlite+aiosqlite://")
    kwargs.setdefault("head", _HEAD)
    return audit_databases.DatabaseReport(**kwargs)


def _pair_installation(the_installation, tmp_path):
    """Point an installation at its own throwaway file databases."""
    paths = {}
    for db_type, db_pfx in (
        (cli_util.AGUI, "thread_persistence"),
        (cli_util.AUTHZ, "authorization"),
    ):
        paths[db_type] = db_path = tmp_path / f"{db_type}.sqlite"
        setattr(
            the_installation._config,
            f"{db_pfx}_async_dburi",
            f"sqlite+aiosqlite:///{db_path}",
        )
        setattr(
            the_installation._config,
            f"{db_pfx}_sync_dburi",
            f"sqlite:///{db_path}",
        )
    return the_installation, paths


@pytest.mark.parametrize(
    "state, revision, known, error, expected",
    [
        (_DB_STATES.STAMPED, _HEAD, True, None, False),
        (_DB_STATES.STAMPED, "older", True, None, True),
        # A stamp this release does not have is ahead, not behind.
        (_DB_STATES.STAMPED, "newer", False, None, False),
        # Neither an empty nor an unstamped database is 'behind' anything.
        (_DB_STATES.EMPTY, None, True, None, False),
        (_DB_STATES.UNSTAMPED, None, True, None, False),
        (None, None, True, "OperationalError: refused", False),
    ],
)
def test_database_report_behind_head(state, revision, known, error, expected):
    report = _report(state=state, revision=revision, known=known, error=error)

    assert report.behind_head is expected


@pytest.mark.parametrize(
    "state, revision, known, expected",
    [
        (_DB_STATES.STAMPED, "newer", False, True),
        (_DB_STATES.STAMPED, _HEAD, True, False),
        (_DB_STATES.STAMPED, "older", True, False),
        # An unstamped database has no revision to be ahead with.
        (_DB_STATES.UNSTAMPED, None, True, False),
        (_DB_STATES.EMPTY, None, True, False),
    ],
)
def test_database_report_downgrade_required(state, revision, known, expected):
    report = _report(state=state, revision=revision, known=known)

    assert report.downgrade_required is expected


@pytest.mark.parametrize(
    "state, revision, error, expected",
    [
        (_DB_STATES.STAMPED, _HEAD, None, f"OK ({_HEAD})"),
        (
            _DB_STATES.STAMPED,
            "older",
            None,
            f"behind head (older -> {_HEAD})",
        ),
        (
            _DB_STATES.EMPTY,
            None,
            None,
            "not created (the next writable open creates it)",
        ),
        (None, None, "OperationalError: refused", None),
        (_DB_STATES.UNSTAMPED, None, None, None),
    ],
)
def test__database_summary(state, revision, error, expected):
    report = _report(state=state, revision=revision, error=error)

    found = audit_databases._database_summary(report)

    if expected is not None:
        assert found == expected
    elif error is not None:
        assert found == f"ERROR: unreachable: {error}"
    else:
        assert found.startswith("ERROR: ")
        assert alembic_migrations.BOOTSTRAP_SCRIPT in found


def test__database_summary_for_a_stamp_needing_a_downgrade():
    report = _report(state=_DB_STATES.STAMPED, revision="newer", known=False)

    found = audit_databases._database_summary(report)

    assert found.startswith("ERROR: newer: ")
    assert "downgrade has to come from" in found
    # Deliberately suggests no command: the revisions needed to move this
    # database are not in this release, so none can be run here.
    assert "alembic" not in found


def test__database_findings_reports_an_unreachable_database():
    reports = {
        cli_util.AGUI: _report(
            name=cli_util.AGUI, state=_DB_STATES.STAMPED, revision=_HEAD
        ),
        cli_util.AUTHZ: _report(error="OperationalError: refused"),
    }

    found = audit_databases._database_findings(reports)

    assert found == {
        "databases": {
            cli_util.AUTHZ: {"unreachable": "OperationalError: refused"}
        }
    }


def test__database_findings_reports_an_unstamped_database():
    reports = {
        cli_util.AGUI: _report(name=cli_util.AGUI, state=_DB_STATES.UNSTAMPED),
        cli_util.AUTHZ: _report(state=_DB_STATES.STAMPED, revision=_HEAD),
    }

    found = audit_databases._database_findings(reports)

    assert (
        alembic_migrations.BOOTSTRAP_SCRIPT
        in (found["databases"][cli_util.AGUI]["unstamped"])
    )
    assert cli_util.AUTHZ not in found["databases"]


@pytest.mark.parametrize(
    "state, revision",
    [
        # At head, and behind head: neither is a finding, because the next
        # writable open migrates a database that is behind.
        (_DB_STATES.STAMPED, _HEAD),
        (_DB_STATES.STAMPED, "older"),
        (_DB_STATES.EMPTY, None),
    ],
)
def test__database_findings_stays_quiet(state, revision):
    reports = {
        name: _report(name=name, state=state, revision=revision)
        for name in (cli_util.AGUI, cli_util.AUTHZ)
    }

    found = audit_databases._database_findings(reports)

    assert found == {}


def test__database_findings_reports_a_stamp_needing_a_downgrade():
    reports = {
        cli_util.AGUI: _report(
            name=cli_util.AGUI,
            state=_DB_STATES.STAMPED,
            revision="newer",
            known=False,
        ),
        cli_util.AUTHZ: _report(state=_DB_STATES.STAMPED, revision=_HEAD),
    }

    found = audit_databases._database_findings(reports)

    assert found["databases"][cli_util.AGUI]["downgrade_required"].startswith(
        "newer: "
    )
    assert cli_util.AUTHZ not in found["databases"]


@pytest.mark.parametrize(
    "state, revision, policy, expected",
    [
        # With no policy the next writable open deals with both of these.
        (_DB_STATES.STAMPED, "older", None, False),
        (_DB_STATES.EMPTY, None, None, False),
        # With one, nothing here will.
        (_DB_STATES.STAMPED, "older", _POLICY.EXPLICIT, True),
        (_DB_STATES.EMPTY, None, _POLICY.DISABLED, True),
        # Nothing is owed at head, whatever the policy says.
        (_DB_STATES.STAMPED, _HEAD, _POLICY.DISABLED, False),
    ],
)
def test_database_report_migration_owed(state, revision, policy, expected):
    report = _report(state=state, revision=revision, policy=policy)

    assert report.migration_owed is expected


@pytest.mark.parametrize(
    "state, revision, policy, expected",
    [
        (
            _DB_STATES.EMPTY,
            None,
            _POLICY.EXPLICIT,
            "ERROR: not created; 'migration_policy' is 'explicit'",
        ),
        (
            _DB_STATES.STAMPED,
            "older",
            _POLICY.DISABLED,
            f"ERROR: behind head (older -> {_HEAD}); 'migration_policy' is",
        ),
    ],
)
def test__database_summary_under_a_policy(state, revision, policy, expected):
    report = _report(state=state, revision=revision, policy=policy)

    found = audit_databases._database_summary(report)

    assert found.startswith(expected)


def test__database_findings_reports_a_migration_the_policy_holds():
    reports = {
        cli_util.AGUI: _report(
            name=cli_util.AGUI,
            state=_DB_STATES.STAMPED,
            revision="older",
            policy=_POLICY.EXPLICIT,
        ),
        cli_util.AUTHZ: _report(state=_DB_STATES.STAMPED, revision=_HEAD),
    }

    found = audit_databases._database_findings(reports)

    assert (
        "soliplex-cli database upgrade"
        in (found["databases"][cli_util.AGUI]["migration_owed"])
    )
    assert cli_util.AUTHZ not in found["databases"]


@pytest.mark.parametrize(
    "policy, migration_dburi, expected",
    [
        # Most deployments configure neither, and get no extra lines.
        (None, None, []),
        (
            _POLICY.DISABLED,
            None,
            ["migration policy: disabled"],
        ),
        (
            _POLICY.EXPLICIT,
            "postgresql://owner:swordfish@db/authz",
            [
                "migration policy: explicit",
                "migration dburi: postgresql://owner:***@db/authz",
            ],
        ),
    ],
)
def test__database_config_lines(policy, migration_dburi, expected):
    report = _report(policy=policy, migration_dburi=migration_dburi)

    found = audit_databases._database_config_lines(report)

    assert found == expected


def test__database_reports_returns_the_cached_probe(ctx, the_installation):
    already = {"agui": object()}
    ctx.obj["database_reports"] = already

    found = audit_databases._database_reports(ctx, the_installation)

    assert found is already


@mock.patch.object(alembic_migrations, "head_revision")
@mock.patch.object(
    audit_databases, "_probe_database", new_callable=mock.AsyncMock
)
def test__database_reports_probes_and_caches(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = [
        (_DB_STATES.STAMPED, _HEAD),
        (_DB_STATES.UNSTAMPED, None),
    ]

    found = audit_databases._database_reports(ctx, the_installation)

    assert found[cli_util.AGUI].state is _DB_STATES.STAMPED
    assert found[cli_util.AGUI].revision == _HEAD
    assert found[cli_util.AUTHZ].state is _DB_STATES.UNSTAMPED
    assert all(report.head == _HEAD for report in found.values())
    assert ctx.obj["database_reports"] is found


@mock.patch.object(alembic_migrations, "head_revision")
@mock.patch.object(
    audit_databases, "_probe_database", new_callable=mock.AsyncMock
)
def test__database_reports_maps_an_uncreated_database_to_empty(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = cli_util.DatabaseNotCreated("authz")

    found = audit_databases._database_reports(ctx, the_installation)

    assert [report.state for report in found.values()] == [
        _DB_STATES.EMPTY,
        _DB_STATES.EMPTY,
    ]
    assert all(report.error is None for report in found.values())


@mock.patch.object(alembic_migrations, "head_revision")
@mock.patch.object(
    audit_databases, "_probe_database", new_callable=mock.AsyncMock
)
def test__database_reports_records_an_unreachable_database(
    probe, head_revision, ctx, the_installation
):
    head_revision.return_value = _HEAD
    probe.side_effect = RuntimeError("refused")

    found = audit_databases._database_reports(ctx, the_installation)

    assert all(
        report.error == "RuntimeError: refused" for report in found.values()
    )
    assert all(report.state is None for report in found.values())


def test__probe_database_reads_a_migrated_database(the_installation, tmp_path):
    # Driven against real files: the probe has to agree with what alembic
    # actually wrote, which a mocked connection could not show.
    the_installation, paths = _pair_installation(the_installation, tmp_path)
    alembic_migrations.upgrade(
        "head",
        dburis={name: f"sqlite:///{path}" for name, path in paths.items()},
    )

    state, revision = asyncio.run(
        audit_databases._probe_database(the_installation, cli_util.AUTHZ)
    )

    assert state is _DB_STATES.STAMPED
    assert revision == alembic_migrations.head_revision()


def test__probe_database_reads_an_unstamped_database(
    the_installation, tmp_path
):
    the_installation, paths = _pair_installation(the_installation, tmp_path)
    alembic_migrations.upgrade(
        "head",
        dburis={name: f"sqlite:///{path}" for name, path in paths.items()},
    )
    engine = sa.create_engine(f"sqlite:///{paths[cli_util.AUTHZ]}")
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(f"DROP TABLE {alembic_migrations.VERSION_TABLE}")
            )
    finally:
        engine.dispose()

    state, revision = asyncio.run(
        audit_databases._probe_database(the_installation, cli_util.AUTHZ)
    )

    assert state is _DB_STATES.UNSTAMPED
    assert revision is None


# _audit_databases_section: ui only
# audit_databases: command
