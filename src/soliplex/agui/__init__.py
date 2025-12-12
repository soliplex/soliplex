from __future__ import annotations

import abc
import collections.abc
import datetime
import typing

import fastapi
from ag_ui import core as agui_core
from sqlalchemy.ext import asyncio as sqla_asyncio

AGUI_Events = list[agui_core.Event]
AGUI_EventStream = collections.abc.AsyncIterator[agui_core.Event]
AGUI_State = dict[str, typing.Any]


class AGUI_Exception(ValueError):
    status_code = 400


class UnknownThread(AGUI_Exception):
    status_code = 404

    def __init__(self, user_name: str, thread_id: str):
        self.user_name = user_name
        self.thread_id = thread_id
        message = f"Unknown thread: UUID {thread_id} for user {user_name}"
        super().__init__(message)


class UnknownRun(AGUI_Exception):
    status_code = 404

    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(
            f"Unknown run: UUID {run_id} does not exist in thread"
        )


class ThreadRoomMismatch(AGUI_Exception):
    def __init__(self, room_id: str, thread_room_id: str):
        self.room_id = room_id
        self.thread_room_id = thread_room_id
        super().__init__(
            f"Thread room ID '{thread_room_id}' "
            f"does not match room ID '{room_id}'"
        )


class MissingParentRun(AGUI_Exception):
    def __init__(self, parent_run_id: str):
        self.parent_run_id = parent_run_id
        super().__init__(
            f"Unknown parent run: UUID {parent_run_id} "
            f"does not exist in thread"
        )


class RunAlreadyStarted(AGUI_Exception):
    def __init__(self, user_name: str, thread_id: str, run_id: str):
        self.user_name = user_name
        self.thread_id = thread_id
        self.run_id = run_id
        super().__init__(f"Run already started: UUID {run_id}")


#
#   ABCs defined here are notional contracts.
#


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


async def get_the_threads(request: fastapi.Request) -> ThreadStorage:
    from . import persistence

    engine = request.state.threads_engine
    async with sqla_asyncio.AsyncSession(bind=engine) as session:
        yield persistence.ThreadStorage(session)


depend_the_threads = fastapi.Depends(get_the_threads)
