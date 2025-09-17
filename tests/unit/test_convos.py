import datetime
from unittest import mock

import fastapi
import pytest
from pydantic_ai import messages as ai_messages

from soliplex import convos

SYSTEM_PROMPT = "You are a testcase"
USER_PROMPT = "Which way is up?"
TOOL_RETURN = "Nailed it"
TOOL_CALL_ID = 1234
RETRY_PROMPT = "Please try again"
TEXT = "The opposite way from down"
THINKING = "Hold on a minute, I'm thinking"
TOOL_NAME = "hammer"

NOW = datetime.datetime(2025, 8, 11, 16, 59, 47, tzinfo=datetime.UTC)
TS_1 = NOW - datetime.timedelta(minutes=11)
TS_2 = NOW - datetime.timedelta(minutes=10)
TS_3 = NOW - datetime.timedelta(minutes=9)
TS_4 = NOW - datetime.timedelta(minutes=8)

ROOM_ID = "testing"
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

timestamp = datetime.datetime.now(datetime.UTC)
system_prompt_part = ai_messages.SystemPromptPart(
    content=SYSTEM_PROMPT, timestamp=timestamp,
)
user_prompt_part = ai_messages.UserPromptPart(
    content=USER_PROMPT, timestamp=timestamp,
)
tool_return_part = ai_messages.ToolReturnPart(
    content=TOOL_RETURN, tool_call_id=TOOL_CALL_ID, tool_name=TOOL_NAME,
)
retry_prompt_part = ai_messages.RetryPromptPart(
    RETRY_PROMPT, timestamp=timestamp,
)

text_part = ai_messages.TextPart(content=TEXT)
thinking_part = ai_messages.ThinkingPart(content=THINKING)
tool_call_part = ai_messages.ToolCallPart(tool_name=TOOL_NAME)


@pytest.mark.parametrize("parts, expect_none", [
    ([system_prompt_part], True),
    ([user_prompt_part], False),
    ([tool_return_part], True),
    ([retry_prompt_part], True),
    ([system_prompt_part, tool_return_part], True),
    ([system_prompt_part, retry_prompt_part], True),
    ([tool_return_part, retry_prompt_part], True),
    ([system_prompt_part, tool_return_part, retry_prompt_part], True),
    ([system_prompt_part, user_prompt_part], False),
    ([tool_return_part, user_prompt_part], False),
    ([retry_prompt_part, user_prompt_part], False),
])
def test__to_convo_message_w_request(parts, expect_none):
    msg = ai_messages.ModelRequest(parts=parts)

    found = convos._to_convo_message(msg)

    if expect_none:
        assert found is None
    else:
        assert found["role"] == "user"
        assert found["content"] == USER_PROMPT
        assert found["timestamp"] == timestamp.isoformat()


@pytest.mark.parametrize("parts, expect_none", [
    ([text_part], False),
    ([thinking_part, text_part], False),
    ([tool_call_part, text_part], False),
    ([thinking_part,tool_call_part, text_part], False),
    ([thinking_part], True),
    ([tool_call_part], True),
    ([thinking_part,tool_call_part], True),
])
def test__to_convo_message_w_response(parts, expect_none):
    msg = ai_messages.ModelResponse(parts=parts)

    found = convos._to_convo_message(msg)

    if expect_none:
        assert found is None
    else:
        assert found["role"] == "model"
        assert found["content"] == TEXT


@pytest.mark.parametrize("parts, expect_none", [
    ([system_prompt_part], True),
    ([user_prompt_part], False),
    ([tool_return_part], True),
    ([retry_prompt_part], True),
    ([system_prompt_part, tool_return_part], True),
    ([system_prompt_part, retry_prompt_part], True),
    ([tool_return_part, retry_prompt_part], True),
    ([system_prompt_part, tool_return_part, retry_prompt_part], True),
    ([system_prompt_part, user_prompt_part], False),
    ([tool_return_part, user_prompt_part], False),
    ([retry_prompt_part, user_prompt_part], False),
])
def test__to_convo_history_message_w_request(parts, expect_none):
    msg = ai_messages.ModelRequest(parts=parts)

    found = convos._to_convo_history_message(msg)

    if expect_none:
        assert found is None
    else:
        assert found["origin"] == "user"
        assert found["text"] == USER_PROMPT
        assert found["timestamp"] == timestamp.isoformat()


@pytest.mark.parametrize("parts, expect_none", [
    ([text_part], False),
    ([thinking_part, text_part], False),
    ([tool_call_part, text_part], False),
    ([thinking_part,tool_call_part, text_part], False),
    ([thinking_part], True),
    ([tool_call_part], True),
    ([thinking_part,tool_call_part], True),
])
def test__to_convo_history_message_w_response(parts, expect_none):
    msg = ai_messages.ModelResponse(parts=parts)

    found = convos._to_convo_history_message(msg)

    if expect_none:
        assert found is None
    else:
        assert found["origin"] == "llm"
        assert found["text"] == TEXT


@pytest.mark.parametrize("parts, expect_len", [
    ([system_prompt_part], 1),
    ([user_prompt_part], 1),
    ([tool_return_part], 0),
    ([retry_prompt_part], 0),
    ([system_prompt_part, tool_return_part], 1),
    ([system_prompt_part, retry_prompt_part], 1),
    ([user_prompt_part, tool_return_part], 1),
    ([user_prompt_part, retry_prompt_part], 1),
    ([tool_return_part, retry_prompt_part], 0),
    ([system_prompt_part, tool_return_part, retry_prompt_part], 1),
    ([system_prompt_part, user_prompt_part], 2),
    ([tool_return_part, user_prompt_part], 1),
    ([retry_prompt_part, user_prompt_part], 1),
])
def test__filter_context_message_w_requests(parts, expect_len):
    msg = ai_messages.ModelRequest(parts=parts)

    found = convos._filter_context_message(msg)

    if expect_len == 0:
        assert found is None
    else:
        assert len(found.parts) == expect_len
        for part in found.parts:
            if part.part_kind == "user-prompt":
                assert part.content == USER_PROMPT
            elif part.part_kind == "system-prompt":
                assert part.content == SYSTEM_PROMPT
            else:  # pragma: NO COVER
                pass


@pytest.mark.parametrize("parts, expect_none", [
    ([text_part], False),
    ([thinking_part, text_part], False),
    ([tool_call_part, text_part], False),
    ([thinking_part,tool_call_part, text_part], False),
    ([thinking_part], True),
    ([tool_call_part], True),
    ([thinking_part,tool_call_part], True),
])
def test__filter_context_message_w_responses(parts, expect_none):
    msg = ai_messages.ModelResponse(parts=parts)

    found = convos._filter_context_message(msg)

    if expect_none:
        assert found is None
    else:
        assert len(found.parts) == 1
        assert found.parts[0].content == TEXT


def test__filter_context_messages():
    request = ai_messages.ModelRequest(parts=[user_prompt_part])
    thinking = ai_messages.ModelResponse(parts=[thinking_part])
    answer = ai_messages.ModelResponse(parts=[text_part])

    found = convos._filter_context_messages([request, thinking, answer])

    m1, m2 = found

    assert m1.kind == "request"
    assert m1.parts == [user_prompt_part]

    assert m2.kind == "response"
    assert m2.parts == [text_part]

@pytest.mark.anyio
@pytest.mark.parametrize("w_none", [False, True])
@mock.patch("soliplex.convos._to_convo_history_message")
async def test_conversation_message_history_dicts(tchm, w_none):
    if w_none:
        tchm.return_value = None

    found = [md async for md in TEST_CONVO.message_history_dicts]

    if w_none:
        assert found == []
    else:
        for f_dict, _e_msg in zip(
            found, OLD_AI_MESSAGES, strict=True,
        ):
            assert f_dict is tchm.return_value


@pytest.mark.anyio
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_user_conversations(w_user):
    the_convos = convos.Conversations()

    if not w_user:
        with pytest.raises(convos.NoUserConversations):
            await the_convos.user_conversations("nonesuch")
    else:
        with mock.patch.dict(the_convos._convos, testing=TEST_CONVOS):
            found = await the_convos.user_conversations("testing")

        assert found == {
            TEST_CONVO_UUID: {
                "name": TEST_CONVO_NAME,
                "room_id": TEST_CONVO_ROOMID,
            },
        }


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_get_conversation(w_user, w_miss):
    the_convos = convos.Conversations()

    if not w_user:
        with pytest.raises(convos.NoUserConversations):
            await the_convos.get_conversation_info("nonesuch", TEST_CONVO_UUID)
    elif w_miss:
        with (
            mock.patch.dict(the_convos._convos, testing={}),
            pytest.raises(convos.UnknownConversation),
        ):
            await the_convos.get_conversation_info("testing", TEST_CONVO_UUID)
    else:
        with (
            mock.patch.dict(the_convos._convos, testing=TEST_CONVOS),
        ):
            found = await the_convos.get_conversation(
                "testing", TEST_CONVO_UUID,
            )

        assert found is TEST_CONVO


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_get_conversation_info(w_user, w_miss):
    the_convos = convos.Conversations()

    if not w_user:
        with pytest.raises(convos.NoUserConversations):
            await the_convos.get_conversation_info("nonesuch", TEST_CONVO_UUID)
    elif w_miss:
        with (
            mock.patch.dict(the_convos._convos, testing={}),
            pytest.raises(convos.UnknownConversation),
        ):
            await the_convos.get_conversation_info("testing", TEST_CONVO_UUID)
    else:
        with (
            mock.patch.dict(the_convos._convos, testing=TEST_CONVOS),
        ):
            found = await the_convos.get_conversation_info(
                "testing", TEST_CONVO_UUID,
            )

        assert found["convo_uuid"] == TEST_CONVO_UUID
        assert found["name"] == TEST_CONVO_NAME
        assert found["room_id"] == TEST_CONVO_ROOMID

        for f_dict, e_msg in zip(
            found["message_history"], OLD_AI_MESSAGES, strict=True,
        ):
            if isinstance(e_msg, ai_messages.ModelRequest):
                assert f_dict["origin"] == "user"
            else:
                assert f_dict["origin"] == "llm"

            assert f_dict["text"] == e_msg.parts[0].content


@pytest.mark.anyio
@pytest.mark.parametrize("w_existing", [False, True])
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_new_conversation(w_user, w_existing):
    the_convos = convos.Conversations()

    kw = {}
    if w_user:
        kw["testing"] = {}

    with (
        mock.patch.dict(the_convos._convos, **kw),
    ):
        found = await the_convos.new_conversation(
            "testing", TEST_CONVO_ROOMID, TEST_CONVO_NAME, OLD_AI_MESSAGES,
        )

    assert isinstance(found["convo_uuid"], str)
    assert found["name"] == TEST_CONVO_NAME
    assert found["room_id"] == TEST_CONVO_ROOMID

    for f_dict, e_msg in zip(
        found["message_history"], OLD_AI_MESSAGES, strict=True,
    ):
        if isinstance(e_msg, ai_messages.ModelRequest):
            assert f_dict["origin"] == "user"
        else:
            assert f_dict["origin"] == "llm"

        assert f_dict["text"] == e_msg.parts[0].content


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_append_to_conversation(w_user, w_miss):
    the_convos = convos.Conversations()

    to_be_appended = convos.Conversation(
        uuid=TEST_CONVO_UUID,
        name=TEST_CONVO_NAME,
        room_id=TEST_CONVO_ROOMID,
        message_history=OLD_AI_MESSAGES[:],
    )
    testing = {TEST_CONVO_UUID: to_be_appended }

    if not w_user:
        with pytest.raises(convos.NoUserConversations):
            await the_convos.append_to_conversation(
                "nonesuch", TEST_CONVO_UUID, NEW_AI_MESSAGES,
            )
    elif w_miss:
        with (
            mock.patch.dict(the_convos._convos, testing={}),
            pytest.raises(convos.UnknownConversation),
        ):
            await the_convos.append_to_conversation(
                "testing", TEST_CONVO_UUID, NEW_AI_MESSAGES,
            )
    else:
        with (
            mock.patch.dict(the_convos._convos, testing=testing),
        ):
            await the_convos.append_to_conversation(
                "testing", TEST_CONVO_UUID, NEW_AI_MESSAGES,
            )

            assert to_be_appended.message_history == (
                OLD_AI_MESSAGES + NEW_AI_MESSAGES
            )


@pytest.mark.anyio
@pytest.mark.parametrize("w_miss", [False, True])
@pytest.mark.parametrize("w_user", [False, True])
async def test_conversations_delete_conversation(w_user, w_miss):
    the_convos = convos.Conversations()

    to_be_deleted = convos.Conversation(
        uuid=TEST_CONVO_UUID,
        name=TEST_CONVO_NAME,
        room_id=TEST_CONVO_ROOMID,
        message_history=OLD_AI_MESSAGES[:],
    )
    testing = {TEST_CONVO_UUID: to_be_deleted }

    if not w_user:
        with pytest.raises(convos.NoUserConversations):
            await the_convos.delete_conversation("nonesuch", TEST_CONVO_UUID)
    elif w_miss:
        with (
            mock.patch.dict(the_convos._convos, testing={}),
            pytest.raises(convos.UnknownConversation),
        ):
            await the_convos.delete_conversation("testing", TEST_CONVO_UUID)
    else:
        with (
            mock.patch.dict(the_convos._convos, testing=testing),
        ):
            await the_convos.delete_conversation("testing", TEST_CONVO_UUID)

            assert TEST_CONVO_UUID not in "testing"


@pytest.mark.anyio
async def test_get_the_convos():
    expected = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.the_convos = expected

    found = await convos.get_the_convos(request)

    assert found is expected
