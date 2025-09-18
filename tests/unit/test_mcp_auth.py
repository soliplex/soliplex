import os
from unittest import mock

import pytest

from soliplex import mcp_auth

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
