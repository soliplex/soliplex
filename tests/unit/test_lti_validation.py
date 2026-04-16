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


@pytest.fixture
def mock_jwks_client():
    client = mock.create_autospec(jwt.PyJWKClient)
    key = mock.Mock()
    key.key = "fake-signing-key"
    client.get_signing_key_from_jwt.return_value = key
    return client


class TestValidateIdToken:
    def test_valid_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.return_value = dict(BASE_PAYLOAD)

            found = lti_validation.validate_id_token(
                "fake-token",
                key_set_url=KEY_SET_URL,
                issuer=ISSUER,
                client_id=CLIENT_ID,
                expected_nonce=NONCE,
                jwks_client=mock_jwks_client,
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

    def test_expired_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.side_effect = jwt.ExpiredSignatureError

            with pytest.raises(lti_validation.LTITokenExpired):
                lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                    jwks_client=mock_jwks_client,
                )

    def test_invalid_token(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            jwtd.side_effect = jwt.InvalidTokenError("bad")

            with pytest.raises(
                lti_validation.LTIValidationError,
                match="bad",
            ):
                lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                    jwks_client=mock_jwks_client,
                )

    def test_bad_nonce(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload["nonce"] = "wrong-nonce"
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidNonce):
                lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                    jwks_client=mock_jwks_client,
                )

    def test_bad_version(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload[lti_validation.LTI_CLAIM_VERSION] = "2.0"
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidVersion):
                lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                    jwks_client=mock_jwks_client,
                )

    def test_bad_message_type(self, mock_jwks_client):
        with mock.patch("jwt.decode") as jwtd:
            payload = dict(BASE_PAYLOAD)
            payload[lti_validation.LTI_CLAIM_MESSAGE_TYPE] = (
                "LtiDeepLinkingRequest"
            )
            jwtd.return_value = payload

            with pytest.raises(lti_validation.LTIInvalidMessageType):
                lti_validation.validate_id_token(
                    "fake-token",
                    key_set_url=KEY_SET_URL,
                    issuer=ISSUER,
                    client_id=CLIENT_ID,
                    expected_nonce=NONCE,
                    jwks_client=mock_jwks_client,
                )

    def test_no_jwks_client_fetches(self):
        """When jwks_client is None, _fetch_jwks is called"""
        with (
            mock.patch("soliplex.lti.validation._fetch_jwks") as fetch,
            mock.patch("jwt.decode") as jwtd,
        ):
            key = mock.Mock()
            key.key = "key"
            fetch.return_value.get_signing_key_from_jwt.return_value = key
            jwtd.return_value = dict(BASE_PAYLOAD)

            lti_validation.validate_id_token(
                "fake-token",
                key_set_url=KEY_SET_URL,
                issuer=ISSUER,
                client_id=CLIENT_ID,
                expected_nonce=NONCE,
            )

            fetch.assert_called_once_with(KEY_SET_URL)


def test_fetch_jwks():
    with mock.patch("soliplex.lti.validation.jwt.PyJWKClient") as mock_cls:
        client = lti_validation._fetch_jwks(KEY_SET_URL)
        mock_cls.assert_called_once_with(KEY_SET_URL, cache_keys=True)
        assert client is mock_cls.return_value
