from __future__ import annotations

import typer

from soliplex import installation
from soliplex import models
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import interpolation as audit_interpolation
from soliplex.cli.audit import non_local_paths as audit_non_local


def _invalid_completions(
    the_installation: installation.Installation,
    non_local_prompt_ids: set,
) -> dict:
    """Check that each completion config renders as a model

    Skips the completions named in 'non_local_prompt_ids'.
    """
    errors = {}

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs

    for compl_config in available_completions.values():
        if compl_config.id in non_local_prompt_ids:
            continue

        try:
            models.Completion.from_config(compl_config)
        except Exception as exc:
            errors.setdefault("completions", {})[compl_config.id] = str(exc)

    return errors


def _audit_completions_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the completions section (rule header + per-completion entry)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured completions")
    tc_line()

    reports = audit_non_local._non_local_path_reports(ctx, the_installation)
    non_local_errors = audit_non_local._non_local_path_findings(
        reports, audit_non_local.COMPLETIONS
    )
    non_local_completions = reports[audit_non_local.COMPLETIONS]

    errors = _invalid_completions(
        the_installation,
        audit_non_local._non_local_prompt_ids(
            reports, audit_non_local.COMPLETIONS
        ),
    )
    invalid_completions = errors.get("completions", {})

    available_completions = the_installation._config.completion_configs
    for compl_config in available_completions.values():
        tc_print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        exc = invalid_completions.get(compl_config.id)
        non_local = non_local_completions.get(compl_config.id, {})
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        audit_non_local._print_non_local_path_findings(
            tc_print,
            non_local,
            "  ",
        )
        if exc is None and not non_local:
            tc_print("  OK")
        tc_line()

    interpolation_errors = (
        audit_interpolation._invalid_completion_interpolations(
            the_installation
        )
    )
    audit_interpolation._print_interpolation_findings(
        tc_print, interpolation_errors
    )

    return errors | non_local_errors | interpolation_errors


def audit_completions(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List completions defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_completions_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
