from __future__ import annotations

import abc
import collections.abc
import datetime
import enum
import typing

import fastapi
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

AGUI_Events = list[agui_core.Event]
AGUI_EventStream = collections.abc.AsyncIterator[agui_core.Event]
AGUI_State = dict[str, typing.Any]


_COMPACTIBLE_TYPES = {
    agui_core.EventType.TEXT_MESSAGE_CONTENT,
    agui_core.EventType.THINKING_TEXT_MESSAGE_CONTENT,
    agui_core.EventType.REASONING_MESSAGE_CONTENT,
}


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
    ],
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

    async for event in stream:
        if compacting is not None:
            event_id = getattr(event, "message_id", None)
            if event.type == compacting.type and event_id == compacting_id:
                compacting.delta += event.delta
            else:
                to_yield, compacting = compacting, None
                yield to_yield
                yield event

        else:
            if event.type in _COMPACTIBLE_TYPES:
                compacting = event.model_copy()
                compacting_id = getattr(event, "message_id", None)
            else:
                yield event


async def get_the_threads(request: fastapi.Request) -> ThreadStorage:
    from . import persistence

    engine = request.state.threads_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        yield persistence.ThreadStorage(session)


depend_the_threads = fastapi.Depends(get_the_threads)
