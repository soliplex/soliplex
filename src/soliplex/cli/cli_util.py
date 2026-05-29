from __future__ import annotations

import contextlib
import pathlib

import typer
from rich import console

from soliplex import authz as authz_package
from soliplex import installation
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


def _check_ram_dburi(dburi: str, command: str):
    if dburi == config_installation.SYNC_MEMORY_ENGINE_URL:
        the_console.rule("Authorization DB is RAM-based")
        the_console.print(f"'{command}' is a no-op with a RAM-based database")
        raise typer.Exit(1)


@contextlib.contextmanager
def _authz_session(dburi):
    """Yield a sync authz session, disposing its engine on exit.

    'authz_schema.get_session' builds a fresh engine (and connection
    pool) per call. Disposing it when the caller finishes -- on both the
    success and 'typer.Exit' paths -- closes the underlying SQLite
    connection deterministically instead of leaking it until garbage
    collection.
    """
    session = authz_schema.get_session(engine_url=dburi, init_schema=True)
    try:
        yield session
    finally:
        session.get_bind().dispose()


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
