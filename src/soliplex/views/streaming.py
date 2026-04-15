"""SSE and WebSocket streaming endpoints.

This module provides Server-Sent Events (SSE) and WebSocket endpoints
for real-time streaming communication.
"""

from __future__ import annotations

import asyncio
import time
import typing

import fastapi
from fastapi import WebSocket
from fastapi.responses import StreamingResponse
from starlette.websockets import WebSocketDisconnect

from soliplex import util

SSE_POLL_INTERVAL_SECS = 2.0
SSE_KEEPALIVE_INTERVAL_SECS = 15.0
# SSE message w/o field name before ':' -> a comment
SSE_KEEPALIVE_MESSAGE = ": keepalive {now}\n\n"
HEADERS_DO_NOT_BUFFER_SSE = {
    "Cache-Control": "no-cache, no-store",
    "X-Accel-Buffering": "no",
}

router = fastapi.APIRouter()


async def stream_sse_with_keepalive(
    sse_event_stream,
    *,
    request: fastapi.Request = None,
    log_info: typing.Callable[str, ...] = None,
    poll_interval_secs: float = SSE_POLL_INTERVAL_SECS,
    keepalive_interval_secs: float = SSE_KEEPALIVE_INTERVAL_SECS,
    keepalive_message: str = SSE_KEEPALIVE_MESSAGE,
):
    """Stream SSE events.

    If an event has not occurred within the given interval, emit
    an empty "keepalive" event
    """
    sse_iter = sse_event_stream.__aiter__()
    pending: asyncio.Future = None
    last_update: float = time.monotonic()

    try:
        #  Unroll the more idiomatic 'async for event in sse_event_stream:'
        #  so that we can do keepalive checking at set intervals.
        while True:
            if request is not None:
                if await request.is_disconnected():
                    break

            if pending is None:
                pending = asyncio.ensure_future(sse_iter.__anext__())

            done, _ = await asyncio.wait(
                [pending],
                timeout=poll_interval_secs,
                return_when=asyncio.FIRST_COMPLETED,
            )

            if pending in done:
                try:
                    event = pending.result()
                    yield event
                    last_update = time.monotonic()
                except StopAsyncIteration:
                    break
                finally:
                    pending = None

            else:
                # Poll timed out — check for keepalive
                now = time.monotonic()
                if now - last_update >= keepalive_interval_secs:
                    yield keepalive_message.format(now=now)
                    last_update = time.monotonic()

    except asyncio.CancelledError:
        if request is not None:
            parms = request.path_params
        else:
            parms = {"thread_id": "<unknown>", "run_id": "<unknown>"}

        log_info = log_info(
            "SSE generator cancelled {thread_id}/{run_id}",
            **parms,
        )
        raise

    finally:  # pragma NO COVER
        if pending and not pending.done():
            pending.cancel()


SSE_RECONNECT_POLL_INTERVAL_SECS = 0.2


async def add_sse_event_ids(
    encoded_stream,
    run_id: str,
    start_index: int = 0,
):
    """Wrap an encoded SSE stream to inject ``id:`` fields.

    Each ``data:`` frame is prefixed with
    ``id: {run_id}:{event_index}\\n`` so that clients can reconnect
    using the ``Last-Event-ID`` header.

    Non-data frames (keepalives, comments) pass through unchanged.
    """
    index = start_index
    async for encoded in encoded_stream:
        if encoded.startswith("data:"):
            yield f"id: {run_id}:{index}\n{encoded}"
            index += 1
        else:
            yield encoded


async def stream_from_db(
    the_threads,
    *,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
    after_index: int = -1,
    poll_interval_secs: float = SSE_RECONNECT_POLL_INTERVAL_SECS,
):
    """Yield ``(event_index, event)`` tuples by polling the DB.

    Used for SSE reconnect: reads persisted events written by the
    background ``drive_llm_stream`` task.  Stops when the run is
    marked finished and all remaining events have been drained.
    """
    while True:
        pairs = await the_threads.list_run_events_after(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            after_index=after_index,
        )

        for idx, event in pairs:
            yield event
            after_index = idx

        finished = await the_threads.is_run_finished(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
        )

        if finished:
            # Drain any final events written between the last
            # query and the finished flag being set.
            final = await the_threads.list_run_events_after(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                after_index=after_index,
            )
            for _idx, event in final:
                yield event
            break

        await asyncio.sleep(poll_interval_secs)


@util.logfire_span("GET /ssetest")
@router.get("/ssetest", tags=["streaming"])
async def sse_endpoint():  # pragma: NO COVER
    """Server-Sent Events endpoint for real-time streaming.

    Returns a continuous stream of counter values every second.
    Useful for testing SSE connectivity and for real-time notifications.
    """

    async def event_generator():
        i = 0
        while True:
            await asyncio.sleep(1)
            yield f"data: {i}\n\n"
            i += 1

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.websocket("/wstest")
async def websocket_endpoint(ws: WebSocket):  # pragma: NO COVER
    """WebSocket endpoint for bidirectional real-time communication.

    Accepts a WebSocket connection and sends counter values every second.
    Useful for testing WebSocket connectivity and for interactive applications.
    """
    await ws.accept()
    i = 0
    try:
        while True:
            await asyncio.sleep(1)
            await ws.send_text(str(i))
            i += 1
    except WebSocketDisconnect:
        pass
