import contextlib
from unittest import mock

import fastapi
import pytest

from soliplex import authn
from soliplex import installation
from soliplex import loggers
from soliplex import views
from soliplex.config import installation as config_installation

EMAIL = "phreddy@example.com"
THE_USER_CLAIMS = {
    "email": EMAIL,
}
ROOM_ID = "test-room"


@pytest.fixture
def the_installation():
    result = mock.create_autospec(installation.Installation)
    result._config = mock.create_autospec(
        config_installation.InstallationConfig
    )
    return result


@pytest.mark.anyio
@pytest.mark.parametrize("w_header_map", [{}, {"frob": "X-Foo"}])
@pytest.mark.parametrize("w_headers", [{}, {"X-Foo": "bar", "X-Spam": "qux"}])
@mock.patch("soliplex.loggers.LogWrapper")
async def test_get_the_unauth_logger(
    lw_klass,
    the_installation,
    w_headers,
    w_header_map,
):
    request = mock.create_autospec(fastapi.Request)
    request.headers = w_headers

    the_installation._config.logging_headers_map = w_header_map

    lw = lw_klass.return_value = mock.AsyncMock()

    found = await views.get_the_unauth_logger(
        request=request,
        the_installation=the_installation,
    )

    assert found is lw

    if w_headers and w_header_map:
        exp_extras = {"frob": "bar"}
    else:
        exp_extras = {}

    lw_klass.assert_called_once_with(
        loggers.AUTHN_LOGGER_NAME,
        the_installation=the_installation,
        **exp_extras,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "code, msg",
    [
        (None, None),
        (401, authn.JWT_VALIDATION_NO_TOKEN),
        (401, authn.JWT_VALIDATION_INVALID_TOKEN),
    ],
)
@mock.patch("soliplex.authn.authenticate")
async def test_get_the_user_claims(auth_fn, the_installation, code, msg):
    token = object()
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    if code is not None:
        auth_fn.side_effect = fastapi.HTTPException(
            status_code=code,
            detail=msg,
        )
        expectation = pytest.raises(fastapi.HTTPException)
    else:
        expectation = contextlib.nullcontext(None)

    with expectation as expected:
        found = await views.get_the_user_claims(
            the_installation=the_installation,
            the_unauth_logger=the_unauth_logger,
            token=token,
        )

    the_unauth_logger.debug.assert_called_once_with(
        loggers.AUTHN_GET_USER_CLAIMS,
    )

    if expected is None:
        assert found is auth_fn.return_value
        the_unauth_logger.exception.assert_not_called()
    else:
        assert expected.value.status_code == code
        assert expected.value.detail == msg
        the_unauth_logger.error.assert_called_once_with(
            loggers.AUTHN_GET_USER_CLAIMS_FAILED,
            msg,
        )

    auth_fn.assert_called_once_with(
        the_installation=the_installation,
        token=token,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_claims_map", [{}, {"user_id": "email"}])
@pytest.mark.parametrize("w_claims", [{}, THE_USER_CLAIMS])
async def test_get_the_logger(the_installation, w_claims, w_claims_map):
    request = mock.create_autospec(fastapi.Request)

    the_installation._config.logging_claims_map = w_claims_map

    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)
    the_unauth_logger.installation = the_installation

    found = await views.get_the_logger(
        request=request,
        the_unauth_logger=the_unauth_logger,
        the_user_claims=w_claims,
    )

    assert found is the_unauth_logger.bind.return_value

    if w_claims_map and w_claims:
        the_unauth_logger.bind.assert_called_once_with(
            loggers.SOLIPLEX_LOGGER_NAME,
            user_id=EMAIL,
        )
    else:
        the_unauth_logger.bind.assert_called_once_with(
            loggers.SOLIPLEX_LOGGER_NAME,
        )


@pytest.mark.anyio
async def test_health_check():
    response = await views.health_check()

    assert response == "OK"
