from __future__ import annotations

import textwrap

import typer

from soliplex import installation
from soliplex import models
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation


def _invalid_installation(
    the_installation: installation.Installation,
) -> dict:
    errors = {}

    try:
        models.Installation.from_config(the_installation._config)
    except Exception as exc:
        errors["installation_model"] = str(exc)

    return errors


def _config_warnings(records) -> dict:
    """Return a finding for each warning recorded while loading the config.

    ``records`` holds the ``warnings.WarningMessage`` instances which
    '_common._get_installation' records.
    """
    findings = [
        {
            "category": record.category.__name__,
            "message": str(record.message),
        }
        for record in records
    ]

    if findings:
        return {"config_warnings": findings}

    return {}


def _audit_installation_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the installation-model section (rule header + OK/ERROR)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured installation model")
    tc_line()

    errors = _invalid_installation(the_installation)
    exc = errors.get("installation_model")
    if exc:
        tc_print(f"ERROR: {exc}")
    else:
        tc_print("OK")

    warning_errors = _config_warnings(ctx.obj.get("config_warnings", ()))
    for finding in warning_errors.get("config_warnings", ()):
        tc_print()
        tc_print(f"WARNING: {finding['category']}")
        tc_print(textwrap.indent(finding["message"].rstrip(), "  "))

    interpolation_errors = (
        audit_interpolation._invalid_installation_interpolations(
            the_installation,
        )
    )
    audit_interpolation._print_interpolation_findings(
        tc_print, interpolation_errors
    )

    return errors | warning_errors | interpolation_errors


def audit_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """Check that the installation config renders as a model"""
    quiet = ctx.obj["quiet"]
    errors = _audit_installation_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
