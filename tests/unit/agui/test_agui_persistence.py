import datetime
from unittest import mock

import pytest
import pytest_asyncio
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui as agui_package
from soliplex.agui import persistence as agui_persistence
from soliplex.agui import schema as agui_schema
from soliplex.config import installation as config_installation
from tests.unit.agui import agui_constants

NOW = datetime.datetime.now(datetime.UTC)

ROOM_ID = "test-room"
USER_NAME = "phreddy"


@pytest.fixture
def faux_sqlaa_session():
    return mock.create_autospec(
        sqla_asyncio.AsyncSession,
    )


@pytest.mark.anyio
async def test_threadstorage_session(faux_sqlaa_session):
    ts = agui_persistence.ThreadStorage(faux_sqlaa_session)
    begin = faux_sqlaa_session.begin

    async with ts.session as session:
        assert session is faux_sqlaa_session

        begin.assert_called_once_with()
        begin.return_value.__aenter__.assert_called_once_with()
        begin.return_value.__aexit__.assert_not_called()

    begin.return_value.__aenter__.assert_called_once_with()


@pytest_asyncio.fixture()
async def the_async_engine():
    engine = sqla_asyncio.create_async_engine(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(agui_schema.Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture()
async def the_async_session(the_async_engine):
    session = sqla_asyncio.AsyncSession(bind=the_async_engine)
    yield session
    await session.close()


@pytest.mark.asyncio
async def test_threadstorage_thread_crud(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == []

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == []

    with pytest.raises(agui_package.UnknownThread):
        await ts.get_thread(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id="NONESUCH",
        )

    thread = await ts.new_thread(user_name=USER_NAME, room_id=ROOM_ID)

    thread_id = await thread.awaitable_attrs.thread_id

    await the_async_session.commit()

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == [thread]

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == [thread]

    await the_async_session.commit()

    with pytest.raises(agui_package.ThreadRoomMismatch):
        await ts.get_thread(
            user_name=USER_NAME,
            room_id="NONESUCH",
            thread_id=thread_id,
        )

    await the_async_session.commit()

    gotten = await ts.get_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    assert gotten is thread

    await the_async_session.commit()

    with pytest.raises(agui_package.ThreadRoomMismatch):
        await ts.update_thread_metadata(
            user_name=USER_NAME,
            thread_id=thread_id,
            room_id="NONESUCH",
            thread_metadata={
                "name": agui_constants.THREAD_NAME,
                "description": agui_constants.THREAD_DESCRIPTION,
            },
        )

    await the_async_session.commit()

    updated = await ts.update_thread_metadata(
        user_name=USER_NAME,
        thread_id=thread_id,
        room_id=ROOM_ID,
        thread_metadata={
            "name": agui_constants.THREAD_NAME,
            "description": agui_constants.THREAD_DESCRIPTION,
        },
    )

    assert updated is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == agui_constants.THREAD_NAME
    assert thread_meta.description == agui_constants.THREAD_DESCRIPTION

    await the_async_session.commit()

    updated_again = await ts.update_thread_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        thread_metadata=agui_schema.ThreadMetadata(
            name=agui_constants.THREAD_NAME,
        ),
    )

    assert updated_again is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == agui_constants.THREAD_NAME
    assert thread_meta.description is None

    await the_async_session.commit()

    cleared = await ts.update_thread_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        thread_metadata=None,
    )

    assert cleared is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata
    assert thread_meta is None

    await the_async_session.commit()

    cleared_again = await ts.update_thread_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        thread_metadata=None,
    )

    assert cleared_again is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata
    assert thread_meta is None

    await the_async_session.commit()

    with pytest.raises(agui_package.ThreadRoomMismatch):
        await ts.delete_thread(
            user_name=USER_NAME,
            room_id="NONESUCH",
            thread_id=thread_id,
        )

    await the_async_session.commit()

    await ts.delete_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    await the_async_session.commit()

    await the_async_session.commit()

    found = (await ts.list_user_threads(user_name=USER_NAME)).all()
    assert found == []

    found = (
        await ts.list_user_threads(user_name=USER_NAME, room_id=ROOM_ID)
    ).all()
    assert found == []

    await the_async_session.commit()

    w_md_dict = await ts.new_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_metadata={
            "name": "w_md_dict",
            "description": "Created with metadata as a dict",
        },
    )

    await w_md_dict.awaitable_attrs.thread_id

    await the_async_session.commit()

    tmd = await w_md_dict.awaitable_attrs.thread_metadata
    assert tmd.name == "w_md_dict"
    assert tmd.description == "Created with metadata as a dict"

    await the_async_session.commit()

    w_md_obj = await ts.new_thread(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_metadata=agui_schema.ThreadMetadata(
            name="w_md_obj",
            description="Created with metadata as an object",
        ),
    )

    await w_md_obj.awaitable_attrs.thread_id

    await the_async_session.commit()

    tmd = await w_md_obj.awaitable_attrs.thread_metadata
    assert tmd.name == "w_md_obj"
    assert tmd.description == "Created with metadata as an object"

    await the_async_session.commit()


@pytest.mark.asyncio
async def test_threadstorage_thread_run_cru(the_async_session):
    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(user_name=USER_NAME, room_id=ROOM_ID)

    thread_id = await thread.awaitable_attrs.thread_id

    runs = await thread.list_runs()

    (initial_run,) = runs

    initial_run_id = await initial_run.awaitable_attrs.run_id

    assert await initial_run.awaitable_attrs.thread_id == thread_id
    assert await initial_run.awaitable_attrs.run_input is None

    assert initial_run in await thread.awaitable_attrs.runs

    await the_async_session.commit()

    found = await thread.list_runs()

    assert found == runs

    await the_async_session.commit()

    rai_added = await ts.add_run_input(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=initial_run_id,
        run_input=agui_constants.FULL_RUN_AGENT_INPUT,
    )

    assert rai_added is initial_run

    await the_async_session.commit()

    assert (
        await initial_run.awaitable_attrs.run_input
        == agui_constants.FULL_RUN_AGENT_INPUT
    )

    await the_async_session.commit()

    with pytest.raises(agui_package.RunAlreadyStarted):
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=initial_run_id,
            run_input=agui_constants.FULL_RUN_AGENT_INPUT,
        )

    await the_async_session.commit()

    gotten = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=initial_run_id,
    )

    assert gotten is initial_run

    await the_async_session.commit()

    with pytest.raises(agui_package.UnknownRun):
        await ts.get_run(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id="NONESUCH",
        )

    added = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata={"label": "added"},
    )
    added_id = await added.awaitable_attrs.run_id

    await the_async_session.commit()

    updated = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata={
            "label": agui_constants.RUN_LABEL,
        },
    )

    assert updated is added

    rmd = await updated.awaitable_attrs.run_metadata
    assert rmd.label == agui_constants.RUN_LABEL

    await the_async_session.commit()

    updated_again = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata=agui_schema.RunMetadata(
            label=agui_constants.OTHER_RUN_LABEL,
        ),
    )

    assert updated_again is added

    rmd = await updated_again.awaitable_attrs.run_metadata
    assert rmd.label == agui_constants.OTHER_RUN_LABEL

    await the_async_session.commit()

    cleared = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata=None,
    )

    assert cleared is added

    assert await cleared.awaitable_attrs.run_metadata is None

    await the_async_session.commit()

    cleared_again = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata=None,
    )

    assert cleared_again is added

    assert await cleared_again.awaitable_attrs.run_metadata is None

    await the_async_session.commit()

    parent = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata=agui_schema.RunMetadata(label="parent"),
    )

    await the_async_session.commit()

    parent_id = await parent.awaitable_attrs.run_id

    await the_async_session.commit()

    spare = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata=agui_schema.RunMetadata(label="spare"),
        parent_run_id=parent_id,
    )
    await spare.awaitable_attrs.run_id

    await the_async_session.commit()

    rmd = await spare.awaitable_attrs.run_metadata
    assert rmd.label == "spare"

    assert await spare.awaitable_attrs.parent is parent

    await the_async_session.commit()

    wo_meta = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    await the_async_session.commit()

    rmd = await wo_meta.awaitable_attrs.run_metadata
    assert rmd is None

    await the_async_session.commit()

    await the_async_session.commit()

    before = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
    )

    await the_async_session.commit()
    before_id = await before.awaitable_attrs.run_id

    usage = await before.awaitable_attrs.run_usage
    assert usage is None

    await ts.save_run_usage(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        input_tokens=1,
        output_tokens=2,
        requests=3,
        tool_calls=4,
    )

    await the_async_session.commit()

    after = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    after_usage = await after.awaitable_attrs.run_usage

    assert after_usage.input_tokens == 1
    assert after_usage.output_tokens == 2
    assert after_usage.requests == 3
    assert after_usage.tool_calls == 4

    await the_async_session.commit()

    pre_feedback = await after.awaitable_attrs.run_feedback
    assert pre_feedback is None

    await the_async_session.commit()

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        feedback="testing",
        reason="just because",
    )

    await the_async_session.commit()

    w_feedback = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    feedback = await w_feedback.awaitable_attrs.run_feedback

    assert feedback.feedback == "testing"
    assert feedback.reason == "just because"

    await the_async_session.commit()

    w_feedback = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    feedback = await w_feedback.awaitable_attrs.run_feedback

    assert feedback.feedback == "testing"
    assert feedback.reason == "just because"

    await ts.save_run_feedback(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
        feedback="moar testing",
        reason="dithering",
    )

    await the_async_session.commit()

    w_moar_feedback = await ts.get_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=before_id,
    )

    moar_feedback = await w_moar_feedback.awaitable_attrs.run_feedback

    assert moar_feedback.feedback == "moar testing"
    assert moar_feedback.reason == "dithering"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "w_agui_events",
    [[], agui_constants.TEST_AGUI_RUN_EVENTS],
)
@mock.patch("soliplex.agui.util._timestamp")
async def test_threadstorage_save_run_events(
    ts,
    the_async_session,
    w_agui_events,
):
    ts.return_value = NOW

    # Work around https://github.com/ag-ui-protocol/ag-ui/issues/752
    exp_events = [
        event
        for event in w_agui_events
        if event.type not in agui_schema.SKIP_EVENT_TYPES
    ]

    ts = agui_persistence.ThreadStorage(the_async_session)

    thread = await ts.new_thread(user_name=USER_NAME, room_id=ROOM_ID)

    thread_id = await thread.awaitable_attrs.thread_id

    (run,) = await thread.list_runs()

    run_id = await run.awaitable_attrs.run_id

    await the_async_session.commit()

    found_events = await ts.save_run_events(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=run_id,
        events=w_agui_events,
    )

    await the_async_session.commit()

    finished = await run.awaitable_attrs.finished
    assert finished == NOW.replace(tzinfo=None)  # sqlalchemy drops zone

    db_events = await run.list_events()

    for found_event, exp_event, db_event in zip(
        found_events,
        exp_events,
        db_events,
        strict=True,
    ):
        assert found_event == exp_event
        assert db_event == exp_event
