from __future__ import annotations

import typer

from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation


def _audit_logfire_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the Logfire section (rule header + config or defaults)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Logfire")
    tc_line()

    l_config = the_installation._config.logfire_config
    if l_config is not None:
        tc_print(l_config.as_yaml)
        tc_print("OK")
    else:
        tc_print("OK (defaults)")

    errors = audit_interpolation._invalid_logfire_interpolations(
        the_installation
    )
    audit_interpolation._print_interpolation_findings(tc_print, errors)

    return errors


def audit_logfire(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Show the Logfire config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logfire_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
