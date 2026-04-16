from unittest import mock

from soliplex.lti import nonce as lti_nonce

SECRET_KEY = "test-secret-key"
NONCE = "test-nonce-value"
PLATFORM_ID = "moodle-workplace"


def test_generate_nonce():
    n1 = lti_nonce.generate_nonce()
    n2 = lti_nonce.generate_nonce()

    assert isinstance(n1, str)
    assert len(n1) > 20
    assert n1 != n2


def test_encode_decode_roundtrip():
    state = lti_nonce.encode_state(
        SECRET_KEY,
        nonce=NONCE,
        platform_id=PLATFORM_ID,
    )

    result = lti_nonce.decode_state(SECRET_KEY, state)

    assert result == (NONCE, PLATFORM_ID)


def test_decode_state_bad_signature():
    state = lti_nonce.encode_state(
        SECRET_KEY,
        nonce=NONCE,
        platform_id=PLATFORM_ID,
    )

    result = lti_nonce.decode_state("wrong-key", state)

    assert result is None


@mock.patch("soliplex.mcp_auth.validate_url_safe_token")
def test_decode_state_expired(vt):
    """Expired state returns None"""
    vt.return_value = None

    result = lti_nonce.decode_state(SECRET_KEY, "some-state", max_age=1)

    assert result is None
    vt.assert_called_once_with(
        SECRET_KEY,
        lti_nonce.LTI_STATE_SALT,
        "some-state",
        max_age=1,
    )


def test_decode_state_tampered():
    result = lti_nonce.decode_state(SECRET_KEY, "tampered-garbage-token")

    assert result is None


def test_decode_state_missing_fields():
    """If the payload lacks nonce or platform_id, returns None"""
    with mock.patch("soliplex.mcp_auth.validate_url_safe_token") as vt:
        # Missing platform_id
        vt.return_value = {"nonce": NONCE}
        result = lti_nonce.decode_state(SECRET_KEY, "tok")
        assert result is None

        # Missing nonce
        vt.return_value = {"platform_id": PLATFORM_ID}
        result = lti_nonce.decode_state(SECRET_KEY, "tok")
        assert result is None
