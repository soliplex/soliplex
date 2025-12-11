"""Slack events API router.

Implements a Slack bot that connects to Soliplex rooms/agents.
Based on: https://ai-sdk.dev/cookbook/guides/slackbot
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import typing

import fastapi
import httpx
import pydantic
from fastapi import BackgroundTasks

from soliplex import installation
from soliplex import models

logger = logging.getLogger(__name__)

router = fastapi.APIRouter(tags=["slack"])

depend_the_installation = installation.depend_the_installation


# =============================================================================
# Pydantic Models for Slack Events
# =============================================================================


class SlackUrlVerificationPayload(pydantic.BaseModel):
    """Slack URL verification challenge payload."""

    type: typing.Literal["url_verification"]
    token: str | None = None
    challenge: str


class SlackEventMessage(pydantic.BaseModel):
    """A message event from Slack."""

    type: str  # "message" or "app_mention"
    subtype: str | None = None
    user: str | None = None
    text: str | None = None
    ts: str  # Timestamp, also serves as message ID
    channel: str
    channel_type: str | None = None  # "im" for DMs, "channel" for public, etc.
    thread_ts: str | None = None  # Parent thread timestamp (if in a thread)
    bot_id: str | None = None  # Present if message is from a bot

    @property
    def is_bot_message(self) -> bool:
        """Check if this message was sent by a bot."""
        return self.bot_id is not None or self.subtype == "bot_message"

    @property
    def is_dm(self) -> bool:
        """Check if this message is a direct message."""
        return self.channel_type == "im"

    @property
    def thread_id(self) -> str:
        """Get the thread ID (thread_ts if in thread, otherwise ts)."""
        return self.thread_ts or self.ts


class SlackEventCallbackPayload(pydantic.BaseModel):
    """Slack event callback payload."""

    type: typing.Literal["event_callback"]
    token: str | None = None
    team_id: str
    event: SlackEventMessage
    event_id: str
    event_time: int


# Union type for all possible Slack payloads
SlackEventPayload = SlackUrlVerificationPayload | SlackEventCallbackPayload


# =============================================================================
# Slack API Client
# =============================================================================


class SlackClient:
    """Simple async Slack API client."""

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self.base_url = "https://slack.com/api"

    async def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> dict:
        """Make a request to the Slack API."""
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"{self.base_url}/{endpoint}",
                headers=headers,
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    async def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        mrkdwn: bool = True,
    ) -> dict:
        """Post a message to a Slack channel."""
        payload = {
            "channel": channel,
            "text": text,
            "mrkdwn": mrkdwn,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts
        return await self._request("POST", "chat.postMessage", json=payload)

    async def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
    ) -> dict:
        """Update an existing message."""
        payload = {
            "channel": channel,
            "ts": ts,
            "text": text,
        }
        return await self._request("POST", "chat.update", json=payload)

    async def get_thread_messages(
        self,
        channel: str,
        thread_ts: str,
        limit: int = 100,
    ) -> list[dict]:
        """Get messages in a thread."""
        result = await self._request(
            "GET",
            "conversations.replies",
            params={
                "channel": channel,
                "ts": thread_ts,
                "limit": limit,
            },
        )
        return result.get("messages", [])

    async def get_channel_info(
        self,
        channel: str,
    ) -> dict:
        """Get channel information including name."""
        result = await self._request(
            "GET",
            "conversations.info",
            params={"channel": channel},
        )
        return result.get("channel", {})


# =============================================================================
# Request Signature Verification
# =============================================================================


async def verify_slack_signature(
    request: fastapi.Request,
    the_installation: installation.Installation,
) -> bytes:
    """Verify that the request came from Slack.

    Raises HTTPException if verification fails.
    Returns the raw body bytes for further processing.
    """
    try:
        signing_secret = the_installation.get_secret("SLACK_SIGNING_SECRET")
    except KeyError:
        logger.warning("SLACK_SIGNING_SECRET not configured")
        raise fastapi.HTTPException(
            status_code=500,
            detail="Slack signing secret not configured",
        )

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not signature:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Missing Slack signature headers",
        )

    # Check timestamp to prevent replay attacks (allow 5 minutes)
    current_time = time.time()
    if abs(current_time - int(timestamp)) > 60 * 5:
        raise fastapi.HTTPException(
            status_code=400,
            detail="Request timestamp too old",
        )

    # Get raw body
    body = await request.body()

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    computed_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
    )

    if not hmac.compare_digest(computed_signature, signature):
        raise fastapi.HTTPException(
            status_code=400,
            detail="Invalid request signature",
        )

    return body


# =============================================================================
# Markdown Conversion
# =============================================================================


def convert_markdown_to_slack(text: str) -> str:
    """Convert standard markdown to Slack's mrkdwn format."""
    # Bold: **text** -> *text*
    import re

    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Links: [text](url) -> <url|text>
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"<\2|\1>", text)
    # Code blocks remain the same in Slack
    return text


def extract_room_id_from_channel_name(channel_name: str) -> str | None:
    """Extract room ID from channel name.

    Channel format: soliplex_ROOM_ID (e.g., soliplex_mcptest, soliplex_faux)
    Returns the room ID or None if the channel doesn't match the pattern.
    """
    prefix = "soliplex_"
    if channel_name.startswith(prefix):
        return channel_name[len(prefix):]
    return None


# =============================================================================
# Caches
# =============================================================================

# Cache for channel ID -> channel name mapping to avoid repeated API calls
_channel_name_cache: dict[str, str] = {}

# In-memory store for DM room selections: {channel_id: room_id}
# In production, consider using Redis or a database for persistence
_dm_room_selections: dict[str, str] = {}


def get_dm_room_selection(channel_id: str) -> str | None:
    """Get the selected room for a DM channel."""
    return _dm_room_selections.get(channel_id)


def set_dm_room_selection(channel_id: str, room_id: str) -> None:
    """Set the selected room for a DM channel."""
    _dm_room_selections[channel_id] = room_id


def clear_dm_room_selection(channel_id: str) -> None:
    """Clear the selected room for a DM channel."""
    _dm_room_selections.pop(channel_id, None)


def parse_room_selection(text: str, available_rooms: list[str]) -> str | None:
    """Parse user's room selection from text.

    Accepts:
    - Room name directly (e.g., "mcptest")
    - Number (e.g., "1", "2")
    - "switch" or "change" to reset selection

    Returns the room_id or None if not a valid selection.
    """
    text = text.strip().lower()

    # Check for reset commands
    if text in ("switch", "change", "reset", "menu", "rooms"):
        return "__RESET__"

    # Check if it's a number
    if text.isdigit():
        idx = int(text) - 1  # 1-indexed for users
        if 0 <= idx < len(available_rooms):
            return available_rooms[idx]
        return None

    # Check if it matches a room name
    for room_id in available_rooms:
        if text == room_id.lower():
            return room_id

    return None


def format_room_menu(rooms: dict) -> str:
    """Format the room selection menu for Slack."""
    lines = ["*Please select a room to chat with:*\n"]
    for i, (room_id, room_info) in enumerate(rooms.items(), 1):
        name = room_info.get("name", room_id)
        description = room_info.get("description", "")
        if description:
            lines.append(f"*{i}.* {name} (`{room_id}`)\n    _{description}_")
        else:
            lines.append(f"*{i}.* {name} (`{room_id}`)")
    lines.append("\n_Reply with the number or room name to select._")
    lines.append("_Type `switch` anytime to change rooms._")
    return "\n".join(lines)


# =============================================================================
# Event Handlers
# =============================================================================


async def handle_message_event(
    event: SlackEventMessage,
    the_installation: installation.Installation,
):
    """Handle a message event from Slack.

    This runs in the background after the endpoint returns 200.

    For channels: Room ID is extracted from channel name (format: soliplex_ROOM_ID).
    For DMs: User selects a room from a menu, selection is remembered.
    """
    # Skip bot messages to avoid infinite loops
    if event.is_bot_message:
        logger.debug("Skipping bot message")
        return

    if not event.text:
        logger.debug("Skipping message with no text")
        return

    try:
        bot_token = the_installation.get_secret("SLACK_BOT_TOKEN")
    except KeyError:
        logger.error("SLACK_BOT_TOKEN not configured")
        return

    slack = SlackClient(bot_token)

    # Handle DMs differently - require room selection
    if event.is_dm:
        await handle_dm_message(event, the_installation, slack)
        return

    # For channels: Get channel name (from cache or API) to extract room ID
    channel_name = _channel_name_cache.get(event.channel)
    if channel_name is None:
        try:
            channel_info = await slack.get_channel_info(event.channel)
            channel_name = channel_info.get("name", "")
            # Cache the result
            _channel_name_cache[event.channel] = channel_name
            logger.debug(
                "Cached channel name: %s -> %s", event.channel, channel_name
            )
        except Exception as e:
            logger.warning("Failed to get channel info: %s, using default room", e)
            channel_name = ""

    room_id = extract_room_id_from_channel_name(channel_name) or "mcptest"
    logger.info(
        "Processing message in channel '%s' -> room '%s'",
        channel_name,
        room_id,
    )

    await process_message_with_agent(event, the_installation, slack, room_id)


async def handle_dm_message(
    event: SlackEventMessage,
    the_installation: installation.Installation,
    slack: SlackClient,
):
    """Handle a direct message - manage room selection flow."""
    # Get available rooms
    slack_user_info = {"preferred_username": f"slack:{event.user}"}
    room_configs = the_installation.get_room_configs(slack_user_info)
    available_room_ids = list(room_configs.keys())

    # Check if user has already selected a room
    selected_room = get_dm_room_selection(event.channel)

    # Check if user wants to change rooms or is selecting
    selection = parse_room_selection(event.text or "", available_room_ids)

    if selection == "__RESET__":
        # User wants to see the menu / change rooms
        clear_dm_room_selection(event.channel)
        rooms_dict = {
            rid: {
                "name": rc.name,
                "description": rc.description,
            }
            for rid, rc in room_configs.items()
        }
        menu_text = format_room_menu(rooms_dict)
        await slack.post_message(
            channel=event.channel,
            text=menu_text,
        )
        return

    if selected_room is None:
        # No room selected yet - check if this message is a selection
        if selection:
            # Valid selection
            set_dm_room_selection(event.channel, selection)
            room_config = room_configs.get(selection)
            room_name = room_config.name if room_config else selection
            await slack.post_message(
                channel=event.channel,
                text=f"✓ Selected *{room_name}* (`{selection}`). How can I help you?\n_Type `switch` to change rooms._",
            )
            return
        else:
            # Show the room menu
            rooms_dict = {
                rid: {
                    "name": rc.name,
                    "description": rc.description,
                }
                for rid, rc in room_configs.items()
            }
            menu_text = format_room_menu(rooms_dict)
            await slack.post_message(
                channel=event.channel,
                text=menu_text,
            )
            return

    # Room is selected - process the message with that room's agent
    logger.info(
        "Processing DM from user '%s' with room '%s'",
        event.user,
        selected_room,
    )
    await process_message_with_agent(event, the_installation, slack, selected_room)


async def process_message_with_agent(
    event: SlackEventMessage,
    the_installation: installation.Installation,
    slack: SlackClient,
    room_id: str,
):
    """Process a message using the specified room's agent."""

    # Post a "thinking" message
    thinking_response = await slack.post_message(
        channel=event.channel,
        text="_Thinking..._",
        thread_ts=event.thread_id,
    )
    thinking_ts: str | None = thinking_response.get("ts")

    try:
        # Get thread context if in a thread
        message_history: list[dict[str, str]] = []
        if event.thread_ts:
            thread_messages = await slack.get_thread_messages(
                channel=event.channel,
                thread_ts=event.thread_ts,
            )
            # Convert to simple message format for context
            for msg in thread_messages[:-1]:  # Exclude current message
                if msg.get("bot_id"):
                    message_history.append(
                        {"role": "assistant", "content": msg.get("text", "")}
                    )
                else:
                    message_history.append(
                        {"role": "user", "content": msg.get("text", "")}
                    )

        # Get the agent for the configured room
        # Use a pseudo-user for Slack interactions
        slack_user_info = {"preferred_username": f"slack:{event.user}"}
        slack_user_profile = models.UserProfile(
            given_name="Slack",
            family_name="User",
            email=f"slack-{event.user}@slack.local",
            preferred_username=f"slack:{event.user}",
        )

        try:
            agent = the_installation.get_agent_for_room(room_id, slack_user_info)
        except KeyError:
            logger.error("Room not found: %s", room_id)
            if thinking_ts:
                await slack.update_message(
                    channel=event.channel,
                    ts=thinking_ts,
                    text=f"_Error: Room '{room_id}' not configured._",
                )
            return

        # Build the prompt with context
        if message_history:
            # Include history in a structured way
            context_text = "\n".join(
                f"{'Assistant' if m['role'] == 'assistant' else 'User'}: {m['content']}"
                for m in message_history[-10:]  # Last 10 messages for context
            )
            full_prompt = f"Previous conversation:\n{context_text}\n\nUser: {event.text}"
        else:
            full_prompt = event.text or ""

        # Generate response using PydanticAI
        from soliplex import agents

        deps = agents.AgentDependencies(
            the_installation=the_installation,
            user=slack_user_profile,
            tool_configs={},
        )

        result = await agent.run(full_prompt, deps=deps)
        response_text = result.output

        # Convert markdown to Slack format
        slack_text = convert_markdown_to_slack(str(response_text))

        # Update the thinking message with the response
        if thinking_ts:
            await slack.update_message(
                channel=event.channel,
                ts=thinking_ts,
                text=slack_text,
            )

    except Exception as e:
        logger.exception("Error handling Slack message")
        # Update thinking message with error
        if thinking_ts:
            await slack.update_message(
                channel=event.channel,
                ts=thinking_ts,
                text=f"_Sorry, I encountered an error: {str(e)}_",
            )


# =============================================================================
# API Endpoint
# =============================================================================


@router.post("/slack/events")
async def slack_events(
    request: fastapi.Request,
    background_tasks: BackgroundTasks,
    the_installation: installation.Installation = depend_the_installation,
) -> dict:
    """
    Handle Slack Events API webhook.

    This endpoint handles:
    - url_verification: Slack's challenge-response for webhook URL verification
    - event_callback: Actual events from Slack (messages, mentions)

    Events are processed asynchronously in the background to meet Slack's
    3-second response requirement.
    """
    # Verify signature and get body
    body = await verify_slack_signature(request, the_installation)

    # Parse the payload
    import json

    payload_dict = json.loads(body)
    event_type = payload_dict.get("type")

    logger.info("Received Slack event: type=%s", event_type)

    # Handle URL verification (must respond synchronously)
    if event_type == "url_verification":
        challenge = payload_dict.get("challenge")
        if not challenge:
            raise fastapi.HTTPException(
                status_code=400,
                detail="Missing challenge in url_verification payload",
            )
        logger.info("Responding to Slack URL verification challenge")
        return {"challenge": challenge}

    # Handle event callbacks
    if event_type == "event_callback":
        event_data = payload_dict.get("event", {})
        event = SlackEventMessage(**event_data)

        # Process message events in background
        # Room ID is extracted from channel name (soliplex_ROOM_ID)
        if event.type in ("message", "app_mention"):
            background_tasks.add_task(
                handle_message_event,
                event,
                the_installation,
            )

        # Return immediately (Slack needs response within 3 seconds)
        return {"ok": True}

    logger.warning("Unknown Slack event type: %s", event_type)
    return {"ok": True}
