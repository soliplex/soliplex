from __future__ import annotations

import asyncio
import dataclasses

import typer

from soliplex import alembic_migrations
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.config import installation as config_installation

_UNSTAMPED = (
    f"tables are present but '{alembic_migrations.VERSION_TABLE}' is empty, "
    "so this database was created by soliplex 0.81 or earlier. "
    f"{alembic_migrations.BOOTSTRAP_REMEDY}"
)


_DOWNGRADE_REQUIRED = (
    "stamped at a revision this release does not have, so its code was "
    "rolled back without downgrading its databases first. The downgrade "
    "has to come from the soliplex version which has that revision -- "
    "nothing here can open this database, or move it"
)


# What to do about a migration the policy will not let this deployment
# run automatically. 'disabled' names no command: the tool refuses it too.
_MIGRATION_OWED = {
    config_installation.MigrationPolicy.EXPLICIT: (
        "'migration_policy' is 'explicit', so apply it with "
        "'soliplex-cli database upgrade'"
    ),
    config_installation.MigrationPolicy.DISABLED: (
        "'migration_policy' is 'disabled', so nothing migrates it from "
        "this configuration"
    ),
}


_SEE_DATABASES = (
    "SKIPPED: authorization database unreachable "
    "(reported under 'Configured databases')"
)


@dataclasses.dataclass(frozen=True)
class DatabaseReport:
    """What one database looks like to a reader, before anything writes.

    ``error`` is set when the database could not be reached at all, in
    which case ``state`` and ``revision`` say nothing.
    """

    name: str
    dburi: str
    head: str
    state: alembic_migrations.DatabaseState | None = None
    revision: str | None = None
    known: bool = True
    error: str | None = None
    policy: config_installation.MigrationPolicy | None = None
    migration_dburi: str | None = None

    @property
    def stamped(self) -> bool:
        return self.state is alembic_migrations.DatabaseState.STAMPED

    @property
    def downgrade_required(self) -> bool:
        """True for a stamp this release's revision tree does not have.

        Only the release which has that revision can downgrade it, so this
        is a finding wherever it is seen.
        """
        return self.stamped and not self.known

    @property
    def behind_head(self) -> bool:
        """True for a stamped database not yet at the packaged head."""
        return self.stamped and self.known and self.revision != self.head

    @property
    def migration_owed(self) -> bool:
        """True when a migration is needed and no open here will run it.

        With no policy the next writable open migrates; with one it
        refuses, so the database stays as it is until an operator acts.
        """
        if self.policy is None:
            return False
        return self.behind_head or (
            self.state is alembic_migrations.DatabaseState.EMPTY
        )


def _inspect_database(connection, db_type: str):
    return (
        alembic_migrations.database_state(
            connection, alembic_migrations.METADATA[db_type]
        ),
        alembic_migrations.current_revision(connection),
    )


async def _probe_database(the_installation, db_type: str):
    """Read one database's state without creating or migrating anything."""
    engine = await cli_util.open_db(
        the_installation,
        db_type,
        command="audit databases",
        allow_ram=True,
        must_exist=True,
    )
    try:
        async with engine.connect() as connection:
            return await connection.run_sync(_inspect_database, db_type)
    finally:
        await engine.dispose()


def _database_reports(ctx, the_installation) -> dict:
    """Probe both databases once per invocation, caching on ``ctx.obj``.

    Every section that needs a database's state shares this, so an
    unreachable DBURI costs one connection attempt per run rather than one
    per section -- which matters when reaching it means waiting for a
    connect timeout.
    """
    cached = ctx.obj.get("database_reports")
    if cached is not None:
        return cached

    head = alembic_migrations.head_revision()
    reports = {}
    for db_type in alembic_migrations.DATABASE_NAMES:
        configured = {
            "name": db_type,
            "dburi": cli_util.async_dburi(the_installation, db_type),
            "head": head,
            "policy": alembic_migrations.migration_policy(
                the_installation, db_type
            ),
            "migration_dburi": (
                alembic_migrations.configured_migration_dburi(
                    the_installation, db_type
                )
            ),
        }
        try:
            state, revision = asyncio.run(
                _probe_database(the_installation, db_type)
            )
        except cli_util.DatabaseNotCreated:
            reports[db_type] = DatabaseReport(
                **configured,
                state=alembic_migrations.DatabaseState.EMPTY,
            )
        except Exception as exc:
            reports[db_type] = DatabaseReport(
                **configured,
                error=f"{type(exc).__name__}: {exc}",
            )
        else:
            reports[db_type] = DatabaseReport(
                **configured,
                state=state,
                revision=revision,
                known=(
                    revision is None
                    or alembic_migrations.knows_revision(revision)
                ),
            )

    ctx.obj["database_reports"] = reports
    return reports


def _database_summary(report: DatabaseReport) -> str:
    """The one-line human summary for one database."""
    if report.error is not None:
        return f"ERROR: unreachable: {report.error}"
    if report.state is alembic_migrations.DatabaseState.UNSTAMPED:
        return f"ERROR: {_UNSTAMPED}"
    if report.state is alembic_migrations.DatabaseState.EMPTY:
        if report.policy is not None:
            return f"ERROR: not created; {_MIGRATION_OWED[report.policy]}"
        return "not created (the next writable open creates it)"
    if report.downgrade_required:
        return f"ERROR: {report.revision}: {_DOWNGRADE_REQUIRED}"
    if report.behind_head:
        behind = f"behind head ({report.revision} -> {report.head})"
        if report.policy is not None:
            return f"ERROR: {behind}; {_MIGRATION_OWED[report.policy]}"
        return behind
    return f"OK ({report.revision})"


def _database_config_lines(report: DatabaseReport) -> list[str]:
    """The migration settings configured for one database, if any.

    Nothing is printed for a deployment which configures neither.
    """
    lines = []
    if report.policy is not None:
        lines.append(f"migration policy: {report.policy}")
    if report.migration_dburi is not None:
        shown = cli_util.redacted_dburi(report.migration_dburi)
        lines.append(f"migration dburi: {shown}")
    return lines


def _database_findings(reports) -> dict:
    """The findings among ``reports``.

    Unreachable, stamp-less, stamped ahead of this release, or owed a
    migration the installation's 'migration_policy' will not let this
    deployment run. A database behind head with no policy is not a
    finding: the next writable open migrates it.
    """
    findings = {}
    for report in reports.values():
        if report.error is not None:
            findings[report.name] = {"unreachable": report.error}
        elif report.state is alembic_migrations.DatabaseState.UNSTAMPED:
            findings[report.name] = {"unstamped": _UNSTAMPED}
        elif report.downgrade_required:
            findings[report.name] = {
                "downgrade_required": (
                    f"{report.revision}: {_DOWNGRADE_REQUIRED}"
                )
            }
        elif report.migration_owed:
            findings[report.name] = {
                "migration_owed": _MIGRATION_OWED[report.policy]
            }
    if findings:
        return {"databases": findings}
    return {}


def _audit_databases_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the databases section (rule header + one line per database)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured databases")
    tc_line()

    reports = _database_reports(ctx, the_installation)
    for report in reports.values():
        tc_print(f"- {report.name}: {cli_util.redacted_dburi(report.dburi)}")
        for line in _database_config_lines(report):
            tc_print(f"  {line}")
        tc_print(f"  {_database_summary(report)}")
    tc_line()

    # Tells the authz sections that they need not repeat an unreachable
    # database: this section has already reported it.
    ctx.obj["databases_audited"] = True

    return _database_findings(reports)


def audit_databases(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Report the migration state of the 'agui' / 'authz' databases.

    Neither database is created nor migrated: a database with no schema is
    reported as such, while one holding tables with no 'alembic_version'
    row is an audit error, because every writable open refuses it.
    """
    quiet = ctx.obj["quiet"]
    errors = _audit_databases_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
