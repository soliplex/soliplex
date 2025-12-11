"""Tests for the Slack events API router."""

import hashlib
import hmac
import json
import time
from unittest import mock

import fastapi
import pytest

from soliplex import installation
from soliplex.views import slack as slack_views


# =============================================================================
# Test Data
# =============================================================================

SIGNING_SECRET = "test-signing-secret"
BOT_TOKEN = "xoxb-test-bot-token"
CHANNEL_ID = "C123ABC456"
CHANNEL_NAME = "soliplex_mcptest"
USER_ID = "U061F7AUR"
MESSAGE_TS = "1515449522.000016"
THREAD_TS = "1515449500.000001"


def make_slack_signature(body: bytes, timestamp: str) -> str:
    """Create a valid Slack signature for testing."""
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    return (
        "v0="
        + hmac.new(
            SIGNING_SECRET.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )


# =============================================================================
# SlackEventMessage Model Tests
# =============================================================================


class TestSlackEventMessage:
    """Tests for SlackEventMessage model."""

    def test_is_bot_message_with_bot_id(self):
        """Test is_bot_message returns True when bot_id is present."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            bot_id="B123456",
        )
        assert event.is_bot_message is True

    def test_is_bot_message_with_bot_subtype(self):
        """Test is_bot_message returns True when subtype is bot_message."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            subtype="bot_message",
        )
        assert event.is_bot_message is True

    def test_is_bot_message_false(self):
        """Test is_bot_message returns False for regular user messages."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
        )
        assert event.is_bot_message is False

    def test_is_dm_true(self):
        """Test is_dm returns True for direct messages."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            channel_type="im",
        )
        assert event.is_dm is True

    def test_is_dm_false(self):
        """Test is_dm returns False for channel messages."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            channel_type="channel",
        )
        assert event.is_dm is False

    def test_thread_id_with_thread_ts(self):
        """Test thread_id returns thread_ts when in a thread."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            thread_ts=THREAD_TS,
        )
        assert event.thread_id == THREAD_TS

    def test_thread_id_without_thread_ts(self):
        """Test thread_id returns ts when not in a thread."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
        )
        assert event.thread_id == MESSAGE_TS


# =============================================================================
# Markdown Conversion Tests
# =============================================================================


class TestConvertMarkdownToSlack:
    """Tests for convert_markdown_to_slack function."""

    def test_bold_conversion(self):
        """Test bold markdown conversion."""
        result = slack_views.convert_markdown_to_slack("This is **bold** text")
        assert result == "This is *bold* text"

    def test_link_conversion(self):
        """Test link markdown conversion."""
        result = slack_views.convert_markdown_to_slack(
            "Check [this link](https://example.com)"
        )
        assert result == "Check <https://example.com|this link>"

    def test_combined_conversion(self):
        """Test multiple markdown elements."""
        result = slack_views.convert_markdown_to_slack(
            "**Bold** and [link](https://example.com)"
        )
        assert result == "*Bold* and <https://example.com|link>"

    def test_no_conversion_needed(self):
        """Test text without markdown passes through unchanged."""
        text = "Plain text without markdown"
        result = slack_views.convert_markdown_to_slack(text)
        assert result == text


# =============================================================================
# Room ID Extraction Tests
# =============================================================================


class TestExtractRoomIdFromChannelName:
    """Tests for extract_room_id_from_channel_name function."""

    def test_valid_channel_name(self):
        """Test extraction from valid soliplex channel name."""
        result = slack_views.extract_room_id_from_channel_name("soliplex_mcptest")
        assert result == "mcptest"

    def test_another_valid_name(self):
        """Test extraction with different room ID."""
        result = slack_views.extract_room_id_from_channel_name("soliplex_faux")
        assert result == "faux"

    def test_invalid_channel_name(self):
        """Test extraction returns None for non-soliplex channels."""
        result = slack_views.extract_room_id_from_channel_name("general")
        assert result is None

    def test_empty_channel_name(self):
        """Test extraction returns None for empty string."""
        result = slack_views.extract_room_id_from_channel_name("")
        assert result is None

    def test_partial_prefix(self):
        """Test extraction returns None for partial prefix match."""
        result = slack_views.extract_room_id_from_channel_name("soliplex")
        assert result is None


# =============================================================================
# DM Room Selection Tests
# =============================================================================


class TestDMRoomSelection:
    """Tests for DM room selection state management."""

    def setup_method(self):
        """Clear the DM room selections before each test."""
        slack_views._dm_room_selections.clear()

    def test_set_and_get_selection(self):
        """Test setting and getting a room selection."""
        slack_views.set_dm_room_selection("D123", "mcptest")
        result = slack_views.get_dm_room_selection("D123")
        assert result == "mcptest"

    def test_get_nonexistent_selection(self):
        """Test getting a selection that doesn't exist."""
        result = slack_views.get_dm_room_selection("D999")
        assert result is None

    def test_clear_selection(self):
        """Test clearing a room selection."""
        slack_views.set_dm_room_selection("D123", "mcptest")
        slack_views.clear_dm_room_selection("D123")
        result = slack_views.get_dm_room_selection("D123")
        assert result is None

    def test_clear_nonexistent_selection(self):
        """Test clearing a selection that doesn't exist (should not raise)."""
        slack_views.clear_dm_room_selection("D999")  # Should not raise


class TestParseRoomSelection:
    """Tests for parse_room_selection function."""

    def test_reset_commands(self):
        """Test reset commands return __RESET__."""
        rooms = ["mcptest", "faux"]
        for cmd in ("switch", "change", "reset", "menu", "rooms"):
            result = slack_views.parse_room_selection(cmd, rooms)
            assert result == "__RESET__", f"Failed for command: {cmd}"

    def test_numeric_selection(self):
        """Test selecting room by number."""
        rooms = ["mcptest", "faux", "another"]
        assert slack_views.parse_room_selection("1", rooms) == "mcptest"
        assert slack_views.parse_room_selection("2", rooms) == "faux"
        assert slack_views.parse_room_selection("3", rooms) == "another"

    def test_invalid_numeric_selection(self):
        """Test invalid numeric selection returns None."""
        rooms = ["mcptest", "faux"]
        assert slack_views.parse_room_selection("0", rooms) is None
        assert slack_views.parse_room_selection("5", rooms) is None

    def test_name_selection(self):
        """Test selecting room by name."""
        rooms = ["mcptest", "faux"]
        assert slack_views.parse_room_selection("mcptest", rooms) == "mcptest"
        assert slack_views.parse_room_selection("MCPTEST", rooms) == "mcptest"
        assert slack_views.parse_room_selection("faux", rooms) == "faux"

    def test_invalid_name_selection(self):
        """Test invalid room name returns None."""
        rooms = ["mcptest", "faux"]
        assert slack_views.parse_room_selection("nonexistent", rooms) is None

    def test_whitespace_handling(self):
        """Test whitespace is trimmed from input."""
        rooms = ["mcptest"]
        assert slack_views.parse_room_selection("  mcptest  ", rooms) == "mcptest"
        assert slack_views.parse_room_selection("  1  ", rooms) == "mcptest"


class TestFormatRoomMenu:
    """Tests for format_room_menu function."""

    def test_basic_menu(self):
        """Test basic room menu formatting."""
        rooms = {
            "mcptest": {"name": "MCP Test Room", "description": ""},
            "faux": {"name": "Faux Room", "description": "A fake room"},
        }
        result = slack_views.format_room_menu(rooms)
        assert "*Please select a room to chat with:*" in result
        assert "*1.* MCP Test Room (`mcptest`)" in result
        assert "*2.* Faux Room (`faux`)" in result
        assert "_A fake room_" in result
        assert "_Reply with the number or room name to select._" in result

    def test_empty_rooms(self):
        """Test menu with no rooms."""
        result = slack_views.format_room_menu({})
        assert "*Please select a room to chat with:*" in result


# =============================================================================
# Signature Verification Tests
# =============================================================================


class TestVerifySlackSignature:
    """Tests for verify_slack_signature function."""

    @pytest.mark.anyio
    async def test_missing_signing_secret(self):
        """Test error when SLACK_SIGNING_SECRET is not configured."""
        request = mock.create_autospec(fastapi.Request)
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.side_effect = KeyError("SLACK_SIGNING_SECRET")

        with pytest.raises(fastapi.HTTPException) as exc:
            await slack_views.verify_slack_signature(request, the_installation)

        assert exc.value.status_code == 500
        assert "not configured" in exc.value.detail

    @pytest.mark.anyio
    async def test_missing_headers(self):
        """Test error when Slack headers are missing."""
        request = mock.create_autospec(fastapi.Request)
        request.headers = {}
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = SIGNING_SECRET

        with pytest.raises(fastapi.HTTPException) as exc:
            await slack_views.verify_slack_signature(request, the_installation)

        assert exc.value.status_code == 400
        assert "Missing" in exc.value.detail

    @pytest.mark.anyio
    async def test_old_timestamp(self):
        """Test error when timestamp is too old."""
        old_timestamp = str(int(time.time()) - 400)  # 6+ minutes old
        request = mock.create_autospec(fastapi.Request)
        request.headers = {
            "X-Slack-Request-Timestamp": old_timestamp,
            "X-Slack-Signature": "v0=dummy",
        }
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = SIGNING_SECRET

        with pytest.raises(fastapi.HTTPException) as exc:
            await slack_views.verify_slack_signature(request, the_installation)

        assert exc.value.status_code == 400
        assert "too old" in exc.value.detail

    @pytest.mark.anyio
    async def test_invalid_signature(self):
        """Test error when signature is invalid."""
        timestamp = str(int(time.time()))
        body = b'{"test": "payload"}'

        request = mock.create_autospec(fastapi.Request)
        request.headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": "v0=invalid_signature",
        }
        request.body = mock.AsyncMock(return_value=body)
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = SIGNING_SECRET

        with pytest.raises(fastapi.HTTPException) as exc:
            await slack_views.verify_slack_signature(request, the_installation)

        assert exc.value.status_code == 400
        assert "Invalid" in exc.value.detail

    @pytest.mark.anyio
    async def test_valid_signature(self):
        """Test successful signature verification."""
        timestamp = str(int(time.time()))
        body = b'{"test": "payload"}'
        signature = make_slack_signature(body, timestamp)

        request = mock.create_autospec(fastapi.Request)
        request.headers = {
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        }
        request.body = mock.AsyncMock(return_value=body)
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = SIGNING_SECRET

        result = await slack_views.verify_slack_signature(request, the_installation)
        assert result == body


# =============================================================================
# Slack Events Endpoint Tests
# =============================================================================


class TestSlackEventsEndpoint:
    """Tests for the /slack/events endpoint."""

    def setup_method(self):
        """Clear caches before each test."""
        slack_views._channel_name_cache.clear()
        slack_views._dm_room_selections.clear()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_url_verification(self, mock_verify):
        """Test URL verification challenge response."""
        challenge = "test-challenge-12345"
        payload = {
            "type": "url_verification",
            "challenge": challenge,
        }
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"challenge": challenge}
        background_tasks.add_task.assert_not_called()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_url_verification_missing_challenge(self, mock_verify):
        """Test URL verification fails without challenge."""
        payload = {"type": "url_verification"}
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        with pytest.raises(fastapi.HTTPException) as exc:
            await slack_views.slack_events(request, background_tasks, the_installation)

        assert exc.value.status_code == 400
        assert "Missing challenge" in exc.value.detail

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_event_callback_message(self, mock_verify):
        """Test event callback schedules background task for messages."""
        payload = {
            "type": "event_callback",
            "token": "test-token",
            "team_id": "T123",
            "event": {
                "type": "message",
                "user": USER_ID,
                "text": "Hello bot!",
                "ts": MESSAGE_TS,
                "channel": CHANNEL_ID,
            },
            "event_id": "Ev123",
            "event_time": 1515449522,
        }
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"ok": True}
        background_tasks.add_task.assert_called_once()
        call_args = background_tasks.add_task.call_args
        assert call_args[0][0] == slack_views.handle_message_event

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_event_callback_app_mention(self, mock_verify):
        """Test event callback schedules background task for app mentions."""
        payload = {
            "type": "event_callback",
            "token": "test-token",
            "team_id": "T123",
            "event": {
                "type": "app_mention",
                "user": USER_ID,
                "text": "<@U0LAN0Z89> hello",
                "ts": MESSAGE_TS,
                "channel": CHANNEL_ID,
            },
            "event_id": "Ev123",
            "event_time": 1515449522,
        }
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"ok": True}
        background_tasks.add_task.assert_called_once()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_unknown_event_type(self, mock_verify):
        """Test unknown event types are handled gracefully."""
        payload = {"type": "unknown_type"}
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"ok": True}
        background_tasks.add_task.assert_not_called()


# =============================================================================
# Message Event Handler Tests
# =============================================================================


class TestHandleMessageEvent:
    """Tests for handle_message_event function."""

    def setup_method(self):
        """Clear caches before each test."""
        slack_views._channel_name_cache.clear()
        slack_views._dm_room_selections.clear()

    @pytest.mark.anyio
    async def test_skip_bot_message(self):
        """Test bot messages are skipped."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            bot_id="B123456",
            text="Bot message",
        )
        the_installation = mock.create_autospec(installation.Installation)

        # Should return without doing anything (no get_secret call)
        await slack_views.handle_message_event(event, the_installation)
        the_installation.get_secret.assert_not_called()

    @pytest.mark.anyio
    async def test_skip_empty_text(self):
        """Test messages with no text are skipped."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text=None,
        )
        the_installation = mock.create_autospec(installation.Installation)

        await slack_views.handle_message_event(event, the_installation)
        the_installation.get_secret.assert_not_called()

    @pytest.mark.anyio
    async def test_missing_bot_token(self):
        """Test handling when SLACK_BOT_TOKEN is not configured."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.side_effect = KeyError("SLACK_BOT_TOKEN")

        # Should return without crashing
        await slack_views.handle_message_event(event, the_installation)

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "process_message_with_agent")
    @mock.patch.object(slack_views.SlackClient, "get_channel_info")
    async def test_channel_message_uses_cache(self, mock_get_info, mock_process):
        """Test channel name is cached after first lookup."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello",
            channel_type="channel",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = BOT_TOKEN

        mock_get_info.return_value = {"name": CHANNEL_NAME}

        # First call - should fetch from API
        await slack_views.handle_message_event(event, the_installation)
        mock_get_info.assert_called_once()
        mock_process.assert_called_once()

        # Check cache was populated
        assert slack_views._channel_name_cache[CHANNEL_ID] == CHANNEL_NAME

        # Reset mocks
        mock_get_info.reset_mock()
        mock_process.reset_mock()

        # Second call - should use cache
        await slack_views.handle_message_event(event, the_installation)
        mock_get_info.assert_not_called()  # Should not call API again
        mock_process.assert_called_once()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "handle_dm_message")
    async def test_dm_message_routes_to_handler(self, mock_handle_dm):
        """Test DM messages are routed to handle_dm_message."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel="D123456",
            user=USER_ID,
            text="Hello",
            channel_type="im",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = BOT_TOKEN

        await slack_views.handle_message_event(event, the_installation)

        mock_handle_dm.assert_called_once()


# =============================================================================
# SlackClient Tests
# =============================================================================


class TestSlackClient:
    """Tests for SlackClient class."""

    @pytest.mark.anyio
    @mock.patch("httpx.AsyncClient")
    async def test_post_message(self, mock_client_class):
        """Test posting a message."""
        mock_client = mock.AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = mock.Mock()
        mock_response.json.return_value = {"ok": True, "ts": MESSAGE_TS}
        mock_client.request.return_value = mock_response

        client = slack_views.SlackClient(BOT_TOKEN)
        result = await client.post_message(
            channel=CHANNEL_ID,
            text="Hello!",
            thread_ts=THREAD_TS,
        )

        assert result == {"ok": True, "ts": MESSAGE_TS}
        mock_client.request.assert_called_once()
        call_kwargs = mock_client.request.call_args[1]
        assert call_kwargs["json"]["channel"] == CHANNEL_ID
        assert call_kwargs["json"]["text"] == "Hello!"
        assert call_kwargs["json"]["thread_ts"] == THREAD_TS

    @pytest.mark.anyio
    @mock.patch("httpx.AsyncClient")
    async def test_update_message(self, mock_client_class):
        """Test updating a message."""
        mock_client = mock.AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = mock.Mock()
        mock_response.json.return_value = {"ok": True}
        mock_client.request.return_value = mock_response

        client = slack_views.SlackClient(BOT_TOKEN)
        result = await client.update_message(
            channel=CHANNEL_ID,
            ts=MESSAGE_TS,
            text="Updated!",
        )

        assert result == {"ok": True}
        call_kwargs = mock_client.request.call_args[1]
        assert call_kwargs["json"]["ts"] == MESSAGE_TS
        assert call_kwargs["json"]["text"] == "Updated!"

    @pytest.mark.anyio
    @mock.patch("httpx.AsyncClient")
    async def test_get_channel_info(self, mock_client_class):
        """Test getting channel info."""
        mock_client = mock.AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "ok": True,
            "channel": {"id": CHANNEL_ID, "name": CHANNEL_NAME},
        }
        mock_client.request.return_value = mock_response

        client = slack_views.SlackClient(BOT_TOKEN)
        result = await client.get_channel_info(CHANNEL_ID)

        assert result == {"id": CHANNEL_ID, "name": CHANNEL_NAME}

    @pytest.mark.anyio
    @mock.patch("httpx.AsyncClient")
    async def test_get_thread_messages(self, mock_client_class):
        """Test getting thread messages."""
        mock_client = mock.AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = mock.Mock()
        mock_response.json.return_value = {
            "ok": True,
            "messages": [
                {"text": "First", "ts": "1"},
                {"text": "Second", "ts": "2"},
            ],
        }
        mock_client.request.return_value = mock_response

        client = slack_views.SlackClient(BOT_TOKEN)
        result = await client.get_thread_messages(CHANNEL_ID, THREAD_TS)

        assert len(result) == 2
        assert result[0]["text"] == "First"

    @pytest.mark.anyio
    @mock.patch("httpx.AsyncClient")
    async def test_post_message_without_thread_ts(self, mock_client_class):
        """Test posting a message without thread_ts (covers lines 133-135)."""
        mock_client = mock.AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = mock.Mock()
        mock_response.json.return_value = {"ok": True, "ts": MESSAGE_TS}
        mock_client.request.return_value = mock_response

        client = slack_views.SlackClient(BOT_TOKEN)
        result = await client.post_message(
            channel=CHANNEL_ID,
            text="Hello!",
            # No thread_ts
        )

        assert result == {"ok": True, "ts": MESSAGE_TS}
        call_kwargs = mock_client.request.call_args[1]
        assert "thread_ts" not in call_kwargs["json"]


# =============================================================================
# Handle Message Event - Channel Info Failure Tests
# =============================================================================


class TestHandleMessageEventChannelInfoFailure:
    """Tests for handle_message_event when get_channel_info fails (lines 396-398)."""

    def setup_method(self):
        """Clear caches before each test."""
        slack_views._channel_name_cache.clear()
        slack_views._dm_room_selections.clear()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "process_message_with_agent")
    @mock.patch.object(slack_views.SlackClient, "get_channel_info")
    async def test_channel_info_failure_uses_default_room(
        self, mock_get_info, mock_process
    ):
        """Test that when get_channel_info fails, default room is used."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello",
            channel_type="channel",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_secret.return_value = BOT_TOKEN

        # Make get_channel_info raise an exception
        mock_get_info.side_effect = Exception("API error")

        await slack_views.handle_message_event(event, the_installation)

        # Should still call process_message_with_agent with default room
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        # room_id should be "mcptest" (the default)
        assert call_args[0][3] == "mcptest"


# =============================================================================
# Handle DM Message Tests (lines 417-478)
# =============================================================================


class TestHandleDMMessage:
    """Tests for handle_dm_message function."""

    def setup_method(self):
        """Clear caches before each test."""
        slack_views._channel_name_cache.clear()
        slack_views._dm_room_selections.clear()

    def _make_mock_room_config(self, name: str, description: str = ""):
        """Create a mock room config."""
        config = mock.Mock()
        config.name = name
        config.description = description
        return config

    @pytest.mark.anyio
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_dm_reset_command_shows_menu(self, mock_post):
        """Test reset command clears selection and shows menu."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel="D123456",
            user=USER_ID,
            text="switch",
            channel_type="im",
        )
        the_installation = mock.create_autospec(installation.Installation)
        room_configs = {
            "mcptest": self._make_mock_room_config("MCP Test", "Test room"),
            "faux": self._make_mock_room_config("Faux Room"),
        }
        the_installation.get_room_configs.return_value = room_configs

        # Pre-set a selection
        slack_views.set_dm_room_selection("D123456", "mcptest")

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.handle_dm_message(event, the_installation, slack_client)

        # Selection should be cleared
        assert slack_views.get_dm_room_selection("D123456") is None
        # Menu should be posted
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "Please select a room" in call_kwargs["text"]

    @pytest.mark.anyio
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_dm_no_selection_shows_menu(self, mock_post):
        """Test that first message without selection shows menu."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel="D123456",
            user=USER_ID,
            text="Hello there!",  # Not a valid selection
            channel_type="im",
        )
        the_installation = mock.create_autospec(installation.Installation)
        room_configs = {
            "mcptest": self._make_mock_room_config("MCP Test"),
        }
        the_installation.get_room_configs.return_value = room_configs

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.handle_dm_message(event, the_installation, slack_client)

        # Menu should be posted
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "Please select a room" in call_kwargs["text"]

    @pytest.mark.anyio
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_dm_valid_selection_sets_room(self, mock_post):
        """Test valid room selection is saved and confirmed."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel="D123456",
            user=USER_ID,
            text="1",  # Select first room
            channel_type="im",
        )
        the_installation = mock.create_autospec(installation.Installation)
        room_configs = {
            "mcptest": self._make_mock_room_config("MCP Test"),
            "faux": self._make_mock_room_config("Faux Room"),
        }
        the_installation.get_room_configs.return_value = room_configs

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.handle_dm_message(event, the_installation, slack_client)

        # Selection should be saved
        assert slack_views.get_dm_room_selection("D123456") == "mcptest"
        # Confirmation should be posted
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert "Selected" in call_kwargs["text"]
        assert "MCP Test" in call_kwargs["text"]

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "process_message_with_agent")
    async def test_dm_with_existing_selection_processes_message(self, mock_process):
        """Test message with existing selection is processed."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel="D123456",
            user=USER_ID,
            text="What is the weather?",
            channel_type="im",
        )
        the_installation = mock.create_autospec(installation.Installation)
        room_configs = {
            "mcptest": self._make_mock_room_config("MCP Test"),
        }
        the_installation.get_room_configs.return_value = room_configs

        # Pre-set a selection
        slack_views.set_dm_room_selection("D123456", "mcptest")

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.handle_dm_message(event, the_installation, slack_client)

        # Should process with the selected room
        mock_process.assert_called_once()
        call_args = mock_process.call_args
        assert call_args[0][3] == "mcptest"  # room_id


# =============================================================================
# Process Message With Agent Tests (lines 490-576)
# =============================================================================


class TestProcessMessageWithAgent:
    """Tests for process_message_with_agent function."""

    def setup_method(self):
        """Clear caches before each test."""
        slack_views._channel_name_cache.clear()
        slack_views._dm_room_selections.clear()

    @pytest.mark.anyio
    @mock.patch("soliplex.agents.AgentDependencies")
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_success(
        self, mock_post, mock_update, mock_agent_deps
    ):
        """Test successful message processing."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        mock_agent = mock.AsyncMock()
        mock_result = mock.Mock()
        mock_result.output = "Hello human!"
        mock_agent.run.return_value = mock_result
        the_installation.get_agent_for_room.return_value = mock_agent

        mock_post.return_value = {"ts": "thinking_ts"}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "mcptest"
        )

        # Should post thinking message
        mock_post.assert_called_once()
        assert "_Thinking..._" in mock_post.call_args[1]["text"]

        # Should update with response
        mock_update.assert_called_once()
        assert "Hello human!" in mock_update.call_args[1]["text"]

    @pytest.mark.anyio
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_room_not_found(self, mock_post, mock_update):
        """Test handling when room is not found."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_agent_for_room.side_effect = KeyError("Room not found")

        mock_post.return_value = {"ts": "thinking_ts"}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "nonexistent"
        )

        # Should update with error
        mock_update.assert_called_once()
        assert "not configured" in mock_update.call_args[1]["text"]

    @pytest.mark.anyio
    @mock.patch("soliplex.agents.AgentDependencies")
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "get_thread_messages")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_with_thread_context(
        self, mock_post, mock_get_thread, mock_update, mock_agent_deps
    ):
        """Test message processing with thread context."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Follow up question",
            thread_ts=THREAD_TS,  # In a thread
        )
        the_installation = mock.create_autospec(installation.Installation)
        mock_agent = mock.AsyncMock()
        mock_result = mock.Mock()
        mock_result.output = "Here's the answer!"
        mock_agent.run.return_value = mock_result
        the_installation.get_agent_for_room.return_value = mock_agent

        mock_post.return_value = {"ts": "thinking_ts"}
        mock_get_thread.return_value = [
            {"text": "First message", "ts": "1"},
            {"text": "Bot response", "ts": "2", "bot_id": "B123"},
            {"text": "Follow up question", "ts": MESSAGE_TS},  # Current message
        ]

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "mcptest"
        )

        # Should fetch thread messages
        mock_get_thread.assert_called_once()

        # Agent should be called with context
        mock_agent.run.assert_called_once()
        prompt = mock_agent.run.call_args[0][0]
        assert "Previous conversation:" in prompt

    @pytest.mark.anyio
    @mock.patch("soliplex.agents.AgentDependencies")
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_agent_error(
        self, mock_post, mock_update, mock_agent_deps
    ):
        """Test handling when agent raises an error."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        mock_agent = mock.AsyncMock()
        mock_agent.run.side_effect = Exception("Agent error")
        the_installation.get_agent_for_room.return_value = mock_agent

        mock_post.return_value = {"ts": "thinking_ts"}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "mcptest"
        )

        # Should update with error message
        mock_update.assert_called_once()
        assert "error" in mock_update.call_args[1]["text"].lower()

    @pytest.mark.anyio
    @mock.patch("soliplex.agents.AgentDependencies")
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_no_thinking_ts(
        self, mock_post, mock_update, mock_agent_deps
    ):
        """Test handling when thinking message doesn't return ts."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        mock_agent = mock.AsyncMock()
        mock_result = mock.Mock()
        mock_result.output = "Hello!"
        mock_agent.run.return_value = mock_result
        the_installation.get_agent_for_room.return_value = mock_agent

        # No ts in response
        mock_post.return_value = {"ok": True}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "mcptest"
        )

        # Should not try to update (no ts)
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_room_not_found_no_thinking_ts(
        self, mock_post, mock_update
    ):
        """Test room not found when thinking message has no ts (covers 530->536)."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        the_installation.get_agent_for_room.side_effect = KeyError("Room not found")

        # No ts in response - thinking_ts will be None
        mock_post.return_value = {"ok": True}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "nonexistent"
        )

        # Should NOT try to update (no ts to update)
        mock_update.assert_not_called()

    @pytest.mark.anyio
    @mock.patch("soliplex.agents.AgentDependencies")
    @mock.patch.object(slack_views.SlackClient, "update_message")
    @mock.patch.object(slack_views.SlackClient, "post_message")
    async def test_process_message_agent_error_no_thinking_ts(
        self, mock_post, mock_update, mock_agent_deps
    ):
        """Test agent error when thinking message has no ts (covers 575->exit)."""
        event = slack_views.SlackEventMessage(
            type="message",
            ts=MESSAGE_TS,
            channel=CHANNEL_ID,
            user=USER_ID,
            text="Hello bot!",
        )
        the_installation = mock.create_autospec(installation.Installation)
        mock_agent = mock.AsyncMock()
        mock_agent.run.side_effect = Exception("Agent error")
        the_installation.get_agent_for_room.return_value = mock_agent

        # No ts in response - thinking_ts will be None
        mock_post.return_value = {"ok": True}

        slack_client = slack_views.SlackClient(BOT_TOKEN)
        await slack_views.process_message_with_agent(
            event, the_installation, slack_client, "mcptest"
        )

        # Should NOT try to update (no ts to update)
        mock_update.assert_not_called()


# =============================================================================
# Event Callback - Non-message Event Tests (line 633->641)
# =============================================================================


class TestEventCallbackNonMessageEvent:
    """Tests for event_callback with non-message events."""

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_event_callback_reaction_added(self, mock_verify):
        """Test event callback doesn't schedule task for reaction_added events."""
        payload = {
            "type": "event_callback",
            "token": "test-token",
            "team_id": "T123",
            "event": {
                "type": "reaction_added",  # Not message or app_mention
                "user": USER_ID,
                "ts": MESSAGE_TS,
                "channel": CHANNEL_ID,
                "reaction": "thumbsup",
            },
            "event_id": "Ev123",
            "event_time": 1515449522,
        }
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"ok": True}
        # Should NOT schedule background task for non-message events
        background_tasks.add_task.assert_not_called()

    @pytest.mark.anyio
    @mock.patch.object(slack_views, "verify_slack_signature")
    async def test_event_callback_channel_created(self, mock_verify):
        """Test event callback doesn't schedule task for channel_created events."""
        payload = {
            "type": "event_callback",
            "token": "test-token",
            "team_id": "T123",
            "event": {
                "type": "channel_created",  # Not message or app_mention
                "ts": MESSAGE_TS,
                "channel": CHANNEL_ID,
            },
            "event_id": "Ev123",
            "event_time": 1515449522,
        }
        mock_verify.return_value = json.dumps(payload).encode()

        request = mock.create_autospec(fastapi.Request)
        background_tasks = mock.create_autospec(fastapi.BackgroundTasks)
        the_installation = mock.create_autospec(installation.Installation)

        result = await slack_views.slack_events(
            request, background_tasks, the_installation
        )

        assert result == {"ok": True}
        background_tasks.add_task.assert_not_called()
