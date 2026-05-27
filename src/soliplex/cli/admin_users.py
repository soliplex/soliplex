from __future__ import annotations

import json

import typer

from soliplex.authz import schema as authz_schema
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


def _check_existing_admin(session, email):
    """Reject 'admin-users add' for an email that is already an admin.

    Inserting a second row for the same email would violate the
    'AdminUser.email' uniqueness constraint; rather than surface that as
    an opaque IntegrityError traceback (exit code depending on the
    backend), report it cleanly and exit non-zero.
    """
    existing = (
        session.query(
            authz_schema.AdminUser,
        )
        .where(
            authz_schema.AdminUser.email == email,
        )
        .first()
    )
    if existing is None:
        return

    the_console.rule(f"{email} is already an admin")
    the_console.print("Nothing to do.")
    raise typer.Exit(1)


def _dump(ctx, session):
    if ctx.obj and ctx.obj.get("verbose"):
        _human_dump_admin_users(session)
    else:
        _dump_admin_users(session)


def _human_dump_admin_users(session):  # pragma NO COVER UI ONLY
    with session:
        emails = [
            admin_user.email
            for admin_user in session.query(
                authz_schema.AdminUser,
            )
        ]

    the_console.rule("Admin users")

    if not emails:
        the_console.print("No admin users configured.")
        return

    the_console.print(f"Admin users ({len(emails)}):")
    for index, email in enumerate(emails, 1):
        the_console.print(f"  {index}. {email}")


def _dump_admin_users(session):  # pragma NO COVER UI ONLY
    with session:
        admin_users = [
            admin_user.email
            for admin_user in session.query(
                authz_schema.AdminUser,
            )
        ]
    print(json.dumps({"admin_users": admin_users}))


@app.command("list")
def list_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Show admin users defined in the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users list")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)
    _dump(ctx, session)


@app.command("clear")
def clear_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Clear admin users from the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users clear")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        for admin_user in session.query(authz_schema.AdminUser):
            session.delete(admin_user)
        session.commit()

    _dump(ctx, session)


@app.command("add")
def add_admin_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    admin_user_email: str,
):  # pragma NO COVER command
    """Add an admin user to the installation's authz database.

    If the email is already an admin, the command reports that and
    exits non-zero without inserting a duplicate row.
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users add")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        _check_existing_admin(session, admin_user_email)
        admin_user = authz_schema.AdminUser(email=admin_user_email)
        session.add(admin_user)
        session.commit()

    _dump(ctx, session)
