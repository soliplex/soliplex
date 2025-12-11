from __future__ import annotations

import contextlib
import copy
import datetime
import typing

import pydantic
import sqlalchemy
from ag_ui import core as agui_core
from sqlalchemy import orm as sqla_orm
from sqlalchemy import schema as sqla_schema
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio
from sqlalchemy.sql import sqltypes as sqla_sqltypes

from soliplex import agui as agui_package
from soliplex.agui import util as agui_util

AsyncAttrs = sqla_asyncio.AsyncAttrs
DeclarativeBase = sqla_orm.DeclarativeBase
ForeignKey = sqlalchemy.ForeignKey
Mapped = sqla_orm.Mapped
mapped_column = sqla_orm.mapped_column
relationship = sqla_orm.relationship

MESSAGE_DESERIALIZER = pydantic.TypeAdapter(agui_core.Message)
EVENT_DESERIALIZER = pydantic.TypeAdapter(agui_core.Event)

SYNC_MEMORY_ENGINE_URL = "sqlite://"
ASYNC_MEMORY_ENGINE_URL = "sqlite+aiosqlite://"

# Recommended naming convention used by Alembic, as various different database
# providers will autogenerate vastly different names making migrations more
# difficult. See: https://alembic.sqlalchemy.org/en/latest/naming.html
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JSON_Mapped_From = dict[str, typing.Any]

metadata = sqla_schema.MetaData(naming_convention=NAMING_CONVENTION)


class Base(AsyncAttrs, DeclarativeBase):
    metadata = metadata
    type_annotation_map = {
        JSON_Mapped_From: sqla_sqltypes.JSON,
    }


class Thread(Base):
    """Hold a set of AG-UI runs sharing the same 'thread_id'

    'thread_id': the AG-UI protocol level 'thread_id' (distinct from our
        actual primary key).

    'thread_metadata': optional thread metadata, stored in the
        'ThreadMetadata' table via an optional one-to-one relationship.

    'runs": stored in the 'Run' table via a one-to-many relationship.
    """

    __tablename__ = "thread"

    id_: Mapped[int] = mapped_column(primary_key=True)

    #
    #   'soliplex.agui.Thread' contract
    #
    thread_id: Mapped[str] = mapped_column(
        default=agui_util._make_uuid_str,
        index=True,
    )

    room_id: Mapped[str] = mapped_column(index=True)

    thread_metadata: Mapped[ThreadMetadata | None] = sqla_orm.relationship(
        back_populates="thread",
        cascade="all, delete",
        passive_deletes=True,
    )

    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    #
    #   Not part of the generic 'soliplex.agui.Thread' contract
    #
    user_name: Mapped[str] = mapped_column(index=True)
    runs: Mapped[list[Run]] = relationship(
        back_populates="thread",
        order_by="Run.created",
        cascade="all, delete",
        passive_deletes=True,
    )

    async def list_runs(self):
        runs = []

        for run in await self.awaitable_attrs.runs:
            await run.awaitable_attrs.run_agent_input
            await run.awaitable_attrs.run_metadata
            runs.append(run)

        return runs


class ThreadMetadata(Base):
    """Hold optional metadata for an AG-UI thread

    'thread' is a one-to-one relationship to 'Thread' (but optional from
             the thread side).

    'name', required

    'description', optional
    """

    __tablename__ = "thread_metadata"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    thread_id_: Mapped[int] = mapped_column(
        ForeignKey("thread.id_", ondelete="CASCADE"),
    )
    thread: Mapped[Thread] = relationship(back_populates="thread_metadata")

    #
    #   'soliplex.agui.ThreadMetadata' contract
    #
    name: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()


#
#   Work around https://github.com/ag-ui-protocol/ag-ui/issues/752
#
SKIP_EVENT_TYPES = {
    agui_core.EventType.THINKING_START,
    agui_core.EventType.THINKING_TEXT_MESSAGE_START,
    agui_core.EventType.THINKING_TEXT_MESSAGE_CONTENT,
    agui_core.EventType.THINKING_TEXT_MESSAGE_END,
    agui_core.EventType.THINKING_END,
}


class Run(Base):
    """Hold information about an AG-UI runs.

    'run_id': the AG-UI protocol level 'run_id' (distinct from our
        actual primary key).

    'parent_id_': foreign key reference to parent run

    'parent': optional reference to the run's parent run.

    'children': list of the run's child runs.

    'run_metadata': optional run metadata, stored in the 'RunMetadata'
        table via an optional one-to-one relationship.

    'run_agent_input': holds optional AG-UI 'RunAgentInput' (runs can
        be created before the client posts an initial protocol-
        level run).
    """

    __tablename__ = "run"

    id_: Mapped[int] = mapped_column(primary_key=True)

    thread_id_: Mapped[int] = mapped_column(
        ForeignKey("thread.id_", ondelete="CASCADE"),
    )
    thread: sqla_orm.Mapped[Thread] = relationship(
        back_populates="runs",
    )

    parent_id_: Mapped[int | None] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    parent: Mapped[Run | None] = relationship(
        back_populates="children",
        remote_side="Run.id_",
    )
    children: Mapped[list[Run]] = relationship(
        back_populates="parent",
        order_by="Run.created",
        cascade="all, delete",
        passive_deletes=True,
    )

    run_metadata: Mapped[RunMetadata | None] = relationship(
        back_populates="run",
        cascade="all, delete",
        passive_deletes=True,
    )

    run_agent_input: Mapped[RunAgentInput | None] = relationship(
        back_populates="run",
        cascade="all, delete",
        passive_deletes=True,
    )

    events: Mapped[list[RunEvent]] = relationship(
        back_populates="run",
        order_by="RunEvent.created",
        cascade="all, delete",
        passive_deletes=True,
    )

    #
    #   'soliplex.agui.Run' contract
    #
    @property
    def thread_id(self) -> str:
        return self.thread.thread_id

    run_id: Mapped[str] = mapped_column(
        default=agui_util._make_uuid_str,
        index=True,
    )

    @property
    def parent_run_id(self) -> str | None:
        return self.parent.run_id if self.parent is not None else None

    @property
    def run_input(self) -> agui_core.RunAgentInput | None:
        if self.run_agent_input is not None:
            return self.run_agent_input.to_agui_model()

    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    async def list_events(self) -> list[agui_core.Event]:
        return [
            event.to_agui_model()
            for event in await self.awaitable_attrs.events
            # Work around https://github.com/ag-ui-protocol/ag-ui/issues/752
            if event.type not in SKIP_EVENT_TYPES
        ]


class RunMetadata(Base):
    """Hold optional metadata for an AG-UI run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'label', required
    """

    __tablename__ = "run_metadata"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    run_id_: Mapped[int] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    run: Mapped[Run] = relationship(back_populates="run_metadata")

    #
    #   'soliplex.agui.RunMetadata' contract
    #
    label: Mapped[str] = mapped_column()


class RunAgentInput(Base):
    """Hold AG-UI 'RunAgentInput' data for a run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'data' is the dumped state of the 'RunAgentInput'.
    """

    __tablename__ = "run_agent_input"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    run_id_: Mapped[int | None] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    run: Mapped[Run] = relationship(
        back_populates="run_agent_input",
    )

    data: Mapped[JSON_Mapped_From] = mapped_column()

    @classmethod
    def empty(cls, run, thread_id, run_id, parent_run_id=None):
        return cls(
            run=run,
            data={
                "thread_id": thread_id,
                "run_id": run_id,
                "parent_run_id": parent_run_id,
                "state": None,
                "messages": [],
                "context": [],
                "tools": [],
                "forwarded_props": None,
            },
        )

    @classmethod
    def from_agui_model(cls, run: Run, model: agui_core.RunAgentInput):
        return cls(run=run, data=model.model_dump())

    def to_agui_model(self):
        return agui_core.RunAgentInput(
            thread_id=self.thread_id,
            run_id=self.run_id,
            parent_run_id=self.parent_run_id,
            state=self.state,
            messages=self.messages,
            context=self.context,
            tools=self.tools,
            forwarded_props=self.forwarded_props,
        )

    @property
    def thread_id(self) -> str:
        return self.data["thread_id"]

    @property
    def run_id(self) -> str:
        return self.data["run_id"]

    @property
    def parent_run_id(self) -> str:
        return self.data.get("parent_run_id")

    @property
    def state(self) -> typing.Any:
        return copy.deepcopy(self.data["state"])

    @property
    def messages(self) -> list[agui_core.Message]:
        return [
            MESSAGE_DESERIALIZER.validate_python(msg_data)
            for msg_data in self.data["messages"]
        ]

    @property
    def context(self) -> list[agui_core.Context]:
        return [
            agui_core.Context(**ctx_data) for ctx_data in self.data["context"]
        ]

    @property
    def tools(self) -> list[agui_core.Tool]:
        return [
            agui_core.Tool(**tool_data) for tool_data in self.data["tools"]
        ]

    @property
    def forwarded_props(self) -> typing.Any:
        return copy.deepcopy(self.data["forwarded_props"])


class RunEvent(Base):
    """Hold data for a singl AG-UI event within a run

    'run' is a many-to-one relationship to 'Run'

    'data' is the dumped state of the event.
    """

    __tablename__ = "run_event"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        default=agui_util._timestamp,
    )

    run_id_: Mapped[int] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    run: Mapped[Run] = relationship(back_populates="events")

    data: Mapped[JSON_Mapped_From] = mapped_column()

    @classmethod
    def from_agui_model(cls, run, model: agui_core.Event):
        return cls(run=run, data=model.model_dump())

    def to_agui_model(self) -> agui_core.Event:
        event = EVENT_DESERIALIZER.validate_python(self.data)
        rai = getattr(event, "run_agent_input", None)

        if isinstance(rai, dict):
            rai = agui_core.RunAgentInput.model_validate(rai)
            event.run_agent_input = rai

        return event

    @property
    def type(self) -> str:
        return self.data["type"]


class ThreadStorage(agui_package.ThreadStorage):
    def __init__(self, session: sqla_asyncio.AsyncSession):
        self._session = session

    @property
    @contextlib.asynccontextmanager
    async def session(self):
        async with self._session.begin():
            yield self._session

    async def _find_user_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
        session,
    ):
        query = (
            sqla_sql.select(Thread)
            .where(Thread.user_name == user_name)
            .where(Thread.thread_id == thread_id)
        )
        thread = (await session.scalars(query)).first()

        if thread is None:
            raise agui_package.UnknownThread(user_name, thread_id)

        return thread

    async def _find_thread_run(
        self,
        *,
        user_name: str,
        thread_id: str,
        run_id: str,
        session,
        exc_type=agui_package.UnknownRun,
    ):
        thread = await self._find_user_thread(
            user_name=user_name,
            thread_id=thread_id,
            session=session,
        )
        for run in await thread.awaitable_attrs.runs:
            if run.run_id == run_id:
                return run

        raise exc_type(run_id)

    async def list_user_threads(
        self,
        *,
        user_name: str,
        room_id: str = None,
    ) -> list[Thread]:
        async with self.session as session:
            query = sqla_sql.select(Thread).where(
                Thread.user_name == user_name
            )
            if room_id is not None:
                query = query.where(Thread.room_id == room_id)
            return await session.scalars(query)

    async def get_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
    ) -> Thread:
        async with self.session as session:
            return await self._find_user_thread(
                user_name=user_name,
                thread_id=thread_id,
                session=session,
            )

    async def new_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_metadata: ThreadMetadata | dict = None,
        initial_run: bool = True,
    ) -> Thread:
        async with self.session as session:
            async with session.begin_nested():
                thread = Thread(user_name=user_name, room_id=room_id)
                session.add(thread)

            async with session.begin_nested():
                run = Run(thread=thread)
                session.add(run)

            async with session.begin_nested():
                run_input = RunAgentInput.empty(
                    run=run,
                    thread_id=await thread.awaitable_attrs.thread_id,
                    run_id=await run.awaitable_attrs.run_id,
                )
                session.add(run_input)

                if thread_metadata is not None:
                    if isinstance(thread_metadata, dict):
                        thread_metadata = ThreadMetadata(
                            thread=thread,
                            **thread_metadata,
                        )
                    else:
                        thread_metadata.thread = thread

                    session.add(thread_metadata)

            return thread

    async def update_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
        thread_metadata: ThreadMetadata | dict = None,
    ) -> Thread:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                thread_id=thread_id,
                session=session,
            )

            existing = await thread.awaitable_attrs.thread_metadata
            if existing is not None:
                await session.delete(existing)

            if thread_metadata is not None:
                if isinstance(thread_metadata, dict):
                    thread_metadata = ThreadMetadata(
                        thread=thread,
                        **thread_metadata,
                    )
                else:
                    thread_metadata.thread = thread

                session.add(thread_metadata)

            return thread

    async def delete_thread(
        self,
        *,
        user_name: str,
        thread_id: str,
    ) -> None:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                thread_id=thread_id,
                session=session,
            )
            await session.delete(thread)

    async def new_run(
        self,
        *,
        user_name: str,
        thread_id: str,
        run_metadata: RunMetadata | dict = None,
        parent_run_id: str = None,
    ) -> Run:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                thread_id=thread_id,
                session=session,
            )

            if parent_run_id is not None:
                parent = await self._find_thread_run(
                    user_name=user_name,
                    thread_id=thread_id,
                    run_id=parent_run_id,
                    session=session,
                    exc_type=agui_package.MissingParentRun,
                )
            else:
                parent = None

            async with session.begin_nested():
                run = Run(
                    thread=thread,
                    parent=parent,
                )
                session.add(run)

            async with session.begin_nested():
                if parent is None:
                    run_input = RunAgentInput.empty(
                        run=run,
                        thread_id=await thread.awaitable_attrs.thread_id,
                        run_id=await run.awaitable_attrs.run_id,
                    )
                else:
                    parent_run_input = (
                        await parent.awaitable_attrs.run_agent_input
                    )
                    parent_run_input_agui = parent_run_input.to_agui_model()
                    run_input_agui = parent_run_input_agui.model_copy(
                        update={
                            "run_id": await run.awaitable_attrs.run_id,
                            "parent_run_id": parent_run_id,
                        },
                    )
                    run_input = RunAgentInput.from_agui_model(
                        run,
                        run_input_agui,
                    )

                session.add(run_input)

                if run_metadata is not None:
                    if isinstance(run_metadata, dict):
                        run_metadata = RunMetadata(run=run, **run_metadata)
                    else:
                        run_metadata.run = run
                    session.add(run_metadata)

            return run

    async def get_run(
        self,
        user_name: str,
        thread_id: str,
        run_id: str,
    ) -> Run:
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            await run.awaitable_attrs.events
            await run.awaitable_attrs.run_agent_input
            await run.awaitable_attrs.run_metadata

            return run

    async def update_run(
        self,
        *,
        user_name: str,
        thread_id: str,
        run_id: str,
        run_metadata: RunMetadata | dict = None,
    ) -> Run:
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            existing = await run.awaitable_attrs.run_metadata
            if existing is not None:
                await session.delete(existing)

            if run_metadata:
                if isinstance(run_metadata, dict):
                    run_metadata = RunMetadata(
                        run=run,
                        **run_metadata,
                    )
                else:
                    run_metadata.run = run

                session.add(run_metadata)

            return run

    async def save_run_events(
        self,
        *,
        user_name: str,
        thread_id: str,
        run_id: str,
        events: agui_package.AGUI_Events,
    ) -> agui_package.AGUI_Events:
        """Save the events for a gven run"""
        await self._session.commit()

        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            for event in events:
                session.add(RunEvent(run=run, data=event.model_dump()))

        return events


def get_session(
    engine_url=SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = sqlalchemy.create_engine(engine_url, **engine_kwargs)

    if init_schema:
        with engine.connect() as connection:
            Base.metadata.create_all(connection)

    return sqla_orm.Session(bind=engine)


async def get_async_session(
    engine_url=ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = sqla_asyncio.create_async_engine(engine_url, **engine_kwargs)

    if init_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    return sqla_asyncio.AsyncSession(bind=engine)
