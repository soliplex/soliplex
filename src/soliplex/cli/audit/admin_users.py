from __future__ import annotations

import asyncio

import typer

from soliplex import authz
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import databases as audit_databases


async def _list_admin_discriminators(the_installation):
    async with cli_util._admin_user_policy(
        the_installation, "audit admin-users", allow_ram=True, must_exist=True
    ) as policy:
        return await policy.list_admin_user_discriminators()


def _admin_user_json_paths(
    the_installation,
) -> tuple[list[str], str | None]:
    """Return ``(json_paths, error)`` for the stored admin rows.

    ``json_paths`` holds every stored 'AdminUser.json_path', in insertion
    order, read via 'AdminUserPolicy.list_admin_user_discriminators';
    ``error`` is ``None`` on success. A database nothing has created yet
    -- including an in-memory one -- holds no admin rows, so it reports
    ``([], None)`` rather than creating a schema to read from.

    When the database itself cannot be reached -- e.g. its DBURI names a
    Postgres server that isn't listening -- ``json_paths`` is empty and
    ``error`` carries the exception message, so the audit can report the
    unreachable DB instead of dying on the traceback.
    """
    try:
        return (
            list(asyncio.run(_list_admin_discriminators(the_installation))),
            None,
        )
    except cli_util.DatabaseNotCreated:
        # As above: no schema means nothing to audit.
        return [], None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _invalid_admin_user_json_paths(
    json_paths,
) -> list[tuple[str, str]]:
    """Collect admin entries whose 'json_path' fails to validate.

    Same intent as '_invalid_acl_json_paths' but for the 'AdminUser'
    table: a row typically lands here when it was authored under a
    meta-config that registered filter functions which are no longer
    present. ``json_paths`` is the list from '_admin_user_json_paths'.

    Returns a list of '(json_path, error)' pairs.
    """
    invalid: list[tuple[str, str]] = []
    for json_path in json_paths:
        try:
            authz.validate_json_path(json_path)
        except authz.InvalidJSONPath as exc:
            invalid.append((json_path, str(exc)))
    return invalid


def _audit_admin_users_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the admin-users section (rule header + listing + invalid)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured admin users")
    tc_line()

    report = audit_databases._database_reports(ctx, the_installation)[
        cli_util.AUTHZ
    ]
    if report.error is not None:
        if ctx.obj.get("databases_audited"):
            tc_print(audit_databases._SEE_DATABASES)
            tc_line()
            return {}
        tc_print(f"ERROR: authorization database unreachable: {report.error}")
        tc_line()
        return {"admin_users": {"unreachable": report.error}}

    json_paths, db_error = _admin_user_json_paths(the_installation)
    if db_error is not None:
        tc_print(f"ERROR: authorization database unreachable: {db_error}")
        tc_line()
        return {"admin_users": {"unreachable": db_error}}

    tc_print(f"Admin users ({len(json_paths)}):")
    if json_paths:
        for json_path in json_paths:
            parsed = authz.parse_token_field_json_path(json_path)
            if parsed is not None:
                field, value = parsed
                tc_print(f"  - {field}={value}")
            else:
                tc_print(f"  - json_path={json_path}")
    else:
        tc_print("  (none)")
    tc_line()

    invalid = _invalid_admin_user_json_paths(json_paths)
    tc_print("Admin users with invalid JSONPath:")
    if invalid:
        for json_path, error in invalid:
            tc_print(f"  - {json_path}  ({error})")
    else:
        tc_print("  (none)")
    tc_line()

    errors: dict = {}
    if invalid:
        errors["admin_users"] = {"invalid_json_paths": invalid}
    return errors


def audit_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List configured admin users and flag any with invalid JSONPath.

    Each stored 'AdminUser.json_path' is re-validated against the
    currently-loaded JSONPath environment. An entry whose query no
    longer compiles (e.g. because the meta-config filter function it
    referenced has been removed) is reported as an audit error.
    """
    quiet = ctx.obj["quiet"]
    errors = _audit_admin_users_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
