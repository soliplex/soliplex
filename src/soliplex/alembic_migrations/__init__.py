"""Alembic migrations for the ``agui`` and ``authz`` databases.

This package *is* the alembic script location: ``env.py``, ``versions/`` and
the revision template live beside this module, and ship in the wheel, so a
deployment can migrate from its own image. It is only about these two
SQLAlchemy databases -- the RAG ``*.lancedb`` stores are haiku.rag's, and
have nothing to do with anything here.

The schema is defined by the revisions, not by ``metadata.create_all()``:
migrating an empty database from base reproduces exactly what the models
would have created (``scripts/lint_alembic_chain.py`` keeps that true), and
leaves the database stamped. So every writable open calls
:func:`ensure_current_engine` rather than creating tables, and a database
soliplex creates is stamped by construction.

One database at a time, on a connection the caller owns. Three situations,
and what :func:`ensure_current_connection` does with each:

- the database is at head -- return, having written nothing (one ``SELECT``);
- it is empty, or behind head -- migrate it, but only when this process is
  the sole writer; otherwise raise :class:`MigrationRequired`, because two
  processes migrating one database race;
- it holds tables but no ``alembic_version`` row -- raise
  :class:`UnstampedDatabase`. Such a database was built by soliplex 0.81 or
  earlier, and needs the one-off bootstrap script named in that error.
"""

from __future__ import annotations

import enum
import logging
import logging.config
import pathlib

import sqlalchemy as sa
from alembic import command as alembic_command
from alembic import config as alembic_config_module
from alembic import script as alembic_script
from alembic import util as alembic_util

from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation

USAGE = """\
Usage:

alembic -x soliplex.installation_path=<path> <command> ...
"""

AGUI = "agui"
AUTHZ = "authz"
# The 'engine_name' each revision dispatches on: every revision carries an
# 'upgrade_agui' / 'upgrade_authz' pair. This is the source of truth --
# alembic never reads the 'databases' option itself, and 'env.py' iterates
# the DBURIs it resolves.
DATABASE_NAMES = (AGUI, AUTHZ)

# This package doubles as the script location.
TREE = pathlib.Path(__file__).resolve().parent

VERSION_TABLE = "alembic_version"

METADATA = {
    AGUI: agui_schema.metadata,
    AUTHZ: authz_schema.metadata,
}

# The one-off repair for databases built before stamping existed.
BOOTSTRAP_ISSUE = "https://github.com/soliplex/soliplex/issues/1367"

logger = logging.getLogger("alembic.env")


class DatabaseState(enum.Enum):
    """What a database looks like before anything is done to it."""

    #: none of this database's tables are present
    EMPTY = "empty"
    #: tables present, and an 'alembic_version' row to say which revision
    STAMPED = "stamped"
    #: tables present, but no version row -- built by soliplex <= 0.81
    UNSTAMPED = "unstamped"


class MigrationError(Exception):
    """A migration cannot proceed (reported without a traceback)."""


class UnstampedDatabase(MigrationError):
    def __init__(self, names):
        self.names = tuple(names)
        which = ", ".join(self.names)
        super().__init__(
            f"{which}: tables are present but {VERSION_TABLE} is empty, so "
            "this database was created by soliplex 0.81 or earlier. Apply "
            f"the one-off bootstrap script once, per {BOOTSTRAP_ISSUE}, and "
            "then start soliplex again."
        )


class NoDatabasesNamed(MigrationError):
    def __init__(self):
        super().__init__(
            "name the databases to migrate: either 'dburis', or a "
            "'connection' and the 'database' it belongs to"
        )


class MigrationRequired(MigrationError):
    def __init__(self, names):
        self.names = tuple(names)
        which = ", ".join(self.names)
        super().__init__(
            f"{which}: a migration is needed, and this process is not the "
            "sole writer (several workers or replicas would race). Migrate "
            "first, with every writer stopped: "
            "alembic -x soliplex.installation_path=<path> upgrade head"
        )


class DowngradeRequired(MigrationError):
    """The database is stamped at a revision this release does not have.

    No command is suggested, because none can be run here: the revisions
    between this release's head and the stamp exist only in the newer
    release's tree, so the downgrade has to come from that version.
    """

    def __init__(self, names, revision, head):
        self.names = tuple(names)
        self.revision = revision
        self.head = head
        which = ", ".join(self.names)
        super().__init__(
            f"{which}: stamped at {revision}, which this release does not "
            "have, so its code was rolled back without downgrading its "
            "databases first. Downgrade them to "
            f"{head} from the soliplex version which has {revision}, with "
            "every writer stopped, then start this version again."
        )


def head_revision() -> str:
    """The newest revision in this package's ``versions/``."""
    return alembic_script.ScriptDirectory(str(TREE)).get_current_head()


def knows_revision(revision: str) -> bool:
    """True when this package's ``versions/`` contains ``revision``.

    A stamp this tree does not know belongs to a *newer* release: the
    deployment's code was rolled back without downgrading its databases
    first, and there is no path from that revision to anything here.
    """
    try:
        alembic_script.ScriptDirectory(str(TREE)).get_revision(revision)
    except alembic_util.CommandError:
        return False
    return True


def version_table() -> sa.Table:
    """Alembic's version table, as alembic itself defines it."""
    return sa.Table(
        VERSION_TABLE,
        sa.MetaData(),
        sa.Column("version_num", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("version_num", name=f"{VERSION_TABLE}_pkc"),
    )


def current_revision(connection) -> str | None:
    """The revision ``connection``'s database is stamped at, if any.

    A version *table* with no row is not a stamp: alembic creates the table
    before it runs any migration, so an upgrade that failed part-way leaves
    an empty one behind.
    """
    if not sa.inspect(connection).has_table(VERSION_TABLE):
        return None
    found = connection.execute(
        sa.select(version_table().c.version_num)
    ).scalars()
    return next(iter(found), None)


def database_state(connection, metadata) -> DatabaseState:
    """Classify ``connection``'s database against ``metadata``.

    Emptiness is judged by *this* metadata's tables rather than by the
    database holding no tables at all, so a database shared with something
    else is still recognized as needing its schema built.
    """
    if current_revision(connection) is not None:
        return DatabaseState.STAMPED
    present = set(sa.inspect(connection).get_table_names())
    if present & set(metadata.tables):
        return DatabaseState.UNSTAMPED
    return DatabaseState.EMPTY


def engine_for(name: str, dburi: str) -> sa.Engine:
    """A sync engine for one database, tuned as the schema module tunes it."""
    if name == AGUI:
        return agui_schema.get_engine(engine_url=dburi)
    return authz_schema.get_engine(engine_url=dburi)


def installation_dburis(installation) -> dict[str, str]:
    """The two *sync* DBURIs, from an installation or its config.

    Either will do: ``Installation`` delegates both properties to the
    ``InstallationConfig`` it wraps.
    """
    return {
        AGUI: installation.thread_persistence_dburi_sync,
        AUTHZ: installation.authorization_dburi_sync,
    }


def upgrade(
    revision: str = "head",
    *,
    dburis=None,
    connection=None,
    database=None,
    _offline: bool = False,
):
    """Migrate to ``revision`` (default: head).

    One source of databases is required, and travels to ``env.py`` in the
    config's ``attributes``: either ``dburis``, a ``{name: dburi}`` mapping
    covering both databases, or a live ``connection`` and the ``database``
    it belongs to.

    ``_offline`` is a test seam: it emits the SQL instead of running it
    (one ``<name>.sql`` per database, in the current directory), which is
    the only way a test reaches :func:`run_migrations_offline`. The
    ``--sql`` an operator or developer runs goes through alembic's own
    CLI, and never through here.
    """
    if dburis is None and connection is None:
        raise NoDatabasesNamed()

    cfg = alembic_config_module.Config()
    cfg.set_main_option("script_location", str(TREE))
    if dburis is not None:
        cfg.attributes["dburis"] = dict(dburis)
    else:
        cfg.attributes["connection"] = connection
        cfg.attributes["database"] = database

    alembic_command.upgrade(cfg, revision, sql=_offline)


def ensure_current_connection(
    connection, database: str, *, sole_writer: bool
) -> None:
    """Bring one database to head, on a connection the caller owns.

    Migrating on the caller's own connection is what makes this work for
    any database, an in-memory one included: such a database lives and
    dies with the engine that opened it, so a migration run through a
    connection opened here would leave the caller's engine with nothing.

    Raises :class:`UnstampedDatabase` for a database built before stamping
    existed, :class:`DowngradeRequired` for one stamped by a newer release
    than this one, and :class:`MigrationRequired` when a migration is
    needed but this process cannot safely be the one to run it.
    """
    if database_state(connection, METADATA[database]) is (
        DatabaseState.UNSTAMPED
    ):
        raise UnstampedDatabase([database])

    head = head_revision()
    current = current_revision(connection)
    if current == head:
        return
    # Before the sole-writer gate: no number of stopped writers makes a
    # database migratable when the revisions to move it are not here.
    if current is not None and not knows_revision(current):
        raise DowngradeRequired([database], current, head)
    if not sole_writer:
        raise MigrationRequired([database])

    logger.info("Migrating %s to %s", database, head)
    upgrade(head, connection=connection, database=database)


async def ensure_current_engine(
    engine, database: str, *, sole_writer: bool
) -> None:
    """Bring the database behind an async ``engine`` to head."""
    async with engine.begin() as connection:
        await connection.run_sync(
            ensure_current_connection, database, sole_writer=sole_writer
        )


# --------------------------------------------------------------------------
# Driven by 'env.py', which alembic executes for every command.
# --------------------------------------------------------------------------
def configure_logging(cfg) -> None:
    """Apply a logging configuration from an ini file, if there is one.

    The file has to be looked for, not just named: the alembic CLI fills
    in a default ``config_file_name`` whether or not that file exists, and
    this project keeps its alembic settings in ``pyproject.toml``, which
    ``fileConfig`` cannot read. The config :func:`upgrade` builds names no
    file at all, and its caller has configured logging already.
    """
    name = cfg.config_file_name
    if name is None or not pathlib.Path(name).is_file():
        return
    logging.config.fileConfig(name, disable_existing_loggers=False)


def resolve_dburis(context) -> dict[str, str]:
    """The two DBURIs for this alembic run.

    Two sources: an explicit mapping in ``config.attributes`` (what
    :func:`upgrade` passes, and what the chain lint uses), or
    ``-x soliplex.installation_path=`` on the command line.

    The config is loaded here rather than through
    ``cli.cli_util.get_installation``, which would build a whole
    ``Installation`` -- from a module that imports this package -- by way
    of ``reload_configurations()``. That also loads the rooms,
    completions, OIDC and filesystem-skill configs, none of which a
    migration needs and any of which can fail, so an unrelated broken
    room config would block an upgrade.

    ``resolve_environment()`` is the one part of it the DBURIs do depend
    on: an ``env:<name>`` marker resolves against the config's
    ``environment`` mapping, which holds declared names until that call
    fills in their values.
    """
    dburis = context.config.attributes.get("dburis")
    if dburis is not None:
        return dict(dburis)

    x_args = context.get_x_argument(as_dictionary=True)
    given = x_args.get("soliplex.installation_path")
    if given is None:
        print(USAGE)
        raise SystemExit(2)

    i_config = config_installation.load_installation(pathlib.Path(given))
    i_config.resolve_environment()
    return installation_dburis(i_config)


def run_migrations_offline(context, dburis: dict[str, str]) -> None:
    """Emit SQL per database instead of running it (``--sql``).

    Writes ``<name>.sql`` into the current directory, one per database.
    There is no connection here, so nothing is inspected.
    """
    for name, dburi in dburis.items():
        logger.info("Migrating database %s", name)
        out = pathlib.Path(f"{name}.sql")
        logger.info("Writing output to %s", out)
        with out.open("w", encoding="utf-8") as buffer:
            context.configure(
                url=dburi,
                output_buffer=buffer,
                target_metadata=METADATA[name],
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
            )
            with context.begin_transaction():
                context.run_migrations(engine_name=name)


def run_migrations_online(context, dburis: dict[str, str]) -> None:
    """Run migrations against both databases, committing both at the end.

    Two-phase commit is not used: neither SQLite nor PostgreSQL needs it
    here, and the alembic template's ``USE_TWOPHASE`` switch was a constant.
    """
    engines = {name: engine_for(name, dburi) for name, dburi in dburis.items()}
    connections = {}
    transactions = {}
    try:
        for name, engine in engines.items():
            connections[name] = connection = engine.connect()
            transactions[name] = connection.begin()

        try:
            for name, connection in connections.items():
                logger.info("Migrating database %s", name)
                context.configure(
                    connection=connection,
                    upgrade_token=f"{name}_upgrades",
                    downgrade_token=f"{name}_downgrades",
                    target_metadata=METADATA[name],
                )
                context.run_migrations(engine_name=name)
            for transaction in transactions.values():
                transaction.commit()
        except BaseException:
            for transaction in transactions.values():
                transaction.rollback()
            raise
    finally:
        for connection in connections.values():
            connection.close()
        for engine in engines.values():
            engine.dispose()


def run_migrations_on_connection(context, connection, database: str) -> None:
    """Migrate one database, on a connection its caller opened.

    The caller owns the transaction, and therefore the commit.
    """
    logger.info("Migrating database %s", database)
    context.configure(
        connection=connection,
        upgrade_token=f"{database}_upgrades",
        downgrade_token=f"{database}_downgrades",
        target_metadata=METADATA[database],
    )
    with context.begin_transaction():
        context.run_migrations(engine_name=database)


def run(context) -> None:
    """The whole of ``env.py``'s job."""
    configure_logging(context.config)

    attributes = context.config.attributes
    connection = attributes.get("connection")
    if connection is not None:
        run_migrations_on_connection(
            context, connection, attributes["database"]
        )
        return

    dburis = resolve_dburis(context)
    if context.is_offline_mode():
        run_migrations_offline(context, dburis)
    else:
        run_migrations_online(context, dburis)
