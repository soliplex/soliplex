from __future__ import annotations

import contextlib
import datetime
import typing

from ag_ui import core as agui_core
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui as agui_package
from soliplex.agui import schema as agui_schema
from soliplex.agui import util as agui_util

# Temporary backward-compatibility:  to be removed in 'v0.45'
from soliplex.agui.schema import *  # noqa F403


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
            raise agui_package.UnknownThread(user_name, thread_id)

        t_room_id = await thread.awaitable_attrs.room_id

        if t_room_id != room_id:
            raise agui_package.ThreadRoomMismatch(room_id, t_room_id)

        return thread

    async def _find_thread_run(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        session,
        exc_type=agui_package.UnknownRun,
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

    async def new_thread(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_metadata: agui_schema.ThreadMetadata | dict = None,
        initial_run: bool = True,
    ) -> agui_schema.Thread:
        async with self.session as session:
            async with session.begin_nested():
                thread = agui_schema.Thread(
                    user_name=user_name, room_id=room_id
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
                    exc_type=agui_package.MissingParentRun,
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
                raise agui_package.RunAlreadyStarted(
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

    async def save_run_events(
        self,
        *,
        user_name: str,
        room_id: str,
        thread_id: str,
        run_id: str,
        events: agui_package.AGUI_Events,
    ) -> agui_package.AGUI_Events:
        """Save the events for a gven run"""
        await self._session.commit()

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
        await self._session.commit()

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
        await self._session.commit()

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
    ) -> agui_package.RunFeedbackType | None:
        """Get the run feedback"""
        await self._session.commit()

        result = None

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
                result = existing

        return result

    async def list_recent_run_feedback(
        self,
        *,
        user_name: str | None = None,
        room_id: str | None = None,
        thread_id: str | None = None,
        limit: int | None = None,
        since: datetime.datetime | None = None,
    ) -> typing.Sequence[agui_schema.Run]:
        """Query run feedback matching given criteria

        Selected values are returned in most-recent first order,
        based on the run's timestamp.
        """
        if limit is None and since is None:
            limit = 20

        await self._session.commit()

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

            if room_id is not None:
                query = query.where(agui_schema.Thread.room_id == room_id)

            if user_name is not None:
                query = query.where(agui_schema.Thread.user_name == user_name)

            if thread_id is not None:
                query = query.where(agui_schema.Thread.thread_id == thread_id)

            if since is not None:
                query = query.where(agui_schema.Run.created >= since)

            if limit is not None:
                query = query.limit(limit)

            return (await session.scalars(query)).all()
