from __future__ import annotations

import json
import pathlib
from importlib import metadata as importlib_metadata

import typer
import yaml

from soliplex import secrets
from soliplex import util
from soliplex.cli import admin_users
from soliplex.cli import audit
from soliplex.cli import cli_util
from soliplex.cli import ollama
from soliplex.cli import room_authz
from soliplex.cli import serve
from soliplex.cli import types
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
    _version: bool = typer.Option(
        False,
        "-v",
        "--version",
        callback=version_callback,
        help="Show version and exit",
    ),
):
    """soliplex CLI - RAG system"""


# Hidden backward-compatibility aliases
def _hidden_alias(name, func):
    the_cli.command(name=name, hidden=True)(func)


_hidden_alias("pull-models", ollama.pull_models)
_hidden_alias("check-config", audit.audit_all)
_hidden_alias("list-secrets", audit.audit_secrets)
_hidden_alias("list-environment", audit.audit_environment)
_hidden_alias("list-oidc-auth-providers", audit.audit_oidc_auth_providers)
_hidden_alias("list-rooms", audit.audit_rooms)
_hidden_alias("list-completions", audit.audit_completions)
_hidden_alias("list-skills", audit.audit_skills)
_hidden_alias("list-admin-users", admin_users.list_admin_users)
_hidden_alias("clear-admin-users", admin_users.clear_admin_users)
_hidden_alias("add-admin-user", admin_users.add_admin_user)
_hidden_alias("show-room-authz", room_authz.show_room_authz)
_hidden_alias("clear-room-authz", room_authz.clear_room_authz)
_hidden_alias("add-room-user", room_authz.add_room_user)

the_cli.add_typer(serve.app)
the_cli.add_typer(audit.app)
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


the_cli.add_typer(misc_app)

if __name__ == "__main__":
    the_cli()
