from __future__ import annotations

import abc
import asyncio
import collections.abc
import datetime
import enum
import time
import typing

import fastapi
import logfire
from ag_ui import core as agui_core
from pydantic_ai import ui as ai_ui
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex.config import sse_delivery as config_sse_delivery

AGUI_Events = list[agui_core.Event]
AGUI_EventStream = collections.abc.AsyncIterator[agui_core.Event]
AGUI_State = dict[str, typing.Any]


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


class AGUI_Exception(ValueError):
    status_code = 400


class UnknownThread(AGUI_Exception):
    status_code = 404

    def __init__(self, user_name: str, thread_id: str):  # pragma: NO COVER
        self.user_name = user_name
        self.thread_id = thread_id
        message = f"Unknown thread: UUID {thread_id} for user {user_name}"
        super().__init__(message)


class UnknownRun(AGUI_Exception):
    status_code = 404

    def __init__(self, run_id: str):  # pragma: NO COVER
        self.run_id = run_id
        super().__init__(
            f"Unknown run: UUID {run_id} does not exist in thread"
        )


class ThreadRoomMismatch(AGUI_Exception):
    def __init__(self, room_id: str, thread_room_id: str):  # pragma: NO COVER
        self.room_id = room_id
        self.thread_room_id = thread_room_id
        super().__init__(
            f"Thread room ID '{thread_room_id}' "
            f"does not match room ID '{room_id}'"
        )


class MissingParentRun(AGUI_Exception):
    def __init__(self, parent_run_id: str):  # pragma: NO COVER
        self.parent_run_id = parent_run_id
        super().__init__(
            f"Unknown parent run: UUID {parent_run_id} "
            f"does not exist in thread"
        )


class RunAlreadyStarted(AGUI_Exception):
    def __init__(
        self,
        user_name: str,
        thread_id: str,
        run_id: str,
    ):  # pragma: NO COVER
        self.user_name = user_name
        self.thread_id = thread_id
        self.run_id = run_id
        super().__init__(f"Run already started: UUID {run_id}")


#
#   ABCs defined here are notional contracts.
#


RunUsageStats = collections.namedtuple(
    "RunUsageStats",
    [
        "input_tokens",
        "output_tokens",
        "requests",
        "tool_calls",
        "final_input_tokens",
        "resolved_model_name",
        "final_output_tokens",
    ],
    # Rows written before these columns existed deserialize with them
    # unset, so they stay optional at the tuple boundary too.
    defaults=(None, None, None),
)


class RunUsage(abc.ABC):
    """LLM usage for a run"""

    input_tokens: int
    """LLM input tokens consumed"""

    output_tokens: int
    """LLM output tokens consumed"""

    requests: int
    """LLM requests made"""

    tool_calls: int
    """LLM tool_calls made"""

    final_input_tokens: int | None
    """Input tokens of the run's *last* model request.

    'input_tokens' is cumulative across every request in the run, so a
    multi-step tool loop reports several times the context actually sent.
    This is the single measurement that answers how full the window was
    when the run ended, which is what a client's context indicator needs.
    None when the run produced no model response.
    """

    resolved_model_name: str | None
    """Model id the provider reported, which may differ from the configured
    name (an alias, or a name carrying a version suffix). Clients pick a
    tokenizer from it in preference to the configured string.
    """

    final_output_tokens: int | None
    """Output tokens of the run's *last* model request.

    That response is the reply the thread now ends with, and it is part of
    the next request's input. 'final_input_tokens' alone therefore reads
    one reply short of what the window holds; the sum of the two is the
    thread's occupancy. None when the run produced no model response.

    The provider's own count, as reported: on a reasoning model it includes
    the reasoning, which providers generally do not carry into the next
    request, so the sum reads high there by the last reply's reasoning --
    never low -- until the next run measures. Ollama itemises no reasoning
    count, so nothing more exact is available for it.
    """

    @abc.abstractmethod
    def as_tuple(self) -> RunUsageStats:
        """Return values as a tuple."""


class FeedbackReviewStatus(enum.StrEnum):
    """Workflow state for feedback."""

    REVIEWED = "reviewed"
    RESOLVED = "resolved"


class RunFeedbackReviewEntry(abc.ABC):
    status: FeedbackReviewStatus
    """Reviewer marked state"""

    note: str | None = None
    """Reviewer supplied"""

    created: datetime.datetime
    """Timestamp"""


class RunFeedback(abc.ABC):
    """Feedback returned from a user for a run"""

    feedback: str
    """Feedback for a run (thumbs up / thumbs down)"""

    reason: str | None
    """Explanation"""

    created: datetime.datetime
    """Timestamp"""

    updated: datetime.datetime
    """Timestamp"""

    review_history: list[RunFeedbackReviewEntry]
    """Track review state over time"""


class RunMetadata(abc.ABC):
    """User-defined metadata for a run"""

    label: str
    """Label for a run (similar to a git tag)"""


class Run(abc.ABC):
    """Input data and events for an AGUI run

    Runs are not accessed directly:  use 'ThreadStorage'.
    """

    thread_id: str
    """ID of the thread in which the run was created"""

    run_id: str
    """Unique ID for a run"""

    parent_run_id: str | None
    """ID of the parent run"""

    run_usage: RunUsage | None
    """Optional LLM usage data for a run"""

    run_metadata: RunMetadata | None
    """Optional user-defined metadata for a run"""

    run_input: agui_core.RunAgentInput
    """Input from the client-request which initiates the AG-UI run"""

    created: datetime.datetime
    """Timestamp"""

    @abc.abstractmethod
    async def list_events(self) -> AGUI_Events:
        """Return AGUI events for the run"""


class ThreadMetadata(abc.ABC):
    """Optional user-defined thread metadata"""

    name: str
    """Name for the thread"""

    description: str
    """Description for the thread"""


class Thread(abc.ABC):
    """Hold a set of AGUI runs sharing the same 'thread_id'

    Runs are not accessed directly:  use 'ThreadStorage'.
    """

    thread_id: str
    """Unique ID for the thread"""

    room_id: str
    """ID for room in which the thread was created"""

    user_name: str
    """'preferred_username' claim for user who created the thread"""

    email: str | None
    """'email' claim for user who created the thread

    Optional only for forward-compatibility of existing data.
    """

    thread_metadata: ThreadMetadata | None
    """Optional thread metadata"""

    created: datetime.datetime
    """Timestamp"""

    @abc.abstractmethod
    async def list_runs(self) -> list[Run]:
        """Return runs for this thread"""


class ThreadStorage(abc.ABC):
    @abc.abstractmethod
    async def list_user_threads(
        self,
        *,
        user_name: str,
        room_id: str = None,
    ) -> list[Thread]:
        """Return a list of the user's threads.

        If 'room_id' is passed, filter the threads to those created
        in that room.
        """

    @abc.abstractmethod
    async def get_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
    ) -> Thread:
        """Return the actual thread instance

        N.B.:  caller must treat the instance as read-only!
        """

    @abc.abstractmethod
    async def get_room_last_activity(
        self,
        *,
        user_name: str,
        room_id: str,
    ) -> datetime.datetime | None:
        """Return the user's latest run activity in a room, or None.

        Activity is the latest, across the user's runs in the room, of
        each run's finish time or -- if it has not finished -- its
        creation time. None when the user has no runs there.
        """

    @abc.abstractmethod
    async def get_rooms_last_activity(
        self,
        *,
        user_name: str,
    ) -> dict[str, datetime.datetime]:
        """Return the user's latest run activity for each of their rooms.

        Keyed by room_id; each value is that room's latest activity as
        in 'get_room_last_activity' (never None). Rooms in which the
        user has no runs are omitted.
        """

    @abc.abstractmethod
    async def get_threads_last_activity(
        self,
        *,
        user_name: str,
        room_id: str,
    ) -> dict[str, datetime.datetime]:
        """Return the user's latest run activity for each thread in a room.

        Keyed by thread_id (the AG-UI protocol id); each value is that
        thread's latest activity as in 'get_room_last_activity' (never
        None). Threads in which the user has no runs are omitted.
        """

    @abc.abstractmethod
    async def new_thread(
        self,
        *,
        user_name: str,
        email: str,
        room_id: str,
        thread_metadata: ThreadMetadata | dict = None,
        initial_run: bool = True,
    ) -> Thread:
        """Create a new thread

        If 'thread_metadata' is a dict, convert it to a 'ThreadMetadata'
        instance.
        """

    @abc.abstractmethod
    async def update_thread_metadata(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        thread_metadata: ThreadMetadata | dict = None,
    ) -> Thread:
        """Update thread instance with the given metadata, or None

        If 'thread_metadata' is a dict, convert it to a 'ThreadMetadata'
        instance.

        If 'thread_metadata' is None, or an empty dict, remove any existing
        metadata on the thread.
        """

    @abc.abstractmethod
    async def delete_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
    ) -> None:
        """Remove a thread"""

    @abc.abstractmethod
    async def new_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_metadata: RunMetadata = None,
        parent_run_id: str = None,
    ) -> Run:
        """Create a new run for the thread

        If 'run_metadata' is a dict, convert it to a 'RunMetadata' instance.

        If 'parent_run_id' is passed, ensure it is valid.
        """

    @abc.abstractmethod
    async def get_run(
        self,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> Run:
        """Return an existing run for a thread"""

    @abc.abstractmethod
    async def add_run_input(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        run_input: agui_core.RunAgentInput,
    ) -> Run:
        """Update a run with the given 'run_agent_input'"""

    @abc.abstractmethod
    async def update_run_metadata(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        run_metadata: RunMetadata | dict = None,
    ) -> Run:
        """Update a run with the given metadata

        If 'run_metadata' is a dict, convert it to a 'RunMetadata' instance.

        If 'run_metadata' is None, or an empty dict, remove any existing
        metadata on the run.
        """

    @abc.abstractmethod
    async def save_single_event(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        event: agui_core.Event,
    ) -> None:
        """Save a single event for a run (incremental persistence)"""

    @abc.abstractmethod
    async def finish_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> None:
        """Mark a run as finished"""

    @abc.abstractmethod
    async def list_run_events_after(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        after_index: int,
    ) -> list[tuple[int, agui_core.Event]]:
        """Return events[after_index + 1:]

        Each element is a (event_index, event) tuple.
        """

    @abc.abstractmethod
    async def is_run_finished(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> bool:
        """Return True if the run has a 'finished' timestamp"""

    @abc.abstractmethod
    async def save_run_events(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        events: AGUI_Events,
    ) -> AGUI_Events:
        """Save the events for a gven run"""

    @abc.abstractmethod
    async def save_run_usage(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        input_tokens: int,
        output_tokens: int,
        requests: int,
        tool_calls: int,
    ):
        """Save the run usage statistics"""

    @abc.abstractmethod
    async def get_run_usage(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> RunUsage | None:
        """Get the run usage, if stored"""

    @abc.abstractmethod
    async def save_run_feedback(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        feedback: str,
        reason: str,
    ):
        """Save the run feedback"""

    @abc.abstractmethod
    async def get_run_feedback(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> RunFeedback | None:
        """Get the run feedback"""

    @abc.abstractmethod
    async def list_recent_run_feedback(
        self,
        *,
        user_name: str | None = None,
        email: str | None = None,
        room_id: str | None = None,
        thread_id: str | None = None,
        limit: int | None = None,
        since: datetime.datetime | None = None,
    ) -> typing.Sequence[Run]:
        """Query run feedback matching given criteria

        Selected values are returned in most-recent first order,
        based on the run's timestamp.
        """

    @typing.overload
    async def review_run_feedback(
        self,
        note: str | None = None,
        *,
        run_feedback: RunFeedback,
    ) -> RunFeedbackReviewEntry: ...

    @typing.overload
    async def review_run_feedback(
        self,
        note: str | None = None,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> RunFeedbackReviewEntry: ...

    @typing.overload
    async def resolve_run_feedback(
        self,
        note: str | None = None,
        *,
        run_feedback: RunFeedback,
    ) -> RunFeedbackReviewEntry: ...

    @typing.overload
    async def resolve_run_feedback(
        self,
        note: str | None = None,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> RunFeedbackReviewEntry: ...


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
    delivery: config_sse_delivery.AGUI_SSEDeliveryConfig,
) -> AGUI_EventStream:
    if (
        delivery.strategy
        == config_sse_delivery.AGUI_SSEDeliveryStrategy.BOUNDED
    ):
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


async def get_the_threads(request: fastapi.Request) -> ThreadStorage:
    from . import persistence

    engine = request.state.threads_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        # One transaction per request: the storage methods no longer
        # commit, so the request owns the unit of work -- committed on a
        # clean response, rolled back if the handler raises.
        async with session.begin():
            yield persistence.ThreadStorage(session)


depend_the_threads = fastapi.Depends(get_the_threads)
