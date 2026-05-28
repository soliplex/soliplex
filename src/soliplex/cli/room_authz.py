from __future__ import annotations

import json
import pathlib
import sys
import typing

import typer
import yaml

from soliplex import authz as authz_package
from soliplex import models
from soliplex.authz import schema as authz_schema
from soliplex.cli import cli_util
from soliplex.cli import types

the_console = cli_util.the_console


app = typer.Typer(
    name="room-authz",
    help="Manage room authorization",
    no_args_is_help=True,
)


# Flip this to True to make human-focused output the default.
# '--quiet' will still force JSON.
_DEFAULT_VERBOSE = False


@app.callback()
def _room_authz_callback(
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


def _check_room_id(the_installation, room_id):
    room_configs = the_installation._config.room_configs
    if room_id in room_configs:
        return

    the_console.rule(f"No room configured with id '{room_id}'")
    configured = sorted(room_configs)
    if configured:
        the_console.print(
            f"Configured rooms: {', '.join(configured)}",
        )
    else:
        the_console.print("The installation has no rooms configured.")
    raise typer.Exit(1)


def _describe_discriminator(entry):
    if entry.everyone:
        return "everyone"
    if entry.authenticated:
        return "authenticated"
    if entry.json_path is not None:
        parsed = authz_package.parse_token_field_json_path(entry.json_path)
        if parsed is not None:
            field, value = parsed
            return f"{field}={value}"
        return f"json_path={entry.json_path}"
    return "(invalid: no discriminator set)"


def _human_dump_room_policy(session, room_id):  # pragma NO COVER UI ONLY
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

        the_console.rule(f"Room policy: {room_id}")

        if policy is None:
            the_console.print(
                "No policy row exists. Room is in default public "
                "state (all authenticated users allowed).",
            )
            return

        if policy.default_allow_deny == authz_package.AllowDeny.DENY:
            the_console.print(
                "Default: DENY (private -- denies callers that don't "
                "match an ALLOW entry).",
            )
        else:
            the_console.print(
                "Default: ALLOW (public-by-policy -- admits callers "
                "that don't match a DENY entry).",
            )

        if not policy.acl_entries:
            the_console.print("ACL entries: (none)")
            return

        the_console.print(f"ACL entries ({len(policy.acl_entries)}):")
        for index, entry in enumerate(policy.acl_entries, 1):
            flag = entry.allow_deny.name
            discriminator = _describe_discriminator(entry)
            the_console.print(f"  {index}. {flag:<5}  {discriminator}")


def _dump(ctx, session, room_id):
    if ctx.obj and ctx.obj.get("verbose"):
        _human_dump_room_policy(session, room_id)
    else:
        _dump_room_policy(session, room_id)


def _acl_entry_as_jsonable(entry) -> dict:
    """JSON-serializable view of an ACL row, tolerant of invalid paths.

    Mirrors the shape of 'authz_schema.ACLEntry.as_model' (and hence
    the public 'models.ACLEntry') but bypasses pydantic validation, so
    a row whose stored 'json_path' no longer compiles (e.g. it
    references a meta-config filter function that's no longer
    registered) still renders cleanly.
    """
    preferred_username = None
    email = None
    json_path = None
    if entry.json_path is not None:
        parsed = authz_package.parse_token_field_json_path(entry.json_path)
        if parsed is not None and parsed[0] == "preferred_username":
            preferred_username = parsed[1]
        elif parsed is not None and parsed[0] == "email":
            email = parsed[1]
        else:
            json_path = entry.json_path
    return {
        "allow_deny": entry.allow_deny.name,
        "everyone": entry.everyone,
        "authenticated": entry.authenticated,
        "preferred_username": preferred_username,
        "email": email,
        "json_path": json_path,
    }


def _room_policy_as_jsonable(policy):
    """Render a RoomPolicy (or None) as a JSON-serializable dict.

    Built directly from the ORM rows rather than via 'policy.as_model'
    so an entry whose stored 'json_path' no longer compiles does not
    raise when dumping (the round-trip pydantic model would reject it).

    AllowDeny values are emitted as their member names ('ALLOW' /
    'DENY') rather than the default 'AllowDeny.ALLOW' /
    'AllowDeny.DENY' string form.
    """
    if policy is None:
        return None
    return {
        "room_id": policy.room_id,
        "default_allow_deny": policy.default_allow_deny.name,
        "acl_entries": [
            _acl_entry_as_jsonable(entry) for entry in policy.acl_entries
        ],
    }


def _room_policy_as_yaml(policy) -> str:
    """Render a RoomPolicy (or None) as a YAML document.

    Uses the same JSON-serializable shape as the JSON dump, so the
    'AllowDeny' values are emitted as their member names.
    """
    to_dump = _room_policy_as_jsonable(policy)
    return yaml.safe_dump(to_dump, sort_keys=False, default_flow_style=False)


def _room_policy_from_jsonable(data) -> models.RoomPolicy | None:
    """Build a 'models.RoomPolicy' from the JSON-serializable shape.

    Inverse of '_room_policy_as_jsonable': 'AllowDeny' member names are
    converted back to enum members. Returns None for a 'null' document.
    """
    if data is None:
        return None
    acl_entries = []
    for entry in data.get("acl_entries", ()):
        entry = dict(entry)
        entry["allow_deny"] = authz_package.AllowDeny[entry["allow_deny"]]
        acl_entries.append(models.ACLEntry(**entry))
    return models.RoomPolicy(
        room_id=data["room_id"],
        default_allow_deny=authz_package.AllowDeny[data["default_allow_deny"]],
        acl_entries=acl_entries,
    )


def _effective_room_id(room_id, model) -> str | None:
    """Resolve the target room id for 'from-yaml'.

    Prefers the explicit 'room_id' argument; otherwise falls back to
    the 'room_id' recorded in the parsed model. Returns None when
    neither is available (e.g. a 'null' import with no explicit room).
    """
    if room_id is not None:
        return room_id
    if model is not None:
        return model.room_id
    return None


def _dump_room_policy(session, room_id):  # pragma NO COVER UI ONLY
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
        to_dump = _room_policy_as_jsonable(policy)

    print(json.dumps(to_dump))


@app.command("show")
def show_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    allow_stale: bool = typer.Option(
        False,
        "--allow-stale",
        help=(
            "Skip the configured-room check, so a policy left behind "
            "by a removed or renamed room can still be inspected."
        ),
    ),
):  # pragma NO COVER command
    """Show room ACL entries defined in the installation's authz database."""
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz show")
    if not allow_stale:
        _check_room_id(the_installation, room_id)

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    _dump(ctx, session, room_id)


@app.command("as-yaml")
def room_authz_as_yaml(
    installation_path: types.installation_path_type,
    room_id: str,
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
    allow_stale: bool = typer.Option(
        False,
        "--allow-stale",
        help=(
            "Skip the configured-room check, so a policy left behind "
            "by a removed or renamed room can still be dumped."
        ),
    ),
):  # pragma NO COVER command
    """Dump a room's RoomPolicy and ACL entries as YAML.

    With '--output', the YAML is written to the given file path;
    otherwise it is written to standard output with no console or rule
    decoration, suitable for piping or redirection.

    A room with no RoomPolicy row dumps as 'null'.
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz as-yaml")
    if not allow_stale:
        _check_room_id(the_installation, room_id)

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
        yaml_text = _room_policy_as_yaml(policy)

    if output is not None:
        output.write_text(yaml_text)
    else:
        print(yaml_text, end="")


@app.command("from-yaml")
def room_authz_from_yaml(
    installation_path: types.installation_path_type,
    room_id: typing.Annotated[
        str | None,
        typer.Argument(
            help=(
                "Target room. If omitted, the 'room_id' recorded in the "
                "input YAML is used."
            ),
        ),
    ] = None,
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
):  # pragma NO COVER command
    """Load a room's RoomPolicy and ACL entries from YAML.

    The YAML uses the same shape produced by 'room-authz as-yaml'.
    With '--input', the YAML is read from the given file path;
    otherwise it is read from standard input.

    If ROOM_ID is given it is authoritative: the policy is written for
    ROOM_ID regardless of the 'room_id' recorded in the YAML. If
    omitted, the YAML's own 'room_id' is used. Either way, any existing
    policy for the target room is replaced, and a 'null' document
    removes the target room's policy entirely.
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz from-yaml")

    if input_ is not None:
        yaml_text = input_.read_text()
    else:
        yaml_text = sys.stdin.read()

    model = _room_policy_from_jsonable(yaml.safe_load(yaml_text))

    room_id = _effective_room_id(room_id, model)
    if room_id is None:
        the_console.rule("No room id")
        the_console.print(
            "Pass ROOM_ID, or supply a non-null policy whose 'room_id' "
            "names the target room.",
        )
        raise typer.Exit(1)

    _check_room_id(the_installation, room_id)

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        existing = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )
        if existing is not None:
            session.delete(existing)
            session.commit()

        if model is not None:
            new_policy = authz_schema.RoomPolicy.from_model(model)
            new_policy.room_id = room_id
            session.add(new_policy)
            session.commit()


@app.command("make-private")
def make_room_private(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    update: bool = typer.Option(
        False,
        "--update",
        help=(
            "If the room already has a policy with "
            "default_allow_deny=ALLOW, update it in place to DENY "
            "(preserving existing ACL entries)."
        ),
    ),
):  # pragma NO COVER command
    """Ensure a room is private

    A room with no RoomPolicy row is public-to-all-authenticated-users
    by default; this command flips it to private by inserting an empty
    RoomPolicy (default_allow_deny=DENY, no ACL entries).

    If a policy already exists for the room, existing ACL entries are
    preserved.

    If the existing policy has default_allow_deny set to DENY,
    the command is a no-op.

    If the existing policy has default_allow_deny set to ALLOW,
    the command fails, unless '--update' is passed in which case the
    policy is updated in place to DENY (ACL entries still preserved).
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz make-private")
    _check_room_id(the_installation, room_id)

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
        elif policy.default_allow_deny == authz_package.AllowDeny.ALLOW:
            if not update:
                the_console.rule(
                    "Room policy already exists with default ALLOW",
                )
                the_console.print(
                    f"Room '{room_id}' has an existing policy with "
                    "default_allow_deny=ALLOW; pass '--update' to "
                    "flip it to DENY.",
                )
                raise typer.Exit(1)
            policy.default_allow_deny = authz_package.AllowDeny.DENY
            session.commit()

    _dump(ctx, session, room_id)


@app.command("make-public")
def make_room_public(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    update: bool = typer.Option(
        False,
        "--update",
        help=(
            "If the room already has a policy with "
            "default_allow_deny=DENY, update it in place to ALLOW "
            "(preserving existing ACL entries)."
        ),
    ),
):  # pragma NO COVER command
    """Ensure a room is public

    A room with no RoomPolicy row is public-to-all-authenticated-users
    by default; this command is a no-op in that case.

    If a policy already exists for the room, existing ACL entries are
    preserved.

    If the existing policy has default_allow_deny set to ALLOW,
    the command is a no-op.

    If the existing policy has default_allow_deny set to DENY,
    the command fails, unless '--update' is passed in which case the
    policy is updated in place to ALLOW (ACL entries still preserved).
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz make-public")
    _check_room_id(the_installation, room_id)

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

        if policy is not None and (
            policy.default_allow_deny == authz_package.AllowDeny.DENY
        ):
            if not update:
                the_console.rule(
                    "Room policy already exists with default DENY",
                )
                the_console.print(
                    f"Room '{room_id}' has an existing policy with "
                    "default_allow_deny=DENY; pass '--update' to "
                    "flip it to ALLOW.",
                )
                raise typer.Exit(1)
            policy.default_allow_deny = authz_package.AllowDeny.ALLOW
            session.commit()

    _dump(ctx, session, room_id)


@app.command("clear-acl")
def clear_room_acl(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
):  # pragma NO COVER command
    """Clear ACL entries from a room's policy, preserving the policy

    Unlike 'clear', this command does not delete the room's
    RoomPolicy row -- only its ACL entries. The policy's
    'default_allow_deny' setting is preserved: a private room
    (default DENY) stays private (and now denies everyone),
    a public-by-policy room (default ALLOW) stays public-by-policy.

    If no RoomPolicy exists for the room, the command is a no-op.
    """
    the_installation = cli_util.get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    cli_util._check_ram_dburi(dburi, "room-authz clear-acl")
    _check_room_id(the_installation, room_id)

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

        if policy is not None:
            for acl_entry in policy.acl_entries:
                session.delete(acl_entry)
            session.commit()

    _dump(ctx, session, room_id)


def _resolve_allow_deny(allow: bool, deny: bool) -> authz_package.AllowDeny:
    """Return the AllowDeny implied by --allow / --deny.

    Raises 'typer.Exit(1)' when both or neither flag is supplied.
    """
    if allow == deny:
        the_console.rule("Exactly one of '--allow' or '--deny' required")
        flags_given = [
            name for name, v in (("--allow", allow), ("--deny", deny)) if v
        ]
        the_console.print(
            "Pass exactly one of '--allow' or '--deny'. "
            f"Got: {flags_given or ['(none)']}.",
        )
        raise typer.Exit(1)

    if allow:
        return authz_package.AllowDeny.ALLOW
    return authz_package.AllowDeny.DENY


_ACL_ENTRY_DISCRIMINATORS_SUMMARY = (
    "'--everyone', '--authenticated', '--json-path', "
    "'--preferred-username', or '--email'"
)


def _check_acl_entry_args(
    installation_path: pathlib.Path,
    room_id: str,
    allow: bool,
    deny: bool,
    everyone: bool,
    authenticated: bool,
    json_path: str | None,
    preferred_username: str | None,
    email: str | None,
    command: str,
    allow_invalid_json_path: bool = False,
) -> tuple[str, authz_package.AllowDeny, str | None]:
    """Run the validation prolog shared by add/delete-acl-entry.

    Loads the installation, checks the room id is configured, validates
    the '--allow'/'--deny' and discriminator selections, resolves and
    validates the JSONPath, and rejects a RAM-based authorization DB.

    Pass 'allow_invalid_json_path=True' to skip the JSONPath compile
    check -- intended for 'delete-acl-entry --allow-invalid-json-path',
    so a stored entry whose 'json_path' no longer compiles can still
    be matched and removed.

    Returns '(dburi, allow_deny, json_path)' -- the values both commands
    need to perform their database update.

    Raises 'typer.Exit(1)' on any validation failure.
    """
    the_installation = cli_util.get_installation(installation_path)
    _check_room_id(the_installation, room_id)

    allow_deny = _resolve_allow_deny(allow, deny)
    cli_util._check_exactly_one_discriminator(
        [
            ("--everyone", everyone),
            ("--authenticated", authenticated),
            ("--json-path", json_path is not None),
            ("--preferred-username", preferred_username is not None),
            ("--email", email is not None),
        ],
        _ACL_ENTRY_DISCRIMINATORS_SUMMARY,
    )
    json_path = cli_util._resolve_json_path(
        the_installation,
        json_path,
        preferred_username,
        email,
        allow_invalid=allow_invalid_json_path,
    )

    dburi = the_installation.authorization_dburi_sync
    cli_util._check_ram_dburi(dburi, command)

    return dburi, allow_deny, json_path


@app.command("add-acl-entry")
def add_acl_entry(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    allow: bool = typer.Option(
        False,
        "--allow",
        help="Entry grants access. Mutually exclusive with '--deny'.",
    ),
    deny: bool = typer.Option(
        False,
        "--deny",
        help="Entry denies access. Mutually exclusive with '--allow'.",
    ),
    everyone: bool = typer.Option(
        False,
        "--everyone",
        help="Match every request (use as a catch-all).",
    ),
    authenticated: bool = typer.Option(
        False,
        "--authenticated",
        help="Match any authenticated user.",
    ),
    json_path: str | None = typer.Option(
        None,
        "--json-path",
        help=(
            "Match the user token via an RFC 9535 JSONPath query. The "
            "entry matches when the query returns at least one node."
        ),
    ),
    preferred_username: str | None = typer.Option(
        None,
        "--preferred-username",
        help="Match a user by OIDC preferred_username claim.",
    ),
    email: str | None = typer.Option(
        None,
        "--email",
        help="Match a user by OIDC email claim.",
    ),
):  # pragma NO COVER command
    """Add an ACL entry to a room's policy.

    Exactly one of '--allow' or '--deny' must be supplied.

    Exactly one discriminator option ('--everyone', '--authenticated',
    '--json-path', '--preferred-username', or '--email') must be
    supplied.

    The room must already have a RoomPolicy row -- run 'make-private'
    or 'make-public' first to establish the policy's
    'default_allow_deny'. This avoids silently flipping a public
    room to private as a side effect of adding the first entry.

    If an existing ACL entry has the same discriminator, it is
    replaced by the new entry. Entries with different discriminators
    are left untouched.
    """
    dburi, allow_deny, json_path = _check_acl_entry_args(
        installation_path,
        room_id,
        allow,
        deny,
        everyone,
        authenticated,
        json_path,
        preferred_username,
        email,
        "room-authz add-acl-entry",
    )

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
            the_console.rule(f"No policy exists for room '{room_id}'")
            the_console.print(
                f"Run 'room-authz make-private' or "
                "'room-authz make-public' to establish a policy "
                f"for '{room_id}' before adding ACL entries.",
            )
            raise typer.Exit(1)

        for entry in list(policy.acl_entries):
            if everyone and entry.everyone:
                session.delete(entry)
            elif authenticated and entry.authenticated:
                session.delete(entry)
            elif json_path is not None and entry.json_path == json_path:
                session.delete(entry)
        session.commit()

        new_acl = authz_schema.ACLEntry(
            room_policy=policy,
            allow_deny=allow_deny,
            everyone=everyone,
            authenticated=authenticated,
            json_path=json_path,
        )
        session.add(new_acl)
        session.commit()

    _dump(ctx, session, room_id)


@app.command("delete-acl-entry")
def delete_acl_entry(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    allow: bool = typer.Option(
        False,
        "--allow",
        help="Match an ALLOW entry. Mutually exclusive with '--deny'.",
    ),
    deny: bool = typer.Option(
        False,
        "--deny",
        help="Match a DENY entry. Mutually exclusive with '--allow'.",
    ),
    everyone: bool = typer.Option(
        False,
        "--everyone",
        help="Match an 'everyone' entry.",
    ),
    authenticated: bool = typer.Option(
        False,
        "--authenticated",
        help="Match an 'authenticated' entry.",
    ),
    json_path: str | None = typer.Option(
        None,
        "--json-path",
        help="Match a 'json_path' entry by query string.",
    ),
    preferred_username: str | None = typer.Option(
        None,
        "--preferred-username",
        help="Match a 'preferred_username' entry by claim value.",
    ),
    email: str | None = typer.Option(
        None,
        "--email",
        help="Match an 'email' entry by claim value.",
    ),
    allow_invalid_json_path: bool = typer.Option(
        False,
        "--allow-invalid-json-path",
        help=(
            "Skip JSONPath compile-validation of '--json-path' so an "
            "entry whose stored 'json_path' no longer compiles (e.g. "
            "because the meta-config filter function it referenced has "
            "been removed) can still be matched and removed."
        ),
    ),
):  # pragma NO COVER command
    """Delete an ACL entry from a room's policy.

    The entry to delete is identified by the combination of
    '--allow'/'--deny' and exactly one discriminator option
    ('--everyone', '--authenticated', '--json-path',
    '--preferred-username', '--email') -- the same parameter shape
    as 'add-acl-entry'.

    The room must already have a RoomPolicy row with at least one
    matching ACL entry. If no matching entry exists, the command
    fails and exits with a non-zero status.

    The RoomPolicy row is preserved; only matching ACL entries
    are removed.
    """
    dburi, allow_deny, json_path = _check_acl_entry_args(
        installation_path,
        room_id,
        allow,
        deny,
        everyone,
        authenticated,
        json_path,
        preferred_username,
        email,
        "room-authz delete-acl-entry",
        allow_invalid_json_path=allow_invalid_json_path,
    )

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
            the_console.rule(f"No policy exists for room '{room_id}'")
            the_console.print(
                f"Room '{room_id}' has no RoomPolicy; nothing to delete.",
            )
            raise typer.Exit(1)

        matches = []
        for entry in policy.acl_entries:
            if entry.allow_deny != allow_deny:
                continue
            if everyone and entry.everyone:
                matches.append(entry)
            elif authenticated and entry.authenticated:
                matches.append(entry)
            elif json_path is not None and entry.json_path == json_path:
                matches.append(entry)

        if not matches:
            the_console.rule("No matching ACL entry found")
            the_console.print(
                f"Room '{room_id}' has no ACL entry matching the "
                "supplied --allow/--deny and discriminator.",
            )
            raise typer.Exit(1)

        for entry in matches:
            session.delete(entry)
        session.commit()

    _dump(ctx, session, room_id)


# Deprecated and hidden BBB commands.


@app.command("add-user", hidden=True, deprecated=True)
def add_room_user(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    user_email: str,
):  # pragma NO COVER command
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

        json_path = authz_package.token_field_json_path("email", user_email)

        existing_acls = [
            acl_entry
            for acl_entry in policy.acl_entries
            if acl_entry.json_path == json_path
        ]
        for to_remove in existing_acls:
            session.delete(to_remove)
        session.commit()

        new_acl = authz_schema.ACLEntry(
            room_policy=policy,
            allow_deny=authz_package.AllowDeny.ALLOW,
            json_path=json_path,
        )
        session.add(new_acl)
        session.commit()

    _dump_room_policy(session, room_id)


@app.command("clear", hidden=True, deprecated=True)
def clear_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    room_id: str,
    make_room_private: bool = typer.Option(
        False,
        "--make-room-private",
        help="Make room private",
    ),
):  # pragma NO COVER command
    """Clear room ACL entries from the installation's authz database

    Unless '--make-room-private' is passed, the room will be in its
    default-public state.

    If '--make-room-private' is passed, the room policy will be set to
    private (default_allow_deny of DENY), with no users.
    """
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

        should_remove = 0
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
