from __future__ import annotations

import code
import json
import pathlib
import sys
from importlib import metadata as importlib_metadata

import typer
import yaml

from soliplex import alembic_migrations
from soliplex import secrets
from soliplex import util
from soliplex.cli import admin_users
from soliplex.cli import ask
from soliplex.cli import audit
from soliplex.cli import cli_util
from soliplex.cli import database
from soliplex.cli import ollama
from soliplex.cli import room_authz
from soliplex.cli import serve
from soliplex.cli import types
from soliplex.cli.audit import completions as audit_completions
from soliplex.cli.audit import environment as audit_environment
from soliplex.cli.audit import oidc as audit_oidc
from soliplex.cli.audit import rooms as audit_rooms
from soliplex.cli.audit import secrets as audit_secrets
from soliplex.cli.audit import skills as audit_skills
from soliplex.config import installation as config_installation

the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)

the_console = cli_util.the_console


def version_callback(value: bool):
    if value:
        gitmeta = util.GitMetadata(pathlib.Path.cwd())
        v = importlib_metadata.version("soliplex")
        the_console.print(f"Installed soliplex version: {v}")
        the_console.print(f"Soliplex git tag          : {gitmeta.git_tag}")
        the_console.print(f"Soliplex git branch       : {gitmeta.git_branch}")
        the_console.print(f"Soliplex git hash         : {gitmeta.git_hash}")
        raise typer.Exit()


@the_cli.callback()
def app(
    ctx: typer.Context,
    _version: bool = typer.Option(
        False,
        "-v",
        "--version",
        callback=version_callback,
        help="Show version and exit",
    ),
):
    """soliplex CLI - RAG system"""
    # Hidden audit aliases (check-config, list-secrets, ...) skip the
    # audit group's _audit_callback, so ctx.obj would otherwise be None
    # when those commands try to read ctx.obj["quiet"].
    ctx.ensure_object(dict)
    ctx.obj.setdefault("quiet", False)


# Hidden backward-compatibility aliases
def _hidden_alias(name, func):
    the_cli.command(name=name, hidden=True)(func)


_hidden_alias("pull-models", ollama.pull_models)
_hidden_alias("check-config", audit.audit_all)
_hidden_alias("list-secrets", audit_secrets.audit_secrets)
_hidden_alias("list-environment", audit_environment.audit_environment)
_hidden_alias("list-oidc-auth-providers", audit_oidc.audit_oidc_auth_providers)
_hidden_alias("list-rooms", audit_rooms.audit_rooms)
_hidden_alias("list-completions", audit_completions.audit_completions)
_hidden_alias("list-skills", audit_skills.audit_skills)
_hidden_alias("list-admin-users", admin_users.list_admin_users)
_hidden_alias("clear-admin-users", admin_users.clear_admin_users)
_hidden_alias("add-admin-user", admin_users.add_admin_user)
_hidden_alias("show-room-authz", room_authz.show_room_authz)

the_cli.add_typer(serve.app)
the_cli.add_typer(ask.app)
the_cli.add_typer(audit.app)
the_cli.add_typer(database.app)
the_cli.add_typer(admin_users.app)
the_cli.add_typer(room_authz.app)
the_cli.add_typer(ollama.app)


misc_app = typer.Typer()


@misc_app.command("config")
def config_as_yaml(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Export the installation config as YAML"""
    the_installation = cli_util.get_installation(installation_path)

    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound:
        pass

    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars:
        pass

    exported_yaml = yaml.dump(
        the_installation._config.as_yaml,
        sort_keys=False,
    )

    the_console.print(f"#{'-' * 78}")
    the_console.print(f"# Source: {installation_path}")
    the_console.print(f"#{'-' * 78}")
    the_console.print(exported_yaml)


@misc_app.command("agui-feature-schemas")
def agui_feature_schemas(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Export AG-UI feature JSON schemas as JSON"""
    the_installation = cli_util.get_installation(installation_path)

    feature_schemas = {
        feature.name: {
            "source": str(feature.source),
            "json_schema": feature.json_schema,
        }
        for feature in the_installation._config.agui_features
    }

    print(json.dumps(feature_schemas))


BANNER = f"""\
Python {sys.version} on {sys.platform}
(Soliplex CLI shell)
'the_intstallation' is available for querying.
"""
EXITMSG = "Now exiting Soliplex CLI shell"


@misc_app.command("shell")
def shell(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Python REPL w/ installation configuration available"""
    the_installation = cli_util.get_installation(installation_path)
    code.interact(local=locals(), banner=BANNER, exitmsg=EXITMSG)


the_cli.add_typer(misc_app)


def main():
    """The 'soliplex-cli' console script.

    The one seam between Typer and the shell, and therefore the only place
    a 'MigrationError' can be given the presentation its own contract
    promises -- "reported without a traceback" -- for every command at
    once, including any added later. 'ask' and the 'database' group
    convert theirs before it could reach here, so this changes nothing for
    them; the 'admin-users' and 'room-authz' commands convert nothing, and
    Typer renders their refusals as tracebacks.

    Only that family is caught. Everything else still renders as it did,
    because a traceback is the right answer for a bug.

    'SystemExit', not 'typer.Exit': the latter is 'click.exceptions.Exit',
    a 'RuntimeError', which outside click's own context would print the
    very traceback this exists to remove.
    """
    try:
        the_cli()
    except alembic_migrations.MigrationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":  # pragma NO COVER
    main()
