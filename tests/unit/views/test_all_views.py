import datetime
from unittest import mock

import fastapi
import pytest
from pydantic_ai import messages as ai_messages

from soliplex import config
from soliplex import convos
from soliplex import views

NOW = datetime.datetime(2025, 8, 11, 16, 59, 47, tzinfo=datetime.UTC)
TS_1 = NOW - datetime.timedelta(minutes=11)
TS_2 = NOW - datetime.timedelta(minutes=10)
TS_3 = NOW - datetime.timedelta(minutes=9)
TS_4 = NOW - datetime.timedelta(minutes=8)

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}

UNKNOWN_USER = {
    "preferred_username": "<unknown>",
    "given_name": "<unknown>",
    "family_name": "<unknown>",
    "email": "<unknown>",
}

SYSTEM_PROMPT = "You are a test."
USER_PROMPT = "This is a test."
MODEL_RESPONSE = "Now you're talking!"
ANOTHER_USER_PROMPT = "Which way is up?"
ANOTHER_MODEL_RESPONSE = "The other way from down"

OLD_AI_MESSAGES = [
    ai_messages.ModelRequest(
        instructions=SYSTEM_PROMPT,
        parts=[
            ai_messages.UserPromptPart(
                content=USER_PROMPT,
                timestamp=TS_1,
            ),
        ],
    ),
    ai_messages.ModelResponse(
        parts=[
            ai_messages.TextPart(content=MODEL_RESPONSE),
        ],
        timestamp=TS_2,
    ),
]
NEW_AI_MESSAGES = [
    ai_messages.ModelRequest(
        parts=[
            ai_messages.UserPromptPart(
                content=ANOTHER_USER_PROMPT,
                timestamp=TS_3,
            ),
        ],
    ),
    ai_messages.ModelResponse(
        parts=[
            ai_messages.TextPart(content=ANOTHER_MODEL_RESPONSE),
        ],
        timestamp=TS_4,
    ),
]

TEST_CONVO_UUID = "test_uuid"
TEST_CONVO_NAME = "Test Convo"
TEST_CONVO_ROOMID = "test-room"
TEST_CONVO = convos.Conversation(
    uuid=TEST_CONVO_UUID,
    name=TEST_CONVO_NAME,
    room_id=TEST_CONVO_ROOMID,
    message_history=OLD_AI_MESSAGES,
)
TEST_CONVOS = {
    TEST_CONVO_UUID: TEST_CONVO,
}
CHUNKS = [
    "This",
    "This is",
    "This is being",
    "This is being my",
    "This is being my answer",
]


@pytest.mark.anyio
async def test_health_check():
    response = await views.health_check()

    assert response == "OK"


@pytest.mark.anyio
@mock.patch("soliplex.models.Installation.from_config")
@mock.patch("soliplex.auth.authenticate")
async def test_get_installation(auth_fn, fc):
    from soliplex import installation

    request = mock.create_autospec(fastapi.Request)

    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    token = object()

    found = await views.get_installation(
        request, the_installation=the_installation, token=token,
    )

    assert found is fc.return_value

    fc.assert_called_once_with(i_config)
    auth_fn.assert_called_once_with(the_installation, token)
