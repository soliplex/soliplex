from unittest import mock

import fastapi
import pytest

from soliplex import installation
from soliplex import loggers
from soliplex import views

EMAIL = "phreddy@example.com"
THE_USER_CLAIMS = {
    "email": EMAIL,
}
ROOM_ID = "test-room"


@pytest.mark.anyio
@mock.patch("soliplex.authn.authenticate")
async def test_get_the_user_claims(auth_fn):
    the_installation = mock.create_autospec(installation.Installation)
    token = object()

    found = await views.get_the_user_claims(
        the_installation=the_installation,
        token=token,
    )

    assert found is auth_fn.return_value

    auth_fn.assert_called_once_with(
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@mock.patch("soliplex.loggers.LogWrapper")
async def test_get_the_unauth_logger(lw_klass):
    request = mock.create_autospec(fastapi.Request)
    the_installation = mock.create_autospec(installation.Installation)
    lw = lw_klass.return_value = mock.AsyncMock()

    found = await views.get_the_unauth_logger(
        request=request,
        the_installation=the_installation,
    )

    assert found is lw

    lw_klass.assert_called_once_with(
        loggers.AUTHN_LOGGER_NAME,
        headers=request.headers,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_room_id", [False, True])
async def test_get_the_logger(w_room_id):
    request = mock.create_autospec(fastapi.Request)

    if w_room_id:
        request.path_params = {"room_id": ROOM_ID}
    else:
        request.path_params = {}

    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    found = await views.get_the_logger(
        request=request,
        the_unauth_logger=the_unauth_logger,
        the_user_claims=THE_USER_CLAIMS,
    )

    assert found is the_unauth_logger.bind.return_value

    if w_room_id:
        the_unauth_logger.bind.assert_called_once_with(
            loggers.SOLIPLEX_LOGGER_NAME,
            claims=THE_USER_CLAIMS,
            room_id=ROOM_ID,
        )
    else:
        the_unauth_logger.bind.assert_called_once_with(
            loggers.SOLIPLEX_LOGGER_NAME,
            claims=THE_USER_CLAIMS,
        )


@pytest.mark.anyio
async def test_health_check():
    response = await views.health_check()

    assert response == "OK"
