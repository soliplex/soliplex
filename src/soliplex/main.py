from __future__ import annotations

import contextlib
import functools
import pathlib
import sys
import typing

import fastapi
import uvicorn
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import authn
from soliplex import haiku_chat
from soliplex import installation
from soliplex import util
from soliplex import views
from soliplex.views import agui as agui_views
from soliplex.views import authn as authn_views
from soliplex.views import authz as authz_views
from soliplex.views import completions as completions_views
from soliplex.views import installation as installation_views
from soliplex.views import quizzes as quizzes_views
from soliplex.views import rooms as rooms_views
from soliplex.views import streaming as streaming_views


def register_metaconfigs():
    haiku_chat.register_metaconfig()


def curry_lifespan(
    *,
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    add_admin_user: str = None,
):
    installation_path = pathlib.Path(installation_path)

    return functools.partial(
        installation.lifespan,
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
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


def app_with_session(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.add_middleware(
        starlette_mw_sessions.SessionMiddleware,
        # Deliberately not an envvar
        secret_key=authn._get_session_secret_key(),
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
    app.middleware("http")(add_custom_header)

    return app


def app_with_soliplex_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(agui_views.router, prefix="/api")
    app.include_router(authn_views.router, prefix="/api")
    app.include_router(authz_views.router, prefix="/api")
    app.include_router(completions_views.router, prefix="/api")
    app.include_router(installation_views.router, prefix="/api")
    app.include_router(quizzes_views.router, prefix="/api")
    app.include_router(rooms_views.router, prefix="/api")
    app.include_router(streaming_views.router, prefix="/api")
    app.include_router(views.router, prefix="/api")

    return app


def create_app(
    installation_path: pathlib.Path,
    no_auth_mode: bool,
    add_admin_user: str = None,
    register_metaconfigs=register_metaconfigs,
    curry_lifespan=curry_lifespan,
    app_with_lifespan=app_with_lifespan,
    app_with_cors=app_with_cors,
    app_with_session=app_with_session,
    app_with_git_hash=app_with_git_hash,
    app_with_soliplex_routers=app_with_soliplex_routers,
):  # pragma: NO COVER
    """Construct the Soliplex FastAPI application

    Callers may override any of the component functions in this module
    via parameters.
    """
    register_metaconfigs()

    curried_lifespan = curry_lifespan(
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
        add_admin_user=add_admin_user,
    )
    app = app_with_lifespan(curried_lifespan)
    app = app_with_cors(app)
    app = app_with_session(app)
    app = app_with_git_hash(app)
    app = app_with_soliplex_routers(app)

    return app


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
