import contextlib
import functools
import os
import pathlib
import sys

import fastapi
import logfire
import uvicorn
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import authn
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


def curry_lifespan(
    installation_path: pathlib.Path = None,
    no_auth_mode: bool = False,
):
    if installation_path is None:
        installation_path = os.environ.get("SOLIPLEX_INSTALLATION_PATH")

        if installation_path is None:
            installation_path = "./example"

    installation_path = pathlib.Path(installation_path)

    return functools.partial(
        installation.lifespan,
        installation_path=installation_path,
        no_auth_mode=no_auth_mode,
    )


def create_app(
    installation_path: pathlib.Path = None,
    no_auth_mode: bool = None,
):  # pragma: NO COVER
    if no_auth_mode is None:
        no_auth_mode = os.environ.get("SOLIPLEX_NO_AUTH_MODE") == "Y"

    curried_lifespan = curry_lifespan(installation_path, no_auth_mode)
    acm_lifespan = contextlib.asynccontextmanager(curried_lifespan)
    app = fastapi.FastAPI(lifespan=acm_lifespan)

    origins = ["*"]
    app.add_middleware(
        fastapi_mw_cors.CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(
        starlette_mw_sessions.SessionMiddleware,
        # Deliberately not an envvar
        secret_key=authn._get_session_secret_key(),
    )

    current_git_hash = util.get_git_hash_for_file(__file__)

    @app.middleware("http")
    async def add_custom_header(request: fastapi.Request, call_next):
        response: fastapi.Response = await call_next(request)
        response.headers["X-Git-Hash"] = current_git_hash
        return response

    app.include_router(agui_views.router, prefix="/api")
    app.include_router(authn_views.router, prefix="/api")
    app.include_router(authz_views.router, prefix="/api")
    app.include_router(completions_views.router, prefix="/api")
    app.include_router(installation_views.router, prefix="/api")
    app.include_router(quizzes_views.router, prefix="/api")
    app.include_router(rooms_views.router, prefix="/api")
    app.include_router(views.router, prefix="/api")

    # pragma: NO COVER
    # 'if-token-present' means nothing will be sent (and the example will work)
    # if you don't have logfire configured
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()
    logfire.instrument_fastapi(app, capture_headers=True)

    return app


if __name__ == "__main__":  # pragma:  NO COVER
    if sys.argv:
        installation_path = sys.argv[1]
    else:
        installation_path = None

    app = create_app(pathlib.Path(installation_path))

    uvicorn.run(app, port=8000)
