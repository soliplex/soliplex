import asyncio
import time
from unittest import mock

import fastapi
import pytest

from soliplex.views import streaming as views_streaming


@pytest.mark.asyncio
@pytest.mark.parametrize("disconnect_after", [None, 0, 2, 1000])
@pytest.mark.parametrize("w_request", [False, True])
@pytest.mark.parametrize(
    "events",
    [
        [],
        ["data: only one\n\n"],
        [f"data: {i_evt}\n\n" for i_evt in range(15)],
    ],
)
async def test_stream_sse_with_keepalive_w_no_timeouts(
    events,
    w_request,
    disconnect_after,
):
    async def event_stream():
        for event in events:
            yield event

    request_kw = {}

    expected = events[:]

    if w_request:
        request = mock.create_autospec(fastapi.Request)

        if disconnect_after is not None:
            flags = [False] * disconnect_after + [True] * 1000
            request.is_disconnected.side_effect = flags
            expected = expected[:disconnect_after]
        else:
            request.is_disconnected.return_value = False

        request_kw = {"request": request}

    found = [
        event
        async for event in views_streaming.stream_sse_with_keepalive(
            event_stream(),
            **request_kw,
        )
    ]

    assert found == expected


@pytest.mark.asyncio
async def test_stream_sse_with_keepalive_w_timeout():
    keepalive_interval = 0.25
    poll_interval = 0.1
    sleep_interval = 0.5
    events = ["data: only one\n\n"]

    async def event_stream():
        for event in events:
            await asyncio.sleep(sleep_interval)
            yield event

    before = time.monotonic()
    found = [
        event
        async for event in views_streaming.stream_sse_with_keepalive(
            event_stream(),
            keepalive_interval_secs=keepalive_interval,
            poll_interval_secs=poll_interval,
        )
    ]
    after = time.monotonic()

    first, *rest = found
    exp_prefix = ": keepalive "
    exp_suffix = "\n\n"
    assert first.startswith(exp_prefix)
    assert first.endswith(exp_suffix)

    timestamp = float(first[len(exp_prefix) : -len(exp_suffix)])
    assert before <= timestamp <= after
    assert rest == events


@pytest.mark.asyncio
@pytest.mark.parametrize("w_request", [False, True])
async def test_stream_sse_with_keepalive_w_cancellation(w_request):
    THREAD_ID = "test-thread"
    RUN_ID = "test-run"

    keepalive_interval = 0.25
    poll_interval = 0.1
    sleep_interval = 0.5
    events = ["data: only one\n\n"]
    log_info = mock.Mock()

    if w_request:
        request = mock.create_autospec(fastapi.Request)
        request.is_disconnected.return_value = False
        request.path_params = {"thread_id": THREAD_ID, "run_id": RUN_ID}
        exp_params = request.path_params
        request_kw = {"request": request}
    else:
        request_kw = {}
        exp_params = {"thread_id": "<unknown>", "run_id": "<unknown>"}

    async def event_stream():
        for _event in events:
            await asyncio.sleep(sleep_interval)
            raise asyncio.CancelledError("testing")
            yield None
        else:  # pragma NO COVER
            pass

    with pytest.raises(asyncio.CancelledError):
        [
            event
            async for event in views_streaming.stream_sse_with_keepalive(
                event_stream(),
                log_info=log_info,
                keepalive_interval_secs=keepalive_interval,
                poll_interval_secs=poll_interval,
                **request_kw,
            )
        ]

    log_info.assert_called_once_with(
        "SSE generator cancelled {thread_id}/{run_id}",
        **exp_params,
    )


# --- add_sse_event_ids tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "events, start_index, expected",
    [
        ([], 0, []),
        (
            ["data: {}\n\n"],
            0,
            ["id: run-1:0\ndata: {}\n\n"],
        ),
        (
            ["data: a\n\n", "data: b\n\n"],
            0,
            ["id: run-1:0\ndata: a\n\n", "id: run-1:1\ndata: b\n\n"],
        ),
        (
            [": keepalive\n\n", "data: x\n\n"],
            0,
            [": keepalive\n\n", "id: run-1:0\ndata: x\n\n"],
        ),
        (
            ["data: a\n\n", "data: b\n\n"],
            5,
            ["id: run-1:5\ndata: a\n\n", "id: run-1:6\ndata: b\n\n"],
        ),
    ],
)
async def test_add_sse_event_ids(events, start_index, expected):
    async def event_stream():
        for event in events:
            yield event

    found = [
        event
        async for event in views_streaming.add_sse_event_ids(
            event_stream(),
            run_id="run-1",
            start_index=start_index,
        )
    ]

    assert found == expected


# --- stream_from_db tests ---


@pytest.mark.asyncio
async def test_stream_from_db_finished_run():
    """Run is already finished: replay events and stop."""
    the_threads = mock.AsyncMock()

    events = [
        (0, mock.Mock(name="evt0")),
        (1, mock.Mock(name="evt1")),
    ]

    the_threads.list_run_events_after = mock.AsyncMock(
        side_effect=[events, []],
    )
    the_threads.is_run_finished = mock.AsyncMock(
        return_value=True,
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            the_threads,
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
        )
    ]

    assert found == [events[0][1], events[1][1]]


@pytest.mark.asyncio
async def test_stream_from_db_in_progress_run():
    """Run is in progress: poll until finished."""
    the_threads = mock.AsyncMock()

    evt0 = (0, mock.Mock(name="evt0"))
    evt1 = (1, mock.Mock(name="evt1"))

    # First poll: one event, not finished
    # Second poll: one more event, now finished
    # Final drain: empty
    the_threads.list_run_events_after = mock.AsyncMock(
        side_effect=[
            [evt0],
            [evt1],
            [],
        ],
    )
    the_threads.is_run_finished = mock.AsyncMock(
        side_effect=[False, True],
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            the_threads,
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
            poll_interval_secs=0.01,
        )
    ]

    assert found == [evt0[1], evt1[1]]


@pytest.mark.asyncio
async def test_stream_from_db_final_drain_has_events():
    """Events arrive between last poll and finished flag."""
    the_threads = mock.AsyncMock()

    evt0 = (0, mock.Mock(name="evt0"))
    evt1 = (1, mock.Mock(name="evt1"))

    # First poll: one event, not finished
    # Second poll: empty, now finished
    # Final drain: one late event
    the_threads.list_run_events_after = mock.AsyncMock(
        side_effect=[
            [evt0],
            [],
            [evt1],
        ],
    )
    the_threads.is_run_finished = mock.AsyncMock(
        side_effect=[False, True],
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            the_threads,
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
            poll_interval_secs=0.01,
        )
    ]

    assert found == [evt0[1], evt1[1]]


@pytest.mark.asyncio
async def test_stream_from_db_empty_finished_run():
    """Run finished with no events."""
    the_threads = mock.AsyncMock()

    the_threads.list_run_events_after = mock.AsyncMock(
        side_effect=[[], []],
    )
    the_threads.is_run_finished = mock.AsyncMock(
        return_value=True,
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            the_threads,
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
        )
    ]

    assert found == []
