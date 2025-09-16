import contextlib
import functools
import os
import pathlib
import sys

import fastapi
import uvicorn
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import auth
from soliplex import completions
from soliplex import installation
from soliplex import rooms
from soliplex import util
from soliplex import views


def curry_lifespan(installation_path: pathlib.Path=None):
    if installation_path is None:
        installation_path = os.environ.get("SOLIPLEX_INSTALLATION_PATH")

        if installation_path is None:
            installation_path = "./example"

    installation_path = pathlib.Path(installation_path)

    return functools.partial(
        installation.lifespan, installation_path=installation_path,
    )

def create_app(installation_path: pathlib.Path=None):  # pragma: NO COVER
    curried_lifespan = curry_lifespan(installation_path)
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
        secret_key=auth._get_session_secret_key(),
    )

    current_git_hash = util.get_git_hash_for_file(__file__)

    @app.middleware("http")
    async def add_custom_header(request: fastapi.Request, call_next):
        response: fastapi.Response = await call_next(request)
        response.headers["X-Git-Hash"] = current_git_hash
        return response

    app.include_router(auth.router, prefix="/api")
    app.include_router(completions.router, prefix="/api")
    app.include_router(installation.router, prefix="/api")
    app.include_router(rooms.router, prefix="/api")
    app.include_router(views.router, prefix="/api")

    return app


if __name__ == "__main__":  # pragma:  NO COVER
    if sys.argv:
        installation_path = sys.argv[1]
    else:
        installation_path = None

    app = create_app(pathlib.Path(installation_path))

    uvicorn.run(app, port=8000)
