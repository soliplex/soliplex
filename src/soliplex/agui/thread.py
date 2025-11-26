"""Track AGUI threads by user and room.

If / when we move to a "persistent" history store, this module should firewall
that choice away from the rest of the system.
"""

import asyncio
import dataclasses
import datetime
import uuid

import fastapi
from ag_ui import core as agui_core

AGUI_Events = list[agui_core.BaseEvent]


class UnknownThread(fastapi.HTTPException):
    def __init__(self, user_name: str, thread_id: str):
        self.user_name = user_name
        self.thread_id = thread_id
        message = f"Unknown thread: UUID {thread_id} for user {user_name}"
        super().__init__(status_code=404, detail=message)


class UnknownRunId(ValueError):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"Run input run ID {run_id} does not exist in thread")


class MissingParentRunId(ValueError):
    def __init__(self, parent_run_id: str):
        self.parent_run_id = parent_run_id
        super().__init__(
            f"Run input parent run ID {parent_run_id} does not exist in thread"
        )


class RunInputMismatch(ValueError):
    def __init__(self, which: str):
        self.which = which
        super().__init__(f"Run input field does not match run: {which}")


def _make_uuid_str() -> str:
    return str(uuid.uuid4())


def _timestamp() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC)


timestamp = dataclasses.field(default_factory=_timestamp)


@dataclasses.dataclass(frozen=True)
class RunMetadata:
    label: str


@dataclasses.dataclass(frozen=True)
class Run:
    """Hold original input data and events for an AGUI run"""

    run_id: str = dataclasses.field(default_factory=_make_uuid_str)

    _: dataclasses.KW_ONLY

    metadata: RunMetadata = None
    _created: datetime.datetime = timestamp

    run_input: agui_core.RunAgentInput = None

    events: AGUI_Events = dataclasses.field(
        default_factory=list,
    )

    @property
    def thread_id(self) -> str | None:
        if self.run_input is not None:
            return self.run_input.thread_id

    @property
    def parent_run_id(self) -> str | None:
        if self.run_input is not None:
            return self.run_input.parent_run_id

    @property
    def label(self) -> str | None:
        if self.metadata is not None:
            return self.metadata.label

    @property
    def created(self) -> datetime.datetime:
        return self._created

    def check_run_input(self, other_run_input: agui_core.RunAgentInput):
        """Raise if 'other_run_input' IDs do not match"""
        if self.thread_id != other_run_input.thread_id:
            raise RunInputMismatch("thread_id")
        if self.run_id != other_run_input.run_id:
            raise RunInputMismatch("run_id")
        if self.parent_run_id != other_run_input.parent_run_id:
            raise RunInputMismatch("parent_run_id")


RunMap = dict[str, Run]


@dataclasses.dataclass(frozen=True)
class ThreadMetadata:
    name: str
    description: str = None


@dataclasses.dataclass(frozen=True)
class Thread:
    """Hold a set of AGUI runs sharing the same 'thread_id'"""

    room_id: str

    thread_id: str = dataclasses.field(default_factory=_make_uuid_str)

    _: dataclasses.KW_ONLY

    metadata: ThreadMetadata = None
    runs: RunMap = dataclasses.field(default_factory=dict)

    _lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)
    _created: datetime.datetime = timestamp

    @property
    def created(self) -> datetime.datetime:
        return self._created

    async def get_run(self, run_id: str) -> Run:
        async with self._lock:
            try:
                return self.runs[run_id]
            except KeyError:
                raise UnknownRunId(run_id) from None

    async def new_run(
        self,
        *,
        metadata: RunMetadata = None,
        parent_run_id: str = None,
    ) -> Run:
        """Create a new run for the thread

        If 'parent_run_id' is passed, ensure it is valid.
        """
        if parent_run_id is not None and parent_run_id not in self.runs:
            raise MissingParentRunId(parent_run_id)

        run_id = _make_uuid_str()

        async with self._lock:
            assert run_id not in self.runs

            run = self.runs[run_id] = Run(
                run_id=run_id,
                metadata=metadata,
                run_input=agui_core.RunAgentInput(
                    thread_id=self.thread_id,
                    run_id=run_id,
                    parent_run_id=parent_run_id,
                    state=None,
                    messages=[],
                    tools=[],
                    context=[],
                    forwarded_props=None,
                ),
            )

        return run

    async def update_run(
        self,
        *,
        run_id: str,
        metadata: RunMetadata = None,
    ) -> Run:
        """Update run instance with the given metadata, or None"""
        async with self._lock:
            try:
                before = self.runs[run_id]
            except KeyError:
                raise UnknownRunId(run_id) from None

            after = dataclasses.replace(before, metadata=metadata)
            self.runs[run_id] = after

            return after


ThreadsByID = dict[str, Thread]


class Threads:
    def __init__(self):
        self._lock = asyncio.Lock()
        # {user_name -> {thread_id: Thread}}
        self._threads = {}

    async def _find_user_threads(
        self,
        user_name: str,
    ) -> ThreadsByID:
        user_threads = self._threads.get(user_name)

        if user_threads is None:
            return {}

        return user_threads.copy()

    async def _find_thread(
        self,
        user_name: str,
        thread_id: str,
    ) -> Thread:
        user_threads = self._threads.get(user_name)

        if user_threads is None:
            raise UnknownThread(user_name, thread_id)

        thread = user_threads.get(thread_id)

        if thread is None:
            raise UnknownThread(user_name, thread_id)

        return thread

    async def user_threads(self, *, user_name: str) -> ThreadsByID:
        async with self._lock:
            return await self._find_user_threads(user_name)

    async def get_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
    ) -> Thread:
        """Return the actual thread instance

        N.B.:  caller must treat the instance as read-only!
        """
        async with self._lock:
            return await self._find_thread(user_name, thread_id)

    async def new_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        metadata: ThreadMetadata = None,
    ) -> Thread:
        """Create a new thread"""
        thread_id = _make_uuid_str()

        thread = Thread(
            thread_id=thread_id,
            room_id=room_id,
            metadata=metadata,
        )

        async with self._lock:
            user_threads = self._threads.setdefault(user_name, {})
            assert thread_id not in user_threads

            user_threads[thread_id] = thread

        return thread

    async def update_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
        metadata: ThreadMetadata = None,
    ) -> Thread:
        """Update thread instance with the given metadata, or None"""
        async with self._lock:
            before = await self._find_thread(user_name, thread_id)
            after = dataclasses.replace(before, metadata=metadata)
            self._threads[user_name][thread_id] = after
            return after

    async def delete_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
    ) -> None:
        """Remove a thread"""
        async with self._lock:
            threads = await self._find_user_threads(user_name)

            try:
                del threads[thread_id]
            except KeyError:
                raise UnknownThread(user_name, thread_id) from None

            self._threads[user_name] = threads


async def get_the_threads(request: fastapi.Request) -> Threads:
    return request.state.the_threads


depend_the_threads = fastapi.Depends(get_the_threads)
