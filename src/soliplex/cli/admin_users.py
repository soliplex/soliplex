from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import typing

import typer
import yaml

from soliplex import authz
from soliplex.cli import cli_util
from soliplex.cli import types

the_console = cli_util.the_console


app = typer.Typer(
    name="admin-users",
    help="Manage admin users",
    no_args_is_help=True,
)


# Flip this to True to make human-focused output the default.
# '--quiet' will still force JSON.
_DEFAULT_VERBOSE = False


@app.callback()
def _admin_users_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False,
        "-v",
        "--verbose",
        help=(
            "Print human-focused output instead of a JSON dump. "
            "Overridden by '--quiet'."
        ),
    ),
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help=(
            "Force JSON output, overriding '--verbose' and any "
            "verbose-by-default setting."
        ),
    ),
):
    if quiet:
        effective = False
    elif verbose:
        effective = True
    else:
        effective = _DEFAULT_VERBOSE
    ctx.obj = {"verbose": effective}


_ADMIN_DISCRIMINATORS_SUMMARY = (
    "EMAIL, '--preferred-username', or '--json-path'"
)


def _check_admin_discriminator(
    email: str | None,
    preferred_username: str | None,
    json_path: str | None,
) -> None:
    """Require exactly one of EMAIL / --preferred-username / --json-path."""
    cli_util._check_exactly_one_discriminator(
        [
            ("EMAIL", email is not None),
            ("--preferred-username", preferred_username is not None),
            ("--json-path", json_path is not None),
        ],
        _ADMIN_DISCRIMINATORS_SUMMARY,
    )


def _describe_admin(json_path) -> str:
    """Human-friendly descriptor for an admin entry's JSONPath."""
    parsed = authz.parse_token_field_json_path(json_path)
    if parsed is not None:
        field, value = parsed
        return f"{field}={value}"
    return f"json_path={json_path}"


def _admin_display(json_path) -> str:
    """Value to show for an admin entry in the JSON dump.

    Email-keyed admins show their email; others show the raw query.
    """
    parsed = authz.parse_token_field_json_path(json_path)
    if parsed is not None and parsed[0] == "email":
        return parsed[1]
    return json_path


def _admin_user_as_jsonable(json_path: str) -> dict:
    """JSON-serializable view of an admin row, tolerant of invalid paths.

    Mirrors the per-entry shape used by 'room-authz as-yaml': surfaces
    the canonical 'email' / 'preferred_username' query as the matching
    shortcut field; other queries (including ones that no longer
    compile) come back as 'json_path'.
    """
    preferred_username = None
    email = None
    other_json_path = None
    parsed = authz.parse_token_field_json_path(json_path)
    if parsed is not None and parsed[0] == "preferred_username":
        preferred_username = parsed[1]
    elif parsed is not None and parsed[0] == "email":
        email = parsed[1]
    else:
        other_json_path = json_path
    return {
        "preferred_username": preferred_username,
        "email": email,
        "json_path": other_json_path,
    }


def _admin_users_as_jsonable(json_paths) -> dict:
    """Render an iterable of admin 'json_path' values as a jsonable dict.

    Wraps the per-entry dicts in a top-level 'admin_users' key, matching
    the shape used by 'admin-users list' (but with each entry as a
    structured dict rather than a bare string).
    """
    return {
        "admin_users": [
            _admin_user_as_jsonable(json_path) for json_path in json_paths
        ],
    }


def _admin_users_as_yaml(json_paths) -> str:
    """Render an iterable of admin 'json_path' values as a YAML document."""
    to_dump = _admin_users_as_jsonable(json_paths)
    return yaml.safe_dump(to_dump, sort_keys=False, default_flow_style=False)


def _admin_user_from_jsonable(entry: dict) -> str:
    """Resolve a from-yaml entry back to a canonical 'json_path' string.

    Each entry must specify exactly one of 'email',
    'preferred_username', or 'json_path'. Raises 'typer.Exit(1)' on a
    malformed entry. The validity of a literal 'json_path' is not
    checked here; the storage layer's '@validates' hook enforces it
    on insert.
    """
    email = entry.get("email")
    preferred_username = entry.get("preferred_username")
    json_path = entry.get("json_path")
    cli_util._check_exactly_one_discriminator(
        [
            ("email", email is not None),
            ("preferred_username", preferred_username is not None),
            ("json_path", json_path is not None),
        ],
        "'email', 'preferred_username', or 'json_path'",
    )
    if email is not None:
        return authz.token_field_json_path("email", email)
    if preferred_username is not None:
        return authz.token_field_json_path(
            "preferred_username", preferred_username
        )
    return json_path


def _admin_users_from_jsonable(data) -> list[str]:
    """Translate the JSON-serializable shape back to a list of json_paths.

    Returns an empty list for a 'null' document or one with no entries.
    """
    if data is None:
        return []
    return [
        _admin_user_from_jsonable(entry)
        for entry in data.get("admin_users", ())
    ]


def _check_admin_user_args(
    installation_path: pathlib.Path,
    admin_user_email: str | None,
    preferred_username: str | None,
    json_path: str | None,
    command: str,
    allow_invalid_json_path: bool = False,
) -> tuple[str, str]:
    """Run the validation prolog shared by 'admin-users' add/delete.

    Loads the installation, validates the discriminator selection,
    resolves and validates the JSONPath, and rejects a RAM-based
    authorization DB.

    Pass 'allow_invalid_json_path=True' to skip the JSONPath compile
    check -- intended for 'admin-users delete --allow-invalid-json-path',
    so a stored entry whose 'json_path' no longer compiles can still
    be matched and removed.

    Returns '(dburi, json_path)' -- the values both commands need to
    perform their database update.

    Raises 'typer.Exit(1)' on any validation failure.
    """
    the_installation = cli_util.get_installation(installation_path)

    _check_admin_discriminator(admin_user_email, preferred_username, json_path)

    resolved = cli_util._resolve_json_path(
        the_installation,
        json_path,
        preferred_username,
        admin_user_email,
        allow_invalid=allow_invalid_json_path,
    )

    dburi = the_installation.authorization_dburi_async
    cli_util._check_ram_dburi(dburi, command)

    return dburi, resolved


def _dump(ctx, json_paths):
    if ctx.obj and ctx.obj.get("verbose"):
        _human_dump_admin_users(json_paths)
    else:
        _dump_admin_users(json_paths)


def _human_dump_admin_users(json_paths):  # pragma NO COVER UI ONLY
    the_console.rule("Admin users")

    if not json_paths:
        the_console.print("No admin users configured.")
        return

    the_console.print(f"Admin users ({len(json_paths)}):")
    for index, json_path in enumerate(json_paths, 1):
        the_console.print(f"  {index}. {_describe_admin(json_path)}")


def _dump_admin_users(json_paths):  # pragma NO COVER UI ONLY
    admin_users = [_admin_display(json_path) for json_path in json_paths]
    print(json.dumps({"admin_users": admin_users}))


async def _list_discriminators(dburi):
    async with cli_util._admin_user_policy(dburi) as policy:
        return await policy.list_admin_user_discriminators()


async def _clear_discriminators(dburi):
    async with cli_util._admin_user_policy(dburi) as policy:
        await policy.clear_admin_user_discriminators()
        return await policy.list_admin_user_discriminators()


async def _add_discriminator(dburi, json_path):
    async with cli_util._admin_user_policy(dburi) as policy:
        await policy.add_admin_user_discriminator(json_path)
        return await policy.list_admin_user_discriminators()


async def _remove_discriminator(dburi, json_path):
    async with cli_util._admin_user_policy(dburi) as policy:
        await policy.remove_admin_user_discriminator(json_path)
        return await policy.list_admin_user_discriminators()


async def _replace_discriminators(dburi, json_paths):
    async with cli_util._admin_user_policy(dburi) as policy:
        await policy.clear_admin_user_discriminators()
        for json_path in json_paths:
            await policy.add_admin_user_discriminator(json_path)


@app.command("list")
def list_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Show admin users defined in the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_async

    cli_util._check_ram_dburi(dburi, "admin-users list")

    discriminators = asyncio.run(_list_discriminators(dburi))
    _dump(ctx, discriminators)


@app.command("clear")
def clear_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Clear admin users from the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_async

    cli_util._check_ram_dburi(dburi, "admin-users clear")

    discriminators = asyncio.run(_clear_discriminators(dburi))
    _dump(ctx, discriminators)


@app.command("add")
def add_admin_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    admin_user_email: typing.Annotated[
        str | None,
        typer.Argument(
            metavar="EMAIL",
            help=(
                "Email address to grant admin (the common case). "
                "Mutually exclusive with '--preferred-username' / "
                "'--json-path'."
            ),
        ),
    ] = None,
    preferred_username: str | None = typer.Option(
        None,
        "--preferred-username",
        help="Grant admin by OIDC preferred_username claim.",
    ),
    json_path: str | None = typer.Option(
        None,
        "--json-path",
        help=(
            "Grant admin to any user token matched by this RFC 9535 "
            "JSONPath query."
        ),
    ),
):
    """Add an admin user to the installation's authz database.

    Exactly one discriminator must be supplied: the positional EMAIL
    (shorthand for the common case), '--preferred-username', or
    '--json-path'. If the resolved entry is already an admin, the
    command reports that and exits non-zero without inserting a
    duplicate row.
    """
    dburi, resolved = _check_admin_user_args(
        installation_path,
        admin_user_email,
        preferred_username,
        json_path,
        "admin-users add",
    )

    try:
        discriminators = asyncio.run(_add_discriminator(dburi, resolved))
    except authz.AdminUserExists:
        the_console.rule(f"{_describe_admin(resolved)} is already an admin")
        the_console.print("Nothing to do.")
        raise typer.Exit(1) from None

    _dump(ctx, discriminators)


@app.command("delete")
def delete_admin_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    admin_user_email: typing.Annotated[
        str | None,
        typer.Argument(
            metavar="EMAIL",
            help=(
                "Email address to revoke admin from (the common case). "
                "Mutually exclusive with '--preferred-username' / "
                "'--json-path'."
            ),
        ),
    ] = None,
    preferred_username: str | None = typer.Option(
        None,
        "--preferred-username",
        help="Revoke admin by OIDC preferred_username claim.",
    ),
    json_path: str | None = typer.Option(
        None,
        "--json-path",
        help=(
            "Revoke admin from any user token matched by this RFC 9535 "
            "JSONPath query."
        ),
    ),
    allow_invalid_json_path: bool = typer.Option(
        False,
        "--allow-invalid-json-path",
        help=(
            "Skip JSONPath compile-validation of '--json-path' so an "
            "admin entry whose stored 'json_path' no longer compiles "
            "(e.g. because the meta-config filter function it "
            "referenced has been removed) can still be matched and "
            "removed."
        ),
    ),
):
    """Remove an admin user from the installation's authz database.

    Exactly one discriminator must be supplied: the positional EMAIL
    (shorthand for the common case), '--preferred-username', or
    '--json-path'. The entry is matched by string equality against the
    stored 'json_path'. If no admin entry matches the resolved
    JSONPath, the command reports that and exits non-zero.
    """
    dburi, resolved = _check_admin_user_args(
        installation_path,
        admin_user_email,
        preferred_username,
        json_path,
        "admin-users delete",
        allow_invalid_json_path=allow_invalid_json_path,
    )

    try:
        discriminators = asyncio.run(_remove_discriminator(dburi, resolved))
    except authz.NoSuchAdminUser:
        the_console.rule(f"{_describe_admin(resolved)} is not an admin")
        the_console.print("Nothing to do.")
        raise typer.Exit(1) from None

    _dump(ctx, discriminators)


@app.command("as-yaml")
def admin_users_as_yaml(
    installation_path: types.installation_path_type,
    output: typing.Annotated[
        pathlib.Path | None,
        typer.Option(
            "--output",
            "-o",
            help=(
                "Write the YAML to this file path. If omitted, the YAML "
                "is written to standard output with no other decoration."
            ),
        ),
    ] = None,
):
    """Dump every admin user as YAML.

    With '--output', the YAML is written to the given file path;
    otherwise it is written to standard output with no console or rule
    decoration, suitable for piping or redirection.

    An installation with no admins dumps as 'admin_users: []'. Entries
    whose stored 'json_path' no longer compiles are still rendered
    (they round-trip via 'from-yaml').
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_async

    cli_util._check_ram_dburi(dburi, "admin-users as-yaml")

    discriminators = asyncio.run(_list_discriminators(dburi))
    yaml_text = _admin_users_as_yaml(discriminators)

    if output is not None:
        output.write_text(yaml_text)
    else:
        print(yaml_text, end="")


@app.command("from-yaml")
def admin_users_from_yaml(
    installation_path: types.installation_path_type,
    input_: typing.Annotated[
        pathlib.Path | None,
        typer.Option(
            "--input",
            "-i",
            help=(
                "Read the YAML from this file path. If omitted, the YAML "
                "is read from standard input."
            ),
        ),
    ] = None,
):
    """Replace admin users with the entries in a YAML document.

    The YAML uses the same shape produced by 'admin-users as-yaml'.
    With '--input', the YAML is read from the given file path;
    otherwise it is read from standard input.

    All existing admin entries are removed; the YAML's admins (if any)
    are inserted. A 'null' document or an empty 'admin_users' list
    removes every admin entry.
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_async

    cli_util._check_ram_dburi(dburi, "admin-users from-yaml")

    if input_ is not None:
        yaml_text = input_.read_text()
    else:
        yaml_text = sys.stdin.read()

    json_paths = _admin_users_from_jsonable(yaml.safe_load(yaml_text))

    asyncio.run(_replace_discriminators(dburi, json_paths))
