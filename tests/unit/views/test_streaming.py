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
