import asyncio
import contextvars
from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex import agui
from soliplex.config import sse_delivery as config_sse_delivery

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

THREAD_ID = "test-thread-id"
RUN_ID = "test-run-id"

RUN_STARTED = agui_core.RunStartedEvent(thread_id=THREAD_ID, run_id=RUN_ID)
RUN_FINISHED = agui_core.RunFinishedEvent(thread_id=THREAD_ID, run_id=RUN_ID)
RUN_ERROR = agui_core.RunErrorEvent(message="test error")

FINAL_STATE = {"rag": {"citations": ["c1"]}}
STATE_SNAPSHOT = agui_core.StateSnapshotEvent(snapshot=FINAL_STATE)


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

    found = [event async for event in agui.compact_event_stream(stream())]

    for f_event, e_event in zip(found, expected, strict=True):
        assert f_event == e_event


@pytest.mark.anyio
@pytest.mark.parametrize(
    "events, w_deps, expected",
    [
        # A snapshot precedes either terminal event, ...
        (
            [RUN_STARTED, RUN_FINISHED],
            True,
            [RUN_STARTED, STATE_SNAPSHOT, RUN_FINISHED],
        ),
        (
            [RUN_STARTED, RUN_ERROR],
            True,
            [RUN_STARTED, STATE_SNAPSHOT, RUN_ERROR],
        ),
        # ... but only for a run which carries AG-UI state, ...
        (
            [RUN_STARTED, RUN_FINISHED],
            False,
            [RUN_STARTED, RUN_FINISHED],
        ),
        # ... and only if the stream reaches a terminal event.
        (
            [RUN_STARTED, OTHER],
            True,
            [RUN_STARTED, OTHER],
        ),
    ],
)
async def test_with_final_state(events, w_deps, expected):
    deps = mock.Mock(state=FINAL_STATE) if w_deps else None

    async def stream():
        for event in events:
            yield event

    found = [
        event
        async for event in agui.with_final_state(
            stream=stream(),
            deps=deps,
        )
    ]

    for f_event, e_event in zip(found, expected, strict=True):
        assert f_event == e_event


@pytest.mark.anyio
@mock.patch("soliplex.agui.persistence.ThreadStorage")
async def test_get_the_threads(ts_klass, fake_async_session):
    engine = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.threads_engine = engine

    counter = 0

    with mock.patch(
        "sqlalchemy.ext.asyncio.AsyncSession",
        new=fake_async_session.cls,
    ):
        async for the_threads in agui.get_the_threads(request):
            assert the_threads is ts_klass.return_value
            counter += 1

    assert counter == 1

    ts_klass.assert_called_once_with(fake_async_session.session)

    fake_async_session.cls.assert_called_once_with(bind=engine)


BIG_MS = 60_000
HANG_GUARD_SECS = 5
BOUNDED_KW = {"max_deltas": 1_000, "max_bytes": 1_000_000, "max_ms": BIG_MS}
TEST_VAR = contextvars.ContextVar("test_var")
FAILED_WHILE_CANCELLED = "failed while cancelled"
CLOSE_FAILED = "close failed"


def _text(delta, message_id=MESSAGE_ID_1, **kw):
    return agui_core.TextMessageContentEvent(
        message_id=message_id,
        delta=delta,
        **kw,
    )


def _summary(events):
    return [getattr(event, "delta", event.type) for event in events]


async def _aiter(events):
    for event in events:
        yield event


async def _drain(stream, found=None):
    found = [] if found is None else found
    async for event in stream:
        found.append(event)
    return found


async def _until(predicate):
    async with asyncio.timeout(HANG_GUARD_SECS):
        while not predicate():
            await asyncio.sleep(0)


def _coalesce(events, **kw):
    return agui.coalesce_event_stream(_aiter(events), **(BOUNDED_KW | kw))


class FakeTime:
    """Hold clock and wait seam driven by the test

    A timed wait returns when an awaited future completes, or once the test
    advances the clock to that wait's deadline with 'advance_to'.
    'wait_started' is the clock time at which the latest timed wait began.
    """

    def __init__(self):
        self.now = 0.0
        self.wait_started = None
        self._deadline = None
        self._expired = None

    def clock(self):
        return self.now

    async def wait(self, fs, *, timeout, return_when):
        if timeout is None:
            await asyncio.wait(fs, return_when=return_when)
            return

        self.wait_started = self.now
        self._deadline = self.now + timeout
        self._expired = asyncio.get_running_loop().create_future()
        await asyncio.wait({*fs, self._expired}, return_when=return_when)

    def advance_to(self, now):
        self.now = now
        if not self._expired.done() and now >= self._deadline:
            self._expired.set_result(None)


@pytest.fixture
def fake_time(monkeypatch):
    fake = FakeTime()
    monkeypatch.setattr(agui, "_hold_clock", fake.clock)
    monkeypatch.setattr(agui, "_wait", fake.wait)
    return fake


class Channel:
    """Upstream fed by the test; 'None' ends it"""

    def __init__(self):
        self.queue = asyncio.Queue()

    def __aiter__(self):
        return self

    async def __anext__(self):
        event = await self.queue.get()
        if event is None:
            raise StopAsyncIteration
        return event

    def send(self, *events):
        for event in events:
            self.queue.put_nowait(event)


class Upstream:
    """Async iterator with an 'aclose' which can fail

    'started' is set, and 'iterated_in' records the task, on the first
    '__anext__'.
    """

    def __init__(self, events, *, fail=None, close_fail=None):
        self.events = list(events)
        self.fail = fail
        self.close_fail = close_fail
        self.started = asyncio.Event()
        self.iterated_in = None
        self.closed_in = []

    def __aiter__(self):
        return self

    def _note_start(self):
        if not self.started.is_set():
            self.started.set()
            self.iterated_in = asyncio.current_task()

    async def __anext__(self):
        self._note_start()
        if self.events:
            return self.events.pop(0)
        if self.fail is not None:
            raise self.fail
        raise StopAsyncIteration

    async def aclose(self):
        self.closed_in.append(asyncio.current_task())
        if self.close_fail is not None:
            raise self.close_fail


class NoCloseUpstream:
    def __init__(self, events):
        self.events = list(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.events:
            return self.events.pop(0)
        raise StopAsyncIteration


@pytest.mark.anyio
@pytest.mark.parametrize(
    "deltas, kw, expected",
    [
        ("abcdefghij", {"max_deltas": 4}, ["abcd", "efgh", "ij"]),
        ("abc", {"max_deltas": 1}, ["a", "b", "c"]),
        ("abc", {}, ["abc"]),
        (["é", "é", "é"], {"max_bytes": 4}, ["éé", "é"]),
        (["é", "é", "é"], {"max_bytes": 3}, ["éé", "é"]),
        (["xxxxxxxxxx", "y", "z"], {"max_bytes": 4}, ["xxxxxxxxxx", "yz"]),
        ("abcd", {"max_deltas": 3, "max_bytes": 2}, ["ab", "cd"]),
        ("abcd", {"max_deltas": 2, "max_bytes": 3}, ["ab", "cd"]),
    ],
)
async def test_coalesce_event_stream_count_and_byte_triggers(
    deltas,
    kw,
    expected,
):
    events = [TEXT_START_1, *[_text(d) for d in deltas], TEXT_END_1]

    found = [event async for event in _coalesce(events, **kw)]

    assert _summary(found) == [
        agui_core.EventType.TEXT_MESSAGE_START,
        *expected,
        agui_core.EventType.TEXT_MESSAGE_END,
    ]
    assert "".join(e.delta for e in found[1:-1]) == "".join(deltas)


@pytest.mark.anyio
async def test_coalesce_event_stream_no_merge_across_ids():
    events = [
        _text("a", MESSAGE_ID_1),
        _text("b", MESSAGE_ID_2),
        _text("c", MESSAGE_ID_2),
        TEXT_END_1,
    ]

    found = [event async for event in _coalesce(events)]

    assert _summary(found) == ["a", "bc", agui_core.EventType.TEXT_MESSAGE_END]
    assert [event.message_id for event in found[:2]] == [
        MESSAGE_ID_1,
        MESSAGE_ID_2,
    ]


@pytest.mark.anyio
async def test_coalesce_event_stream_no_merge_across_tool_call_ids():
    other_args = agui_core.ToolCallArgsEvent(
        tool_call_id="other-tool-call-id",
        delta="X",
    )
    events = [TOOL_CALL_ARGS_A, other_args, TOOL_CALL_ARGS_B]

    found = [event async for event in _coalesce(events)]

    assert found == events


@pytest.mark.anyio
async def test_coalesce_event_stream_prefetches_at_most_two_events():
    produced = []
    received = []

    async def upstream():
        for index in range(10):
            produced.append(index)
            yield agui_core.CustomEvent(name="test", value=index)

    stream = agui.coalesce_event_stream(upstream(), **BOUNDED_KW)
    try:
        async for event in stream:
            received.append(event.value)
            assert len(produced) <= len(received) + 2
    finally:
        await stream.aclose()

    assert received == list(range(10))


@pytest.mark.anyio
async def test_coalesce_event_stream_no_merge_across_types():
    events = [THINK_CONTENT_A, TEXT_CONTENT_1_A, TEXT_CONTENT_1_B]

    found = [event async for event in _coalesce(events)]

    assert found == [THINK_CONTENT_A, TEXT_CONTENT_1_AB]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "first, second, merged",
    [
        (TEXT_CONTENT_1_A, TEXT_CONTENT_1_B, TEXT_CONTENT_1_AB),
        (THINK_CONTENT_A, THINK_CONTENT_B, THINK_CONTENT_AB),
        (TOOL_CALL_ARGS_A, TOOL_CALL_ARGS_B, TOOL_CALL_ARGS_AB),
        (
            agui_core.ReasoningMessageContentEvent(
                message_id=MESSAGE_ID_1,
                delta="A ",
            ),
            agui_core.ReasoningMessageContentEvent(
                message_id=MESSAGE_ID_1,
                delta="B ",
            ),
            agui_core.ReasoningMessageContentEvent(
                message_id=MESSAGE_ID_1,
                delta="A B ",
            ),
        ),
    ],
)
async def test_coalesce_event_stream_merges_each_eligible_type(
    first,
    second,
    merged,
):
    found = [event async for event in _coalesce([first, second, OTHER])]

    assert found == [merged, OTHER]


@pytest.mark.anyio
async def test_coalesce_event_stream_passes_other_events_after_flush():
    events = [
        RUN_STARTED,
        TEXT_START_1,
        TEXT_CONTENT_1_A,
        TOOL_CALL_START,
        TEXT_CONTENT_1_B,
        TEXT_CONTENT_1_C,
        TEXT_END_1,
        RUN_FINISHED,
    ]

    found = [event async for event in _coalesce(events)]

    assert found == [
        RUN_STARTED,
        TEXT_START_1,
        TEXT_CONTENT_1_A,
        TOOL_CALL_START,
        agui_core.TextMessageContentEvent(
            message_id=MESSAGE_ID_1,
            delta="B C",
        ),
        TEXT_END_1,
        RUN_FINISHED,
    ]


@pytest.mark.anyio
async def test_coalesce_event_stream_keeps_first_timestamp():
    events = [_text("a", timestamp=1), _text("b", timestamp=2)]

    (found,) = [event async for event in _coalesce(events)]

    assert found.delta == "ab"
    assert found.timestamp == 1
    assert events[0].delta == "a"


@pytest.mark.anyio
async def test_coalesce_event_stream_flushes_at_end_of_stream():
    found = [event async for event in _coalesce([_text("a"), _text("b")])]

    assert _summary(found) == ["ab"]


@pytest.mark.anyio
async def test_coalesce_event_stream_empty_upstream():
    assert [event async for event in _coalesce([])] == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "events, expected",
    [
        ([], []),
        ([TEXT_CONTENT_1_A, TEXT_CONTENT_1_B], [TEXT_CONTENT_1_AB]),
    ],
)
async def test_coalesce_event_stream_iteration_error(events, expected):
    upstream = Upstream(events, fail=RuntimeError("boom"))
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    found = []

    with pytest.raises(RuntimeError, match="boom"):
        await _drain(stream, found)

    assert found == expected
    (closed_in,) = upstream.closed_in
    assert closed_in is not asyncio.current_task()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "events, expected",
    [
        ([], []),
        ([TEXT_CONTENT_1_A, TEXT_CONTENT_1_B], [TEXT_CONTENT_1_AB]),
    ],
)
async def test_coalesce_event_stream_close_error(events, expected):
    upstream = Upstream(events, close_fail=RuntimeError("close failed"))
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    found = []

    with pytest.raises(RuntimeError, match="close failed"):
        await _drain(stream, found)

    assert found == expected


@pytest.mark.anyio
async def test_coalesce_event_stream_iteration_and_close_error():
    upstream = Upstream(
        [TEXT_CONTENT_1_A],
        fail=RuntimeError("boom"),
        close_fail=ValueError("close failed"),
    )
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    found = []

    with pytest.raises(RuntimeError, match="boom") as exc_info:
        await _drain(stream, found)

    assert found == [TEXT_CONTENT_1_A]
    (note,) = exc_info.value.__notes__
    assert "close failed" in note


@pytest.mark.anyio
async def test_coalesce_event_stream_upstream_without_aclose():
    upstream = NoCloseUpstream([TEXT_CONTENT_1_A, TEXT_CONTENT_1_B])

    found = [
        event
        async for event in agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    ]

    assert found == [TEXT_CONTENT_1_AB]


@pytest.mark.anyio
async def test_coalesce_event_stream_pump_cancelled_does_not_flush():
    async def upstream():
        yield TEXT_CONTENT_1_A
        asyncio.current_task().cancel()
        await asyncio.sleep(0)

    found = []

    with pytest.raises(asyncio.CancelledError):
        await _drain(
            agui.coalesce_event_stream(upstream(), **BOUNDED_KW),
            found,
        )

    assert found == []


@pytest.mark.anyio
async def test_coalesce_event_stream_upstream_raises_cancelled_error():
    upstream = Upstream([TEXT_CONTENT_1_A], fail=asyncio.CancelledError())
    found = []

    with pytest.raises(asyncio.CancelledError):
        await _drain(
            agui.coalesce_event_stream(upstream, **BOUNDED_KW),
            found,
        )

    assert found == []
    assert len(upstream.closed_in) == 1


@pytest.mark.anyio
async def test_coalesce_event_stream_early_aclose_closes_upstream_in_pump():
    gate = asyncio.Event()
    closed_in = []

    async def upstream():
        token = TEST_VAR.set("set-in-upstream")
        try:
            yield TEXT_START_1
            await gate.wait()
        finally:
            TEST_VAR.reset(token)
            closed_in.append(asyncio.current_task())

    stream = agui.coalesce_event_stream(upstream(), **BOUNDED_KW)

    assert await anext(stream) == TEXT_START_1
    await stream.aclose()

    (closed_task,) = closed_in
    assert closed_task is not asyncio.current_task()
    assert closed_task.cancelled()
    assert closed_task not in agui._BACKGROUND_PUMPS


@pytest.mark.anyio
async def test_coalesce_event_stream_consumer_cancelled_while_holding(
    fake_time,
):
    gate = asyncio.Event()
    closed = asyncio.Event()

    async def upstream():
        try:
            yield TEXT_CONTENT_1_A
            await gate.wait()
        finally:
            closed.set()

    stream = agui.coalesce_event_stream(upstream(), **BOUNDED_KW)
    found = []
    consumer = asyncio.create_task(_drain(stream, found))
    await _until(lambda: fake_time.wait_started is not None)

    consumer.cancel()

    with pytest.raises(asyncio.CancelledError):
        await consumer
    assert found == []
    assert closed.is_set()


@pytest.mark.anyio
async def test_coalesce_event_stream_consumer_cancelled_during_close():
    gate = asyncio.Event()
    waiting = asyncio.Event()
    close_started = asyncio.Event()
    release_close = asyncio.Event()
    closed = asyncio.Event()
    iterated_in = []

    async def upstream():
        iterated_in.append(asyncio.current_task())
        try:
            yield TEXT_CONTENT_1_A
            waiting.set()
            await gate.wait()
        finally:
            close_started.set()
            await release_close.wait()
            closed.set()

    consumer = asyncio.create_task(
        _drain(agui.coalesce_event_stream(upstream(), **BOUNDED_KW)),
    )
    try:
        await _until(waiting.is_set)
        consumer.cancel()
        async with asyncio.timeout(HANG_GUARD_SECS):
            await close_started.wait()
        (pump,) = iterated_in

        consumer.cancel()

        with pytest.raises(asyncio.CancelledError):
            await consumer
        assert not closed.is_set()
        assert pump in agui._BACKGROUND_PUMPS

        release_close.set()
        await _until(lambda: pump not in agui._BACKGROUND_PUMPS)
    finally:
        release_close.set()

    assert closed.is_set()


@pytest.mark.anyio
@mock.patch("soliplex.agui.logfire")
async def test_coalesce_event_stream_logs_close_error_after_cancel(logfire):
    gate = asyncio.Event()

    class Blocked(Upstream):
        async def __anext__(self):
            self._note_start()
            await gate.wait()

    upstream = Blocked([], close_fail=RuntimeError("close failed"))
    consumer = asyncio.create_task(
        _drain(agui.coalesce_event_stream(upstream, **BOUNDED_KW)),
    )
    await _until(upstream.started.is_set)

    consumer.cancel()

    with pytest.raises(asyncio.CancelledError):
        await consumer
    logfire.error.assert_called_once()
    assert isinstance(logfire.error.call_args.kwargs["error"], RuntimeError)


@pytest.mark.anyio
@mock.patch("soliplex.agui.logfire")
async def test_coalesce_event_stream_logs_error_raised_on_cancel(logfire):
    gate = asyncio.Event()

    class FailsOnCancel(Upstream):
        async def __anext__(self):
            self._note_start()
            try:
                await gate.wait()
            except asyncio.CancelledError:
                raise RuntimeError(FAILED_WHILE_CANCELLED) from None

    upstream = FailsOnCancel([])
    consumer = asyncio.create_task(
        _drain(agui.coalesce_event_stream(upstream, **BOUNDED_KW)),
    )
    await _until(upstream.started.is_set)

    consumer.cancel()

    with pytest.raises(asyncio.CancelledError):
        await consumer
    logfire.error.assert_called_once()
    error = logfire.error.call_args.kwargs["error"]
    assert str(error) == FAILED_WHILE_CANCELLED


@pytest.mark.anyio
async def test_coalesce_event_stream_hold_age_while_upstream_quiet(fake_time):
    channel = Channel()
    stream = agui.coalesce_event_stream(
        channel,
        max_deltas=1_000,
        max_bytes=1_000_000,
        max_ms=250,
    )
    found = []
    consumer = asyncio.create_task(_drain(stream, found))

    channel.send(TEXT_CONTENT_1_A)
    await _until(lambda: fake_time.wait_started is not None)

    assert found == []

    fake_time.advance_to(0.25)
    await _until(lambda: found)

    assert found == [TEXT_CONTENT_1_A]

    channel.send(TEXT_CONTENT_1_B, TEXT_END_1, None)
    async with asyncio.timeout(HANG_GUARD_SECS):
        await consumer

    assert found == [TEXT_CONTENT_1_A, TEXT_CONTENT_1_B, TEXT_END_1]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "advance, expected",
    [
        (0.25, [TEXT_CONTENT_1_A, TEXT_CONTENT_1_B]),
        (0.249, [TEXT_CONTENT_1_AB]),
    ],
)
async def test_coalesce_event_stream_event_received_after_deadline(
    fake_time,
    advance,
    expected,
):
    channel = Channel()
    stream = agui.coalesce_event_stream(
        channel,
        max_deltas=1_000,
        max_bytes=1_000_000,
        max_ms=250,
    )
    found = []
    consumer = asyncio.create_task(_drain(stream, found))

    channel.send(TEXT_CONTENT_1_A)
    await _until(lambda: fake_time.wait_started is not None)
    fake_time.now += advance
    channel.send(TEXT_CONTENT_1_B, None)

    async with asyncio.timeout(HANG_GUARD_SECS):
        await consumer

    assert found == expected


@pytest.mark.anyio
async def test_coalesce_event_stream_merge_keeps_hold_deadline(fake_time):
    channel = Channel()
    stream = agui.coalesce_event_stream(
        channel,
        max_deltas=1_000,
        max_bytes=1_000_000,
        max_ms=250,
    )
    found = []
    consumer = asyncio.create_task(_drain(stream, found))
    try:
        channel.send(TEXT_CONTENT_1_A)
        await _until(lambda: fake_time.wait_started == 0.0)
        fake_time.advance_to(0.2)
        channel.send(TEXT_CONTENT_1_B)
        await _until(lambda: fake_time.wait_started == 0.2)

        assert found == []

        fake_time.advance_to(0.25)
        await _until(lambda: found)

        assert found == [TEXT_CONTENT_1_AB]
    finally:
        channel.send(None)
        async with asyncio.timeout(HANG_GUARD_SECS):
            await consumer


@pytest.mark.anyio
async def test_coalesce_event_stream_real_clock_flushes_quiet_hold():
    channel = Channel()
    stream = agui.coalesce_event_stream(
        channel,
        max_deltas=1_000,
        max_bytes=1_000_000,
        max_ms=1,
    )
    channel.send(TEXT_CONTENT_1_A)
    try:
        async with asyncio.timeout(HANG_GUARD_SECS):
            first = await anext(stream)
    finally:
        channel.send(None)
        await stream.aclose()

    assert first == TEXT_CONTENT_1_A


class Fatal(BaseException):
    """Neither an 'Exception' nor a cancellation"""


@pytest.mark.anyio
async def test_coalesce_event_stream_reraises_fatal_upstream_error():
    upstream = Upstream([TEXT_CONTENT_1_A], fail=Fatal())
    found = []

    with pytest.raises(Fatal):
        await _drain(
            agui.coalesce_event_stream(upstream, **BOUNDED_KW),
            found,
        )

    assert found == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "strategy, expected",
    [
        ("message", ["a", "b", "c", agui_core.EventType.TEXT_MESSAGE_END]),
        ("bounded", ["a", "bc", agui_core.EventType.TEXT_MESSAGE_END]),
    ],
)
async def test_apply_delivery_strategy(strategy, expected):
    delivery = config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
        None,
        {"strategy": strategy} | ({} if strategy == "message" else BOUNDED_KW),
    )
    events = [
        _text("a", MESSAGE_ID_1),
        _text("b", MESSAGE_ID_2),
        _text("c", MESSAGE_ID_2),
        TEXT_END_1,
    ]

    found = [
        event
        async for event in agui.apply_delivery_strategy(
            _aiter(events),
            delivery,
        )
    ]

    assert _summary(found) == expected


@pytest.mark.anyio
async def test_coalesce_event_stream_early_close_waits_for_normal_close():
    close_started = asyncio.Event()
    release_close = asyncio.Event()
    outcome = []

    class SlowClose(Upstream):
        async def aclose(self):
            close_started.set()
            await release_close.wait()
            outcome.append("closed")

    upstream = SlowClose([OTHER])
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    try:
        assert await anext(stream) == OTHER
        async with asyncio.timeout(HANG_GUARD_SECS):
            await close_started.wait()

        closer = asyncio.ensure_future(stream.aclose())
        await asyncio.sleep(0)

        assert not closer.done()

        release_close.set()
        async with asyncio.timeout(HANG_GUARD_SECS):
            await closer
    finally:
        release_close.set()

    assert outcome == ["closed"]


@pytest.mark.anyio
@mock.patch("soliplex.agui.logfire")
async def test_coalesce_event_stream_logs_close_error_after_early_close(
    logfire,
):
    upstream = Upstream(
        [TEXT_CONTENT_1_A, TEXT_CONTENT_1_B],
        close_fail=RuntimeError("close failed"),
    )
    stream = agui.coalesce_event_stream(
        upstream,
        **(BOUNDED_KW | {"max_deltas": 1}),
    )

    assert await anext(stream) == TEXT_CONTENT_1_A
    await _until(lambda: upstream.closed_in)
    await stream.aclose()

    logfire.error.assert_called_once()
    error = logfire.error.call_args.kwargs["error"]
    assert str(error) == "close failed"


class TimedDelta(str):
    """Delta text whose UTF-8 encoding advances 'clock' by 'cost' seconds"""

    def __new__(cls, text, clock, cost):
        found = super().__new__(cls, text)
        found.clock = clock
        found.cost = cost
        return found

    def encode(self, *args, **kwargs):
        self.clock[0] += self.cost
        return super().encode(*args, **kwargs)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "cost, expected",
    [
        (1.0, ["a", "b", "c"]),
        (0.0, ["a", "bc"]),
    ],
)
async def test_coalesce_event_stream_expired_hold_with_event_queued(
    monkeypatch,
    cost,
    expected,
):
    """A hold that expires with the next event already queued is flushed

    No await separates establishing a hold from the next deadline check,
    so time can pass there only while the code runs: measuring the held
    delta for 'b' takes 'cost' seconds, while 'c' is already queued.
    """
    clock = [0.0]
    monkeypatch.setattr(agui, "_hold_clock", lambda: clock[0])
    timed_b = _text("b", MESSAGE_ID_2).model_copy(
        update={"delta": TimedDelta("b", clock, cost)},
    )
    channel = Channel()
    channel.send(_text("a", MESSAGE_ID_1), timed_b, _text("c", MESSAGE_ID_2))
    stream = agui.coalesce_event_stream(
        channel,
        max_deltas=1_000,
        max_bytes=1_000_000,
        max_ms=250,
    )
    try:
        first = await anext(stream)
        await _until(channel.queue.empty)
        channel.send(None)
        rest = [event async for event in stream]
    finally:
        await stream.aclose()

    assert _summary([first, *rest]) == expected


@pytest.mark.anyio
@mock.patch("soliplex.agui.logfire")
async def test_coalesce_event_stream_logs_error_closed_at_final_yield(
    logfire,
):
    upstream = Upstream(
        [TEXT_CONTENT_1_A],
        close_fail=RuntimeError("close failed"),
    )
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)

    assert await anext(stream) == TEXT_CONTENT_1_A
    await stream.aclose()

    logfire.error.assert_called_once()
    assert str(logfire.error.call_args.kwargs["error"]) == "close failed"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "close_error, w_log",
    [
        (RuntimeError(CLOSE_FAILED), True),
        (None, False),
        (Fatal(), False),
    ],
)
@mock.patch("soliplex.agui.logfire")
async def test_coalesce_event_stream_detached_close(
    logfire,
    close_error,
    w_log,
):
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    class SlowClose(Upstream):
        async def aclose(self):
            close_started.set()
            await release_close.wait()
            if close_error is not None:
                raise close_error

    upstream = SlowClose([OTHER])
    stream = agui.coalesce_event_stream(upstream, **BOUNDED_KW)
    try:
        assert await anext(stream) == OTHER
        async with asyncio.timeout(HANG_GUARD_SECS):
            await close_started.wait()
        pump = upstream.iterated_in

        closer = asyncio.ensure_future(stream.aclose())
        await asyncio.sleep(0)
        closer.cancel()

        with pytest.raises(asyncio.CancelledError):
            async with asyncio.timeout(HANG_GUARD_SECS):
                await closer
        assert pump in agui._BACKGROUND_PUMPS
        logfire.error.assert_not_called()

        release_close.set()
        await _until(lambda: pump not in agui._BACKGROUND_PUMPS)
    finally:
        release_close.set()

    if w_log:
        logfire.error.assert_called_once()
        error = logfire.error.call_args.kwargs["error"]
        assert str(error) == CLOSE_FAILED
    else:
        logfire.error.assert_not_called()
