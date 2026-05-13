from unittest import mock

import pytest

from soliplex.lti import nonce as lti_nonce

SECRET_KEY = "test-secret-key"
NONCE = "test-nonce-value"
PLATFORM_ID = "moodle-workplace"


@pytest.fixture(autouse=True)
def _reset_seen_nonces():
    lti_nonce._seen_nonces.clear()
    yield
    lti_nonce._seen_nonces.clear()


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


class TestConsumeNonce:
    def test_first_call_returns_true(self):
        assert lti_nonce.consume_nonce("nonce-a") is True
        assert "nonce-a" in lti_nonce._seen_nonces

    def test_replay_returns_false(self):
        assert lti_nonce.consume_nonce("nonce-a") is True
        assert lti_nonce.consume_nonce("nonce-a") is False

    def test_distinct_nonces_both_accepted(self):
        assert lti_nonce.consume_nonce("nonce-a") is True
        assert lti_nonce.consume_nonce("nonce-b") is True

    def test_expired_nonce_can_be_reused(self):
        """An entry past its TTL should sweep out and the next call
        with the same value should be treated as fresh."""
        lti_nonce._seen_nonces["stale"] = 0.0  # epoch-old = long expired

        assert lti_nonce.consume_nonce("stale") is True
        assert lti_nonce._seen_nonces["stale"] > 0.0

    def test_expired_other_entries_swept_on_access(self):
        """Lazy sweep happens on each call, not just on collision."""
        lti_nonce._seen_nonces["old-1"] = 0.0
        lti_nonce._seen_nonces["old-2"] = 0.0

        lti_nonce.consume_nonce("fresh")

        assert "old-1" not in lti_nonce._seen_nonces
        assert "old-2" not in lti_nonce._seen_nonces
        assert "fresh" in lti_nonce._seen_nonces

    def test_eviction_when_cache_overflows(self, monkeypatch):
        """When the cache hits its cap, oldest entries are evicted."""
        monkeypatch.setattr(lti_nonce, "_SEEN_NONCE_LIMIT", 3)

        # All entries have valid (future) expiries, so the lazy
        # expiry sweep cannot evict them — only the cap can.
        future = 1e12
        lti_nonce._seen_nonces["k0"] = future + 0
        lti_nonce._seen_nonces["k1"] = future + 1
        lti_nonce._seen_nonces["k2"] = future + 2

        assert lti_nonce.consume_nonce("k3") is True

        # k0 had the earliest expiry → evicted first.
        assert "k0" not in lti_nonce._seen_nonces
        assert "k1" in lti_nonce._seen_nonces
        assert "k2" in lti_nonce._seen_nonces
        assert "k3" in lti_nonce._seen_nonces
