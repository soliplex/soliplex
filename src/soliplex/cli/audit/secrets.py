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


def _secret_status(secret_config, missing_names: set[str]) -> str:
    """Return the audit status for a secret, after resolution

    A resolved secret's status names the kind of the source which
    resolved it, e.g. 'OK (env_var)'.
    """
    if secret_config.secret_name in missing_names:
        return "MISSING"

    return f"OK ({secret_config.resolved_by.kind})"


def _ephemeral_secrets(the_installation: installation.Installation) -> list:
    """Return the names of secrets resolved from a 'random_chars' source"""
    return [
        secret_config.secret_name
        for secret_config in the_installation._config.secrets
        if secret_config.is_ephemeral
    ]


_EPHEMERAL_SECRETS_WARNING = """
WARNING: secrets resolved from a 'random_chars' source have values which
change whenever the server restarts / reloads, and differ between server
processes.
"""


def _audit_secrets_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the secrets section (rule header + per-secret OK/MISSING).

    Secrets resolved from a 'random_chars' source are warning-grade:
    the audit prints them, and no installation fails on their account.
    """
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured secrets")
    tc_line()

    errors = _missing_secrets(the_installation)
    missing_names = set(errors.get("missing_secrets", ()))

    for secret_config in the_installation._config.secrets:
        status = _secret_status(secret_config, missing_names)
        tc_print(f"- {secret_config.secret_name:25} {status}")

    ephemeral = _ephemeral_secrets(the_installation)
    if ephemeral:
        tc_print(_EPHEMERAL_SECRETS_WARNING)

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
