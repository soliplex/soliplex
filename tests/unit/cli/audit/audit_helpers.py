from __future__ import annotations

import sqlalchemy as sa

TESTING_MODEL_ERROR = "testing model error"
TESTING_AUTHZ_DB_ERROR = "testing authz db error"


class ModelException(ValueError):
    def __init__(self):
        super().__init__(TESTING_MODEL_ERROR)


class AuthzDBError(OSError):
    """Stand-in for whatever the DB driver raises when it can't connect."""

    def __init__(self):
        super().__init__(TESTING_AUTHZ_DB_ERROR)


# The authz-DB readers prefix the exception type: a bare 'str(exc)' on e.g.
# the 'FileNotFoundError' asyncpg raises for a missing unix socket reads as
# a stray "[Errno 2] No such file or directory".
EXP_AUTHZ_DB_ERROR = f"AuthzDBError: {TESTING_AUTHZ_DB_ERROR}"


def tables(db_path):
    """The tables in a SQLite file. Connecting creates the file itself --
    an empty one -- so the schema is what says whether anything was
    created."""
    engine = sa.create_engine(f"sqlite:///{db_path}")
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def uncreated_installation(the_installation, tmp_path):
    """Point an installation at an authz database nothing has created."""
    db_path = tmp_path / "authz.sqlite"
    the_installation._config.authorization_async_dburi = (
        f"sqlite+aiosqlite:///{db_path}"
    )
    the_installation._config.authorization_sync_dburi = f"sqlite:///{db_path}"
    return the_installation, db_path
