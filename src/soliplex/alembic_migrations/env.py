"""Alembic's entry point for this script location.

Alembic executes this file for every command. Everything it does lives in
the package beside it (``soliplex.alembic_migrations``), which is ordinary,
tested code; this file stays a four-line shim so there is nothing here to
get wrong -- or to leave uncovered.

Run it the usual way::

    alembic -x soliplex.installation_path=<path> <command> ...
"""

from alembic import context as alembic_context

from soliplex import alembic_migrations

alembic_migrations.run(alembic_context)
