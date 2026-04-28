from __future__ import annotations

import json

import typer

from soliplex import authz as authz_package
from soliplex.authz import schema as authz_schema
from soliplex.cli import cli_util
from soliplex.cli import types

the_console = cli_util.the_console


app = typer.Typer(
    name="room-authz",
    help="Manage room authorization",
    no_args_is_help=True,
)


def _dump_room_policy(session, room_id):
    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        if policy is None:
            to_dump = policy
        else:
            to_dump = policy.as_model.model_dump()
            to_dump["default_allow_deny"] = str(to_dump["default_allow_deny"])

            for dump_ae in to_dump["acl_entries"]:
                dump_ae["allow_deny"] = str(dump_ae["allow_deny"])

    print(json.dumps(to_dump))


@app.command("show")
def show_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
):
    """Show room ACL entries defined in the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz show")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    _dump_room_policy(session, room_id)


@app.command("clear")
def clear_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    make_room_private: bool = typer.Option(
        False,
        "--make-room-private",
        help="Make room private",
    ),
):
    """Clear room ACL entries from the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz clear")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        before_entries = len(session.query(authz_schema.ACLEntry).all())

        if policy is not None:
            # for acl_entry in policy.acl_entries:
            #    session.delete(acl_entry)
            should_remove = len(policy.acl_entries)

            session.delete(policy)
            session.commit()

        after_entries = len(session.query(authz_schema.ACLEntry).all())
        assert after_entries == before_entries - should_remove

        if make_room_private:
            policy = authz_schema.RoomPolicy(room_id=room_id)
            session.add(policy)
            session.commit()

    _dump_room_policy(session, room_id)


@app.command("add-user")
def add_room_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    user_email: str,
):
    """Add a user to the ACL for a room."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz add-user")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        if policy is None:
            policy = authz_schema.RoomPolicy(room_id=room_id)
            session.add(policy)
            session.commit()

        existing_acls = [
            acl_entry
            for acl_entry in policy.acl_entries
            if acl_entry.email == user_email
        ]
        for to_remove in existing_acls:
            session.delete(to_remove)
        session.commit()

        new_acl = authz_schema.ACLEntry(
            room_policy=policy,
            allow_deny=authz_package.AllowDeny.ALLOW,
            email=user_email,
        )
        session.add(new_acl)
        session.commit()

    _dump_room_policy(session, room_id)
