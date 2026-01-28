from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex import agui as agui_package

TEST_THREAD_ID = "thread-123"
TEST_RUN_ID = "run-345"

MESSAGE_ID_0 = "message-id-0"
MESSAGE_ID_1 = "message-id-1"
MESSAGE_ID_2 = "message-id-2"
MESSAGE_ID_3 = "message-id-3"
MESSAGE_ID_4 = "message-id-4"

SYSTEM_MESSAGE_W_STR_CONTENT = agui_core.SystemMessage(
    id=MESSAGE_ID_0,
    content="system content",
)
TEXT_CONTENT_1 = agui_core.TextInputContent(text="string content")
BINARY_CONTENT_1 = agui_core.BinaryInputContent(
    mime_type="application/binary",
    data="DEADBEEF",
)
BINARY_CONTENT_2 = agui_core.BinaryInputContent(
    mime_type="application/binary",
    data="FACEDACE",
)
USER_MESSAGE_W_STR_CONTENT = agui_core.UserMessage(
    id=MESSAGE_ID_1,
    content="string content",
)
USER_MESSAGE_W_TEXT_CONTENT = agui_core.UserMessage(
    id=MESSAGE_ID_2,
    content=[TEXT_CONTENT_1],
)
USER_MESSAGE_W_BINARY_CONTENT = agui_core.UserMessage(
    id=MESSAGE_ID_3,
    content=[BINARY_CONTENT_1],
)
USER_MESSAGE_W_MIXED_CONTENT = agui_core.UserMessage(
    id=MESSAGE_ID_4,
    content=[TEXT_CONTENT_1, BINARY_CONTENT_2],
)

TEXT_START_1 = agui_core.TextMessageStartEvent(message_id=MESSAGE_ID_1)
TEXT_CONTENT_1_A = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_1,
    delta="A ",
)
TEXT_CONTENT_1_B = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_1,
    delta="B ",
)
TEXT_CONTENT_1_C = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_1,
    delta="C",
)
TEXT_CONTENT_1_AB = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_1,
    delta="A B ",
)
TEXT_CONTENT_1_ABC = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_1,
    delta="A B C",
)
TEXT_END_1 = agui_core.TextMessageEndEvent(message_id=MESSAGE_ID_1)

THINK_START = agui_core.ThinkingTextMessageStartEvent()
THINK_CONTENT_A = agui_core.ThinkingTextMessageContentEvent(
    delta="A ",
)
THINK_CONTENT_B = agui_core.ThinkingTextMessageContentEvent(
    delta="B ",
)
THINK_CONTENT_C = agui_core.ThinkingTextMessageContentEvent(
    delta="C",
)
THINK_CONTENT_AB = agui_core.ThinkingTextMessageContentEvent(
    delta="A B ",
)
THINK_CONTENT_ABC = agui_core.ThinkingTextMessageContentEvent(
    delta="A B C",
)
THINK_END = agui_core.ThinkingTextMessageEndEvent()


TEXT_CONTENT_2_D = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_2,
    delta="D ",
)

OTHER = agui_core.RawEvent(event=None, source="test-raw")


@pytest.fixture
def run_input():
    return agui_core.RunAgentInput(
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props=None,
    )


@pytest.mark.parametrize(
    "messages, expected",
    [
        ([], []),
        ([SYSTEM_MESSAGE_W_STR_CONTENT], []),
        ([USER_MESSAGE_W_STR_CONTENT], []),
        ([USER_MESSAGE_W_TEXT_CONTENT], []),
        ([USER_MESSAGE_W_BINARY_CONTENT], [BINARY_CONTENT_1]),
        ([USER_MESSAGE_W_MIXED_CONTENT], [BINARY_CONTENT_2]),
        (
            [
                USER_MESSAGE_W_STR_CONTENT,
                USER_MESSAGE_W_TEXT_CONTENT,
                USER_MESSAGE_W_BINARY_CONTENT,
                USER_MESSAGE_W_MIXED_CONTENT,
                SYSTEM_MESSAGE_W_STR_CONTENT,
            ],
            [
                BINARY_CONTENT_1,
                BINARY_CONTENT_2,
            ],
        ),
    ],
)
def test_extract_binary_attachments(run_input, messages, expected):
    run_input.messages.extend(messages)

    found = agui_package.extract_binary_attachments(run_input)

    assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "events, expected",
    [
        ([], []),
        (
            [TEXT_START_1, TEXT_CONTENT_1_A, TEXT_END_1],
            [TEXT_START_1, TEXT_CONTENT_1_A, TEXT_END_1],
        ),
        (
            [
                TEXT_START_1,
                TEXT_CONTENT_1_A,
                TEXT_CONTENT_1_B,
                TEXT_CONTENT_1_C,
                TEXT_END_1,
            ],
            [TEXT_START_1, TEXT_CONTENT_1_ABC, TEXT_END_1],
        ),
        (
            [
                TEXT_START_1,
                TEXT_CONTENT_1_A,
                TEXT_CONTENT_1_B,
                OTHER,
                TEXT_CONTENT_1_C,
                TEXT_END_1,
            ],
            [
                TEXT_START_1,
                TEXT_CONTENT_1_AB,
                OTHER,
                TEXT_CONTENT_1_C,
                TEXT_END_1,
            ],
        ),
        (
            [
                TEXT_START_1,
                TEXT_CONTENT_1_A,
                TEXT_CONTENT_2_D,
                TEXT_CONTENT_1_C,
                TEXT_END_1,
            ],
            [
                TEXT_START_1,
                TEXT_CONTENT_1_A,
                TEXT_CONTENT_2_D,
                TEXT_CONTENT_1_C,
                TEXT_END_1,
            ],
        ),
        (
            [THINK_START, THINK_CONTENT_A, THINK_END],
            [THINK_START, THINK_CONTENT_A, THINK_END],
        ),
        (
            [
                THINK_START,
                THINK_CONTENT_A,
                THINK_CONTENT_B,
                THINK_CONTENT_C,
                THINK_END,
            ],
            [THINK_START, THINK_CONTENT_ABC, THINK_END],
        ),
        (
            [
                THINK_START,
                THINK_CONTENT_A,
                THINK_CONTENT_B,
                OTHER,
                THINK_CONTENT_C,
                THINK_END,
            ],
            [
                THINK_START,
                THINK_CONTENT_AB,
                OTHER,
                THINK_CONTENT_C,
                THINK_END,
            ],
        ),
    ],
)
async def test_compact_event_stream(events, expected):
    async def stream():
        for event in events:
            yield event

    found = [
        event async for event in agui_package.compact_event_stream(stream())
    ]

    for f_event, e_event in zip(found, expected, strict=True):
        assert f_event == e_event


@pytest.mark.anyio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
@mock.patch("sqlalchemy.ext.asyncio.AsyncSession")
async def test_get_the_threads(as_klass, ts_klass):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.threads_engine = engine

    counter = 0

    async for the_threads in agui_package.get_the_threads(request):
        assert the_threads is ts_klass.return_value
        counter += 1

    assert counter == 1

    ts_klass.assert_called_once_with(
        as_klass.return_value.__aenter__.return_value,
    )

    as_klass.assert_called_once_with(bind=engine)
