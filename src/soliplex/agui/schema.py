from __future__ import annotations

import copy
import datetime
import typing

import pydantic
import sqlalchemy
from ag_ui import core as agui_core
from sqlalchemy import orm as sqla_orm
from sqlalchemy import schema as sqla_schema
from sqlalchemy.ext import asyncio as sqla_asyncio
from sqlalchemy.sql import sqltypes as sqla_sqltypes

from soliplex import agui
from soliplex import util
from soliplex.agui import util as agui_util
from soliplex.config import installation as config_installation

AsyncAttrs = sqla_asyncio.AsyncAttrs
DeclarativeBase = sqla_orm.DeclarativeBase
ForeignKey = sqlalchemy.ForeignKey
Mapped = sqla_orm.Mapped
mapped_column = sqla_orm.mapped_column
relationship = sqla_orm.relationship

MESSAGE_DESERIALIZER = pydantic.TypeAdapter(agui_core.Message)
EVENT_DESERIALIZER = pydantic.TypeAdapter(agui_core.Event)

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

FeedbackReviewStatus = agui.FeedbackReviewStatus


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
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    #
    #   Not part of the generic 'soliplex.agui.Thread' contract
    #
    user_name: Mapped[str] = mapped_column(index=True)
    email: Mapped[str | None] = mapped_column(index=True)
    runs: Mapped[list[Run]] = relationship(
        back_populates="thread",
        order_by="Run.created",
        cascade="all, delete",
        passive_deletes=True,
    )

    # Deliberately one-way: 'Label' carries no 'threads' collection. A
    # back-reference would let one stray attribute access load every
    # thread in the installation; usage counts come from a grouped
    # aggregate instead.
    #
    # 'passive_deletes' leaves the association rows to the database's
    # 'ON DELETE CASCADE' rather than having SQLAlchemy delete them one
    # by one. Labels themselves are never cascaded -- detaching a label
    # from a thread must not delete it from the catalogue.
    labels: Mapped[list[Label]] = relationship(
        secondary="thread_label",
        order_by="Label.name_key",
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
        sqla_sqltypes.TIMESTAMP(timezone=True),
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


class Label(Base):
    """A category which may be attached to threads.

    Labels are global to the installation -- one namespace shared by
    every room -- and are curated by administrators; ordinary users may
    only attach existing ones to their own threads.

    'name' is what people read and type; 'name_key' is that name folded
    to lower case and carries the uniqueness constraint, so 'Urgent' and
    'urgent' are the same label. The constraint lives on a stored column
    rather than on a functional index over 'lower(name)' because SQLite
    cannot express the latter.

    'color' is a '#RRGGBB' string, defaulted from the row's own ID (see
    'agui.util.hue_rotated_hex') and thereafter editable.
    """

    __tablename__ = "label"

    # Plain SQLite hands out 'max(id) + 1', so deleting the highest label
    # and creating another gives the new one the old one's ID -- and any
    # client still holding the previous catalogue would then paint the
    # wrong chip. AUTOINCREMENT makes IDs monotonic. No-op on PostgreSQL.
    #
    # Consequence to keep in mind: IDs are allocated per deployment, so
    # nothing portable between installations (config, seed data, exports)
    # may key on them.
    __table_args__ = {"sqlite_autoincrement": True}

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    name: Mapped[str] = mapped_column()
    # 'unique' only: adding 'index=True' as well would make autogenerate
    # emit a redundant index alongside the constraint's own.
    name_key: Mapped[str] = mapped_column(unique=True)
    color: Mapped[str] = mapped_column()


# A Core table rather than a mapped class: it carries no payload of its
# own, and modelling it as an entity would only invite queries that treat
# the association as a thing in itself.
thread_label = sqla_schema.Table(
    "thread_label",
    Base.metadata,
    sqla_schema.Column(
        "thread_id_",
        ForeignKey("thread.id_", ondelete="CASCADE"),
        primary_key=True,
    ),
    # Indexed explicitly: the composite primary key only indexes
    # '(thread_id_, label_id_)', which does not serve a lookup keyed on
    # the label -- and both the label filter and the usage count are
    # exactly that.
    sqla_schema.Column(
        "label_id_",
        ForeignKey("label.id_", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Run(Base):
    """Hold information about an AG-UI runs.

    'run_id': the AG-UI protocol level 'run_id' (distinct from our
        actual primary key).

    'parent_id_': foreign key reference to parent run

    'parent': optional reference to the run's parent run.

    'children': list of the run's child runs.

    'run_agent_input': holds optional AG-UI 'RunAgentInput' (runs can
        be created before the client posts an initial protocol-
        level run).

    'events': AG-UI events for the run (one-to-many).

    'run_metadata': optional run metadata, stored in the 'RunMetadata'
        table via an optional one-to-one relationship.

    'run_usage': optional run usage statistics, stored in the 'RunUsage'
        table via an optional one-to-one relationship.

    'run_feedback': optional run feedback, stored in the 'RunFeedback'
        table via an optional one-to-one relationship.
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

    run_agent_input: Mapped[RunAgentInput | None] = relationship(
        back_populates="run",
        cascade="all, delete",
        passive_deletes=True,
    )

    events: Mapped[list[RunEvent]] = relationship(
        back_populates="run",
        order_by="RunEvent.created, RunEvent.id_",
        cascade="all, delete",
        passive_deletes=True,
    )

    run_metadata: Mapped[RunMetadata | None] = relationship(
        back_populates="run",
        cascade="all, delete",
        passive_deletes=True,
    )

    run_usage: Mapped[RunUsage | None] = relationship(
        back_populates="run",
        cascade="all, delete",
        passive_deletes=True,
    )

    run_feedback: Mapped[RunFeedback | None] = relationship(
        back_populates="run",
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
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    finished: Mapped[datetime.datetime | None] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=None,
    )

    async def list_events(self) -> list[agui_core.Event]:
        return [
            event.to_agui_model()
            for event in await self.awaitable_attrs.events
        ]


class RunAgentInput(Base):
    """Hold AG-UI 'RunAgentInput' data for a run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'data' is the dumped state of the 'RunAgentInput'.
    """

    __tablename__ = "run_agent_input"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
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
        sqla_sqltypes.TIMESTAMP(timezone=True),
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


class RunMetadata(Base):
    """Hold optional metadata for an AG-UI run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'label', required
    """

    __tablename__ = "run_metadata"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
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


class RunUsage(Base):
    """Hold optional usage info for an AG-UI run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'input_tokens', int, required
    'output_tokens', int, required
    'requests', int, required
    'tool_calls', int, required
    """

    __tablename__ = "run_usage"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    run_id_: Mapped[int] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    run: Mapped[Run] = relationship(back_populates="run_usage")

    input_tokens: Mapped[int] = mapped_column()
    output_tokens: Mapped[int] = mapped_column()
    requests: Mapped[int] = mapped_column()
    tool_calls: Mapped[int] = mapped_column()

    def as_tuple(self) -> agui.RunUsageStats:
        return agui.RunUsageStats(
            self.input_tokens,
            self.output_tokens,
            self.requests,
            self.tool_calls,
        )


class RunFeedback(Base):
    """Hold optional feedback info for an AG-UI run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'feedback', str, required
    'reason', str, optional
    """

    __tablename__ = "run_feedback"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    run_id_: Mapped[int] = mapped_column(
        ForeignKey("run.id_", ondelete="CASCADE"),
    )
    run: Mapped[Run] = relationship(back_populates="run_feedback")

    feedback: Mapped[str] = mapped_column()
    reason: Mapped[str | None] = mapped_column(default=None)

    review_history: Mapped[list[RunFeedbackReviewEntry]] = relationship(
        back_populates="run_feedback",
        cascade="all, delete",
        passive_deletes=True,
        order_by="desc(RunFeedbackReviewEntry.created)",
    )


class RunFeedbackReviewEntry(Base):
    """Hold optional feedback info for an AG-UI run

    'run' is a one-to-one relationship to 'Run' (but optional from
          the run side).

    'feedback', str, required
    'reason', str, optional
    """

    __tablename__ = "review_history"

    id_: Mapped[int] = mapped_column(primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        sqla_sqltypes.TIMESTAMP(timezone=True),
        default=agui_util._timestamp,
    )

    run_feedback_id_: Mapped[int] = mapped_column(
        ForeignKey("run_feedback.id_", ondelete="CASCADE"),
    )
    run_feedback: Mapped[RunFeedback] = relationship(
        back_populates="review_history",
    )

    status: Mapped[FeedbackReviewStatus | None] = mapped_column()
    note: Mapped[str | None] = mapped_column(default=None)
    user_name: Mapped[str | None] = mapped_column(default=None)
    email: Mapped[str | None] = mapped_column(default=None)


def get_engine(
    engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
) -> sqlalchemy.Engine:
    engine = sqlalchemy.create_engine(
        engine_url,
        json_serializer=util.serialize_sqla_json,
        **engine_kwargs,
    )

    @sqlalchemy.event.listens_for(engine, "connect")
    def _set_sqlite_pragma(  # pragma: no cover
        dbapi_connection, connection_record
    ):
        # SQLite ignores foreign-key constraints -- and hence the
        # 'ON DELETE CASCADE' threading thread -> run -> events -- unless
        # they are enabled per connection. Mirrors
        # 'soliplex.installation._set_sqlite_pragma' (issue #950) for the
        # sync engine; without it, deleting a parent row orphans its
        # children instead of cascading.
        if engine.dialect.name != "sqlite":
            return
        cursor_fk = dbapi_connection.cursor()
        cursor_fk.execute("PRAGMA foreign_keys=ON")
        cursor_fk.close()

    if init_schema:
        with engine.connect() as connection:
            Base.metadata.create_all(connection)

    return engine


def get_session(
    engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
) -> sqla_orm.Session:
    engine = get_engine(
        engine_url=engine_url,
        init_schema=init_schema,
        **engine_kwargs,
    )
    return sqla_orm.Session(bind=engine)


async def get_async_engine(
    engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
) -> sqla_asyncio.AsyncEngine:
    engine = sqla_asyncio.create_async_engine(
        engine_url,
        json_serializer=util.serialize_sqla_json,
        **engine_kwargs,
    )

    if init_schema:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    return engine


async def get_async_session(
    engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
    init_schema=False,
    **engine_kwargs,
):
    engine = await get_async_engine(
        engine_url=engine_url,
        init_schema=init_schema,
        **engine_kwargs,
    )
    return sqla_asyncio.AsyncSession(bind=engine)
