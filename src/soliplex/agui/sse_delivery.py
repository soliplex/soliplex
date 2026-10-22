# ============================================================================
#   AG-UI event-stream delivery shaping machinery
# ============================================================================

import asyncio
import collections.abc
import time

import logfire
from ag_ui import core as agui_core
from pydantic_ai import ui as ai_ui

from soliplex.config import sse_delivery as config_sse_delivery

AGUI_EventStream = collections.abc.AsyncIterator[agui_core.Event]


_COMPACTIBLE_TYPES = {  # event_type: compacting_attr
    agui_core.EventType.TEXT_MESSAGE_CONTENT: "message_id",
    agui_core.EventType.THINKING_TEXT_MESSAGE_CONTENT: "message_id",
    agui_core.EventType.REASONING_MESSAGE_CONTENT: "message_id",
    agui_core.EventType.TOOL_CALL_ARGS: "tool_call_id",
}

#
#   Events which terminate a run's event stream
#
TERMINAL_EVENT_TYPES = frozenset(
    [
        agui_core.EventType.RUN_FINISHED,
        agui_core.EventType.RUN_ERROR,
    ]
)


async def compact_event_stream(stream: AGUI_EventStream):
    compacting: agui_core.Event = None
    compacting_id: str = None
    compacting_attr: str = None

    async for event in stream:
        if compacting is not None:
            event_id = getattr(event, compacting_attr, None)
            if event.type == compacting.type and event_id == compacting_id:
                compacting.delta += event.delta
            else:
                to_yield, compacting = compacting, None
                yield to_yield
                yield event

        else:
            compacting_attr = _COMPACTIBLE_TYPES.get(event.type)
            if compacting_attr is not None:
                compacting = event.model_copy()
                compacting_id = getattr(event, compacting_attr, None)
            else:
                yield event


_hold_clock = time.monotonic
_wait = asyncio.wait
_TIMEOUT = object()
_BACKGROUND_PUMPS: set[asyncio.Task] = set()


class _PumpState:
    def __init__(self):
        self.closing = False
        self.error: Exception | None = None


async def _pump(
    stream: AGUI_EventStream,
    queue: asyncio.Queue,
    state: _PumpState,
) -> _PumpState:
    """Iterate and close 'stream' in this one task, putting events on 'queue'

    Returns 'state', holding any error from iterating or closing the
    stream.  'state.closing' is set before closing, after which the task is
    no longer cancelled.  If the task is cancelled, the error is logged, as
    nobody will read it.
    """
    cancelled = False

    try:
        async for event in stream:
            await queue.put(event)
    except asyncio.CancelledError:
        cancelled = True
    except Exception as exc:
        state.error = exc

    state.closing = True
    aclose = getattr(stream, "aclose", None)
    if aclose is not None:
        try:
            await aclose()
        except Exception as close_exc:
            if state.error is None:
                state.error = close_exc
            else:
                state.error.add_note(
                    f"Closing the stream also failed: {close_exc!r}"
                )

    if cancelled or asyncio.current_task().cancelling():
        if state.error is not None:
            logfire.error(
                "AG-UI event stream failed after cancellation: {error!r}",
                error=state.error,
            )
        raise asyncio.CancelledError

    return state


def _log_undelivered(error: Exception):
    logfire.error(
        "AG-UI event stream failed after its consumer closed: {error!r}",
        error=error,
    )


def _forget_background_pump(pump: asyncio.Task):
    """Drop a pump left closing by a cancelled consumer, logging its error"""
    _BACKGROUND_PUMPS.discard(pump)
    if not pump.cancelled() and pump.exception() is None:
        error = pump.result().error
        if error is not None:
            _log_undelivered(error)


async def _next_item(queue: asyncio.Queue, pump: asyncio.Future, timeout):
    """Return the next queued event, else the pump's result once it is done

    Returns '_TIMEOUT' if neither arrives within 'timeout' seconds.
    """
    if queue.empty() and not pump.done():
        getter = asyncio.ensure_future(queue.get())
        try:
            await _wait(
                {getter, pump},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            if not getter.done():
                getter.cancel()
                await asyncio.wait({getter})

        if not getter.cancelled():
            return getter.result()

    if not queue.empty():
        return queue.get_nowait()

    if pump.done():
        if pump.cancelled():
            raise asyncio.CancelledError
        return pump.result()

    return _TIMEOUT


async def coalesce_event_stream(
    stream: AGUI_EventStream,
    *,
    max_deltas: int,
    max_bytes: int,
    max_ms: int,
) -> AGUI_EventStream:
    """Merge deltas as 'compact_event_stream' does, within bounds

    The merged event is yielded once it holds 'max_deltas' deltas, or
    'max_bytes' bytes of UTF-8 text, or has been held about 'max_ms'
    milliseconds (a target, checked when the event loop runs this
    generator), or when any other event arrives.  The upstream is
    iterated and closed in a separate task, so the time bound applies
    while the upstream is quiet.
    """
    queue = asyncio.Queue(maxsize=1)
    state = _PumpState()
    pump = asyncio.create_task(_pump(stream, queue, state))
    delivered = False
    held = held_attr = held_id = None
    held_count = 0
    deadline = 0.0

    try:
        while True:
            timeout = None
            if held is not None:
                timeout = max(0.0, deadline - _hold_clock())

            item = await _next_item(queue, pump, timeout)

            if held is not None and _hold_clock() >= deadline:
                to_yield, held = held, None
                yield to_yield

            if item is _TIMEOUT:
                continue

            if item is state:
                if held is not None:
                    yield held
                delivered = True
                if state.error is not None:
                    raise state.error
                return

            if (
                held is not None
                and item.type == held.type
                and getattr(item, held_attr, None) == held_id
            ):
                held.delta += item.delta
                held_count += 1
            else:
                if held is not None:
                    to_yield, held = held, None
                    yield to_yield

                held_attr = _COMPACTIBLE_TYPES.get(item.type)
                if held_attr is None:
                    yield item
                    continue

                held = item.model_copy()
                held_id = getattr(item, held_attr, None)
                held_count = 1
                deadline = _hold_clock() + max_ms / 1000

            if (
                held_count >= max_deltas
                or len(held.delta.encode("utf-8")) >= max_bytes
            ):
                to_yield, held = held, None
                yield to_yield

    finally:
        if not state.closing:
            pump.cancel()
        try:
            await asyncio.shield(pump)
        except asyncio.CancelledError:
            if asyncio.current_task().cancelling():
                _BACKGROUND_PUMPS.add(pump)
                pump.add_done_callback(_forget_background_pump)
                raise
        else:
            if not delivered and state.error is not None:
                _log_undelivered(state.error)


def apply_delivery_strategy(
    stream: AGUI_EventStream,
    delivery: config_sse_delivery.SSEDeliveryConfig,
) -> AGUI_EventStream:
    if delivery.strategy == config_sse_delivery.SSEDeliveryStrategy.BOUNDED:
        return coalesce_event_stream(
            stream,
            max_deltas=delivery.max_deltas,
            max_bytes=delivery.max_bytes,
            max_ms=delivery.max_ms,
        )

    return compact_event_stream(stream)


async def with_final_state(
    *,
    stream: AGUI_EventStream,
    deps: ai_ui.StateHandler | None,
) -> AGUI_EventStream:
    """Yield events from 'stream', adding a final AG-UI state snapshot.

    The snapshot precedes the run's terminal event: AG-UI clients may stop
    reading after a terminal event, and on replay the parser only accepts a
    snapshot while the run is still in the RUNNING state.
    """
    async for event in stream:
        if deps is not None and event.type in TERMINAL_EVENT_TYPES:
            yield agui_core.StateSnapshotEvent(snapshot=deps.state)

        yield event
