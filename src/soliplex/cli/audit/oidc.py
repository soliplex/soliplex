from __future__ import annotations

import typer

from soliplex import installation
from soliplex import models
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation


def _invalid_oidc_auth_providers(
    the_installation: installation.Installation,
) -> dict:
    errors = {}

    for oidc_config in the_installation.oidc_auth_system_configs:
        try:
            models.OIDCAuthSystem.from_config(oidc_config)
        except Exception as exc:
            errors.setdefault("oidc", {})[oidc_config.id] = str(exc)

    return errors


def _audit_oidc_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the OIDC section (rule header + per-provider listing)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured OIDC authentication systems")
    tc_line()

    errors = _invalid_oidc_auth_providers(the_installation)
    invalid_providers = errors.get("oidc", {})

    for oidc_config in the_installation.oidc_auth_system_configs:
        tc_print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        tc_print(f"  {oidc_config.server_url}")
        exc = invalid_providers.get(oidc_config.id)
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        tc_line()

    interpolation_errors = audit_interpolation._invalid_oidc_interpolations(
        the_installation
    )
    audit_interpolation._print_interpolation_findings(
        tc_print, interpolation_errors
    )

    return errors | interpolation_errors


def audit_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List OIDC Auth Providers defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_oidc_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
