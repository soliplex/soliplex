"""Run / report on database migrations

In its default mode, the Soliplex server / CLI commands migrate its own
databases on any writable open.  This command exists for deployments which
divide the roles between different users: one user with the "migration" role
owns the database and every object in it, while the "normal" user is
granted only DML.

In such a deployment, the operator will run migrations manually, typically
during a maintenance window where a new version of Soliplex is begin installed.
This command group uses the configured 'migration_dburi' and 'migration_policy'
to do that work:

- 'status' reports, per database, the policy in force, the revisions
  already applied, and those still pending. Nothing is created, migrated
  or stamped: it is the pre-flight for the other two.

- 'upgrade' and 'downgrade' move the databases, through the migration
  DBURI when one is configured and the runtime 'sync_dburi' when it is not.

This command group reads the revision tree out of the installed package
(see 'docs/server/migrations.md').
"""

from __future__ import annotations

import contextlib
import dataclasses
import enum

import typer

from soliplex import alembic_migrations
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.config import installation as config_installation

the_console = cli_util.the_console

DATABASE_HELP = "Report and apply database migrations"

app = typer.Typer(
    name="database",
    help=DATABASE_HELP,
    no_args_is_help=True,
)


class Database(enum.StrEnum):
    """The databases a command can be limited to."""

    AGUI = alembic_migrations.AGUI
    AUTHZ = alembic_migrations.AUTHZ


_DATABASE_OPTION = typer.Option(
    None,
    "-d",
    "--database",
    help="Limit the command to one database (default: both)",
)

_REVISION_OPTION = typer.Option(
    "head",
    "-r",
    "--revision",
    help=(
        "Revision to migrate to. With '--sql', alembic's '<from>:<to>' "
        "range form is also accepted, and skips reading the stamp."
    ),
)

# 'downgrade' takes its revision positionally, since there is no sensible
# default to go backwards to. The range form it accepts is the same one,
# so the wording is deliberately parallel to '_REVISION_OPTION'.
_REVISION_ARGUMENT = typer.Argument(
    help=(
        "Revision to migrate back to. With '--sql', alembic's "
        "'<from>:<to>' range form is also accepted, and skips reading "
        "the stamp."
    ),
)

_SQL_OPTION = typer.Option(
    False,
    "--sql",
    help=(
        "Write the operation's DDL to '<database>.sql' in the current "
        "directory, instead of running it."
    ),
)


@dataclasses.dataclass(frozen=True)
class MigrationStatus:
    """One database, as the migration tool finds it before moving anything.

    ``dburi`` is the *migration* DBURI -- the configured one, or the
    runtime sync one standing in for it -- held unredacted because a
    command connects through it; printing goes through
    :func:`cli_util.redacted_dburi`.

    ``state`` and ``revision`` are unset either because the database could
    not be read (``error``) or because it was deliberately not probed (an
    explicit ``--sql`` range says the operator is offline).
    """

    name: str
    dburi: str
    policy: config_installation.MigrationPolicy | None
    state: alembic_migrations.DatabaseState | None = None
    revision: str | None = None
    known: bool = True
    error: str | None = None

    @property
    def disabled(self) -> bool:
        return self.policy is config_installation.MigrationPolicy.DISABLED

    @property
    def unstamped(self) -> bool:
        return self.state is alembic_migrations.DatabaseState.UNSTAMPED

    @property
    def downgrade_required(self) -> bool:
        """True for a stamp this release's revision tree does not have."""
        return self.revision is not None and not self.known

    @property
    def chain(self):
        """``(applied, pending)`` for this database.

        Empty on either side when there is no chain to speak of: a
        database which did not open, one whose stamp belongs to a newer
        release, and an unstamped one, whose tables say revisions have run
        while its missing version row says which is unknowable.
        """
        if self.error is not None or self.unstamped:
            return (), ()
        if self.downgrade_required:
            return (), ()
        return alembic_migrations.split_chain(self.revision)


def _probe(name: str, dburi: str):
    """Read one database's state, creating and migrating nothing."""
    engine = alembic_migrations.engine_for(name, dburi)
    try:
        with engine.connect() as connection:
            return (
                alembic_migrations.database_state(
                    connection, alembic_migrations.METADATA[name]
                ),
                alembic_migrations.current_revision(connection),
            )
    finally:
        engine.dispose()


def _status(i_config, name: str, *, probe: bool = True) -> MigrationStatus:
    """One database's status, reporting rather than raising.

    A database which will not open is a line in the report, not the end of
    it: the other one may still be fine, and which of them failed is the
    thing the operator needs.

    The commands that move a database turn these back into refusals;
    see :func:`_check_movable`.
    """
    dburi = alembic_migrations.migration_dburi(i_config, name)
    policy = alembic_migrations.migration_policy(i_config, name)

    if not probe:
        return MigrationStatus(name=name, dburi=dburi, policy=policy)

    try:
        state, revision = _probe(name, dburi)
    except Exception as exc:
        return MigrationStatus(
            name=name,
            dburi=dburi,
            policy=policy,
            error=f"{type(exc).__name__}: {exc}",
        )

    return MigrationStatus(
        name=name,
        dburi=dburi,
        policy=policy,
        state=state,
        revision=revision,
        known=(
            revision is None or alembic_migrations.knows_revision(revision)
        ),
    )


def _targets(database: Database | None) -> tuple[str, ...]:
    """The databases a command acts on."""
    if database is None:
        return alembic_migrations.DATABASE_NAMES
    return (str(database),)


def _statuses(i_config, database, *, probe: bool = True):
    return tuple(
        _status(i_config, name, probe=probe) for name in _targets(database)
    )


def _load_config(installation_path):
    return alembic_migrations.load_installation_config(
        cli_util.installation_config_path(installation_path)
    )


def _blocker(status: MigrationStatus):
    """Why ``status``'s database cannot be migrated, if it cannot.

    Returns the exception a refusal raises, so a command which refuses and
    a report which merely notes the condition say the same thing in the
    same words.
    """
    if status.error is not None:
        return alembic_migrations.DatabaseUnreachable(
            [status.name], status.error
        )
    if status.unstamped:
        return alembic_migrations.UnstampedDatabase([status.name])
    if status.downgrade_required:
        return alembic_migrations.DowngradeRequired(
            [status.name],
            status.revision,
            alembic_migrations.head_revision(),
        )
    return None


def _check_movable(statuses) -> None:
    """Refuse the whole run unless every target can be migrated.

    All or nothing: both databases move in one alembic run, committing
    together, and a half-applied upgrade is a worse place for an operator
    to stand than a refused one.
    """
    disabled = [status.name for status in statuses if status.disabled]
    if disabled:
        raise alembic_migrations.MigrationsDisabled(disabled)

    for status in statuses:
        blocker = _blocker(status)
        if blocker is not None:
            raise blocker


@contextlib.contextmanager
def _reported(title: str):
    """Report a migration refusal or failure without a traceback.

    A wrong revision name, a database that will not open, a role the
    database refuses the DDL to: all of them are things the operator can
    read and act on, and none of them is a bug in soliplex.
    """
    try:
        yield
    except alembic_migrations.OPERATOR_ERRORS as exc:
        the_console.rule(title)
        the_console.print(str(exc))
        raise typer.Exit(1) from exc


def _print_revisions(label: str, revisions) -> None:
    the_console.print(f"  {label}: {len(revisions)}")
    for revision in revisions:
        the_console.print(f"    {revision.revision}  {revision.doc}")


def _print_status(status: MigrationStatus) -> None:
    shown = cli_util.redacted_dburi(status.dburi)
    the_console.print(f"- {status.name}: {shown}")
    the_console.print(f"  policy: {status.policy or '(unset)'}")

    blocker = _blocker(status)
    if blocker is not None:
        the_console.print(f"  ERROR: {blocker}")
        return

    applied, pending = status.chain
    _print_revisions("applied", applied)
    _print_revisions("pending", pending)


def _sql_revision(status: MigrationStatus, revision: str) -> str:
    """The ``<from>:<to>`` range offline mode needs for one database.

    Offline there is no connection for alembic to read a stamp from, so
    it would otherwise replay the whole chain from base. The stamp read
    during the pre-flight supplies the range's *from* end -- the lower
    revision when upgrading, the higher one when downgrading. A range the
    operator passed themselves is left alone, which is the only form that
    works when the database cannot be reached from here at all.
    """
    if ":" in revision:
        return revision
    start = "base" if status.revision is None else status.revision
    return f"{start}:{revision}"


def _emit_sql(command, statuses, revision: str) -> None:
    """Write one ``<database>.sql`` per target, running nothing.

    One alembic invocation per database, rather than the single one the
    online path uses: each database's range starts at its own stamp, and
    one revision argument cannot say two things.
    """
    for status in statuses:
        command(
            _sql_revision(status, revision),
            dburis={status.name: status.dburi},
            sql=True,
        )
        the_console.print(f"- {status.name}: wrote {status.name}.sql")


def _migrate(command, statuses, revision: str) -> None:
    command(
        revision,
        dburis={status.name: status.dburi for status in statuses},
    )
    for status in statuses:
        the_console.print(f"- {status.name}: migrated to {revision}")


def _move(command, installation_path, database, revision, sql, title):
    """The shared body of ``upgrade`` and ``downgrade``."""
    with _reported(title):
        i_config = _load_config(installation_path)
        # An explicit '<from>:<to>' range is the operator saying where the
        # databases stand, which is the one case where they need not be
        # reachable from here.
        probe = not (sql and ":" in revision)
        statuses = _statuses(i_config, database, probe=probe)
        _check_movable(statuses)

        if sql:
            _emit_sql(command, statuses, revision)
        else:
            _migrate(command, statuses, revision)


@app.command("status")
def database_status(
    installation_path: types.installation_path_type,
    database: Database | None = _DATABASE_OPTION,
):
    """Report the revisions applied to each database, and those pending.

    Nothing is created, migrated or stamped. Exits 1 when a database
    cannot be migrated as it stands -- unreachable, unstamped, or stamped
    by a newer release -- so this doubles as the pre-flight check for
    'upgrade'.
    """
    i_config = _load_config(installation_path)
    statuses = _statuses(i_config, database)

    the_console.rule("Database migrations")
    the_console.print(f"head: {alembic_migrations.head_revision()}")
    for status in statuses:
        _print_status(status)

    if any(_blocker(status) is not None for status in statuses):
        raise typer.Exit(1)


@app.command("upgrade")
def database_upgrade(
    installation_path: types.installation_path_type,
    database: Database | None = _DATABASE_OPTION,
    revision: str = _REVISION_OPTION,
    sql: bool = _SQL_OPTION,
):
    """Migrate the databases forward, to 'head' by default."""
    _move(
        alembic_migrations.upgrade,
        installation_path,
        database,
        revision,
        sql,
        "Cannot upgrade",
    )


@app.command("downgrade")
def database_downgrade(
    installation_path: types.installation_path_type,
    revision: str = _REVISION_ARGUMENT,
    database: Database | None = _DATABASE_OPTION,
    sql: bool = _SQL_OPTION,
):
    """Migrate the databases back to 'revision', which is required.

    For the deployment whose code is about to be rolled back: downgrade
    first, from the version which still has these revisions, with every
    writer stopped.
    """
    _move(
        alembic_migrations.downgrade,
        installation_path,
        database,
        revision,
        sql,
        "Cannot downgrade",
    )
