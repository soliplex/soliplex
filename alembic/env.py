"""Usage:

alembic -x soliplex.installation_path=<path> <command> ...
"""

import logging
import logging.config
import pathlib
import sys

from alembic import context as alembic_context
from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema
from soliplex.cli import cli_util

USE_TWOPHASE = False

x_args = alembic_context.get_x_argument(as_dictionary=True)
installation_path = x_args.get("soliplex.installation_path")

if installation_path is None:
    print(__doc__)
    sys.exit(2)

installation_path = pathlib.Path(installation_path)
the_installation = cli_util.get_installation(installation_path)

# Resolve installation secrets into DBURIs
agui_dburi = the_installation.thread_persistence_dburi_sync
authz_dburi = the_installation.authorization_dburi_sync

the_dburis = {
    "agui": agui_dburi,
    "authz": authz_dburi,
}

the_engines = {
    "agui": agui_schema.get_engine(engine_url=agui_dburi, init_schema=True),
    "authz": authz_schema.get_engine(engine_url=authz_dburi, init_schema=True),
}

target_metadata = {
    "agui": agui_schema.metadata,
    "authz": authz_schema.metadata,
}

db_names = list(the_dburis)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
alembic_config = alembic_context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if alembic_config.config_file_name is not None:
    logging.config.fileConfig(alembic_config.config_file_name)

logger = logging.getLogger("alembic.env")

# gather section names referring to different
# databases.  These are named "engine1", "engine2"
# in the sample .ini file.

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # for the --sql use case, run migrations for each URL into
    # individual files.

    engines = {}
    for name, dburi in the_dburis.items():
        engines[name] = rec = {}
        rec["url"] = dburi

    for name, rec in engines.items():
        logger.info("Migrating database %s", name)
        file_ = f"{name}.sql"
        logger.info("Writing output to %s", file_)
        with open(file_, "w") as buffer:
            alembic_context.configure(
                url=rec["url"],
                output_buffer=buffer,
                target_metadata=target_metadata.get(name),
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
            )
            with alembic_context.begin_transaction():
                alembic_context.run_migrations(engine_name=name)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # for the direct-to-DB use case, start a transaction on all
    # engines, then run all migrations, then commit all transactions.

    engines = {}
    for name, engine in the_engines.items():
        engines[name] = rec = {}
        rec["engine"] = engine

    for rec in engines.values():
        engine = rec["engine"]
        rec["connection"] = conn = engine.connect()

        if USE_TWOPHASE:
            rec["transaction"] = conn.begin_twophase()
        else:
            rec["transaction"] = conn.begin()

    try:
        for name, rec in engines.items():
            logger.info("Migrating database %s", name)
            alembic_context.configure(
                connection=rec["connection"],
                upgrade_token=f"{name}_upgrades",
                downgrade_token=f"{name}_downgrades",
                target_metadata=target_metadata.get(name),
            )
            alembic_context.run_migrations(engine_name=name)

        if USE_TWOPHASE:
            for rec in engines.values():
                rec["transaction"].prepare()

        for rec in engines.values():
            rec["transaction"].commit()
    except:
        for rec in engines.values():
            rec["transaction"].rollback()
        raise
    finally:
        for rec in engines.values():
            rec["connection"].close()


if alembic_context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
