from __future__ import annotations

import contextlib
import functools
import os
import pathlib
import sys
import typing

import fastapi
import uvicorn
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import installation
from soliplex.config import installation as config_installation


def curry_lifespan(
    *,
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    log_config_file: str = None,
):
    installation_path = pathlib.Path(installation_path)

    return functools.partial(
        installation.lifespan,
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        log_config_file=log_config_file,
    )


def app_with_lifespan(curried_lifespan: typing.Callable) -> fastapi.FastAPI:
    acm_lifespan = contextlib.asynccontextmanager(curried_lifespan)
    app = fastapi.FastAPI(lifespan=acm_lifespan)
    app.state.agui_background_tasks = set()

    return app


def app_with_cors(app: fastapi.FastAPI) -> fastapi.FastAPI:
    origins = ["*"]
    app.add_middleware(
        fastapi_mw_cors.CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


def app_with_session(
    app: fastapi.FastAPI,
    token: str,
    *,
    https_only: bool = True,
    same_site: str = "lax",
) -> fastapi.FastAPI:
    app.add_middleware(
        starlette_mw_sessions.SessionMiddleware,
        secret_key=token.encode("ascii"),
        https_only=https_only,
        same_site=same_site,
    )
    return app


def create_app(
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    log_config_file: str = None,
    session_https_only: bool = True,
    curry_lifespan=None,
    app_with_lifespan=None,
    app_with_cors=None,
    app_with_session=None,
):
    """Construct the Soliplex FastAPI application

    Callers may override any of the component functions in this module
    via parameters.
    """
    globs = globals()

    # Create a temporary InstallationConfig, to permit us to use
    # its secrets before the lifespan starts.
    tmp_installation = config_installation.load_installation(
        pathlib.Path(installation_path)
    )

    curry_lifespan = curry_lifespan or globs["curry_lifespan"]
    app_with_lifespan = app_with_lifespan or globs["app_with_lifespan"]
    app_with_cors = app_with_cors or globs["app_with_cors"]
    app_with_session = app_with_session or globs["app_with_session"]

    curried_lifespan = curry_lifespan(
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        log_config_file=log_config_file,
    )
    app = app_with_lifespan(curried_lifespan)
    app = app_with_cors(app)

    session_token = tmp_installation.get_secret(
        "secret:SESSION_MIDDLEWARE_TOKEN"
    )
    app = app_with_session(app, session_token, https_only=session_https_only)

    return app


def create_app_from_environment():
    """Work around uvicorn's aversion to passing arguments to the app factory

    N.B.:  The environment variables set here are a private contract between
           the 'soliplex-cli serve' command and this function:  do not
           try setting them yourself, either directly or via a '.env' file.
    """
    installation_path_str = os.environ["_SOLIPLEX_INSTALLATION_PATH"]
    installation_path = pathlib.Path(installation_path_str)
    no_auth_mode = os.environ.get("_SOLIPLEX_NO_AUTH_MODE") == "Y"
    log_config_file = os.environ.get("_SOLIPLEX_LOG_CONFIG_FILE")
    session_https_only = (
        os.environ.get("_SOLIPLEX_INSECURE_SESSION_COOKIE") != "Y"
    )

    return create_app(
        installation_path=installation_path,
        log_config_file=log_config_file,
        no_auth_mode=no_auth_mode,
        session_https_only=session_https_only,
    )


if __name__ == "__main__":  # pragma:  NO COVER
    args = sys.argv[1:]

    no_auth_mode = "--no-auth-mode" in args

    if no_auth_mode:
        args.remove("--no-auth-mode")

    if args:
        installation_path = args[0]
    else:
        installation_path = "example/minimal.yaml"

    app = create_app(
        installation_path=pathlib.Path(installation_path),
        no_auth_mode=no_auth_mode,
    )

    uvicorn.run(app, port=8000)
