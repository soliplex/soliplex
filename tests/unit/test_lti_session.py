from unittest import mock

from soliplex.lti import LTI_CLAIM_RESOURCE_LINK
from soliplex.lti import LTI_CLAIM_ROLES
from soliplex.lti import session as lti_session

SECRET_KEY = "test-secret-key"
ROOM_ID = "moodle-tools"
PLATFORM_ID = "moodle-workplace"


class TestClaimsFromLtiPayload:
    def test_full_payload(self):
        payload = {
            "sub": "user-123",
            "email": "phred@example.com",
            "given_name": "Phred",
            "family_name": "Phlyntstone",
            "name": "Phred Phlyntstone",
            LTI_CLAIM_ROLES: [
                "http://purl.imsglobal.org/vocab/lis/v2/membership#Learner"
            ],
            LTI_CLAIM_RESOURCE_LINK: {
                "id": "link-456",
                "title": "Soliplex Chat",
            },
        }

        found = lti_session.claims_from_lti_payload(payload)

        assert found["sub"] == "user-123"
        assert found["email"] == "phred@example.com"
        assert found["given_name"] == "Phred"
        assert found["family_name"] == "Phlyntstone"
        assert found["name"] == "Phred Phlyntstone"
        assert found["preferred_username"] == ("phred@example.com")
        assert len(found["lti_roles"]) == 1
        assert found["lti_resource_link_id"] == "link-456"

    def test_minimal_payload(self):
        payload = {"sub": "user-123"}

        found = lti_session.claims_from_lti_payload(payload)

        assert found["sub"] == "user-123"
        assert found["email"] == "user-123"
        assert found["given_name"] == ""
        assert found["family_name"] == ""
        assert found["name"] == "user-123"
        assert found["preferred_username"] == "user-123"
        assert found["lti_roles"] == []
        assert found["lti_resource_link_id"] == ""

    def test_name_fallback_to_parts(self):
        """When name is empty, falls back to given+family"""
        payload = {
            "sub": "u1",
            "given_name": "Phred",
            "family_name": "Phlyntstone",
        }

        found = lti_session.claims_from_lti_payload(payload)

        assert found["name"] == "Phred Phlyntstone"

    def test_name_fallback_to_sub(self):
        """When name and given/family are empty, falls to sub"""
        payload = {"sub": "user-anon"}

        found = lti_session.claims_from_lti_payload(payload)

        assert found["name"] == "user-anon"

    def test_email_preferred_over_sub_for_username(self):
        payload = {
            "sub": "user-123",
            "email": "phred@example.com",
        }

        found = lti_session.claims_from_lti_payload(payload)

        assert found["preferred_username"] == ("phred@example.com")


class TestSessionTokenRoundTrip:
    def test_mint_and_validate(self):
        claims = {
            "sub": "user-123",
            "email": "phred@example.com",
        }

        token = lti_session.mint_session_token(
            SECRET_KEY, claims, ROOM_ID, PLATFORM_ID
        )

        found = lti_session.validate_session_token(
            SECRET_KEY, token, max_age=3600
        )

        assert found is not None
        assert found["sub"] == "user-123"
        assert found["email"] == "phred@example.com"
        # Internal fields are stripped by validate_session_token.
        assert "_room_id" not in found
        assert "_platform_id" not in found

    def test_validate_bad_token(self):
        found = lti_session.validate_session_token(
            SECRET_KEY, "garbage-token", max_age=3600
        )
        assert found is None

    def test_validate_wrong_key(self):
        claims = {"sub": "user-123"}
        token = lti_session.mint_session_token(
            SECRET_KEY, claims, ROOM_ID, PLATFORM_ID
        )

        found = lti_session.validate_session_token(
            "wrong-key", token, max_age=3600
        )
        assert found is None

    @mock.patch("soliplex.mcp_auth.validate_url_safe_token")
    def test_validate_expired(self, vt):
        """Expired token returns None"""
        vt.return_value = None

        found = lti_session.validate_session_token(
            SECRET_KEY, "some-token", max_age=1
        )
        assert found is None


class TestPeekPlatformId:
    def test_round_trip(self):
        token = lti_session.mint_session_token(
            SECRET_KEY, {"sub": "u"}, ROOM_ID, PLATFORM_ID
        )
        assert lti_session.peek_platform_id(SECRET_KEY, token) == PLATFORM_ID

    def test_garbage_token(self):
        assert lti_session.peek_platform_id(SECRET_KEY, "junk") is None

    def test_wrong_key(self):
        token = lti_session.mint_session_token(
            SECRET_KEY, {"sub": "u"}, ROOM_ID, PLATFORM_ID
        )
        assert lti_session.peek_platform_id("wrong-key", token) is None

    def test_age_check_skipped(self):
        """peek_platform_id must work regardless of token age — the
        caller looks up the platform first, then checks age via the
        platform-specific session_ttl."""
        with mock.patch("soliplex.mcp_auth.validate_url_safe_token") as v:
            v.return_value = {"_platform_id": PLATFORM_ID}
            found = lti_session.peek_platform_id(SECRET_KEY, "tok")
            assert found == PLATFORM_ID
            # max_age was explicitly None.
            _, kwargs = v.call_args
            assert kwargs.get("max_age") is None
