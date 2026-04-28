from __future__ import annotations

import enum
import os
import pathlib

import typer
import uvicorn
import uvicorn.config

import soliplex
from soliplex import main
from soliplex.cli import cli_util
from soliplex.cli import types


class ReloadOption(enum.StrEnum):
    CONFIG = "config"
    PYTHON = "python"
    BOTH = "both"


class LogLevelOption(enum.StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


app = typer.Typer()
the_console = cli_util.the_console

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

app_factory_name_option = typer.Option(None, hidden=True)
app_maker_option = typer.Option(None, hidden=True)


@app.command("serve")
def serve(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    no_auth_mode: bool = typer.Option(
        False,
        "--no-auth-mode",
        help="""\
Disable OIDC authentication providers

Incompatible with '--add-admin-user'.
""",
    ),
    add_admin_user: str | None = typer.Option(
        None,
        "--add-admin-user",
        help="""\
Add an admin user to the authorization database

Incompatible with '--no-auth-mode'.
""",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "-H",
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
    app_factory_name=app_factory_name_option,
    app_maker=app_maker_option,
):
    """Run the Soliplex server"""
    if no_auth_mode and (add_admin_user is not None):
        the_console.rule("Incompatible CLI arguments")
        the_console.print(
            "'--no-auth-mode' and '--add-admin-user' are incompatible."
        )
        raise typer.Exit()

    # Temporary, to permit updating logging config if not passed on CLI.
    the_installation = cli_util.get_installation(installation_path)
    i_config = the_installation._config

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
        "ws": "websockets-sansio",
    }

    if uds is not None:
        uvicorn_kw["uds"] = uds

    if fd is not None:
        uvicorn_kw["fd"] = fd

    if workers is not None:
        uvicorn_kw["workers"] = workers

    if log_level is not None:
        uvicorn_kw["log_level"] = log_level

    if log_config is not None:
        uvicorn_kw["log_config"] = str(log_config)
    elif i_config._logging_config_file is not None:
        uvicorn_kw["log_config"] = str(i_config.logging_config_file)

    if access_log is not None:
        uvicorn_kw["access_log"] = access_log

    if proxy_headers is not None:
        uvicorn_kw["proxy_headers"] = proxy_headers

    if forwarded_allow_ips is not None:
        uvicorn_kw["forwarded_allow_ips"] = forwarded_allow_ips

    reload_dirs = [str(rd) for rd in reload_dirs]

    if reload or workers:
        # Work around uvicorn's aversion to passing arguments to the app
        # factory.
        #
        # N.B.:  The environment variables set here are a private contract
        #        between this command and the
        #        'soliplex.main.create_app_from_environment'
        #        function:  do not try setting them yourself, either
        #        directly or via a '.env' file.
        os.environ["_SOLIPLEX_INSTALLATION_PATH"] = str(installation_path)

        if no_auth_mode:
            os.environ["_SOLIPLEX_NO_AUTH_MODE"] = "Y"

        if log_config is not None:  # pass to the app, disable Uvicorn.
            os.environ["_SOLIPLEX_LOG_CONFIG_FILE"] = str(log_config)

        if add_admin_user is not None:
            os.environ["_SOLIPLEX_ADD_ADMIN_USER"] = add_admin_user

        if app_factory_name is None:
            app_factory_name = "soliplex.main:create_app_from_environment"

        uvicorn.run(
            app_factory_name,
            factory=True,
            reload=reload,
            reload_dirs=reload_dirs,
            reload_includes=reload_includes,
            **uvicorn_kw,
        )
    else:
        if app_maker is None:
            app_maker = main.create_app

        app = app_maker(
            installation_path=installation_path,
            no_auth_mode=no_auth_mode,
            log_config_file=log_config,
            add_admin_user=add_admin_user,
        )
        uvicorn.run(app, **uvicorn_kw)
