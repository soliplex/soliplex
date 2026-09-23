from __future__ import annotations

import pathlib

import typer
from typer import core as typer_core

from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common
from soliplex.cli.audit import admin_users as audit_admin_users
from soliplex.cli.audit import completions as audit_completions
from soliplex.cli.audit import databases as audit_databases
from soliplex.cli.audit import environment as audit_environment
from soliplex.cli.audit import installation as audit_installation
from soliplex.cli.audit import logfire as audit_logfire
from soliplex.cli.audit import logging as audit_logging
from soliplex.cli.audit import oidc as audit_oidc
from soliplex.cli.audit import ollama as audit_ollama
from soliplex.cli.audit import quizzes as audit_quizzes
from soliplex.cli.audit import room_authz as audit_room_authz
from soliplex.cli.audit import rooms as audit_rooms
from soliplex.cli.audit import secrets as audit_secrets
from soliplex.cli.audit import skills as audit_skills

AUDIT_HELP = "Audit a Soliplex installation configuration"


_QUIET_OPTION = typer.Option(
    False,
    "-q",
    "--quiet",
    help="Show only errors",
)


class _AuditGroup(typer_core.TyperGroup):
    """Default to the 'all' subcommand when none is given.

    Allows 'soliplex-cli audit', 'soliplex-cli audit -q', and
    'soliplex-cli audit <path>' as shorthands for the corresponding
    'soliplex-cli audit all ...' invocation. The path-less forms rely
    on Typer's ``SOLIPLEX_INSTALLATION_PATH`` envvar fallback on
    'audit all'.
    """

    def parse_args(self, ctx, args):
        for i, token in enumerate(args):
            if token.startswith("-"):
                continue
            if token not in self.commands:
                args = [*args[:i], "all", *args[i:]]
            break
        else:
            args = [*args, "all"]
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="audit",
    help=AUDIT_HELP,
    cls=_AuditGroup,
)


@app.callback()
def _audit_callback(
    ctx: typer.Context,
    quiet: bool = _QUIET_OPTION,
    cli_log_config: pathlib.Path | None = cli_util.CLI_LOG_CONFIG_OPTION,
):
    cli_util._configure_cli_logging(cli_log_config)
    ctx.obj = {"quiet": quiet}


@app.command(
    "all",
    help=AUDIT_HELP,
)
def audit_all(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    quiet = ctx.obj["quiet"]
    errors: dict = {}

    errors |= audit_installation._audit_installation_section(
        ctx, installation_path
    )
    errors |= audit_secrets._audit_secrets_section(ctx, installation_path)
    errors |= audit_environment._audit_environment_section(
        ctx, installation_path
    )
    errors |= audit_oidc._audit_oidc_section(ctx, installation_path)
    errors |= audit_rooms._audit_rooms_section(ctx, installation_path)
    errors |= audit_databases._audit_databases_section(ctx, installation_path)
    errors |= audit_admin_users._audit_admin_users_section(
        ctx, installation_path
    )
    errors |= audit_room_authz._audit_room_authz_section(
        ctx, installation_path
    )
    errors |= audit_completions._audit_completions_section(
        ctx, installation_path
    )
    errors |= audit_quizzes._audit_quizzes_section(ctx, installation_path)
    errors |= audit_skills._audit_skills_section(ctx, installation_path)
    errors |= audit_logging._audit_logging_section(ctx, installation_path)
    errors |= audit_logfire._audit_logfire_section(ctx, installation_path)
    errors |= audit_ollama._audit_ollama_section(ctx, installation_path)

    audit_common._emit_errors(errors, quiet)


app.command("installation")(audit_installation.audit_installation)
app.command("secrets")(audit_secrets.audit_secrets)
app.command("environment")(audit_environment.audit_environment)
app.command("oidc")(audit_oidc.audit_oidc_auth_providers)
app.command("rooms")(audit_rooms.audit_rooms)
app.command("databases")(audit_databases.audit_databases)
app.command("admin-users")(audit_admin_users.audit_admin_users)
app.command("room-authz")(audit_room_authz.audit_room_authz)
app.command("completions")(audit_completions.audit_completions)
app.command("quizzes")(audit_quizzes.audit_quizzes)
app.command("skills")(audit_skills.audit_skills)
app.command("logging")(audit_logging.audit_logging)
app.command("logfire")(audit_logfire.audit_logfire)
app.command("ollama")(audit_ollama.audit_ollama)
