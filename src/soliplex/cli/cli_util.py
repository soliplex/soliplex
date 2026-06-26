from __future__ import annotations

import contextlib
import pathlib

import typer
from rich import console
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import authz as authz_package
from soliplex import installation
from soliplex.authz import persistence as authz_persistence
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation

the_console = console.Console()


def get_installation(
    installation_path: pathlib.Path,
    auditing: bool = False,
) -> installation.Installation:

    if installation_path.is_dir():
        installation_path = installation_path / "installation.yaml"
    i_config = config_installation.load_installation(installation_path)

    try:
        i_config.reload_configurations()
    except config_installation.MissingEnvVars:
        if not auditing:
            raise

    return installation.Installation(i_config)


# Both the sync ('sqlite://') and async ('sqlite+aiosqlite://') in-memory
# URLs spell a throwaway database; a CLI mutation against either is a no-op
# once the process exits, so commands reject them up front.
_RAM_DBURIS = frozenset(
    {
        config_installation.SYNC_MEMORY_ENGINE_URL,
        config_installation.ASYNC_MEMORY_ENGINE_URL,
    }
)


def _check_ram_dburi(dburi: str, command: str):
    if dburi in _RAM_DBURIS:
        the_console.rule("Authorization DB is RAM-based")
        the_console.print(f"'{command}' is a no-op with a RAM-based database")
        raise typer.Exit(1)


@contextlib.asynccontextmanager
async def _authz_policy(dburi):
    """Yield an async 'AuthorizationPolicy', disposing its engine on exit.

    Builds a fresh async engine per call via
    'installation._create_async_engine' -- the same factory the app's
    lifespan uses -- so the CLI inherits its file-based-SQLite tuning,
    notably 'PRAGMA foreign_keys=ON' (which enables the 'ON DELETE
    CASCADE' behind room policy / ACL deletes). The schema is created if
    needed, and the engine is disposed on exit -- on both the success and
    'typer.Exit' paths -- so the underlying SQLite connection is released
    deterministically instead of leaking it until garbage collection.
    """
    engine = installation._create_async_engine(dburi)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(authz_schema.Base.metadata.create_all)
        async with sqla_asyncio.AsyncSession(bind=engine) as session:
            yield authz_persistence.AuthorizationPolicy(session)
    finally:
        await engine.dispose()


def _check_exactly_one_discriminator(
    discriminators: list[tuple[str, bool]],
    options_summary: str,
) -> None:
    """Require exactly one discriminator to be set.

    'discriminators' is a list of '(display_name, is_present)' tuples.
    'options_summary' is the human-readable "X, Y, or Z" portion that
    fills the per-call error message (so the wording can match the
    flag names exposed by the caller -- e.g. 'EMAIL' as a positional
    vs '--email' as an OIDC-claim option).

    Raises 'typer.Exit(1)' on zero or more than one selection.
    """
    selected = [name for name, present in discriminators if present]
    if len(selected) != 1:
        the_console.rule("Exactly one discriminator required")
        the_console.print(
            f"Pass exactly one of {options_summary}. "
            f"Got: {selected or ['(none)']}.",
        )
        raise typer.Exit(1)


def _resolve_json_path(
    _the_installation,
    json_path: str | None,
    preferred_username: str | None,
    email: str | None,
    allow_invalid: bool = False,
) -> str | None:
    """Resolve and validate a JSONPath for a stored ACL/admin entry.

    Collapses the OIDC 'preferred_username' / 'email' claim shortcuts
    into the canonical 'authz.token_field_json_path' form, then
    validates the result via 'authz_package.validate_json_path'.

    The loaded installation is taken as a required positional argument
    -- its presence at the call site enforces the ordering constraint
    that the installation must be loaded (and any meta-config-defined
    JSONPath filter functions thereby registered) before compilation.
    '_the_installation' is not otherwise consumed here; the leading
    underscore signals that to readers (and to ruff).

    Pass 'allow_invalid=True' to skip the compile check; this lets
    deletion commands match a stored entry whose 'json_path' no longer
    compiles (e.g. because the meta-config filter function it
    referenced has been removed).

    Raises 'typer.Exit(1)' when 'validate_json_path' rejects the result.
    """
    if preferred_username is not None:
        json_path = authz_package.token_field_json_path(
            "preferred_username", preferred_username
        )
    elif email is not None:
        json_path = authz_package.token_field_json_path("email", email)

    if json_path is None or allow_invalid:
        return json_path

    try:
        authz_package.validate_json_path(json_path)
    except authz_package.InvalidJSONPath as exc:
        the_console.rule("Invalid JSONPath")
        the_console.print(str(exc))
        raise typer.Exit(1) from exc

    return json_path
