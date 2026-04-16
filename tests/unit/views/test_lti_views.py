from unittest import mock

import fastapi
import pytest
from fastapi import responses as fastapi_responses

from soliplex import installation
from soliplex import loggers
from soliplex.config import lti as config_lti
from soliplex.lti import validation as lti_validation
from soliplex.views import lti as lti_views

ISSUER = "https://moodle.example.com"
CLIENT_ID = "soliplex-lti-tool"
PLATFORM_ID = "moodle-workplace"
DEFAULT_ROOM = "moodle-tools"
SECRET_KEY = "test-lti-secret"
NONCE = "test-nonce-value"
STATE = "test-state-token"
SESSION_TOKEN = "test-session-token"
AUTH_LOGIN_URL = "https://moodle.example.com/mod/lti/auth.php"
KEY_SET_URL = "https://moodle.example.com/mod/lti/certs.php"

PLATFORM = config_lti.LTIPlatformConfig(
    id=PLATFORM_ID,
    issuer=ISSUER,
    client_id=CLIENT_ID,
    deployment_ids=["1"],
    auth_login_url=AUTH_LOGIN_URL,
    auth_token_url=("https://moodle.example.com/mod/lti/token.php"),
    key_set_url=KEY_SET_URL,
    default_room_id=DEFAULT_ROOM,
)

PLATFORM_WITH_PICKER = config_lti.LTIPlatformConfig(
    id=PLATFORM_ID,
    issuer=ISSUER,
    client_id=CLIENT_ID,
    deployment_ids=["1"],
    auth_login_url=AUTH_LOGIN_URL,
    auth_token_url=("https://moodle.example.com/mod/lti/token.php"),
    key_set_url=KEY_SET_URL,
    default_room_id=DEFAULT_ROOM,
    show_room_picker=True,
)


def _make_installation(platforms=None):
    inst = mock.create_autospec(installation.Installation)
    inst.lti_platform_configs = (
        platforms if platforms is not None else [PLATFORM]
    )
    inst.get_secret.return_value = SECRET_KEY
    return inst


def _make_request(
    method="GET",
    query_string="",
    form_data=None,
):
    request = mock.create_autospec(fastapi.Request)
    request.method = method
    request.query_params = {}
    if query_string:
        from urllib.parse import parse_qs

        pairs = parse_qs(query_string, keep_blank_values=True)
        request.query_params = {k: v[0] for k, v in pairs.items()}

    async def _form():
        return form_data or {}

    request.form = _form
    request.url_for = mock.Mock(return_value="http://testserver/lti/launch")
    request.base_url = "http://testserver/"
    return request


@pytest.mark.anyio
async def test_get_lti_jwks():
    found = await lti_views.get_lti_jwks()
    assert found == {"keys": []}


class TestReadParams:
    @pytest.mark.anyio
    async def test_get(self):
        request = mock.create_autospec(fastapi.Request)
        request.method = "GET"
        request.query_params = {"iss": ISSUER}

        found = await lti_views._read_params(request)
        assert found == {"iss": ISSUER}

    @pytest.mark.anyio
    async def test_post(self):
        request = mock.create_autospec(fastapi.Request)
        request.method = "POST"

        async def _form():
            return {"iss": ISSUER}

        request.form = _form

        found = await lti_views._read_params(request)
        assert found == {"iss": ISSUER}


class TestLtiLogin:
    @pytest.mark.anyio
    @mock.patch("soliplex.lti.nonce.encode_state")
    @mock.patch("soliplex.lti.nonce.generate_nonce")
    async def test_success_get(self, gen_nonce, enc_state):
        gen_nonce.return_value = NONCE
        enc_state.return_value = STATE

        request = _make_request(
            method="GET",
            query_string=(
                f"iss={ISSUER}&client_id={CLIENT_ID}"
                f"&login_hint=user1"
                f"&lti_message_hint=hint1"
            ),
        )
        the_installation = _make_installation()

        found = await lti_views.lti_login(request, the_installation)

        assert isinstance(found, fastapi_responses.RedirectResponse)
        assert found.status_code == 302

        location = dict(found.headers)["location"]
        assert location.startswith(AUTH_LOGIN_URL)
        assert "response_type=id_token" in location
        assert f"client_id={CLIENT_ID}" in location
        assert f"nonce={NONCE}" in location
        assert f"state={STATE}" in location

        enc_state.assert_called_once_with(
            SECRET_KEY,
            nonce=NONCE,
            platform_id=PLATFORM_ID,
        )

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.nonce.encode_state")
    @mock.patch("soliplex.lti.nonce.generate_nonce")
    async def test_success_post(self, gen_nonce, enc_state):
        gen_nonce.return_value = NONCE
        enc_state.return_value = STATE

        request = _make_request(
            method="POST",
            form_data={
                "iss": ISSUER,
                "client_id": CLIENT_ID,
                "login_hint": "user1",
                "lti_message_hint": "hint1",
            },
        )
        the_installation = _make_installation()

        found = await lti_views.lti_login(request, the_installation)

        assert isinstance(found, fastapi_responses.RedirectResponse)
        assert found.status_code == 302

    @pytest.mark.anyio
    async def test_unknown_platform(self):
        request = _make_request(
            method="GET",
            query_string=("iss=https://unknown.com&client_id=bogus"),
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_login(request, the_installation)

        assert exc.value.status_code == 400
        assert exc.value.detail == loggers.LTI_UNKNOWN_PLATFORM

    @pytest.mark.anyio
    async def test_missing_secret(self):
        request = _make_request(
            method="GET",
            query_string=(
                f"iss={ISSUER}&client_id={CLIENT_ID}&login_hint=user1"
            ),
        )
        the_installation = _make_installation()
        the_installation.get_secret.side_effect = KeyError(
            "LTI_SESSION_SECRET"
        )

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_login(request, the_installation)

        assert exc.value.status_code == 500
        assert exc.value.detail == loggers.LTI_SECRET_NOT_CONFIGURED


class TestLtiLaunch:
    LTI_PAYLOAD = {
        "sub": "user-123",
        "email": "phred@example.com",
        "name": "Phred Phlyntstone",
        "nonce": NONCE,
        lti_validation.LTI_CLAIM_VERSION: "1.3.0",
        lti_validation.LTI_CLAIM_MESSAGE_TYPE: ("LtiResourceLinkRequest"),
        lti_validation.LTI_CLAIM_DEPLOYMENT_ID: "1",
        lti_validation.LTI_CLAIM_CONTEXT: {"id": "101"},
    }

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_success(self, dec_state, val_tok, mint_tok):
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.return_value = dict(self.LTI_PAYLOAD)
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        found = await lti_views.lti_launch(request, the_installation)

        assert isinstance(found, fastapi_responses.HTMLResponse)
        assert found.status_code == 200

        csp = dict(found.headers).get("content-security-policy")
        assert csp == f"frame-ancestors {ISSUER}"

        body = found.body.decode()
        assert DEFAULT_ROOM in body
        assert SESSION_TOKEN in body

        val_tok.assert_called_once_with(
            "fake-jwt",
            key_set_url=KEY_SET_URL,
            issuer=ISSUER,
            client_id=CLIENT_ID,
            expected_nonce=NONCE,
        )

    @pytest.mark.anyio
    async def test_missing_id_token(self):
        request = _make_request(
            method="POST",
            form_data={"state": STATE},
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400
        assert exc.value.detail == loggers.LTI_INVALID_LAUNCH

    @pytest.mark.anyio
    async def test_missing_state(self):
        request = _make_request(
            method="POST",
            form_data={"id_token": "fake-jwt"},
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400
        assert exc.value.detail == loggers.LTI_INVALID_LAUNCH

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_bad_state(self, dec_state):
        dec_state.return_value = None

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": "bad-state",
            },
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400
        assert exc.value.detail == loggers.LTI_INVALID_LAUNCH

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_unknown_platform_in_state(self, dec_state):
        dec_state.return_value = (NONCE, "nonexistent-id")

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400
        assert exc.value.detail == loggers.LTI_UNKNOWN_PLATFORM

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_validation_error(self, dec_state, val_tok):
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.side_effect = lti_validation.LTITokenExpired("expired")

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_invalid_deployment(self, dec_state, val_tok):
        dec_state.return_value = (NONCE, PLATFORM_ID)
        payload = dict(self.LTI_PAYLOAD)
        payload[lti_validation.LTI_CLAIM_DEPLOYMENT_ID] = "99"
        val_tok.return_value = payload

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)
        assert exc.value.status_code == 400

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_context_not_dict(self, dec_state, val_tok, mint_tok):
        """When LTI context is not a dict, course_id=None"""
        dec_state.return_value = (NONCE, PLATFORM_ID)
        payload = dict(self.LTI_PAYLOAD)
        payload[lti_validation.LTI_CLAIM_CONTEXT] = "not-a-dict"
        val_tok.return_value = payload
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        found = await lti_views.lti_launch(request, the_installation)

        assert isinstance(found, fastapi_responses.HTMLResponse)

    @pytest.mark.anyio
    async def test_missing_secret(self):
        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()
        the_installation.get_secret.side_effect = KeyError(
            "LTI_SESSION_SECRET"
        )

        with pytest.raises(fastapi.HTTPException) as exc:
            await lti_views.lti_launch(request, the_installation)

        assert exc.value.status_code == 500
        assert exc.value.detail == loggers.LTI_SECRET_NOT_CONFIGURED


class TestLtiLaunchPicker:
    LTI_PAYLOAD = TestLtiLaunch.LTI_PAYLOAD

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_shown_when_enabled(
        self, dec_state, val_tok, mint_tok
    ):
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.return_value = dict(self.LTI_PAYLOAD)
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation(platforms=[PLATFORM_WITH_PICKER])

        found = await lti_views.lti_launch(request, the_installation)

        assert isinstance(found, fastapi_responses.HTMLResponse)
        body = found.body.decode()
        assert 'id="picker"' in body
        assert "loadRooms" in body

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_not_shown_when_disabled(
        self, dec_state, val_tok, mint_tok
    ):
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.return_value = dict(self.LTI_PAYLOAD)
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        found = await lti_views.lti_launch(request, the_installation)

        body = found.body.decode()
        assert 'id="picker"' not in body
        assert DEFAULT_ROOM in body

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_bypassed_for_course_map(
        self, dec_state, val_tok, mint_tok
    ):
        """When course_room_map resolves a specific room,
        picker is bypassed even if show_room_picker=True."""
        dec_state.return_value = (NONCE, PLATFORM_ID)
        payload = dict(self.LTI_PAYLOAD)
        payload[lti_validation.LTI_CLAIM_CONTEXT] = {"id": "101"}
        val_tok.return_value = payload
        mint_tok.return_value = SESSION_TOKEN

        platform = config_lti.LTIPlatformConfig(
            id=PLATFORM_ID,
            issuer=ISSUER,
            client_id=CLIENT_ID,
            deployment_ids=["1"],
            auth_login_url=AUTH_LOGIN_URL,
            auth_token_url=("https://moodle.example.com/mod/lti/token.php"),
            key_set_url=KEY_SET_URL,
            default_room_id=DEFAULT_ROOM,
            show_room_picker=True,
            course_room_map={"101": "specific-room"},
        )

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation(platforms=[platform])

        found = await lti_views.lti_launch(request, the_installation)

        body = found.body.decode()
        assert 'id="picker"' not in body
        assert "specific-room" in body

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_bypassed_for_target_link_uri(
        self, dec_state, val_tok, mint_tok
    ):
        """When target_link_uri resolves a room,
        picker is bypassed even if show_room_picker=True."""
        dec_state.return_value = (NONCE, PLATFORM_ID)
        payload = dict(self.LTI_PAYLOAD)
        payload[lti_validation.LTI_CLAIM_TARGET_LINK_URI] = (
            "https://soliplex.example.com/lti/chat/uri-room"
        )
        val_tok.return_value = payload
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation(platforms=[PLATFORM_WITH_PICKER])

        found = await lti_views.lti_launch(request, the_installation)

        body = found.body.decode()
        assert 'id="picker"' not in body
        assert "uri-room" in body

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_default_false(self, dec_state, val_tok, mint_tok):
        """Platform without show_room_picker defaults to
        False -- no picker shown."""
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.return_value = dict(self.LTI_PAYLOAD)
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation()

        found = await lti_views.lti_launch(request, the_installation)

        body = found.body.decode()
        assert 'id="picker"' not in body

    @pytest.mark.anyio
    @mock.patch("soliplex.lti.session.mint_session_token")
    @mock.patch("soliplex.lti.validation.validate_id_token")
    @mock.patch("soliplex.lti.nonce.decode_state")
    async def test_picker_session_token_has_empty_room_id(
        self, dec_state, val_tok, mint_tok
    ):
        """When picker is shown, mint_session_token is called
        with room_id=''."""
        dec_state.return_value = (NONCE, PLATFORM_ID)
        val_tok.return_value = dict(self.LTI_PAYLOAD)
        mint_tok.return_value = SESSION_TOKEN

        request = _make_request(
            method="POST",
            form_data={
                "id_token": "fake-jwt",
                "state": STATE,
            },
        )
        the_installation = _make_installation(platforms=[PLATFORM_WITH_PICKER])

        await lti_views.lti_launch(request, the_installation)

        mint_tok.assert_called_once()
        _, _, room_id_arg = mint_tok.call_args[0]
        assert room_id_arg == ""
