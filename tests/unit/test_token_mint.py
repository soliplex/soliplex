import uuid
from unittest import mock

import pytest

from soliplex import loggers
from soliplex import token_mint

URL_SAFE_TOKEN_SECRET_KEY = "really, seriously seekrit"
URL_SAFE_TOKEN_SALT = "testing"

SERVICE_TOKEN_NOW = 1_700_000_000
SERVICE_TOKEN_EXPIRES_IN = 3600
SERVICE_TOKEN_CLAIMS = {"sub": "ops", "email": "ops@example.com"}
SERVICE_TOKEN_UUID = uuid.UUID("12345678-1234-5678-1234-567812345678")


@mock.patch("itsdangerous.url_safe.URLSafeTimedSerializer")
def test_generate_url_safe_token(idusts_klass):
    usts = idusts_klass.return_value
    to_sign = {"foo": "bar", "baz": 123}

    found = token_mint.generate_url_safe_token(
        URL_SAFE_TOKEN_SECRET_KEY, URL_SAFE_TOKEN_SALT, **to_sign
    )

    assert found is usts.dumps.return_value
    usts.dumps.assert_called_once_with(to_sign)
    idusts_klass.assert_called_once_with(
        secret_key=URL_SAFE_TOKEN_SECRET_KEY,
        salt=URL_SAFE_TOKEN_SALT,
    )


@pytest.mark.parametrize("w_valid", [False, True])
@pytest.mark.parametrize(
    "kwargs, exp_max_age",
    [
        ({}, None),
        ({"max_age": 3600}, 3600),
    ],
)
@mock.patch("itsdangerous.url_safe.URLSafeTimedSerializer")
def test_validate_url_safe_token(idusts_klass, kwargs, exp_max_age, w_valid):
    usts = idusts_klass.return_value
    token = "DEADBEEF"
    loaded = {"foo": "bar", "baz": 123}

    if w_valid:
        usts.loads_unsafe.return_value = True, loaded
    else:
        usts.loads_unsafe.return_value = False, None

    found = token_mint.validate_url_safe_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        URL_SAFE_TOKEN_SALT,
        token,
        **kwargs,
    )

    if w_valid:
        assert found is loaded
    else:
        assert found is None
    usts.loads_unsafe.assert_called_once_with(token, max_age=exp_max_age)
    idusts_klass.assert_called_once_with(
        secret_key=URL_SAFE_TOKEN_SECRET_KEY,
        salt=URL_SAFE_TOKEN_SALT,
    )


@mock.patch("time.time", return_value=SERVICE_TOKEN_NOW)
def test_mint_service_token(time_time):

    token = token_mint.mint_service_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        SERVICE_TOKEN_CLAIMS,
        expires_in=SERVICE_TOKEN_EXPIRES_IN,
    )

    found = token_mint.validate_url_safe_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        token_mint.SERVICE_TOKEN_SALT,
        token,
    )
    assert found == {
        **SERVICE_TOKEN_CLAIMS,
        "iat": SERVICE_TOKEN_NOW,
        "exp": SERVICE_TOKEN_NOW + SERVICE_TOKEN_EXPIRES_IN,
    }


@pytest.mark.parametrize(
    "claims",
    [
        {"email": "ops@example.com"},
        {},
    ],
)
@mock.patch("uuid.uuid4", return_value=SERVICE_TOKEN_UUID)
@mock.patch("time.time", return_value=SERVICE_TOKEN_NOW)
def test_mint_service_token_wo_sub(time_time, uuid_uuid4, claims):

    token = token_mint.mint_service_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        claims,
        expires_in=SERVICE_TOKEN_EXPIRES_IN,
    )

    found = token_mint.validate_url_safe_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        token_mint.SERVICE_TOKEN_SALT,
        token,
    )
    assert found == {
        **claims,
        "sub": str(SERVICE_TOKEN_UUID),
        "iat": SERVICE_TOKEN_NOW,
        "exp": SERVICE_TOKEN_NOW + SERVICE_TOKEN_EXPIRES_IN,
    }


@pytest.mark.parametrize(
    "claims, exp_claim",
    [
        ({"sub": "ops", "iat": 123}, "iat"),
        ({"sub": "ops", "exp": 123}, "exp"),
    ],
)
def test_mint_service_token_w_reserved_claim(claims, exp_claim):

    with pytest.raises(token_mint.ReservedClaim) as exc_info:
        token_mint.mint_service_token(
            URL_SAFE_TOKEN_SECRET_KEY,
            claims,
            expires_in=SERVICE_TOKEN_EXPIRES_IN,
        )

    assert exc_info.value.claim == exp_claim


@pytest.mark.parametrize("expires_in", [0, -1])
def test_mint_service_token_w_invalid_lifetime(expires_in):

    with pytest.raises(token_mint.InvalidLifetime) as exc_info:
        token_mint.mint_service_token(
            URL_SAFE_TOKEN_SECRET_KEY,
            SERVICE_TOKEN_CLAIMS,
            expires_in=expires_in,
        )

    assert exc_info.value.expires_in == expires_in


@pytest.mark.parametrize(
    "w_secret, w_salt, w_payload, expected, exp_reason",
    [
        pytest.param(
            URL_SAFE_TOKEN_SECRET_KEY,
            token_mint.SERVICE_TOKEN_SALT,
            {**SERVICE_TOKEN_CLAIMS, "exp": SERVICE_TOKEN_NOW + 1},
            {**SERVICE_TOKEN_CLAIMS, "exp": SERVICE_TOKEN_NOW + 1},
            None,
            id="valid",
        ),
        pytest.param(
            "other secret",
            token_mint.SERVICE_TOKEN_SALT,
            {**SERVICE_TOKEN_CLAIMS, "exp": SERVICE_TOKEN_NOW + 1},
            None,
            loggers.AUTHN_SERVICE_TOKEN_BAD_SIGNATURE,
            id="bad_signature",
        ),
        pytest.param(
            URL_SAFE_TOKEN_SECRET_KEY,
            "test-room",
            {**SERVICE_TOKEN_CLAIMS, "exp": SERVICE_TOKEN_NOW + 1},
            None,
            loggers.AUTHN_SERVICE_TOKEN_BAD_SIGNATURE,
            id="mcp_room_token",
        ),
        pytest.param(
            URL_SAFE_TOKEN_SECRET_KEY,
            token_mint.SERVICE_TOKEN_SALT,
            dict(SERVICE_TOKEN_CLAIMS),
            None,
            loggers.AUTHN_SERVICE_TOKEN_BAD_ENVELOPE,
            id="missing_exp",
        ),
        pytest.param(
            URL_SAFE_TOKEN_SECRET_KEY,
            token_mint.SERVICE_TOKEN_SALT,
            {**SERVICE_TOKEN_CLAIMS, "exp": "tomorrow"},
            None,
            loggers.AUTHN_SERVICE_TOKEN_BAD_ENVELOPE,
            id="non_numeric_exp",
        ),
        pytest.param(
            URL_SAFE_TOKEN_SECRET_KEY,
            token_mint.SERVICE_TOKEN_SALT,
            {**SERVICE_TOKEN_CLAIMS, "exp": SERVICE_TOKEN_NOW},
            None,
            loggers.AUTHN_SERVICE_TOKEN_EXPIRED,
            id="expired",
        ),
    ],
)
@mock.patch("time.time", return_value=SERVICE_TOKEN_NOW)
def test_load_service_token(
    time_time,
    w_secret,
    w_salt,
    w_payload,
    expected,
    exp_reason,
):
    token = token_mint.generate_url_safe_token(w_secret, w_salt, **w_payload)

    found, reason = token_mint.load_service_token(
        URL_SAFE_TOKEN_SECRET_KEY,
        token,
    )

    assert found == expected
    assert reason == exp_reason
