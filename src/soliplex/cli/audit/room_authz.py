from __future__ import annotations

import asyncio

import typer

from soliplex import authz
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import databases as audit_databases


async def _list_room_policies(the_installation):
    async with cli_util._room_authz_policy(
        the_installation, "audit room-authz", allow_ram=True, must_exist=True
    ) as policy:
        return await policy.list_room_policies()


def _room_policies(the_installation) -> tuple[list, str | None]:
    """Return ``(policies, error)`` for the stored room policies.

    ``policies`` holds the unchecked policy models read via
    'RoomAuthorizationPolicy.list_room_policies' and ``error`` is ``None``
    on success. A database nothing has created yet -- including an
    in-memory one -- holds no policies, so it reports ``([], None)``
    rather than creating a schema to read from.

    When the database itself cannot be reached -- e.g. its DBURI names a
    Postgres server that isn't listening -- ``policies`` is empty and
    ``error`` carries the exception message, so the audit can report the
    unreachable DB instead of dying on the traceback.
    """
    try:
        return list(asyncio.run(_list_room_policies(the_installation))), None
    except cli_util.DatabaseNotCreated:
        # Nothing has created the authorization schema, so there are no
        # policies to audit. Creating one is a writable open's job, never
        # an audit's.
        return [], None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _room_authz_groups(the_installation, room_policies):
    """Bucket configured rooms by authorization state; collect stale rows.

    ``room_policies`` is the policy list from '_room_policies'.
    """
    configured = sorted(the_installation._config.room_configs)

    policies = {
        policy.room_id: policy.default_allow_deny for policy in room_policies
    }

    configured_set = set(configured)
    default, public, private = [], [], []
    for room_id in configured:
        if room_id not in policies:
            default.append(room_id)
        elif policies[room_id] == authz.AllowDeny.ALLOW:
            public.append(room_id)
        else:
            private.append(room_id)

    stale = sorted(rid for rid in policies if rid not in configured_set)

    return {
        "default": default,
        "public": public,
        "private": private,
        "stale": stale,
    }


def _invalid_acl_json_paths(room_policies) -> dict:
    """Collect ACL entries whose stored 'json_path' fails to validate.

    ``room_policies`` is the policy list from '_room_policies' -- the
    unchecked models, which tolerate entries that would fail
    'policy.as_model'. Each surfaced 'json_path' is re-validated against
    the currently-loaded JSONPath environment. Typically an entry lands
    here when it was authored under a meta-config that registered filter
    functions which are no longer present.

    Returns a dict mapping 'room_id' to a list of '(json_path, error)'
    pairs.
    """
    invalid: dict = {}
    for policy in room_policies:
        for entry in policy.acl_entries:
            if entry.json_path is None:
                continue
            try:
                authz.validate_json_path(entry.json_path)
            except authz.InvalidJSONPath as exc:
                invalid.setdefault(policy.room_id, []).append(
                    (entry.json_path, str(exc)),
                )
    return invalid


def _audit_room_authz_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the room-authz section (rule header + four buckets)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured rooms by authorization state")
    tc_line()

    report = audit_databases._database_reports(ctx, the_installation._config)[
        cli_util.AUTHZ
    ]
    if report.error is not None:
        if ctx.obj.get("databases_audited"):
            tc_print(audit_databases._SEE_DATABASES)
            tc_line()
            return {}
        tc_print(f"ERROR: authorization database unreachable: {report.error}")
        tc_line()
        return {"room_authz": {"unreachable": report.error}}

    room_policies, db_error = _room_policies(the_installation)
    if db_error is not None:
        tc_print(f"ERROR: authorization database unreachable: {db_error}")
        tc_line()
        return {"room_authz": {"unreachable": db_error}}

    groups = _room_authz_groups(the_installation, room_policies)

    for label, room_ids in (
        (
            "Default (no policy row -- public to authenticated users)",
            groups["default"],
        ),
        ("Public (policy row, default ALLOW)", groups["public"]),
        ("Private (policy row, default DENY)", groups["private"]),
    ):
        tc_print(f"{label}:")
        if room_ids:
            for room_id in room_ids:
                tc_print(f"  - {room_id}")
        else:
            tc_print("  (none)")
        tc_line()

    tc_print("Stale (policy row exists for unconfigured room):")
    if groups["stale"]:
        for room_id in groups["stale"]:
            tc_print(f"  - {room_id}  STALE")
    else:
        tc_print("  (none)")
    tc_line()

    invalid_acls = _invalid_acl_json_paths(room_policies)
    tc_print("ACL entries with invalid JSONPath:")
    if invalid_acls:
        for room_id in sorted(invalid_acls):
            for json_path, error in invalid_acls[room_id]:
                tc_print(f"  - {room_id}: {json_path}  ({error})")
    else:
        tc_print("  (none)")
    tc_line()

    sub_errors: dict = {}
    if groups["stale"]:
        sub_errors["stale_rooms"] = groups["stale"]
    if invalid_acls:
        sub_errors["invalid_acls"] = invalid_acls

    errors: dict = {}
    if sub_errors:
        errors["room_authz"] = sub_errors
    return errors


def audit_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List rooms by authorization status.

    Buckets: 'default' (no policy row), 'public' (policy with
    default_allow_deny=ALLOW), 'private' (policy with
    default_allow_deny=DENY), 'stale' (policy row exists in the
    authorization database for a room that isn't configured in the
    YAML). A non-empty 'stale' bucket is reported as an audit error.
    """
    quiet = ctx.obj["quiet"]
    errors = _audit_room_authz_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
