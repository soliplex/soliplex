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


def _dump_admin_users(session):
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
):
    """Show admin users defined in the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users list")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)
    _dump_admin_users(session)


@app.command("clear")
def clear_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Clear admin users from the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users clear")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        for admin_user in session.query(authz_schema.AdminUser):
            session.delete(admin_user)
        session.commit()

        _dump_admin_users(session)


@app.command("add")
def add_admin_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    admin_user_email: str,
):
    """Add an admin user to the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "admin-users add")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        admin_user = authz_schema.AdminUser(email=admin_user_email)
        session.add(admin_user)
        session.commit()

        _dump_admin_users(session)
