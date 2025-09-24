import os
from unittest import mock

import pytest
from mcp.server.auth import provider as mcp_auth_provider

from soliplex import config
from soliplex import mcp_auth

ROOM_ID = "test-room"
URL_SAFE_TOKEN_SALT = "testing"
URL_SAFE_TOKEN_SECRET_KEY = "really, seriously seekrit"


def test_get_url_safe_token_secret():
    kw = {
        mcp_auth.URL_SAFE_TOKEN_SECRET_ENV: URL_SAFE_TOKEN_SECRET_KEY,
    }

    with mock.patch.dict(os.environ, clear=True, **kw):
        found = mcp_auth.get_url_safe_token_secret()

    assert found == URL_SAFE_TOKEN_SECRET_KEY


@mock.patch("soliplex.mcp_auth.get_url_safe_token_secret")
@mock.patch("itsdangerous.url_safe.URLSafeTimedSerializer")
def test_generate_url_safe_token(idusts_klass, gusts):
    usts = idusts_klass.return_value
    to_sign = {"foo": "bar", "baz": 123}

    found = mcp_auth.generate_url_safe_token(URL_SAFE_TOKEN_SALT, **to_sign)

    assert found is usts.dumps.return_value

    usts.dumps.assert_called_once_with(to_sign)

    idusts_klass.assert_called_once_with(
        secret_key=gusts.return_value, salt=URL_SAFE_TOKEN_SALT,
    )


@pytest.mark.parametrize("w_valid", [False, True])
@pytest.mark.parametrize("w_max_age", [None, 3600])
@mock.patch("soliplex.mcp_auth.get_url_safe_token_secret")
@mock.patch("itsdangerous.url_safe.URLSafeTimedSerializer")
def test_validate_url_safe_token(idusts_klass, gusts, w_max_age, w_valid):
    usts = idusts_klass.return_value
    token = "DEADBEEF"
    loaded = {"foo": "bar", "baz": 123}

    if w_valid:
        usts.loads_unsafe.return_value = True, loaded
    else:
        usts.loads_unsafe.return_value = False, None

    exp_kw = {"max_age": w_max_age}

    if w_max_age is not None:
        found = mcp_auth.validate_url_safe_token(
            URL_SAFE_TOKEN_SALT, token, max_age=w_max_age,
        )
    else:
        found = mcp_auth.validate_url_safe_token(URL_SAFE_TOKEN_SALT, token)

    if w_valid:
        assert found is loaded
    else:
        assert found is None

    usts.loads_unsafe.assert_called_once_with(token, **exp_kw)

    idusts_klass.assert_called_once_with(
        secret_key=gusts.return_value, salt=URL_SAFE_TOKEN_SALT,
    )


@pytest.fixture
def the_installation():
    return mock.create_autospec(config.InstallationConfig)


@pytest.mark.parametrize("w_max_age", [None, 3600])
@pytest.mark.parametrize("w_auth_disabled", [False, True])
def test_fmcptokenprovider_ctor(the_installation, w_auth_disabled, w_max_age):

    the_installation.auth_disabled = w_auth_disabled

    if w_max_age is not None:
        found = mcp_auth.FastMCPTokenProvider(
            ROOM_ID, the_installation, max_age=w_max_age)
    else:
        found = mcp_auth.FastMCPTokenProvider(ROOM_ID, the_installation)

    assert found.room_id == ROOM_ID
    assert found.max_age == w_max_age
    assert found.auth_disabled == w_auth_disabled


@pytest.mark.anyio
@pytest.mark.parametrize("w_hit", [False, True])
@pytest.mark.parametrize("w_max_age", [None, 3600])
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@mock.patch("soliplex.mcp_auth.validate_url_safe_token")
async def test_fmcptokenprovider_verify_token(
    vust, the_installation, w_auth_disabled, w_max_age, w_hit,
):
    TOKEN = "DEADBEEF"
    REAL_USER = {
        "name": "Bharney Rhybble", "email": "bharney@example.com",
    }

    the_installation.auth_disabled = w_auth_disabled

    if w_max_age is not None:
        fmtp = mcp_auth.FastMCPTokenProvider(
            ROOM_ID, the_installation, max_age=w_max_age,
        )
    else:
        fmtp = mcp_auth.FastMCPTokenProvider(ROOM_ID, the_installation)

    if w_hit:
        vust.return_value = REAL_USER
    else:
        vust.return_value = None

    found = await fmtp.verify_token(TOKEN)

    if w_auth_disabled or w_hit:
        assert isinstance(found, mcp_auth_provider.AccessToken)
        assert found.token == TOKEN
        assert found.client_id == ROOM_ID
    else:
        assert found is None

    if not w_auth_disabled:
        vust.assert_called_once_with(ROOM_ID, TOKEN, max_age=w_max_age)
