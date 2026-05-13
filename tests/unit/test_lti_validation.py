from unittest import mock

import jwt
import pytest

from soliplex.lti import validation as lti_validation

ISSUER = "https://moodle.example.com"
CLIENT_ID = "soliplex-lti-tool"
NONCE = "test-nonce-12345"
KEY_SET_URL = "https://moodle.example.com/mod/lti/certs.php"

BASE_PAYLOAD = {
    "sub": "user-123",
    "iss": ISSUER,
    "aud": CLIENT_ID,
    "nonce": NONCE,
    lti_validation.LTI_CLAIM_VERSION: "1.3.0",
    lti_validation.LTI_CLAIM_MESSAGE_TYPE: ("LtiResourceLinkRequest"),
    lti_validation.LTI_CLAIM_DEPLOYMENT_ID: "1",
}


@pytest.fixture(autouse=True)
def _reset_jwks_cache():
    """Module-level JWKS-client cache must not leak between tests."""
    lti_validation._jwks_clients.clear()
    lti_validation._jwks_lock = None
    yield
    lti_validation._jwks_clients.clear()
    lti_validation._jwks_lock = None


@pytest.fixture
def mock_jwks_client():
    """A PyJWKClient stand-in pre-installed in the module cache."""
    client = mock.create_autospec(jwt.PyJWKClient)
    key = mock.Mock()
    key.key = "fake-signing-key"
    client.get_signing_key_from_jwt.return_value = key
    lti_validation._jwks_clients[KEY_SET_URL] = client
    return client


class TestValidateIdToken:
    @pytest.mark.anyio
    async def test_valid_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.return_value = dict(BASE_PAYLOAD)

            found = await lti_validation.validate_id_token(
                "fake-token",
                key_set_url=KEY_SET_URL,
                issuer=ISSUER,
                client_id=CLIENT_ID,
                expected_nonce=NONCE,
            )

        assert found["sub"] == "user-123"
        assert found["nonce"] == NONCE

        jwtd.assert_called_once_with(
            "fake-token",
            "fake-signing-key",
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": False,
            },
            leeway=30,
        )

    @pytest.mark.anyio
    async def test_expired_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.side_effect = jwt.ExpiredSignatureError

            with pytest.raises(lti_validation.LTITokenExpired):
                await lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                )

    @pytest.mark.anyio
    async def test_invalid_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.side_effect = jwt.InvalidTokenError("bad")

            with pytest.raises(
                lti_validation.LTIValidationError,
                match="bad",
            ):
                await lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                )

    @pytest.mark.anyio
    async def test_bad_nonce(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload["nonce"] = "wrong-nonce"
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidNonce):
                await lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                )

    @pytest.mark.anyio
    async def test_bad_version(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload[lti_validation.LTI_CLAIM_VERSION] = "2.0"
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidVersion):
                await lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                )

    @pytest.mark.anyio
    async def test_bad_message_type(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload[lti_validation.LTI_CLAIM_MESSAGE_TYPE] = (
                "LtiDeepLinkingRequest"
            )
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidMessageType):
                await lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                )


class TestJwksClientCache:
    @pytest.mark.anyio
    async def test_first_call_creates_and_caches(self):
        with mock.patch("soliplex.lti.validation.jwt.PyJWKClient") as klass:
            client = await lti_validation._get_jwks_client(KEY_SET_URL)

        klass.assert_called_once_with(KEY_SET_URL, cache_keys=True)
        assert client is klass.return_value
        assert lti_validation._jwks_clients[KEY_SET_URL] is client

    @pytest.mark.anyio
    async def test_subsequent_call_reuses_cached_client(self):
        with mock.patch("soliplex.lti.validation.jwt.PyJWKClient") as klass:
            first = await lti_validation._get_jwks_client(KEY_SET_URL)
            second = await lti_validation._get_jwks_client(KEY_SET_URL)

        klass.assert_called_once()
        assert first is second

    @pytest.mark.anyio
    async def test_distinct_urls_get_distinct_clients(self):
        url_b = "https://other.example.com/mod/lti/certs.php"
        with mock.patch("soliplex.lti.validation.jwt.PyJWKClient") as klass:
            klass.side_effect = ["client-a", "client-b"]
            a = await lti_validation._get_jwks_client(KEY_SET_URL)
            b = await lti_validation._get_jwks_client(url_b)

        assert a == "client-a"
        assert b == "client-b"
        assert klass.call_count == 2

    @pytest.mark.anyio
    async def test_double_checked_locking_avoids_duplicate_construction(self):
        """Simulate the race where a second coroutine wins the cache-miss
        check, then waits on the lock, then finds the key already present."""

        class _PrePopulatingLock:
            """anyio.Lock stand-in that inserts the entry on acquire."""

            def __init__(self, prebuilt):
                self._prebuilt = prebuilt

            async def __aenter__(self):
                lti_validation._jwks_clients[KEY_SET_URL] = self._prebuilt
                return self

            async def __aexit__(self, *exc):
                return False

        prebuilt = mock.Mock(name="prebuilt-client")
        lti_validation._jwks_lock = _PrePopulatingLock(prebuilt)

        with mock.patch("soliplex.lti.validation.jwt.PyJWKClient") as klass:
            result = await lti_validation._get_jwks_client(KEY_SET_URL)

        assert result is prebuilt
        klass.assert_not_called()

    @pytest.mark.anyio
    async def test_validate_does_not_stall_event_loop(self, mock_jwks_client):
        """The blocking JWKS lookup is offloaded via anyio.to_thread."""
        with (
            mock.patch("jwt.decode") as jwtd,
            mock.patch(
                "soliplex.lti.validation.anyio.to_thread.run_sync"
            ) as run_sync,
        ):
            jwtd.return_value = dict(BASE_PAYLOAD)
            key = mock.Mock(key="k")

            async def _passthrough(fn, *args):
                return fn(*args)

            run_sync.side_effect = _passthrough
            mock_jwks_client.get_signing_key_from_jwt.return_value = key

            await lti_validation.validate_id_token(
                "fake-token",
                key_set_url=KEY_SET_URL,
                issuer=ISSUER,
                client_id=CLIENT_ID,
                expected_nonce=NONCE,
            )

            run_sync.assert_called_once_with(
                mock_jwks_client.get_signing_key_from_jwt, "fake-token"
            )
