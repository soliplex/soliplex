import datetime
import uuid
from unittest import mock

import pytest
import pytest_asyncio
import sqlalchemy
from ag_ui import core as agui_core
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agui as agui_package
from soliplex import config
from soliplex.agui import persistence as agui_persistence

NOW = datetime.datetime.now(datetime.UTC)

THREAD_UUID = str(uuid.uuid4())
THREAD_NAME = "Test Thread"
THREAD_DESCRIPTION = "This thread is for testing"

RUN_UUID = str(uuid.uuid4())
RUN_LABEL = "test-run-label"
OTHER_RUN_LABEL = "other-run-label"
PARENT_RUN_ID = str(uuid.uuid4())

USER_MESSAGE_ID = str(uuid.uuid4())
STATE = {
    "foo": "Bar",
}
USER_PROMPT = "Which way is up?"
USER_MESSAGE = agui_core.UserMessage(
    id=USER_MESSAGE_ID,
    content=USER_PROMPT,
)
CONTEXT_DESC = "This context is for testing"
CONTEXT_VALUE = "Test context"
CONTEXT = agui_core.Context(
    description=CONTEXT_DESC,
    value=CONTEXT_VALUE,
)
TOOL_NAME = "test-tool"
TOOL_DESC = "This tool is for testing"
TOOL = agui_core.Tool(
    name=TOOL_NAME,
    description=TOOL_DESC,
    parameters=None,
)
FORWRDED_PROPS = {
    "spam": "Qux",
}

EMPTY_RUN_AGENT_INPUT = agui_core.RunAgentInput(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=None,
    state=None,
    messages=[],
    context=[],
    tools=[],
    forwarded_props=None,
)

FULL_RUN_AGENT_INPUT = agui_core.RunAgentInput(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=PARENT_RUN_ID,
    state=STATE,
    messages=[USER_MESSAGE],
    context=[CONTEXT],
    tools=[TOOL],
    forwarded_props=FORWRDED_PROPS,
)

TEXT_MESSAGE_ID = str(uuid.uuid4())
TEXT_MESSAGE_DELTA = "delta"

TEXT_MESSAGE_START_EVENT = agui_core.TextMessageStartEvent(
    message_id=TEXT_MESSAGE_ID,
)

TEXT_MESSAGE_CONTENT_EVENT = agui_core.TextMessageContentEvent(
    message_id=TEXT_MESSAGE_ID,
    delta=TEXT_MESSAGE_DELTA,
)

TEXT_MESSAGE_END_EVENT = agui_core.TextMessageEndEvent(
    message_id=TEXT_MESSAGE_ID,
)

TEXT_MESSAGE_CHUNK_EVENT = agui_core.TextMessageChunkEvent(
    message_id=TEXT_MESSAGE_ID,
    delta=TEXT_MESSAGE_DELTA,
)

TOOL_CALL_ID = str(uuid.uuid4())
TOOL_CALL_NAME = "test-tool"
TOOL_CALL_ARGS_DELTA = "args delta"
TOOL_CALL_MESSAGE_ID = str(uuid.uuid4())
TOOL_CALL_RESULT_CONTENT = "tool result"

TOOL_CALL_START_EVENT = agui_core.ToolCallStartEvent(
    tool_call_id=TOOL_CALL_ID,
    tool_call_name=TOOL_CALL_NAME,
)

TOOL_CALL_ARGS_EVENT = agui_core.ToolCallArgsEvent(
    tool_call_id=TOOL_CALL_ID,
    delta=TOOL_CALL_ARGS_DELTA,
)

TOOL_CALL_END_EVENT = agui_core.ToolCallEndEvent(
    tool_call_id=TOOL_CALL_ID,
)

EMPTY_TOOL_CALL_CHUNK_EVENT = agui_core.ToolCallChunkEvent(
    tool_call_id=TOOL_CALL_ID,
)
TOOL_CALL_CHUNK_EVENT = agui_core.ToolCallChunkEvent(
    tool_call_id=TOOL_CALL_ID,
    tool_call_name=TOOL_CALL_NAME,
    parent_message_id=TOOL_CALL_MESSAGE_ID,
    delta=TOOL_CALL_ARGS_DELTA,
)

TOOL_CALL_RESULT_EVENT = agui_core.ToolCallResultEvent(
    message_id=TOOL_CALL_MESSAGE_ID,
    tool_call_id=TOOL_CALL_ID,
    content=TOOL_CALL_RESULT_CONTENT,
)

STATE_SNAPTSHOT = {"foo": "Bar", "baz": "Quz"}
STATE_DELTA = {"baz": "Spam"}
STATE_SNAPSHOT_EVENT = agui_core.StateSnapshotEvent(
    snapshot=STATE_SNAPTSHOT,
)

STATE_DELTA_EVENT = agui_core.StateDeltaEvent(
    delta=[STATE_DELTA],
)

DEVELOPER_MESSAGE_ID = str(uuid.uuid4())
DEVELOPER_MESSAGE_CONTENT = "this is a test"
DEVELOPER_MESSAGE_NAME = "phreddy"
DEVELOPER_MESSAGE = agui_core.DeveloperMessage(
    id=DEVELOPER_MESSAGE_ID,
    content=DEVELOPER_MESSAGE_CONTENT,
    name=DEVELOPER_MESSAGE_NAME,
)
EMPTY_MESSAGES_SNAPSHOT_EVENT = agui_core.MessagesSnapshotEvent(
    messages=[],
)
MESSAGES_SNAPSHOT_EVENT = agui_core.MessagesSnapshotEvent(
    messages=[DEVELOPER_MESSAGE],
)

ACTIVITY_MESSAGE_ID = str(uuid.uuid4())
ACTIVITY_TYPE = "test activity"
ACTIVITY_CONTENT = {"waaa": "Blaah"}
ACTIVITY_PATCH = {"waaa": "Oooph"}
ACTIVITY_SNAPSHOT_EVENT = agui_core.ActivitySnapshotEvent(
    message_id=ACTIVITY_MESSAGE_ID,
    activity_type=ACTIVITY_TYPE,
    content=ACTIVITY_CONTENT,
    replace=False,
)

ACTIVITY_DELTA_EVENT = agui_core.ActivityDeltaEvent(
    message_id=ACTIVITY_MESSAGE_ID,
    activity_type=ACTIVITY_TYPE,
    patch=[ACTIVITY_PATCH],
)

RAW_EVENT_EVENT = {"raw": "hide"}
RAW_SOURCE = "raw source"
NO_SOURCE_RAW_EVENT = agui_core.RawEvent(
    event=RAW_EVENT_EVENT,
)
RAW_EVENT = agui_core.RawEvent(
    event=RAW_EVENT_EVENT,
    source=RAW_SOURCE,
)

CUSTOM_NAME = "test-custom"
CUSTOM_VALUE = {"tailor": "made"}
CUSTOM_EVENT = agui_core.CustomEvent(
    name=CUSTOM_NAME,
    value=CUSTOM_VALUE,
)

BARE_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
)

W_PARENT_RUN_ID_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    parent_run_id=PARENT_RUN_ID,
)

W_RAI_RUN_STARTED_EVENT = agui_core.RunStartedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    run_agent_input=FULL_RUN_AGENT_INPUT,
)

RUN_RESULT = "test run result"
BARE_RUN_FINISHED_EVENT = agui_core.RunFinishedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
)
W_RESULT_RUN_FINISHED_EVENT = agui_core.RunFinishedEvent(
    thread_id=THREAD_UUID,
    run_id=RUN_UUID,
    result=RUN_RESULT,
)

RUN_ERROR_MESSAGE = "test error"
RUN_CODE = "999"
BARE_RUN_ERROR_EVENT = agui_core.RunErrorEvent(
    message=RUN_ERROR_MESSAGE,
)
W_CODE_RUN_ERROR_EVENT = agui_core.RunErrorEvent(
    message=RUN_ERROR_MESSAGE,
    code=RUN_CODE,
)

STEP_NAME = "test step"
STEP_STARTED_EVENT = agui_core.StepStartedEvent(
    step_name=STEP_NAME,
)

STEP_FINISHED_EVENT = agui_core.StepFinishedEvent(
    step_name=STEP_NAME,
)

ROOM_ID = "test-room"
USER_NAME = "phreddy"

TEST_AGUI_RUN_EVENTS = [
    BARE_RUN_STARTED_EVENT,
    STEP_STARTED_EVENT,
    ACTIVITY_SNAPSHOT_EVENT,
    ACTIVITY_DELTA_EVENT,
    STEP_FINISHED_EVENT,
    TEXT_MESSAGE_START_EVENT,
    TEXT_MESSAGE_CONTENT_EVENT,
    TEXT_MESSAGE_END_EVENT,
    TOOL_CALL_START_EVENT,
    TOOL_CALL_ARGS_EVENT,
    TOOL_CALL_END_EVENT,
    TOOL_CALL_RESULT_EVENT,
    W_RESULT_RUN_FINISHED_EVENT,
]


def _mock_run(run_id, thread):
    return agui_persistence.Run(
        run_id=run_id,
        thread=thread,
    )


@pytest.mark.anyio
async def test_thread_list_runs():
    thread = agui_persistence.Thread()
    runs = [
        _mock_run("one", thread),
        _mock_run("two", thread),
    ]

    found = await thread.list_runs()

    assert found == runs


def test_run_thread_id():
    thread = agui_persistence.Thread(thread_id=THREAD_UUID)
    run = agui_persistence.Run(thread=thread)

    assert run.thread_id == THREAD_UUID


@pytest.mark.parametrize("w_parent_id", [None, PARENT_RUN_ID])
def test_run_parent_run_id(w_parent_id):
    thread = agui_persistence.Thread(thread_id=THREAD_UUID)

    if w_parent_id is not None:
        parent = agui_persistence.Run(thread=thread, run_id=w_parent_id)
    else:
        parent = None

    run = agui_persistence.Run(thread=thread, parent=parent)

    assert run.parent_run_id == w_parent_id


@pytest.mark.parametrize(
    "w_run_input",
    [
        None,
        EMPTY_RUN_AGENT_INPUT,
        FULL_RUN_AGENT_INPUT,
    ],
)
def test_run_run_input(w_run_input):
    run = agui_persistence.Run()

    if w_run_input is not None:
        _ = agui_persistence.RunAgentInput.from_agui_model(run, w_run_input)

    assert run.run_input == w_run_input


@pytest.mark.anyio
@pytest.mark.parametrize("w_agui_events", [[], TEST_AGUI_RUN_EVENTS])
async def test_run_list_events(w_agui_events):
    run = agui_persistence.Run()

    run.events = [
        agui_persistence.RunEvent.from_agui_model(run, agui_event)
        for agui_event in w_agui_events
    ]

    assert await run.list_events() == w_agui_events


@pytest.mark.anyio
async def test_runusage_as_tuple(the_session):
    thread = agui_persistence.Thread(
        room_id=ROOM_ID,
        user_name=USER_NAME,
        thread_id=THREAD_UUID,
    )
    the_session.add(thread)
    the_session.commit()

    run = agui_persistence.Run(
        thread=thread,
        run_id=RUN_UUID,
    )
    the_session.add(run)
    the_session.commit()

    usage = agui_persistence.RunUsage(
        run=run,
        input_tokens=1,
        output_tokens=2,
        requests=3,
        tool_calls=4,
    )
    the_session.add(usage)
    the_session.commit()

    found = usage.as_tuple()

    assert found == (1, 2, 3, 4)


@pytest.mark.parametrize(
    "agui_rai",
    [
        EMPTY_RUN_AGENT_INPUT,
        FULL_RUN_AGENT_INPUT,
    ],
)
def test_runagentinput_from_agui_model(agui_rai):
    run = agui_persistence.Run()

    found = agui_persistence.RunAgentInput.from_agui_model(run, agui_rai)

    assert found.run is run
    assert found.to_agui_model() == agui_rai
    assert found.data == agui_rai.model_dump()

    assert found.thread_id == agui_rai.thread_id
    assert found.run_id == agui_rai.run_id
    assert found.parent_run_id == agui_rai.parent_run_id
    assert found.state == agui_rai.state
    assert found.messages == agui_rai.messages
    assert found.context == agui_rai.context
    assert found.tools == agui_rai.tools
    assert found.forwarded_props == agui_rai.forwarded_props


@pytest.mark.parametrize(
    "agui_event",
    [
        TEXT_MESSAGE_START_EVENT,
        TEXT_MESSAGE_CONTENT_EVENT,
        TEXT_MESSAGE_END_EVENT,
        TEXT_MESSAGE_CHUNK_EVENT,
        TOOL_CALL_START_EVENT,
        TOOL_CALL_ARGS_EVENT,
        TOOL_CALL_END_EVENT,
        EMPTY_TOOL_CALL_CHUNK_EVENT,
        TOOL_CALL_CHUNK_EVENT,
        TOOL_CALL_RESULT_EVENT,
        STATE_SNAPSHOT_EVENT,
        STATE_DELTA_EVENT,
        EMPTY_MESSAGES_SNAPSHOT_EVENT,
        MESSAGES_SNAPSHOT_EVENT,
        ACTIVITY_SNAPSHOT_EVENT,
        ACTIVITY_DELTA_EVENT,
        NO_SOURCE_RAW_EVENT,
        RAW_EVENT,
        CUSTOM_EVENT,
        BARE_RUN_STARTED_EVENT,
        W_PARENT_RUN_ID_RUN_STARTED_EVENT,
        W_RAI_RUN_STARTED_EVENT,
        BARE_RUN_FINISHED_EVENT,
        W_RESULT_RUN_FINISHED_EVENT,
        BARE_RUN_ERROR_EVENT,
        W_CODE_RUN_ERROR_EVENT,
        STEP_STARTED_EVENT,
        STEP_FINISHED_EVENT,
    ],
)
def test_runevent_from_agui_event(agui_event):
    run = agui_persistence.Run()

    found = agui_persistence.RunEvent.from_agui_model(run, agui_event)

    assert found.run is run
    assert found.to_agui_model() == agui_event
    assert found.data == agui_event.model_dump()

    assert found.type == agui_event.type


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
        config.ASYNC_MEMORY_ENGINE_URL,
    )
    async with engine.begin() as connection:
        await connection.run_sync(agui_persistence.Base.metadata.create_all)

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
                "name": THREAD_NAME,
                "description": THREAD_DESCRIPTION,
            },
        )

    await the_async_session.commit()

    updated = await ts.update_thread_metadata(
        user_name=USER_NAME,
        thread_id=thread_id,
        room_id=ROOM_ID,
        thread_metadata={
            "name": THREAD_NAME,
            "description": THREAD_DESCRIPTION,
        },
    )

    assert updated is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == THREAD_NAME
    assert thread_meta.description == THREAD_DESCRIPTION

    await the_async_session.commit()

    updated_again = await ts.update_thread_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        thread_metadata=agui_persistence.ThreadMetadata(
            name=THREAD_NAME,
        ),
    )

    assert updated_again is thread

    await the_async_session.commit()

    thread_meta = await updated.awaitable_attrs.thread_metadata

    assert thread_meta.name == THREAD_NAME
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
        thread_metadata=agui_persistence.ThreadMetadata(
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
        run_input=FULL_RUN_AGENT_INPUT,
    )

    assert rai_added is initial_run

    await the_async_session.commit()

    assert await initial_run.awaitable_attrs.run_input == FULL_RUN_AGENT_INPUT

    await the_async_session.commit()

    with pytest.raises(agui_package.RunAlreadyStarted):
        await ts.add_run_input(
            user_name=USER_NAME,
            room_id=ROOM_ID,
            thread_id=thread_id,
            run_id=initial_run_id,
            run_input=FULL_RUN_AGENT_INPUT,
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
            "label": RUN_LABEL,
        },
    )

    assert updated is added

    rmd = await updated.awaitable_attrs.run_metadata
    assert rmd.label == RUN_LABEL

    await the_async_session.commit()

    updated_again = await ts.update_run_metadata(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_id=added_id,
        run_metadata=agui_persistence.RunMetadata(
            label=OTHER_RUN_LABEL,
        ),
    )

    assert updated_again is added

    rmd = await updated_again.awaitable_attrs.run_metadata
    assert rmd.label == OTHER_RUN_LABEL

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
        run_metadata=agui_persistence.RunMetadata(label="parent"),
    )

    await the_async_session.commit()

    parent_id = await parent.awaitable_attrs.run_id

    await the_async_session.commit()

    spare = await ts.new_run(
        user_name=USER_NAME,
        room_id=ROOM_ID,
        thread_id=thread_id,
        run_metadata=agui_persistence.RunMetadata(label="spare"),
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


@pytest.fixture
def the_engine():
    engine = sqlalchemy.create_engine(config.SYNC_MEMORY_ENGINE_URL)

    yield engine

    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("w_agui_events", [[], TEST_AGUI_RUN_EVENTS])
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
        if event.type not in agui_persistence.SKIP_EVENT_TYPES
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


@pytest.fixture
def the_session(the_engine):
    with the_engine.connect() as connection:
        agui_persistence.Base.metadata.create_all(connection)

    assert connection.closed

    with sqla_orm.Session(bind=the_engine) as session:
        yield session


def test_sqla_thread_ctor(the_session):
    thread = agui_persistence.Thread(
        room_id=ROOM_ID,
        user_name=USER_NAME,
    )
    the_session.add(thread)
    the_session.commit()


@pytest.mark.parametrize(
    "agui_rai",
    [
        EMPTY_RUN_AGENT_INPUT,
        FULL_RUN_AGENT_INPUT,
    ],
)
def test_sqla_thread_run_interactions(the_session, agui_rai):
    with the_session as session:
        thread = agui_persistence.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        assert thread.thread_metadata is None
        assert thread.runs == []

        thread_meta = agui_persistence.ThreadMetadata(
            thread=thread,
            name=THREAD_NAME,
            description=THREAD_DESCRIPTION,
        )
        session.add(thread_meta)
        session.commit()

        assert thread.thread_metadata is thread_meta

        run = agui_persistence.Run(
            thread=thread,
        )
        session.add(run)
        session.commit()

        assert thread.runs == [run]

        assert run.run_metadata is None
        assert run.run_agent_input is None

        run_meta = agui_persistence.RunMetadata(
            run=run,
            label=RUN_LABEL,
        )
        session.add(run_meta)
        session.commit()

        assert run.run_metadata is run_meta

        rai = agui_persistence.RunAgentInput.from_agui_model(
            run,
            agui_rai,
        )
        session.add(rai)
        session.commit()

        assert run.run_agent_input is rai


def test_sqla_run_hierarchy(the_session):
    with the_session as session:
        thread = agui_persistence.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        parent_run = agui_persistence.Run(
            thread=thread,
        )
        session.add(parent_run)
        session.commit()

        assert thread.runs == [parent_run]
        assert parent_run.children == []

        child_run = agui_persistence.Run(thread=thread, parent=parent_run)
        session.add(parent_run)
        session.commit()

        assert thread.runs == [parent_run, child_run]
        assert parent_run.children == [child_run]


@pytest.mark.anyio
async def test_sqla_run_events(the_session):
    with the_session as session:
        thread = agui_persistence.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        run = agui_persistence.Run(
            thread=thread,
        )
        session.add(run)
        session.commit()

        events = []

        for agui_event in TEST_AGUI_RUN_EVENTS:
            event = agui_persistence.RunEvent.from_agui_model(run, agui_event)
            events.append(event)
            session.add(event)

        session.commit()

        for agui_event, db_event in zip(
            TEST_AGUI_RUN_EVENTS,
            await run.list_events(),
            strict=True,
        ):
            assert db_event == agui_event


@pytest.mark.parametrize("init_schema", [False, True])
@mock.patch("sqlalchemy.create_engine")
@mock.patch("soliplex.agui.persistence.metadata.create_all")
def test_get_session(
    ca,
    ce,
    init_schema,
):
    kwargs = {}

    if init_schema:
        kwargs["init_schema"] = True

    with agui_persistence.get_session(**kwargs) as session:
        assert isinstance(session, sqla_orm.Session)
        assert session.bind is ce.return_value

        ce.assert_called_once_with(config.SYNC_MEMORY_ENGINE_URL)

        if init_schema:
            connection = ce.return_value.connect.return_value
            ca.assert_called_once_with(connection.__enter__.return_value)
        else:
            ca.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [False, True])
@mock.patch("sqlalchemy.ext.asyncio.create_async_engine")
@mock.patch("soliplex.agui.persistence.metadata.create_all")
async def test_get_async_session(
    ca,
    cae,
    init_schema,
):
    engine = cae.return_value

    kwargs = {}

    if init_schema:
        kwargs["init_schema"] = True

    session_maker = await agui_persistence.get_async_session(**kwargs)

    async with session_maker as session:
        assert isinstance(session, sqla_asyncio.AsyncSession)
        assert session.bind is engine

        cae.assert_called_once_with(config.ASYNC_MEMORY_ENGINE_URL)

        if init_schema:
            engine.begin.assert_called_once_with()
            connection = engine.begin.return_value.__aenter__.return_value
            connection.run_sync.assert_called_once_with(ca)
        else:
            engine.begin.assert_not_called()
