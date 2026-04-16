import pytest

from soliplex.config import lti as config_lti
from soliplex.lti import platform as lti_platform
from tests.unit.conftest import LTI_TEST_CLIENT_ID as CLIENT_ID
from tests.unit.conftest import LTI_TEST_DEFAULT_ROOM as DEFAULT_ROOM
from tests.unit.conftest import LTI_TEST_ISSUER as ISSUER
from tests.unit.conftest import LTI_TEST_PLATFORM_ID as PLATFORM_ID


def _make_platform(**overrides):
    defaults = {
        "id": PLATFORM_ID,
        "issuer": ISSUER,
        "client_id": CLIENT_ID,
        "auth_login_url": "https://moodle.example.com/auth.php",
        "auth_token_url": "https://moodle.example.com/token.php",
        "key_set_url": "https://moodle.example.com/certs.php",
        "default_room_id": DEFAULT_ROOM,
    }
    return config_lti.LTIPlatformConfig(**(defaults | overrides))


class TestFindPlatform:
    def test_found(self):
        p = _make_platform()
        found = lti_platform.find_platform(
            [p], issuer=ISSUER, client_id=CLIENT_ID
        )
        assert found is p

    def test_not_found_empty(self):
        with pytest.raises(lti_platform.UnknownLTIPlatform) as exc:
            lti_platform.find_platform([], issuer=ISSUER, client_id=CLIENT_ID)
        assert exc.value.issuer == ISSUER
        assert exc.value.client_id == CLIENT_ID

    def test_not_found_wrong_issuer(self):
        p = _make_platform()
        with pytest.raises(lti_platform.UnknownLTIPlatform):
            lti_platform.find_platform(
                [p], issuer="https://other.com", client_id=CLIENT_ID
            )

    def test_not_found_wrong_client_id(self):
        p = _make_platform()
        with pytest.raises(lti_platform.UnknownLTIPlatform):
            lti_platform.find_platform([p], issuer=ISSUER, client_id="wrong")


class TestFindPlatformById:
    def test_found(self):
        p = _make_platform()
        found = lti_platform.find_platform_by_id([p], PLATFORM_ID)
        assert found is p

    def test_not_found_returns_none(self):
        p = _make_platform()
        found = lti_platform.find_platform_by_id([p], "nonexistent-id")
        assert found is None

    def test_empty_list_returns_none(self):
        found = lti_platform.find_platform_by_id([], PLATFORM_ID)
        assert found is None

    def test_multiple_platforms_finds_correct_one(self):
        p1 = _make_platform(id="platform-1")
        p2 = _make_platform(
            id="platform-2", issuer="https://other.example.com"
        )
        found = lti_platform.find_platform_by_id([p1, p2], "platform-2")
        assert found is p2


class TestCheckDeployment:
    def test_valid(self):
        p = _make_platform(deployment_ids=["1", "2"])
        lti_platform.check_deployment(p, "1")

    def test_invalid(self):
        p = _make_platform(deployment_ids=["1"])
        with pytest.raises(lti_platform.InvalidLTIDeployment) as exc:
            lti_platform.check_deployment(p, "99")
        assert exc.value.deployment_id == "99"
        assert exc.value.platform_id == PLATFORM_ID


class TestResolveRoomId:
    def test_from_target_link_uri(self):
        p = _make_platform()
        found = lti_platform.resolve_room_id(
            p,
            target_link_uri=("https://soliplex.example.com/lti/chat/my-room"),
        )
        assert found == "my-room"

    def test_from_target_link_uri_trailing_slash(self):
        p = _make_platform()
        found = lti_platform.resolve_room_id(
            p,
            target_link_uri=("https://soliplex.example.com/lti/chat/my-room/"),
        )
        assert found == "my-room"

    def test_target_link_uri_no_chat_segment(self):
        p = _make_platform()
        found = lti_platform.resolve_room_id(
            p,
            target_link_uri=("https://soliplex.example.com/lti/launch"),
        )
        assert found == DEFAULT_ROOM

    def test_from_course_room_map(self):
        p = _make_platform(course_room_map={"101": "room-101"})
        found = lti_platform.resolve_room_id(p, course_id="101")
        assert found == "room-101"

    def test_course_id_not_in_map(self):
        p = _make_platform(course_room_map={"101": "room-101"})
        found = lti_platform.resolve_room_id(p, course_id="999")
        assert found == DEFAULT_ROOM

    def test_default_room(self):
        p = _make_platform()
        found = lti_platform.resolve_room_id(p)
        assert found == DEFAULT_ROOM

    def test_target_link_uri_chat_trailing_slash(self):
        """chat/ trailing slash gets stripped, falls to default"""
        p = _make_platform()
        found = lti_platform.resolve_room_id(
            p,
            target_link_uri=("https://soliplex.example.com/lti/chat/"),
        )
        # After rstrip("/"), URL ends in /chat, so parts[-2]
        # is "lti", not "chat" → falls to default
        assert found == DEFAULT_ROOM
