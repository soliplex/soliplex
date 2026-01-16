import enum
import json
import os
import pathlib
import typing
from importlib.metadata import version

import typer
import uvicorn
import uvicorn.config
import yaml
from rich import console

import soliplex
from soliplex import config
from soliplex import installation
from soliplex import main
from soliplex import models
from soliplex import ollama
from soliplex import secrets


class ReloadOption(str, enum.Enum):
    CONFIG = "config"
    PYTHON = "python"
    BOTH = "both"


class LogLevelOption(str, enum.Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    no_args_is_help=True,
    add_completion=False,
)

the_console = console.Console()


def version_callback(value: bool):
    if value:
        v = version("soliplex")
        the_console.print(f"soliplex version {v}")
        raise typer.Exit()


installation_path_type = typing.Annotated[
    pathlib.Path,
    typer.Argument(
        envvar="SOLIPLEX_INSTALLATION_PATH",
        help="Soliplex installation path",
    ),
]


def get_installation(
    installation_path: pathlib.Path,
) -> installation.Installation:
    if installation_path.is_dir():
        installation_path = installation_path / "installation.yaml"
    i_config = config.load_installation(installation_path)
    i_config.reload_configurations()
    return installation.Installation(i_config)


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


reload_option: ReloadOption = typer.Option(
    None,
    "-r",
    "--reload",
    help="Reload on file changes",
)


reload_dirs_option: list[pathlib.Path] = typer.Option(
    [],
    "--reload-dirs",
    help="Additional directories to be monitored for reload",
)


reload_includes_option: list[str] = typer.Option(
    [],
    "--reload-includes",
    help="Additional glob patterns for files to be montored for reload",
)


log_config_option: pathlib.Path = typer.Option(
    None,
    "--log-config",
    help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
)


log_level_option: LogLevelOption = typer.Option(
    None, "--log-level", help="Log level"
)


@the_cli.command(
    "serve",
)
def serve(
    ctx: typer.Context,
    installation_path: installation_path_type,
    no_auth_mode: bool = typer.Option(
        False,
        "--no-auth-mode",
        help="Disable OIDC authentication providers",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "-h",
        "--host",
        help="Bind socket to this host",
    ),
    port: int = typer.Option(
        8000,
        "-p",
        "--port",
        help="Port number",
    ),
    uds: str = typer.Option(
        None,
        "--uds",
        help="Bind to a Unix domain socket",
    ),
    fd: int = typer.Option(
        None,
        "--fd",
        help="Bind to socket from this file descriptor",
    ),
    reload: ReloadOption = reload_option,
    reload_dirs: list[pathlib.Path] = reload_dirs_option,
    reload_includes: list[str] = reload_includes_option,
    workers: int = typer.Option(
        None,
        "--workers",
        envvar="WEB_CONCURRENCY",
        help="Number of worker processes. Defaults to the "
        "$WEB_CONCURRENCY environment variable if available, or 1. "
        "Not valid with --reload.",
    ),
    log_config: pathlib.Path = log_config_option,
    log_level: LogLevelOption = log_level_option,
    access_log: bool | None = typer.Option(
        None,
        "--access-log",
        help="Enable/Disable access log",
    ),
    proxy_headers: bool = typer.Option(
        None,
        "--proxy-headers",
        help="Enable/Disable X-Forwarded-Proto, X-Forwarded-For "
        "to populate url scheme and remote address info.",
    ),
    forwarded_allow_ips: str = typer.Option(
        None,
        "--forwarded-allow-ips",
        envvar="FORWARDED_ALLOW_IPS",
        help="Comma separated list of IP Addresses, IP Networks, or "
        "literals (e.g. UNIX Socket path) to trust with proxy headers. "
        "Defaults to the $FORWARDED_ALLOW_IPS environment "
        "variable if available, or '127.0.0.1'. "
        "The literal '*' means trust everything.",
    ),
):
    """Run the Soliplex server"""
    if reload in (ReloadOption.PYTHON, ReloadOption.BOTH):
        reload_dirs.extend(soliplex.__path__)

    if reload in (ReloadOption.CONFIG, ReloadOption.BOTH):
        if installation_path.is_dir():
            reload_dirs.append(installation_path)
        else:
            reload_dirs.append(installation_path.parent)

        reload_includes.append("*.yaml")
        reload_includes.append("*.yml")
        reload_includes.append("*.txt")

    uvicorn_kw = {
        "host": host,
        "port": port,
    }

    if uds is not None:
        uvicorn_kw["uds"] = uds

    if fd is not None:
        uvicorn_kw["fd"] = fd

    if workers is not None:
        uvicorn_kw["workers"] = workers

    if log_config is not None:
        uvicorn_kw["log_config"] = log_config

    if log_level is not None:
        uvicorn_kw["log_level"] = log_level

    if access_log is not None:
        uvicorn_kw["access_log"] = access_log

    if proxy_headers is not None:
        uvicorn_kw["proxy_headers"] = proxy_headers

    if forwarded_allow_ips is not None:
        uvicorn_kw["forwarded_allow_ips"] = forwarded_allow_ips

    reload_dirs = [str(rd) for rd in reload_dirs]

    if reload or workers:
        os.environ["SOLIPLEX_INSTALLATION_PATH"] = str(installation_path)

        if no_auth_mode:
            os.environ["SOLIPLEX_NO_AUTH_MODE"] = "Y"

        uvicorn.run(
            "soliplex.main:create_app",
            factory=True,
            reload=reload,
            reload_dirs=reload_dirs,
            reload_includes=reload_includes,
            **uvicorn_kw,
        )
    else:
        app = main.create_app(installation_path, no_auth_mode=no_auth_mode)
        uvicorn.run(app, **uvicorn_kw)


@the_cli.command(
    "check-config",
)
def check_config(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Check that secrets / env vars can be resolved"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Checking secrets")
    the_console.line()
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        the_console.print("Missing secrets")
        for secret_name in exc.secret_names.split(","):
            the_console.print(f"- {secret_name}")
    else:
        the_console.print("OK")

    the_console.line()
    the_console.rule("Checking environment")
    the_console.line()
    try:
        the_installation.resolve_environment()
    except config.MissingEnvVars as exc:
        the_console.line()
        the_console.print("Missing environment variables")
        for env_var in exc.env_vars.split(","):
            the_console.print(f"- {env_var}")
    else:
        the_console.print("OK")

    # Check that conversion to models doesn't raise
    the_console.line()
    the_console.rule("Validating installation model")
    the_console.line()
    try:
        models.Installation.from_config(the_installation._config)
    except Exception as exc:
        the_console.print(exc)
    else:
        the_console.print("OK")

    the_console.line()
    the_console.rule("Validating room models")
    the_console.line()
    room_configs = the_installation._config.room_configs
    for room_config in room_configs.values():
        the_console.print(f"Room: {room_config.id}")
        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            the_console.print(exc)
        else:
            the_console.print("OK")
        the_console.line()

    the_console.line()
    the_console.rule("Validating completion models")
    the_console.line()
    completion_configs = the_installation._config.completion_configs

    for compl_config in completion_configs.values():
        the_console.print(f"Completion: {compl_config.id}")
        try:
            models.Completion.from_config(compl_config)
        except Exception as exc:
            the_console.print(exc)
        else:
            the_console.print("OK")
        the_console.line()


@the_cli.command(
    "list-secrets",
)
def list_secrets(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List secrets defined in the installation"""
    the_installation = get_installation(installation_path)
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = set(exc.secret_names.split(","))
    else:
        missing = set()

    the_console.line()
    the_console.rule("Configured secrets")
    the_console.line()

    for secret_config in the_installation._config.secrets:
        flag = "MISSING" if secret_config.secret_name in missing else "OK"
        the_console.print(f"- {secret_config.secret_name:25} {flag}")

    the_console.print()


@the_cli.command(
    "list-environment",
)
def list_environment(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List environment variables defined in the installation"""
    the_installation = get_installation(installation_path)
    try:
        the_installation.resolve_environment()
    except config.MissingEnvVars as exc:
        missing = set(exc.env_vars.split(","))
    else:
        missing = set()

    the_console.line()
    the_console.rule("Configured environment variables")
    the_console.line()

    for key, value in the_installation._config.environment.items():
        if key in missing:
            value = "MISSING"

        the_console.print(f"- {key:25}: {value}")

    the_console.print()


@the_cli.command(
    "list-oidc-auth-providers",
)
def list_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured OIDC Auth Providers")
    the_console.line()

    for oidc_config in the_installation.oidc_auth_system_configs:
        the_console.print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        the_console.print(f"  {oidc_config.server_url}")
        the_console.line()


@the_cli.command(
    "list-rooms",
)
def list_rooms(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List rooms defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured Rooms")
    the_console.line()

    for room_config in the_installation.get_room_configs(None).values():
        the_console.print(f"- [ {room_config.id} ] {room_config.name}: ")
        the_console.print(f"  {room_config.description}")
        the_console.line()


@the_cli.command(
    "list-completions",
)
def list_completions(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List completions defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured Completions")
    the_console.line()

    for compl_config in the_installation.get_completion_configs(None).values():
        the_console.print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        the_console.line()


@the_cli.command(
    "config",
)
def config_as_yaml(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Export the installatin config as YAML"""
    the_installation = get_installation(installation_path)

    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound:
        pass

    try:
        the_installation.resolve_environment()
    except config.MissingEnvVars:
        pass

    exported_yaml = yaml.dump(
        the_installation._config.as_yaml,
        sort_keys=False,
    )

    the_console.print(f"#{'-' * 78}")
    the_console.print(f"# Source: {installation_path}")
    the_console.print(f"#{'-' * 78}")
    the_console.print(exported_yaml)


@the_cli.command(
    "agui-feature-schemas",
)
def agui_feature_schemas(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Export the installatin config as YAML"""
    the_installation = get_installation(installation_path)

    feature_schemas = {
        feature.name: {
            "source": str(feature.source),
            "json_schema": feature.json_schema,
        }
        for feature in the_installation._config.agui_features
    }

    print(json.dumps(feature_schemas))


@the_cli.command(
    "pull-models",
)
def pull_models(
    ctx: typer.Context,
    installation_path: installation_path_type,
    ollama_url: str = typer.Option(
        os.environ.get("OLLAMA_BASE_URL", ollama.DEFAULT_OLLAMA_URL),
        "-u",
        "--ollama-url",
        help="Ollama API base URL (default: $OLLAMA_BASE_URL or "
        f"{ollama.DEFAULT_OLLAMA_URL})",
    ),
    dry_run: bool = typer.Option(
        False,
        "-n",
        "--dry-run",
        help="Show which models would be pulled without actually pulling them",
    ),
):
    """Pull Ollama models referenced in the installation configuration"""
    the_console.line()
    the_console.rule("Scanning for Ollama models")
    the_console.line()

    the_installation = get_installation(installation_path)
    models = the_installation.get_all_models()

    if not models:
        the_console.print("No Ollama models found in configuration files.")
        return

    the_console.line()
    the_console.rule(f"Found {len(models)} unique Ollama model(s)")
    the_console.line()
    for model in sorted(models):
        the_console.print(f"  - {model}")

    if dry_run:
        return

    the_console.line()
    the_console.rule(f"Pulling models from {ollama_url}")

    def on_status(msg, is_error=False):
        style = "red" if is_error else None
        the_console.print(f"  {msg}", style=style)

    success_count = 0
    for model in sorted(models):
        the_console.print(f"\nPulling: {model}")
        if ollama.pull_model(model, ollama_url, on_status=on_status):
            success_count += 1

    the_console.line()
    msg = f"Pulled {success_count}/{len(models)} model(s) successfully"
    the_console.rule(msg)
    the_console.line()


if __name__ == "__main__":
    the_cli()
