from __future__ import annotations

import typer

from soliplex import installation
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.config import installation as config_installation


def _missing_env_vars(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        return {"missing_env_vars": exc.failed}
    return {}


def _audit_environment_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    *,
    verbose: bool = False,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the environment section (rule header + per-var listing)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured environment")
    tc_line()

    errors = _missing_env_vars(the_installation)
    missing = set(errors.get("missing_env_vars", ()))

    for key, value in the_installation._config.environment.items():
        if key in missing:
            value = "MISSING"

        tc_print(f"- {key:25}: {value}")

        if verbose:
            for i_source, source in enumerate(
                the_installation.get_environment_sources(key)
            ):
                mark = " " if i_source else "*"
                tc_print(
                    f"  {mark}{str(source.source_type):24}: {source.value}"
                )

        tc_print()

    tc_print()
    return errors


def audit_environment(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="""\
Show available sources, and which is selected.
""",
    ),
):  # pragma NO COVER command
    """List environment variables defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_environment_section(
        ctx,
        installation_path,
        verbose=verbose,
    )
    audit_common._emit_errors(errors, quiet)
