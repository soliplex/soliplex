import datetime
import json
from unittest import mock

import fastapi
import pytest
from fastapi import responses
from pydantic_ai import messages as ai_messages

from soliplex import config
from soliplex import convos
from soliplex import models
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


def _make_the_installation():
    from soliplex import installation

    return mock.create_autospec(installation.Installation, instance=True)


async def get_chunks(**kwargs):
    for chunk in CHUNKS:
        yield chunk


async def _check_streaming_response(found):

    found_messages = []

    async def consume_streamed_messages(message):
        found_messages.append(message)

    await found.stream_response(consume_streamed_messages)

    assert len(found_messages) == len(CHUNKS) + 3

    def parse_it(message):
        body = message.get("body")

        if body not in (None, b""):
            body = json.loads(body.decode("utf-8"))

        return message["type"], body

    for i_msg, msg in enumerate(found_messages):
        type_, body = parse_it(msg)

        if i_msg == 0:
            assert type_ == "http.response.start"
        else:
            assert type_ == "http.response.body"

            if i_msg == 1:
                assert body["role"] == "user"
                assert body["content"] == USER_PROMPT

            elif i_msg < len(found_messages) - 1:
                assert body["role"] == "model"
                assert msg["more_body"]

            else:
                assert not msg["more_body"]


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


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user", [
    ({}, UNKNOWN_USER),
    (AUTH_USER, AUTH_USER),
])
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.convos._filter_context_messages")
@mock.patch("soliplex.auth.authenticate")
async def test_post_convos_new(
    auth_fn, fcm, w_error, w_auth_user, exp_user,
):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(
        scope={"type": "http"},
    )
    convo_msg = models.NewConvoClientMessage(
        text=USER_PROMPT, room_id=TEST_CONVO_ROOMID,
    )
    the_installation = _make_the_installation()
    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    token = object()

    gafr = the_installation.get_agent_for_room

    if w_error:
        gafr.side_effect = KeyError("testing")

    if w_error:

        with pytest.raises(fastapi.HTTPException):
            await views.post_convos_new(
                request=request,
                convo_msg=convo_msg,
                the_installation=the_installation,
                the_convos=the_convos,
                token=token,
            )

        the_convos.new_conversation.assert_not_called()

    else:
        agent = gafr.return_value = mock.Mock(spec_set=["run_stream"])
        s_rslt = mock.MagicMock()
        agent.run_stream.return_value = s_rslt
        ctx_result = s_rslt.__aenter__.return_value
        ctx_result.get_output.return_value = "Who knows? Not me!"
        ctx_result.timestamp = mock.Mock(spec_set=(), return_value=NOW)
        ctx_result.new_messages = mock.Mock(
            spec_set=(), return_value=NEW_AI_MESSAGES,
        )

        found = await views.post_convos_new(
            request=request,
            convo_msg=convo_msg,
            the_installation=the_installation,
            the_convos=the_convos,
            token=token,
        )

        assert found is the_convos.new_conversation.return_value

        exp_user_profile = models.UserProfile(**exp_user)

        expected_deps = models.AgentDependencies(
            user=exp_user_profile,
        )

        agent.run_stream.assert_called_once_with(
            USER_PROMPT,
            message_history=[],
            deps=expected_deps,
        )

        the_convos.new_conversation.assert_called_once_with(
            exp_user["preferred_username"],
            TEST_CONVO_ROOMID,
            USER_PROMPT,
            fcm.return_value,
        )
        gafr.assert_called_once_with(
            TEST_CONVO_ROOMID, user=w_auth_user,
        )

        fcm.assert_called_once_with(NEW_AI_MESSAGES)

    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user", [
    ({}, UNKNOWN_USER),
    (AUTH_USER, AUTH_USER),
])
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.convos._filter_context_messages")
@mock.patch("soliplex.auth.authenticate")
async def test_post_convos_new_room(
    auth_fn, fcm, w_error, w_auth_user, exp_user,
):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(
        scope={"type": "http"},
    )
    convo_msg = models.UserPromptClientMessage(text=USER_PROMPT)
    the_installation = _make_the_installation()
    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    token = object()

    gafr = the_installation.get_agent_for_room

    if w_error:
        gafr.side_effect = KeyError("testing")

    if w_error:

        with pytest.raises(fastapi.HTTPException):
            await views.post_convos_new_room(
                request=request,
                room_id=TEST_CONVO_ROOMID,
                convo_msg=convo_msg,
                the_installation=the_installation,
                the_convos=the_convos,
                token=token,
            )

        the_convos.new_conversation.assert_not_called()

    else:
        agent = mock.Mock(spec_set=["run_stream"])
        the_installation.get_agent_for_room.return_value = agent
        s_rslt = mock.MagicMock()
        agent.run_stream.return_value = s_rslt
        ctx_result = s_rslt.__aenter__.return_value
        ctx_result.get_output.return_value = "Who knows? Not me!"
        ctx_result.timestamp = mock.Mock(spec_set=(), return_value=NOW)
        ctx_result.new_messages = mock.Mock(
            spec_set=(), return_value=NEW_AI_MESSAGES,
        )

        found = await views.post_convos_new_room(
            request=request,
            room_id=TEST_CONVO_ROOMID,
            convo_msg=convo_msg,
            the_installation=the_installation,
            the_convos=the_convos,
            token=token,
        )

        assert found is the_convos.new_conversation.return_value

        exp_user_profile = models.UserProfile(**exp_user)

        expected_deps = models.AgentDependencies(
            user=exp_user_profile,
        )

        agent.run_stream.assert_called_once_with(
            USER_PROMPT,
            message_history=[],
            deps=expected_deps,
        )

        the_convos.new_conversation.assert_called_once_with(
            exp_user["preferred_username"],
            TEST_CONVO_ROOMID,
            USER_PROMPT,
            fcm.return_value,
        )
        gafr.assert_called_once_with(
            TEST_CONVO_ROOMID, user=w_auth_user,
        )

        fcm.assert_called_once_with(NEW_AI_MESSAGES)

    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@mock.patch("soliplex.auth.authenticate")
@pytest.mark.parametrize("w_auth_user, exp_user_name", [
    ({}, "<unknown>"),
    (AUTH_USER, USER_NAME),
])
async def test_get_convos(auth_fn, w_auth_user, exp_user_name):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(scope={"type": "http"})
    the_installation = _make_the_installation()
    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    token = object()

    found = await views.get_convos(
        request=request,
        the_installation=the_installation,
        the_convos=the_convos,
        token=token,
    )

    assert found is the_convos.user_conversations.return_value

    the_convos.user_conversations.assert_called_once_with(exp_user_name)


@pytest.mark.anyio
@mock.patch("soliplex.auth.authenticate")
@pytest.mark.parametrize("w_auth_user, exp_user_name", [
    ({}, "<unknown>"),
    (AUTH_USER, USER_NAME),
])
async def test_get_convo(auth_fn, w_auth_user, exp_user_name):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(scope={"type": "http"})
    the_installation = _make_the_installation()
    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    token = object()

    found = await views.get_convo(
        request=request,
        convo_uuid=TEST_CONVO_UUID,
        the_installation=the_installation,
        the_convos=the_convos,
        token=token,
    )

    assert found is the_convos.get_conversation_info.return_value

    the_convos.get_conversation_info.assert_called_once_with(
        exp_user_name, TEST_CONVO_UUID,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user", [
    ({}, UNKNOWN_USER),
    (AUTH_USER, AUTH_USER),
])
@pytest.mark.parametrize("w_error", [False, True])
@mock.patch("soliplex.convos._filter_context_messages")
@mock.patch("soliplex.auth.authenticate")
async def test_post_convo(
    auth_fn, fcm, w_error, w_auth_user, exp_user,
):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(scope={"type": "http"})
    the_installation = _make_the_installation()
    convo_msg = models.UserPromptClientMessage(text=USER_PROMPT)

    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    convo = mock.create_autospec(
        convos.Conversation, instance=True,
        room_id=TEST_CONVO_ROOMID,
        message_history=OLD_AI_MESSAGES,
    )
    the_convos.get_conversation.return_value = convo
    token = object()

    gafr = the_installation.get_agent_for_room
    if w_error:
        gafr.side_effect = KeyError("testing")

    agent = gafr.return_value = mock.Mock(spec_set=["run_stream"])
    s_rslt = mock.MagicMock()
    agent.run_stream.return_value = s_rslt
    ctx_result = s_rslt.__aenter__.return_value
    ctx_result.stream = get_chunks
    ctx_result.timestamp = mock.Mock(spec_set=(), return_value=NOW)
    ctx_result.new_messages = mock.Mock(
        spec_set=(), return_value=NEW_AI_MESSAGES,
    )

    if w_error:
        with pytest.raises(fastapi.HTTPException) as exc:
             await views.post_convo(
                request=request,
                convo_uuid=TEST_CONVO_UUID,
                convo_msg=convo_msg,
                the_installation=the_installation,
                the_convos=the_convos,
                token=token,
            )

        assert exc.value.status_code == 404

    else:
        found = await views.post_convo(
            request=request,
            convo_uuid=TEST_CONVO_UUID,
            convo_msg=convo_msg,
            the_installation=the_installation,
            the_convos=the_convos,
            token=token,
        )

        assert isinstance(found, responses.StreamingResponse)

        await _check_streaming_response(found)

        exp_user_profile = models.UserProfile(**exp_user)

        expected_deps = models.AgentDependencies(
            user=exp_user_profile,
        )

        agent.run_stream.assert_called_once_with(
            USER_PROMPT,
            message_history=OLD_AI_MESSAGES,
            deps=expected_deps,
        )

        the_convos.get_conversation.assert_called_once_with(
            exp_user["preferred_username"], TEST_CONVO_UUID,
        )

        the_convos.append_to_conversation.assert_called_once_with(
            exp_user["preferred_username"], TEST_CONVO_UUID, fcm.return_value,
        )

        fcm.assert_called_once_with(NEW_AI_MESSAGES)

    gafr.assert_called_once_with(
        TEST_CONVO_ROOMID, user=w_auth_user,
    )
    auth_fn.assert_called_once_with(the_installation, token)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_user, exp_user_name", [
    ({}, "<unknown>"),
    (AUTH_USER, USER_NAME),
])
@mock.patch("soliplex.auth.authenticate")
async def test_delete_convo(auth_fn, w_auth_user, exp_user_name):
    auth_fn.return_value = w_auth_user

    request = fastapi.Request(scope={"type": "http"})
    the_installation = _make_the_installation()
    the_convos = mock.create_autospec(
        convos.Conversations, instance=True,
    )
    token = object()

    found = await views.delete_convo(
        request=request,
        convo_uuid=TEST_CONVO_UUID,
        the_installation=the_installation,
        the_convos=the_convos,
        token=token,
    )

    assert found is None  # no response body for 204

    the_convos.delete_conversation.assert_called_once_with(
        exp_user_name, TEST_CONVO_UUID,
    )

    auth_fn.assert_called_once_with(the_installation, token)
