from __future__ import annotations

import collections.abc
import contextlib
import copy
import datetime
import typing

import logfire
from ag_ui import core as agui_core
from sqlalchemy import exc as sqla_exc
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.agui import util as agui_util

# Temporary backward-compatibility:  to be removed in 'v0.45'
from soliplex.agui.schema import *  # noqa F403

FeedbackReviewStatus = agui.FeedbackReviewStatus


class NoFeedbackFound(ValueError):
    def __init__(self, run_id: str):
        self.run_id = run_id
        super().__init__(f"No feed back found for run: {run_id}")


def _as_utc(value: datetime.datetime) -> datetime.datetime:
    """Re-tag a naive SQLite-read timestamp as UTC.

    The backend writes UTC, but SQLite stores no timezone and SQLAlchemy
    returns naive datetimes on read. Without re-tagging, FastAPI would
    serialize the value with no offset and clients would parse it as
    local time.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)
    return value


# A run's activity time is its finish, or -- while unfinished -- its
# start; the latest such time across the selected runs.
_LAST_ACTIVITY = sqla_sql.func.max(
    sqla_sql.func.coalesce(
        agui_schema.Run.finished,
        agui_schema.Run.created,
    )
)


async def _final_state_snapshot(
    run: agui_schema.Run,
) -> agui.AGUI_State | None:
    """Return the state the run last snapshotted, or None."""
    for event in reversed(await run.awaitable_attrs.events):
        if event.data.get("type") == agui_core.EventType.STATE_SNAPSHOT:
            return copy.deepcopy(event.data.get("snapshot"))

    return None


class ThreadStorage(agui.ThreadStorage):
    def __init__(self, session: sqla_asyncio.AsyncSession):
        self._session = session

    @property
    @contextlib.asynccontextmanager
    async def session(self):
        # Yield the caller-owned session as-is: the session owner (a
        # FastAPI dependency, CLI context manager, or streaming helper)
        # owns the transaction boundary and commits the unit of work
        # exactly once. Methods here never open their own transaction or
        # commit, so callers -- and tests -- need no interleaved commits.
        yield self._session

    async def _find_user_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        session,
    ):
        query = (
            sqla_sql.select(agui_schema.Thread)
            .where(agui_schema.Thread.user_name == user_name)
            .where(agui_schema.Thread.thread_id == thread_id)
        )
        thread = (await session.scalars(query)).first()

        if thread is None:
            raise agui.UnknownThread(user_name, thread_id)

        t_room_id = await thread.awaitable_attrs.room_id

        if t_room_id != room_id:
            raise agui.ThreadRoomMismatch(room_id, t_room_id)

        return thread

    async def _find_thread_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        session,
        exc_type=agui.UnknownRun,
    ):
        thread = await self._find_user_thread(
            user_name=user_name,
            room_id=room_id,
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
    ) -> list[agui_schema.Thread]:
        async with self.session as session:
            query = sqla_sql.select(agui_schema.Thread).where(
                agui_schema.Thread.user_name == user_name
            )
            if room_id is not None:
                query = query.where(agui_schema.Thread.room_id == room_id)
            result = await session.scalars(query)
        return result

    async def get_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
    ) -> agui_schema.Thread:
        async with self.session as session:
            result = await self._find_user_thread(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                session=session,
            )

        return result

    async def get_room_last_activity(
        self,
        *,
        user_name: str,
        room_id: str,
    ) -> datetime.datetime | None:
        async with self.session as session:
            query = (
                sqla_sql.select(_LAST_ACTIVITY)
                .join(agui_schema.Run.thread)
                .where(agui_schema.Thread.user_name == user_name)
                .where(agui_schema.Thread.room_id == room_id)
            )
            result = await session.scalar(query)
        return _as_utc(result) if result is not None else None

    async def get_rooms_last_activity(
        self,
        *,
        user_name: str,
    ) -> dict[str, datetime.datetime]:
        async with self.session as session:
            query = (
                sqla_sql.select(agui_schema.Thread.room_id, _LAST_ACTIVITY)
                .join(agui_schema.Run.thread)
                .where(agui_schema.Thread.user_name == user_name)
                .group_by(agui_schema.Thread.room_id)
            )
            rows = (await session.execute(query)).all()
        return {room_id: _as_utc(activity) for room_id, activity in rows}

    async def get_threads_last_activity(
        self,
        *,
        user_name: str,
        room_id: str,
    ) -> dict[str, datetime.datetime]:
        async with self.session as session:
            query = (
                sqla_sql.select(agui_schema.Thread.thread_id, _LAST_ACTIVITY)
                .join(agui_schema.Run.thread)
                .where(agui_schema.Thread.user_name == user_name)
                .where(agui_schema.Thread.room_id == room_id)
                .group_by(agui_schema.Thread.thread_id)
            )
            rows = (await session.execute(query)).all()
        return {thread_id: _as_utc(activity) for thread_id, activity in rows}

    async def new_thread(
        self,
        *,
        user_name: str,
        email: str,
        room_id: str,
        thread_metadata: agui_schema.ThreadMetadata | dict = None,
        initial_run: bool = True,
    ) -> agui_schema.Thread:
        async with self.session as session:
            async with session.begin_nested():
                thread = agui_schema.Thread(
                    user_name=user_name,
                    email=email,
                    room_id=room_id,
                )
                session.add(thread)

            async with session.begin_nested():
                run = agui_schema.Run(thread=thread)
                session.add(run)

            async with session.begin_nested():
                if thread_metadata is not None:
                    if isinstance(thread_metadata, dict):
                        thread_metadata = agui_schema.ThreadMetadata(
                            thread=thread,
                            **thread_metadata,
                        )
                    else:
                        thread_metadata.thread = thread

                    session.add(thread_metadata)

        return thread

    async def update_thread_metadata(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        thread_metadata: agui_schema.ThreadMetadata | dict = None,
    ) -> agui_schema.Thread:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                session=session,
            )

            existing = await thread.awaitable_attrs.thread_metadata
            if existing is not None:
                await session.delete(existing)

            if thread_metadata is not None:
                if isinstance(thread_metadata, dict):
                    thread_metadata = agui_schema.ThreadMetadata(
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
        room_id: str,
        thread_id: str,
    ) -> None:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                session=session,
            )
            await session.delete(thread)

    async def new_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_metadata: agui_schema.RunMetadata | dict = None,
        parent_run_id: str = None,
    ) -> agui_schema.Run:
        async with self.session as session:
            thread = await self._find_user_thread(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                session=session,
            )

            if parent_run_id is not None:
                parent = await self._find_thread_run(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=parent_run_id,
                    session=session,
                    exc_type=agui.MissingParentRun,
                )
            else:
                parent = None

            async with session.begin_nested():
                run = agui_schema.Run(
                    thread=thread,
                    parent=parent,
                )
                session.add(run)

            async with session.begin_nested():
                if run_metadata is not None:
                    if isinstance(run_metadata, dict):
                        run_metadata = agui_schema.RunMetadata(
                            run=run, **run_metadata
                        )
                    else:
                        run_metadata.run = run
                    session.add(run_metadata)

        return run

    async def get_run(
        self,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> agui_schema.Run:
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            await run.awaitable_attrs.events
            await run.awaitable_attrs.run_agent_input
            await run.awaitable_attrs.run_metadata

        return run

    async def add_run_input(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        run_input: agui_core.RunAgentInput,
    ) -> agui_schema.Run:
        """Update a run with the given 'run_agent_input'"""
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            already = await run.awaitable_attrs.run_agent_input

            if already is not None:
                raise agui.RunAlreadyStarted(
                    user_name,
                    thread_id,
                    run_id,
                )
            session.add(
                agui_schema.RunAgentInput.from_agui_model(
                    run=run, model=run_input
                )
            )

        return run

    async def get_latest_state(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
    ) -> agui.AGUI_State | None:
        async with self.session as session:
            try:
                thread = await self._find_user_thread(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    session=session,
                )
            except agui.UnknownThread:
                return None

            for run in reversed(await thread.awaitable_attrs.runs):
                # A run's own answer is in the state it ends with: the
                # snapshot emitted once it finishes. Its input is the state
                # the client held when the run began, so it lacks the
                # evidence and citations of that run's own answer.
                snapshot = await _final_state_snapshot(run)
                if snapshot:
                    return snapshot

                run_input = await run.awaitable_attrs.run_agent_input
                if run_input is not None and run_input.state:
                    return run_input.state

        return None

    async def update_run_metadata(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        run_metadata: agui_schema.RunMetadata | dict = None,
    ) -> agui_schema.Run:
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            existing = await run.awaitable_attrs.run_metadata
            if existing is not None:
                await session.delete(existing)

            if run_metadata:
                if isinstance(run_metadata, dict):
                    run_metadata = agui_schema.RunMetadata(
                        run=run,
                        **run_metadata,
                    )
                else:
                    run_metadata.run = run

                session.add(run_metadata)

        return run

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
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            data = event.model_dump(mode="json")
            session.add(
                agui_schema.RunEvent(
                    run=run,
                    data=data,
                )
            )

    async def finish_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> None:
        """Mark a run as finished"""
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            run.finished = agui_util._timestamp()
            session.add(run)

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
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            events = await run.awaitable_attrs.events
            first_unseen = after_index + 1
            unseen_events = events[first_unseen:]

            return [
                (first_unseen + i_unseen, unseen_event.to_agui_model())
                for i_unseen, unseen_event in enumerate(unseen_events)
            ]

    async def is_run_finished(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> bool:
        """Return True if the run has a 'finished' timestamp"""
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            return run.finished is not None

    async def save_run_events(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        events: agui.AGUI_Events,
    ) -> agui.AGUI_Events:
        """Save the events for a gven run"""
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            run.finished = agui_util._timestamp()
            session.add(run)

            for event in events:
                data = event.model_dump(mode="json")
                session.add(agui_schema.RunEvent(run=run, data=data))

        return events

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
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )
            session.add(
                agui_schema.RunUsage(
                    run=run,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    requests=requests,
                    tool_calls=tool_calls,
                )
            )

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
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            existing = await run.awaitable_attrs.run_feedback

            if existing is not None:
                await session.delete(existing)

            session.add(
                agui_schema.RunFeedback(
                    run=run,
                    feedback=feedback,
                    reason=reason,
                )
            )

        return run

    async def get_run_feedback(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> agui.RunFeedbackType | None:
        """Get the run feedback"""
        async with self.session as session:
            run = await self._find_thread_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                session=session,
            )

            return await run.awaitable_attrs.run_feedback

    async def list_recent_run_feedback(
        self,
        *,
        user_name: str | None = None,
        email: str | None = None,
        room_id: str | None = None,
        thread_id: str | None = None,
        limit: int | None = None,
        since: datetime.datetime | None = None,
        status: FeedbackReviewStatus | None = None,
    ) -> typing.Sequence[agui_schema.RunFeedback]:
        """Query run feedback matching given criteria

        Selected values are returned in most-recent first order,
        based on the run's timestamp.
        """
        if limit is None and since is None:
            limit = 20

        async with self.session as session:
            query = (
                sqla_sql.Select(
                    agui_schema.Run,
                )
                .join(
                    agui_schema.Run.run_feedback,
                )
                .join(
                    agui_schema.Run.thread,
                )
                .order_by(agui_schema.RunFeedback.created.desc())
            )

            if status is not None:
                query = (
                    query.join(agui_schema.RunFeedback.review_history)
                    .where(
                        agui_schema.RunFeedbackReviewEntry.status == status,
                    )
                    .order_by(
                        agui_schema.RunFeedbackReviewEntry.created,
                    )
                    .distinct()
                )

            if room_id is not None:
                query = query.where(agui_schema.Thread.room_id == room_id)

            if user_name is not None:
                query = query.where(agui_schema.Thread.user_name == user_name)

            if email is not None:
                query = query.where(agui_schema.Thread.email == email)

            if thread_id is not None:
                query = query.where(agui_schema.Thread.thread_id == thread_id)

            if since is not None:
                query = query.where(agui_schema.Run.created >= since)

            if limit is not None:
                query = query.limit(limit)

            return (await session.scalars(query)).all()

    async def _find_run_feedback(
        self,
        session,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> agui_schema.RunFeedback:
        run = await self._find_thread_run(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
            run_id=run_id,
            session=session,
        )
        run_feedback = await run.awaitable_attrs.run_feedback

        if run_feedback is None:
            raise NoFeedbackFound(run.run_id)

        return run_feedback

    async def _record_run_feedback_history(
        self,
        session,
        run_feedback: agui_schema.RunFeedback,
        status: FeedbackReviewStatus,
        user_name: str,
        email: str,
        note: str | None,
    ):
        history_entry = agui_schema.RunFeedbackReviewEntry(
            run_feedback=run_feedback,
            status=status,
            user_name=user_name,
            email=email,
            note=note,
        )
        session.add(history_entry)

        return history_entry

    @typing.overload
    async def review_run_feedback(
        self,
        reviewer_user_name: str,
        reviewer_email: str,
        note: str | None = None,
        *,
        run_feedback: agui_schema.RunFeedback,
    ) -> agui_schema.RunFeedbackReviewEntry: ...

    @typing.overload
    async def review_run_feedback(
        self,
        reviewer_user_name: str,
        reviewer_email: str,
        note: str | None = None,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> agui_schema.RunFeedbackReviewEntry: ...

    async def review_run_feedback(
        self,
        reviewer_user_name: str,
        reviewer_email: str,
        note: str | None = None,
        *,
        run_feedback: agui_schema.RunFeedback | None = None,
        user_name: str | None = None,
        room_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> agui_schema.RunFeedbackReviewEntry:
        """Note that a run's feedback has been reviewed.

        Find the feedback from its run.
        """

        async with self.session as session:
            if run_feedback is None:
                run_feedback = await self._find_run_feedback(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    session=session,
                )

            history_entry = await self._record_run_feedback_history(
                session,
                run_feedback,
                FeedbackReviewStatus.REVIEWED,
                reviewer_user_name,
                reviewer_email,
                note,
            )

            return history_entry

    @typing.overload
    async def resolve_run_feedback(
        self,
        resolver_user_name: str,
        resolver_email: str,
        note: str | None = None,
        *,
        run_feedback: agui_persistence.RunFeedback,
    ) -> agui_schema.RunFeedbackReviewEntry: ...

    @typing.overload
    async def resolve_run_feedback(
        self,
        resolver_user_name: str,
        resolver_email: str,
        note: str | None = None,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
    ) -> agui_schema.RunFeedbackReviewEntry: ...

    async def resolve_run_feedback(
        self,
        resolver_user_name: str,
        resolver_email: str,
        note: str | None = None,
        *,
        run_feedback: agui_persistence.RunFeedback | None = None,
        user_name: str | None = None,
        room_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
    ) -> agui_schema.RunFeedbackReviewEntry:
        """Note that a run's feedback has been resolveed.

        Find the feedback from its run.
        """

        async with self.session as session:
            if run_feedback is None:
                run_feedback = await self._find_run_feedback(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    session=session,
                )

            history_entry = await self._record_run_feedback_history(
                session,
                run_feedback,
                FeedbackReviewStatus.RESOLVED,
                resolver_user_name,
                resolver_email,
                note,
            )

            return history_entry


# --------------------------------------------------------------------------
# Engine-owning run-persistence helpers
#
# Each builds its own short-lived session (the one bound to a request's
# lifetime may already be closed, e.g. after an early connection reset) and
# owns its commit: 'ThreadStorage' methods no longer commit on their own.
# Committing per event is what lets a reconnecting client's poll observe
# events incrementally.
# --------------------------------------------------------------------------


async def capture_usage_after_stream(
    result,
    *,
    sqla_engine,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    """Save the run usage to the database."""
    usage = getattr(result, "usage", None)

    if usage is not None:
        async with sqla_asyncio.AsyncSession(bind=sqla_engine) as session:
            the_threads = ThreadStorage(session)

            async with session.begin():
                await the_threads.save_run_usage(
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    requests=usage.requests,
                    tool_calls=usage.tool_calls,
                )


async def save_single_event(
    sqla_engine,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
    event,
):
    """Save a single run event to the database (incremental persistence)."""
    async with sqla_asyncio.AsyncSession(bind=sqla_engine) as session:
        the_threads = ThreadStorage(session)

        async with session.begin():
            await the_threads.save_single_event(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                event=event,
            )


async def finish_run(
    sqla_engine,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
):
    """Mark a run as finished in the database."""
    async with sqla_asyncio.AsyncSession(bind=sqla_engine) as session:
        the_threads = ThreadStorage(session)

        async with session.begin():
            await the_threads.finish_run(
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
            )


async def drive_agui_turn(
    *,
    adapter,
    engine,
    user_name: str,
    room_id: str,
    thread_id: str,
    run_id: str,
    run_stream_kwargs: dict | None = None,
) -> collections.abc.AsyncIterator:
    """Drive one room-agent turn as an AG-UI event stream.

    An async generator: for each event it persists the event (via
    :func:`save_single_event`), then yields it. Callers own
    presentation (an SSE queue, or collecting the assistant text) and any
    post-run work such as :func:`finish_run`, usage capture, or title
    generation.

    ``run_stream_kwargs`` is forwarded verbatim to the Pydantic AI adapter.
    """
    stream_kwargs = run_stream_kwargs or {}
    event_stream = agui.with_final_state(
        stream=adapter.run_stream(**stream_kwargs),
        deps=stream_kwargs.get("deps"),
    )
    compacted = agui.compact_event_stream(event_stream)
    async for event in compacted:
        try:
            await save_single_event(
                engine,
                user_name=user_name,
                room_id=room_id,
                thread_id=thread_id,
                run_id=run_id,
                event=event,
            )
        except sqla_exc.SQLAlchemyError as sa_exc:
            logfire.error(
                "Error saving event: {error_message}",
                error_message=str(sa_exc),
            )

        yield event
