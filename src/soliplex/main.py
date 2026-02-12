from __future__ import annotations

import contextlib
import functools
import os
import pathlib
import sys
import typing
import warnings

import fastapi
import uvicorn
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import config
from soliplex import haiku_chat
from soliplex import installation
from soliplex import util
from soliplex import views
from soliplex.views import agui as agui_views
from soliplex.views import authn as authn_views
from soliplex.views import authz as authz_views
from soliplex.views import completions as completions_views
from soliplex.views import installation as installation_views
from soliplex.views import log_ingest as log_ingest_views
from soliplex.views import quizzes as quizzes_views
from soliplex.views import rooms as rooms_views
from soliplex.views import streaming as streaming_views


def register_metaconfigs():
    haiku_chat.register_metaconfig()


def curry_lifespan(
    *,
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    log_config_file: str = None,
    add_admin_user: str = None,
):
    installation_path = pathlib.Path(installation_path)

    return functools.partial(
        installation.lifespan,
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        log_config_file=log_config_file,
        add_admin_user=add_admin_user,
    )


def app_with_lifespan(curried_lifespan: typing.Callable) -> fastapi.FastAPI:
    acm_lifespan = contextlib.asynccontextmanager(curried_lifespan)
    app = fastapi.FastAPI(lifespan=acm_lifespan)

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


def app_with_session(app: fastapi.FastAPI, token: str) -> fastapi.FastAPI:
    app.add_middleware(
        starlette_mw_sessions.SessionMiddleware,
        secret_key=token.encode("ascii"),
    )
    return app


the_git_metadata = None


async def add_custom_header(request: fastapi.Request, call_next):
    global the_git_metadata

    if the_git_metadata is None:
        cwd = pathlib.Path.cwd()
        the_git_metadata = util.GitMetadata(cwd)

    response: fastapi.Response = await call_next(request)
    response.headers["X-Git-Hash"] = the_git_metadata.git_hash
    return response


def app_with_git_hash(app: fastapi.FastAPI) -> fastapi.FastAPI:
    # The direct caller is likely 'create_app' below: use 'stacklevel=3'
    # to get *its* caller.
    warnings.warn(
        "'soliplex.main.app_with_git_hash' is deprecated, and will be "
        "removed after version 0.43.",
        DeprecationWarning,
        stacklevel=3,
    )
    app.middleware("http")(add_custom_header)

    return app


def app_with_soliplex_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(agui_views.router, prefix="/api")
    app.include_router(authn_views.router, prefix="/api")
    app.include_router(authz_views.router, prefix="/api")
    app.include_router(completions_views.router, prefix="/api")
    app.include_router(installation_views.router, prefix="/api")
    app.include_router(log_ingest_views.router, prefix="/api")
    app.include_router(quizzes_views.router, prefix="/api")
    app.include_router(rooms_views.router, prefix="/api")
    app.include_router(streaming_views.router, prefix="/api")
    app.include_router(views.router, prefix="/api")

    return app


def create_app(
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    log_config_file: str = None,
    add_admin_user: str = None,
    register_metaconfigs=None,
    curry_lifespan=None,
    app_with_lifespan=None,
    app_with_cors=None,
    app_with_session=None,
    app_with_git_hash=None,  # deprecated
    app_with_soliplex_routers=None,
):
    """Construct the Soliplex FastAPI application

    Callers may override any of the component functions in this module
    via parameters.
    """
    globs = globals()

    register_metaconfigs = (
        register_metaconfigs or globs["register_metaconfigs"]
    )
    curry_lifespan = curry_lifespan or globs["curry_lifespan"]
    app_with_lifespan = app_with_lifespan or globs["app_with_lifespan"]
    app_with_cors = app_with_cors or globs["app_with_cors"]
    app_with_session = app_with_session or globs["app_with_session"]
    app_with_soliplex_routers = (
        app_with_soliplex_routers or globs["app_with_soliplex_routers"]
    )

    # Create a temporary InstallationConfig, to permit us to use
    # its secrets before the lifespan starts.
    tmp_installation = config.load_installation(
        pathlib.Path(installation_path)
    )

    register_metaconfigs()

    curried_lifespan = curry_lifespan(
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        log_config_file=log_config_file,
        add_admin_user=add_admin_user,
    )
    app = app_with_lifespan(curried_lifespan)
    app = app_with_cors(app)

    session_token = tmp_installation.get_secret(
        "secret:SESSION_MIDDLEWARE_TOKEN"
    )
    app = app_with_session(app, session_token)

    if app_with_git_hash is not None:
        app = app_with_git_hash(app)

    app = app_with_soliplex_routers(app)

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
    add_admin_user = os.environ.get("_SOLIPLEX_ADD_ADMIN_USER")

    return create_app(
        installation_path=installation_path,
        log_config_file=log_config_file,
        no_auth_mode=no_auth_mode,
        add_admin_user=add_admin_user,
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
