from __future__ import annotations

import asyncio
import json

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


def _null_matching_admin_json_paths(
    json_paths: list[str],
) -> list[tuple[str, dict]]:
    """Collect admin discriminators matching a null-claims probe token.

    Each stored 'json_path' which 'audit_common._null_claims_match'
    flags is returned as a '(json_path, matched_token)' pair;
    predicate-driven expressions (no claim references) contribute
    nothing.
    """
    matched: list[tuple[str, dict]] = []
    for json_path in json_paths:
        probe = authz.null_claims_match(json_path)
        if probe is not None:
            matched.append((json_path, probe))
    return matched


def _unresolvable_discriminators(
    refs: dict[str, set[str]],
    auth_system_configs,
) -> list[tuple[str, list[str]]]:
    """Report discriminators 'the authn cookie' can never satisfy.

    The admin check (see the nginx 'auth_request' check endpoint)
    evaluates stored discriminators against the claims carried by the
    authn cookie, so a discriminator is satisfiable for an auth
    system's users only when that system carries every claim the
    discriminator references.

    Returns '(json_path, needs)' for every discriminator referenced in
    'refs' which NO configured auth system fully carries (with no auth
    systems configured, there are no cookies, and nothing is flagged);
    'needs' holds the discriminator's referenced claims, sorted.  These
    entries are warning-grade:  the audit prints them and no
    installation fails on their account -- bearer-token admin checks
    see full claims regardless.
    """
    if not auth_system_configs:
        return []

    unresolvable: list[tuple[str, list[str]]] = []
    for json_path, needed in sorted(refs.items()):
        for oidc_config in auth_system_configs:
            carried = set(authn.AUTHN_COOKIE_ALWAYS_CLAIMS)
            carried |= set(oidc_config.cookie_claims)
            if not (needed - carried):
                break
        else:
            unresolvable.append((json_path, sorted(needed)))
    return unresolvable


def _cookie_claims_gaps(
    refs: dict[str, set[str]],
    auth_system_configs,
) -> dict[str, list[str]]:
    """Report the claims each auth system's cookie does not carry.

    Returns, per auth system id (config order), the sorted referenced
    claims its 'cookie_claims' does not carry -- the additions which
    would let its users satisfy every stored discriminator through the
    check endpoint -- for auth systems with gaps only.  With no auth
    systems configured, there are no cookies, and nothing is flagged.
    Warning-grade, like the unresolvable-discriminator report.
    """
    if not auth_system_configs:
        return {}

    referenced: set[str] = set()
    for needed in refs.values():
        referenced.update(needed)

    gaps: dict[str, list[str]] = {}
    for oidc_config in auth_system_configs:
        carried = set(authn.AUTHN_COOKIE_ALWAYS_CLAIMS)
        carried |= set(oidc_config.cookie_claims)
        missing = sorted(referenced - carried)
        if missing:
            gaps[oidc_config.id] = missing
    return gaps


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

    null_matching = _null_matching_admin_json_paths(json_paths)
    tc_print("Admin users matching a null/empty claims token:")
    if null_matching:
        for json_path, token in null_matching:
            tc_print(
                f"  - {json_path}  (matched {json.dumps(token)})",
            )
    else:
        tc_print("  (none)")
    tc_line()

    refs = {
        json_path: set(authz.discriminator_claim_names(json_path))
        for json_path in json_paths
    }
    unresolvable = _unresolvable_discriminators(
        refs,
        the_installation.oidc_auth_system_configs,
    )
    gaps = _cookie_claims_gaps(
        refs,
        the_installation.oidc_auth_system_configs,
    )
    tc_print("Claims not carried in the authn cookie:")
    if not unresolvable and not gaps:
        tc_print("  (none)")
        tc_line()
    else:
        if unresolvable:
            tc_print(
                "  Unresolvable discriminators"
                " (no provider carries every claim):"
            )
            for json_path, needs in unresolvable:
                tc_print(f"    - {json_path}  (needs {', '.join(needs)})")
        if gaps:
            tc_print("  Gaps by auth system (referenced claims not carried):")
            for the_id, missing in gaps.items():
                tc_print(f"    - {the_id}: {', '.join(missing)}")
        tc_line()

    errors: dict = {}
    admin_user_errors: dict = {}
    if invalid:
        admin_user_errors["invalid_json_paths"] = invalid
    if null_matching:
        admin_user_errors["null_matching"] = null_matching
    if admin_user_errors:
        errors["admin_users"] = admin_user_errors
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
