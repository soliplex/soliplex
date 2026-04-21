from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex import agui as agui_package

MESSAGE_ID_1 = "message-id-1"
MESSAGE_ID_2 = "message-id-2"

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

TOOL_CALL_ID = "test-tool-call-id"
TOOL_CALL_NAME = "test_tool_call_name"
TOOL_CALL_START = agui_core.ToolCallStartEvent(
    tool_call_id=TOOL_CALL_ID,
    tool_call_name=TOOL_CALL_NAME,
)
TOOL_CALL_ARGS_A = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta="A ",
)
TOOL_CALL_ARGS_B = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta="B ",
)
TOOL_CALL_ARGS_C = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta="C",
)
TOOL_CALL_ARGS_AB = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta="A B ",
)
TOOL_CALL_ARGS_ABC = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta="A B C",
)
TOOL_CALL_END = agui_core.ToolCallEndEvent(
    tool_call_id=TOOL_CALL_ID,
)


TEXT_CONTENT_2_D = agui_core.TextMessageContentEvent(
    message_id=MESSAGE_ID_2,
    delta="D ",
)

OTHER = agui_core.RawEvent(event=None, source="test-raw")


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
        (
            [TOOL_CALL_START, TOOL_CALL_ARGS_A, TOOL_CALL_END],
            [TOOL_CALL_START, TOOL_CALL_ARGS_A, TOOL_CALL_END],
        ),
        (
            [
                TOOL_CALL_START,
                TOOL_CALL_ARGS_A,
                TOOL_CALL_ARGS_B,
                TOOL_CALL_ARGS_C,
                TOOL_CALL_END,
            ],
            [TOOL_CALL_START, TOOL_CALL_ARGS_ABC, TOOL_CALL_END],
        ),
        (
            [
                TOOL_CALL_START,
                TOOL_CALL_ARGS_A,
                TOOL_CALL_ARGS_B,
                OTHER,
                TOOL_CALL_ARGS_C,
                TOOL_CALL_END,
            ],
            [
                TOOL_CALL_START,
                TOOL_CALL_ARGS_AB,
                OTHER,
                TOOL_CALL_ARGS_C,
                TOOL_CALL_END,
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
