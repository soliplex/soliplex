from __future__ import annotations

import typer

from soliplex import installation
from soliplex import secrets
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common


def _missing_secrets(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = exc.secret_names.split(",")
        return {"missing_secrets": missing}
    return {}


def _audit_secrets_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the secrets section (rule header + per-secret OK/MISSING)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured secrets")
    tc_line()

    errors = _missing_secrets(the_installation)
    missing_names = set(errors.get("missing_secrets", ()))

    for secret_config in the_installation._config.secrets:
        flag = (
            "MISSING" if secret_config.secret_name in missing_names else "OK"
        )
        tc_print(f"- {secret_config.secret_name:25} {flag}")

    tc_print()
    return errors


def audit_secrets(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List secrets defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_secrets_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
