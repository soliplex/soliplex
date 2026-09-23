from __future__ import annotations

import typer
import yaml

from soliplex import installation
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common


def _load_logging_config(the_installation):
    """Return parsed Python-logging YAML, or ``None`` when none is configured.

    Raises ``yaml.YAMLError`` or ``OSError`` if the configured file cannot
    be opened or parsed.
    """
    pyl_config = the_installation._config.logging_config_file
    if pyl_config is None:
        return None
    with pyl_config.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _invalid_logging(the_installation: installation.Installation) -> dict:
    try:
        _load_logging_config(the_installation)
    except (yaml.YAMLError, OSError) as exc:
        return {"logging": str(exc)}
    return {}


def _audit_logging_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the Python-logging section (rule header + config or defaults)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Python logging")
    tc_line()

    errors = _invalid_logging(the_installation)

    pyl_config = the_installation._config.logging_config_file
    if pyl_config is None:
        tc_print("OK (defaults)")
        return errors

    tc_print(f"Logging config: {pyl_config}")
    exc = errors.get("logging")
    if exc is not None:
        tc_print(exc)
    else:
        logging_config = _load_logging_config(the_installation)
        tc_print(logging_config)
        tc_print(
            f"Headers map: {the_installation._config.logging_headers_map}",
        )
        tc_print(
            f"Claims map: {the_installation._config.logging_claims_map}",
        )
        tc_print("OK")
    return errors


def audit_logging(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Show the Python-logging config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logging_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
