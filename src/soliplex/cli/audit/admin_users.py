from __future__ import annotations

import asyncio
import re

import typer

from soliplex import authn
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


_DISCRIMINATOR_CLAIM_RE = re.compile(r"\$\.([A-Za-z_]\w*)")
_BRACKETED_CLAIM_RE = re.compile(r"\$\[[\"']([\w.]+)[\"']\]")


def _discriminator_claim_names(json_path: str) -> list[str]:
    """Extract the claim names referenced by an admin discriminator.

    Returns the (sorted) distinct root claims of every '$.name' and
    '$["name"]' reference in 'json_path'.  A dotted reference such as
    '$.realm_access.roles[0]' contributes only its root, 'realm_access',
    matching how the authn cookie carries claims.  Quoted string
    literals are stripped first:  a comparison value which itself
    contains '$.something' contributes nothing.
    """
    stripped = re.sub(r'"[^"]*"', "", json_path)

    claims = set(_DISCRIMINATOR_CLAIM_RE.findall(stripped))
    claims |= {
        match.split(".")[0] for match in _BRACKETED_CLAIM_RE.findall(stripped)
    }
    return sorted(claims)


def _claims_not_carried(
    json_paths: list[str],
    auth_system_configs,
) -> list[tuple[str, str]]:
    """Report admin discriminators claims an authn cookie won't carry.

    The admin check (see the nginx 'auth_request' check endpoint)
    evaluates stored discriminators against the claims carried by the
    authn cookie, so a discriminator whose claims are not all carried
    can never be satisfied by that auth system's users.

    Returns '(auth_system_id, claim)' pairs, in config order, listing
    every referenced claim not carried by each configured auth system
    (including always-carried claims such as 'sub':  see
    'authn.AUTHN_COOKIE_ALWAYS_CLAIMS').
    """
    referenced: set[str] = set()
    for json_path in json_paths:
        referenced.update(_discriminator_claim_names(json_path))

    not_carried: list[tuple[str, str]] = []
    for oidc_config in auth_system_configs:
        carried = set(authn.AUTHN_COOKIE_ALWAYS_CLAIMS)
        carried |= set(oidc_config.cookie_claims)
        for claim in sorted(referenced - carried):
            not_carried.append((oidc_config.id, claim))
    return not_carried


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

    not_carried = _claims_not_carried(
        json_paths,
        the_installation.oidc_auth_system_configs,
    )
    tc_print("Claims not carried in the authn cookie:")
    if not_carried:
        for the_id, claim in not_carried:
            tc_print(f"  - {the_id}: {claim}")
    else:
        tc_print("  (none)")
    tc_line()

    errors: dict = {}
    section_findings: dict = {}
    if invalid:
        section_findings["invalid_json_paths"] = invalid
    if not_carried:
        section_findings["claims_not_carried"] = not_carried
    if section_findings:
        errors["admin_users"] = section_findings
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
