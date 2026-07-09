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
from soliplex.config import middleware as config_middleware


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


def app_with_cors(app: fastapi.FastAPI, **extra_params) -> fastapi.FastAPI:
    app.add_middleware(
        fastapi_mw_cors.CORSMiddleware,
        **extra_params,
    )
    return app


def app_with_session(
    app: fastapi.FastAPI,
    *,
    installation_config: config_installation.InstallationConfig,
    same_site: str = "lax",
) -> fastapi.FastAPI:
    token = installation_config.get_secret("secret:SESSION_MIDDLEWARE_TOKEN")
    https_only = os.environ.get("_SOLIPLEX_INSECURE_SESSION_COOKIE") != "Y"
    app.add_middleware(
        starlette_mw_sessions.SessionMiddleware,
        secret_key=token.encode("ascii"),
        https_only=https_only,
        same_site=same_site,
    )
    return app


def default_middleware_stack() -> list[config_middleware.MiddlewareConfig]:
    """Return the built-in middleware stack used when config omits one.

    Ordered outermost-first: the session middleware wraps the CORS
    middleware, matching Soliplex's historical registration order.
    """
    return [
        config_middleware.MiddlewareConfig(
            name="session",
            app_factory=app_with_session,
        ),
        config_middleware.MiddlewareConfig(
            name="cors",
            app_factory=app_with_cors,
            extra_params={
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            },
        ),
    ]


def create_app(
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    log_config_file: str = None,
    curry_lifespan=None,
    app_with_lifespan=None,
    compose_middleware_stack=None,
    default_middleware_stack=None,
):
    """Construct the Soliplex FastAPI application

    Callers may override any of the component functions in this module
    via parameters.
    """
    globs = globals()

    # Create a temporary InstallationConfig, to permit us to use
    # its secrets / middleware stack before the lifespan starts.
    tmp_installation = config_installation.load_installation(
        pathlib.Path(installation_path)
    )

    curry_lifespan = curry_lifespan or globs["curry_lifespan"]
    app_with_lifespan = app_with_lifespan or globs["app_with_lifespan"]
    compose_middleware_stack = (
        compose_middleware_stack or config_middleware.compose_middleware_stack
    )
    default_middleware_stack = (
        default_middleware_stack or globs["default_middleware_stack"]
    )

    curried_lifespan = curry_lifespan(
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        log_config_file=log_config_file,
    )
    app = app_with_lifespan(curried_lifespan)

    to_compose = (
        tmp_installation.middleware_stack or default_middleware_stack()
    )
    app = compose_middleware_stack(app, tmp_installation, to_compose)

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

    return create_app(
        installation_path=installation_path,
        log_config_file=log_config_file,
        no_auth_mode=no_auth_mode,
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
