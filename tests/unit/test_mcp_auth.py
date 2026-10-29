from unittest import mock

import pytest
from mcp.server.auth import provider as mcp_auth_provider

from soliplex import mcp_auth

URL_SAFE_TOKEN_SECRET_KEY = "really, seriously seekrit"
ROOM_ID = "test-room"


@pytest.mark.parametrize("w_max_age", [None, 3600])
@pytest.mark.parametrize("w_auth_disabled", [False, True])
def test_fmcptokenprovider_ctor(w_auth_disabled, w_max_age):
    auth_disabled = w_auth_disabled

    if w_max_age is not None:
        found = mcp_auth.FastMCPTokenProvider(
            room_id=ROOM_ID,
            auth_disabled=auth_disabled,
            secret_key=URL_SAFE_TOKEN_SECRET_KEY,
            max_age=w_max_age,
        )
    else:
        found = mcp_auth.FastMCPTokenProvider(
            room_id=ROOM_ID,
            auth_disabled=auth_disabled,
            secret_key=URL_SAFE_TOKEN_SECRET_KEY,
        )

    assert found.room_id == ROOM_ID
    assert found.max_age == w_max_age
    assert found.auth_disabled == w_auth_disabled
    assert found.secret_key == URL_SAFE_TOKEN_SECRET_KEY


@pytest.mark.anyio
@pytest.mark.parametrize("w_hit", [False, True])
@pytest.mark.parametrize("w_max_age", [None, 3600])
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@mock.patch("soliplex.token_mint.validate_url_safe_token")
async def test_fmcptokenprovider_verify_token(
    vust,
    w_auth_disabled,
    w_max_age,
    w_hit,
):
    TOKEN = "DEADBEEF"
    REAL_USER = {
        "name": "Bharney Rhybble",
        "email": "bharney@example.com",
    }

    auth_disabled = w_auth_disabled

    if w_max_age is not None:
        fmtp = mcp_auth.FastMCPTokenProvider(
            room_id=ROOM_ID,
            auth_disabled=auth_disabled,
            secret_key=URL_SAFE_TOKEN_SECRET_KEY,
            max_age=w_max_age,
        )
    else:
        fmtp = mcp_auth.FastMCPTokenProvider(
            room_id=ROOM_ID,
            auth_disabled=auth_disabled,
            secret_key=URL_SAFE_TOKEN_SECRET_KEY,
        )

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
        vust.assert_called_once_with(
            URL_SAFE_TOKEN_SECRET_KEY,
            ROOM_ID,
            TOKEN,
            max_age=w_max_age,
        )
