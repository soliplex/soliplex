import functools
import pathlib
from unittest import mock

import pytest
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import main
from soliplex.views import agui as agui_views
from soliplex.views import authn as authn_views
from soliplex.views import authz as authz_views
from soliplex.views import completions as completions_views
from soliplex.views import installation as installation_views
from soliplex.views import quizzes as quizzes_views
from soliplex.views import rooms as rooms_views

EXPLICIT_INST_PATH = "/explicit"
ENVIRON_INST_PATH = "/environ"


@pytest.fixture(scope="module", params=[False, True])
def no_auth_mode_kwargs(request):
    kw = {"no_auth_mode": request.param}
    return kw


def test_curry_lifespan(no_auth_mode_kwargs):
    exp_path = EXPLICIT_INST_PATH
    exp_no_auth_mode = no_auth_mode_kwargs["no_auth_mode"]

    found = main.curry_lifespan(
        installation_path=EXPLICIT_INST_PATH,
        **no_auth_mode_kwargs,
    )

    assert isinstance(found, functools.partial)

    assert found.keywords == {
        "installation_path": pathlib.Path(exp_path),
        "no_auth_mode": exp_no_auth_mode,
    }


@mock.patch("fastapi.FastAPI")
@mock.patch("contextlib.asynccontextmanager")
def test_app_with_lifespan(acm, fapi):
    lifespan = mock.Mock(spec_set=())

    found = main.app_with_lifespan(lifespan)

    assert found is fapi.return_value

    fapi.assert_called_once_with(lifespan=acm.return_value)
    acm.assert_called_once_with(lifespan)


def test_app_with_cors():
    app = mock.Mock(spec_set=["add_middleware"])

    found = main.app_with_cors(app)

    assert found is app

    app.add_middleware.assert_called_once_with(
        fastapi_mw_cors.CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@mock.patch("soliplex.main.authn")
def test_app_with_session(authn):
    app = mock.Mock(spec_set=["add_middleware"])

    found = main.app_with_session(app)

    assert found is app

    app.add_middleware.assert_called_once_with(
        starlette_mw_sessions.SessionMiddleware,
        secret_key=authn._get_session_secret_key.return_value,
    )

    authn._get_session_secret_key.assert_called_once_with()


@pytest.mark.anyio
@pytest.mark.parametrize("hash_patch", [{}, {"current_git_hash": "DEADBEEF"}])
@mock.patch("soliplex.main.util")
async def test_add_custom_header(util, hash_patch):
    if hash_patch:
        exp_hash = "DEADBEEF"
    else:
        exp_hash = util.get_git_hash_for_file.return_value

    request = object()
    call_next = mock.AsyncMock(spec_set=())
    exp_response = call_next.return_value = mock.Mock(
        spec_set=["headers"],
        headers={},
    )

    with mock.patch.dict("soliplex.main.__dict__", **hash_patch):
        response = await main.add_custom_header(request, call_next)

    assert response is exp_response
    assert response.headers["X-Git-Hash"] == exp_hash
    call_next.assert_awaited_once_with(request)

    if hash_patch:
        util.get_git_hash_for_file.assert_not_called()
    else:
        util.get_git_hash_for_file.assert_called_once_with(main.__file__)


def test_app_with_git_hash():
    app = mock.Mock(spec_set=["middleware"])

    found = main.app_with_git_hash(app)

    assert found is app

    app.middleware.assert_called_once_with("http")
    (called,) = app.middleware.return_value.call_args_list
    assert called.kwargs == {}
    (mw_func,) = called.args
    assert mw_func is main.add_custom_header


def test_app_with_soliplex_routers():
    app = mock.Mock(spec_set=["include_router"])

    found = main.app_with_soliplex_routers(app)

    assert found is app

    air_calls = app.include_router.mock_calls
    assert mock.call(agui_views.router, prefix="/api") in air_calls
    assert mock.call(authn_views.router, prefix="/api") in air_calls
    assert mock.call(authz_views.router, prefix="/api") in air_calls
    assert mock.call(completions_views.router, prefix="/api") in air_calls
    assert mock.call(installation_views.router, prefix="/api") in air_calls
    assert mock.call(quizzes_views.router, prefix="/api") in air_calls
    assert mock.call(rooms_views.router, prefix="/api") in air_calls
