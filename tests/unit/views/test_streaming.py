import asyncio
import time
import types
from unittest import mock

import fastapi
import pytest
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import installation
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.views import streaming as views_streaming
from tests.unit.agui import agui_constants


@pytest.fixture
def poll_storage(fake_async_session, mock_thread_storage):
    """Patch ``stream_from_db``'s per-poll session + storage.

    ``stream_from_db`` opens a fresh ``AsyncSession`` + ``ThreadStorage``
    on every poll iteration; patch both (against the ``streaming``
    module) so a single stand-in storage answers every poll. Yields a
    namespace exposing:

      * ``storage``  -- the stand-in ``ThreadStorage`` (drive its
        ``list_run_events_after`` / ``is_run_finished`` with
        ``side_effect``, assert its calls).
      * ``session``  -- the session each poll receives.
      * ``async_session`` -- the patched ``AsyncSession`` (assert it was
        opened with the expected ``bind=`` engine each poll).
    """
    with (
        mock.patch(
            "soliplex.views.streaming.sqla_asyncio.AsyncSession",
            new=fake_async_session.cls,
        ),
        mock.patch(
            "soliplex.views.streaming.agui_persistence.ThreadStorage",
            return_value=mock_thread_storage,
        ),
    ):
        yield types.SimpleNamespace(
            storage=mock_thread_storage,
            session=fake_async_session.session,
            async_session=fake_async_session.cls,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("disconnect_after", [None, 0, 2, 1000])
@pytest.mark.parametrize("w_request", [False, True])
@pytest.mark.parametrize(
    "events",
    [
        [],
        ["data: only one\n\n"],
        [f"data: {i_evt}\n\n" for i_evt in range(15)],
    ],
)
async def test_stream_sse_with_keepalive_w_no_timeouts(
    events,
    w_request,
    disconnect_after,
):
    async def event_stream():
        for event in events:
            yield event

    request_kw = {}

    expected = events[:]

    if w_request:
        request = mock.create_autospec(fastapi.Request)

        if disconnect_after is not None:
            flags = [False] * disconnect_after + [True] * 1000
            request.is_disconnected.side_effect = flags
            expected = expected[:disconnect_after]
        else:
            request.is_disconnected.return_value = False

        request_kw = {"request": request}

    found = [
        event
        async for event in views_streaming.stream_sse_with_keepalive(
            event_stream(),
            **request_kw,
        )
    ]

    assert found == expected


@pytest.mark.asyncio
async def test_stream_sse_with_keepalive_w_timeout():
    keepalive_interval = 0.25
    poll_interval = 0.1
    sleep_interval = 0.5
    events = ["data: only one\n\n"]

    async def event_stream():
        for event in events:
            await asyncio.sleep(sleep_interval)
            yield event

    before = time.monotonic()
    found = [
        event
        async for event in views_streaming.stream_sse_with_keepalive(
            event_stream(),
            keepalive_interval_secs=keepalive_interval,
            poll_interval_secs=poll_interval,
        )
    ]
    after = time.monotonic()

    first, *rest = found
    exp_prefix = ": keepalive "
    exp_suffix = "\n\n"
    assert first.startswith(exp_prefix)
    assert first.endswith(exp_suffix)

    timestamp = float(first[len(exp_prefix) : -len(exp_suffix)])
    assert before <= timestamp <= after
    assert rest == events


@pytest.mark.asyncio
@pytest.mark.parametrize("w_request", [False, True])
async def test_stream_sse_with_keepalive_w_cancellation(w_request):
    THREAD_ID = "test-thread"
    RUN_ID = "test-run"

    keepalive_interval = 0.25
    poll_interval = 0.1
    sleep_interval = 0.5
    events = ["data: only one\n\n"]
    log_info = mock.Mock()

    if w_request:
        request = mock.create_autospec(fastapi.Request)
        request.is_disconnected.return_value = False
        request.path_params = {"thread_id": THREAD_ID, "run_id": RUN_ID}
        exp_params = request.path_params
        request_kw = {"request": request}
    else:
        request_kw = {}
        exp_params = {"thread_id": "<unknown>", "run_id": "<unknown>"}

    async def event_stream():
        for _event in events:
            await asyncio.sleep(sleep_interval)
            raise asyncio.CancelledError("testing")
            yield None
        else:  # pragma NO COVER
            pass

    with pytest.raises(asyncio.CancelledError):
        [
            event
            async for event in views_streaming.stream_sse_with_keepalive(
                event_stream(),
                log_info=log_info,
                keepalive_interval_secs=keepalive_interval,
                poll_interval_secs=poll_interval,
                **request_kw,
            )
        ]

    log_info.assert_called_once_with(
        "SSE generator cancelled {thread_id}/{run_id}",
        **exp_params,
    )


# --- add_sse_event_ids tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "events, start_index, expected",
    [
        ([], 0, []),
        (
            ["data: {}\n\n"],
            0,
            ["id: run-1:0\ndata: {}\n\n"],
        ),
        (
            ["data: a\n\n", "data: b\n\n"],
            0,
            ["id: run-1:0\ndata: a\n\n", "id: run-1:1\ndata: b\n\n"],
        ),
        (
            [": keepalive\n\n", "data: x\n\n"],
            0,
            [": keepalive\n\n", "id: run-1:0\ndata: x\n\n"],
        ),
        (
            ["data: a\n\n", "data: b\n\n"],
            5,
            ["id: run-1:5\ndata: a\n\n", "id: run-1:6\ndata: b\n\n"],
        ),
    ],
)
async def test_add_sse_event_ids(events, start_index, expected):
    async def event_stream():
        for event in events:
            yield event

    found = [
        event
        async for event in views_streaming.add_sse_event_ids(
            event_stream(),
            run_id="run-1",
            start_index=start_index,
        )
    ]

    assert found == expected


# --- stream_from_db tests ---


@pytest.mark.asyncio
async def test_stream_from_db_finished_run(poll_storage):
    """Run is already finished: replay events and stop."""
    engine = mock.Mock()
    events = [
        (0, mock.Mock(name="evt0")),
        (1, mock.Mock(name="evt1")),
    ]

    poll_storage.storage.list_run_events_after = mock.AsyncMock(
        side_effect=[events, []],
    )
    poll_storage.storage.is_run_finished = mock.AsyncMock(
        return_value=True,
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            engine,
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
        )
    ]

    assert found == [events[0][1], events[1][1]]
    # Each poll opens its own session bound to the given engine.
    poll_storage.async_session.assert_called_with(bind=engine)


@pytest.mark.asyncio
async def test_stream_from_db_in_progress_run(poll_storage):
    """Run is in progress: poll until finished."""
    evt0 = (0, mock.Mock(name="evt0"))
    evt1 = (1, mock.Mock(name="evt1"))

    # First poll: one event, not finished
    # Second poll: one more event, now finished
    # Final drain: empty
    poll_storage.storage.list_run_events_after = mock.AsyncMock(
        side_effect=[
            [evt0],
            [evt1],
            [],
        ],
    )
    poll_storage.storage.is_run_finished = mock.AsyncMock(
        side_effect=[False, True],
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            mock.Mock(),
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
            poll_interval_secs=0.01,
        )
    ]

    assert found == [evt0[1], evt1[1]]


@pytest.mark.asyncio
async def test_stream_from_db_final_drain_has_events(poll_storage):
    """Events arrive between last poll and finished flag."""
    evt0 = (0, mock.Mock(name="evt0"))
    evt1 = (1, mock.Mock(name="evt1"))

    # First poll: one event, not finished
    # Second poll: empty, now finished
    # Final drain: one late event
    poll_storage.storage.list_run_events_after = mock.AsyncMock(
        side_effect=[
            [evt0],
            [],
            [evt1],
        ],
    )
    poll_storage.storage.is_run_finished = mock.AsyncMock(
        side_effect=[False, True],
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            mock.Mock(),
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
            poll_interval_secs=0.01,
        )
    ]

    assert found == [evt0[1], evt1[1]]


@pytest.mark.asyncio
async def test_stream_from_db_empty_finished_run(poll_storage):
    """Run finished with no events."""
    poll_storage.storage.list_run_events_after = mock.AsyncMock(
        side_effect=[[], []],
    )
    poll_storage.storage.is_run_finished = mock.AsyncMock(
        return_value=True,
    )

    found = [
        event
        async for event in views_streaming.stream_from_db(
            mock.Mock(),
            user_name="user",
            room_id="room",
            thread_id="thread",
            run_id="run",
            after_index=-1,
        )
    ]

    assert found == []


@pytest.mark.asyncio
async def test_stream_from_db_observes_cross_session_writes(tmp_path):
    """Integration: the reconnect poll sees another session's commits.

    This is the property the design turns on -- and that the mocked
    tests above cannot exercise: ``stream_from_db`` opens a fresh
    session per poll, so it must observe events a *separate* writer
    session commits incrementally, then stop once the run is finished.
    Run against a real file-backed SQLite DB (built through the app's
    own engine factory, WAL and all) so per-transaction snapshot
    isolation is real -- the same mechanism holds under Postgres READ
    COMMITTED, so this guards both backends.
    """
    user_name = "phreddy"
    email = "phreddy@example.com"
    room_id = "test-room"
    events = [
        agui_constants.TEXT_MESSAGE_START_EVENT,
        agui_constants.TEXT_MESSAGE_CONTENT_EVENT,
        agui_constants.TEXT_MESSAGE_END_EVENT,
    ]

    engine = installation._create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'threads.sqlite'}",
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(agui_schema.Base.metadata.create_all)

        # A thread and its initial run, each committed by their owner.
        async with sqla_asyncio.AsyncSession(bind=engine) as session:
            async with session.begin():
                storage = agui_persistence.ThreadStorage(session)
                thread = await storage.new_thread(
                    user_name=user_name,
                    email=email,
                    room_id=room_id,
                )
                thread_id = await thread.awaitable_attrs.thread_id
                (run,) = await thread.list_runs()
                run_id = await run.awaitable_attrs.run_id

        async def _writer():
            # Persist each event in its own committed session (mirrors the
            # background 'save_single_event' helper), then finish the run.
            for event in events:
                async with sqla_asyncio.AsyncSession(bind=engine) as s:
                    async with s.begin():
                        await agui_persistence.ThreadStorage(
                            s
                        ).save_single_event(
                            user_name=user_name,
                            room_id=room_id,
                            thread_id=thread_id,
                            run_id=run_id,
                            event=event,
                        )
                await asyncio.sleep(0.01)
            async with sqla_asyncio.AsyncSession(bind=engine) as s:
                async with s.begin():
                    await agui_persistence.ThreadStorage(s).finish_run(
                        user_name=user_name,
                        room_id=room_id,
                        thread_id=thread_id,
                        run_id=run_id,
                    )

        async def _collect():
            return [
                event
                async for event in views_streaming.stream_from_db(
                    engine,
                    user_name=user_name,
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    after_index=-1,
                    poll_interval_secs=0.01,
                )
            ]

        writer = asyncio.create_task(_writer())
        try:
            seen = await asyncio.wait_for(_collect(), timeout=5.0)
            await writer
        finally:
            writer.cancel()

        # Every incrementally-committed event was observed, in order, and
        # the poll terminated once the run was marked finished.
        assert seen == events
    finally:
        await engine.dispose()
