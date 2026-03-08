from unittest import mock

import pytest
from sqlalchemy import orm as sqla_orm
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import util
from soliplex.agui import schema as agui_schema
from soliplex.config import installation as config_installation
from tests.unit.agui import agui_constants

ROOM_ID = "test-room"
USER_NAME = "phreddy"


def _mock_run(run_id, thread):
    return agui_schema.Run(
        run_id=run_id,
        thread=thread,
    )


@pytest.mark.anyio
async def test_thread_list_runs():
    thread = agui_schema.Thread()
    runs = [
        _mock_run("one", thread),
        _mock_run("two", thread),
    ]

    found = await thread.list_runs()

    assert found == runs


def test_run_thread_id():
    thread = agui_schema.Thread(thread_id=agui_constants.THREAD_UUID)
    run = agui_schema.Run(thread=thread)

    assert run.thread_id == agui_constants.THREAD_UUID


@pytest.mark.parametrize("w_parent_id", [None, agui_constants.PARENT_RUN_ID])
def test_run_parent_run_id(w_parent_id):
    thread = agui_schema.Thread(thread_id=agui_constants.THREAD_UUID)

    if w_parent_id is not None:
        parent = agui_schema.Run(thread=thread, run_id=w_parent_id)
    else:
        parent = None

    run = agui_schema.Run(thread=thread, parent=parent)

    assert run.parent_run_id == w_parent_id


@pytest.mark.parametrize(
    "w_run_input",
    [
        None,
        agui_constants.EMPTY_RUN_AGENT_INPUT,
        agui_constants.FULL_RUN_AGENT_INPUT,
    ],
)
def test_run_run_input(w_run_input):
    run = agui_schema.Run()

    if w_run_input is not None:
        _ = agui_schema.RunAgentInput.from_agui_model(run, w_run_input)

    assert run.run_input == w_run_input


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_agui_events", [[], agui_constants.TEST_AGUI_RUN_EVENTS]
)
async def test_run_list_events(w_agui_events):
    run = agui_schema.Run()

    run.events = [
        agui_schema.RunEvent.from_agui_model(run, agui_event)
        for agui_event in w_agui_events
    ]

    assert await run.list_events() == w_agui_events


@pytest.mark.anyio
async def test_runusage_as_tuple(the_session):
    thread = agui_schema.Thread(
        room_id=ROOM_ID,
        user_name=USER_NAME,
        thread_id=agui_constants.THREAD_UUID,
    )
    the_session.add(thread)
    the_session.commit()

    run = agui_schema.Run(
        thread=thread,
        run_id=agui_constants.RUN_UUID,
    )
    the_session.add(run)
    the_session.commit()

    usage = agui_schema.RunUsage(
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
        agui_constants.EMPTY_RUN_AGENT_INPUT,
        agui_constants.FULL_RUN_AGENT_INPUT,
    ],
)
def test_runagentinput_from_agui_model(agui_rai):
    run = agui_schema.Run()

    found = agui_schema.RunAgentInput.from_agui_model(run, agui_rai)

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
        agui_constants.TEXT_MESSAGE_START_EVENT,
        agui_constants.TEXT_MESSAGE_CONTENT_EVENT,
        agui_constants.TEXT_MESSAGE_END_EVENT,
        agui_constants.TEXT_MESSAGE_CHUNK_EVENT,
        agui_constants.TOOL_CALL_START_EVENT,
        agui_constants.TOOL_CALL_ARGS_EVENT,
        agui_constants.TOOL_CALL_END_EVENT,
        agui_constants.EMPTY_TOOL_CALL_CHUNK_EVENT,
        agui_constants.TOOL_CALL_CHUNK_EVENT,
        agui_constants.TOOL_CALL_RESULT_EVENT,
        agui_constants.STATE_SNAPSHOT_EVENT,
        agui_constants.STATE_DELTA_EVENT,
        agui_constants.EMPTY_MESSAGES_SNAPSHOT_EVENT,
        agui_constants.MESSAGES_SNAPSHOT_EVENT,
        agui_constants.ACTIVITY_SNAPSHOT_EVENT,
        agui_constants.ACTIVITY_DELTA_EVENT,
        agui_constants.NO_SOURCE_RAW_EVENT,
        agui_constants.RAW_EVENT,
        agui_constants.CUSTOM_EVENT,
        agui_constants.BARE_RUN_STARTED_EVENT,
        agui_constants.W_PARENT_RUN_ID_RUN_STARTED_EVENT,
        agui_constants.W_RAI_RUN_STARTED_EVENT,
        agui_constants.BARE_RUN_FINISHED_EVENT,
        agui_constants.W_RESULT_RUN_FINISHED_EVENT,
        agui_constants.BARE_RUN_ERROR_EVENT,
        agui_constants.W_CODE_RUN_ERROR_EVENT,
        agui_constants.STEP_STARTED_EVENT,
        agui_constants.STEP_FINISHED_EVENT,
    ],
)
def test_runevent_from_agui_event(agui_event):
    run = agui_schema.Run()

    found = agui_schema.RunEvent.from_agui_model(run, agui_event)

    assert found.run is run
    assert found.to_agui_model() == agui_event
    assert found.data == agui_event.model_dump()

    assert found.type == agui_event.type


def test_thread_ctor(the_session):
    thread = agui_schema.Thread(
        room_id=ROOM_ID,
        user_name=USER_NAME,
    )
    the_session.add(thread)
    the_session.commit()


@pytest.mark.parametrize(
    "agui_rai",
    [
        agui_constants.EMPTY_RUN_AGENT_INPUT,
        agui_constants.FULL_RUN_AGENT_INPUT,
    ],
)
def test_thread_run_interactions(the_session, agui_rai):
    with the_session as session:
        thread = agui_schema.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        assert thread.thread_metadata is None
        assert thread.runs == []

        thread_meta = agui_schema.ThreadMetadata(
            thread=thread,
            name=agui_constants.THREAD_NAME,
            description=agui_constants.THREAD_DESCRIPTION,
        )
        session.add(thread_meta)
        session.commit()

        assert thread.thread_metadata is thread_meta

        run = agui_schema.Run(
            thread=thread,
        )
        session.add(run)
        session.commit()

        assert thread.runs == [run]

        assert run.run_metadata is None
        assert run.run_agent_input is None

        run_meta = agui_schema.RunMetadata(
            run=run,
            label=agui_constants.RUN_LABEL,
        )
        session.add(run_meta)
        session.commit()

        assert run.run_metadata is run_meta

        rai = agui_schema.RunAgentInput.from_agui_model(
            run,
            agui_rai,
        )
        session.add(rai)
        session.commit()

        assert run.run_agent_input is rai


def test_run_hierarchy(the_session):
    with the_session as session:
        thread = agui_schema.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        parent_run = agui_schema.Run(
            thread=thread,
        )
        session.add(parent_run)
        session.commit()

        assert thread.runs == [parent_run]
        assert parent_run.children == []

        child_run = agui_schema.Run(thread=thread, parent=parent_run)
        session.add(parent_run)
        session.commit()

        assert thread.runs == [parent_run, child_run]
        assert parent_run.children == [child_run]


@pytest.mark.anyio
async def test_run_events(the_session):
    with the_session as session:
        thread = agui_schema.Thread(
            room_id=ROOM_ID,
            user_name=USER_NAME,
        )
        session.add(thread)
        session.commit()

        run = agui_schema.Run(
            thread=thread,
        )
        session.add(run)
        session.commit()

        events = []

        for agui_event in agui_constants.TEST_AGUI_RUN_EVENTS:
            event = agui_schema.RunEvent.from_agui_model(run, agui_event)
            events.append(event)
            session.add(event)

        session.commit()

        for agui_event, db_event in zip(
            agui_constants.TEST_AGUI_RUN_EVENTS,
            await run.list_events(),
            strict=True,
        ):
            assert db_event == agui_event


@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("sqlalchemy.create_engine")
@mock.patch("soliplex.agui.schema.metadata.create_all")
def test_get_engine(
    ca,
    ce,
    init_schema,
):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema

    found = agui_schema.get_engine(**kwargs)

    assert found is ce.return_value

    ce.assert_called_once_with(
        config_installation.SYNC_MEMORY_ENGINE_URL,
        json_serializer=util.serialize_sqla_json,
    )

    if init_schema:
        connection = ce.return_value.connect.return_value
        ca.assert_called_once_with(connection.__enter__.return_value)
    else:
        ca.assert_not_called()


@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("soliplex.agui.schema.get_engine")
def test_get_session(
    ge,
    init_schema,
):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema
        exp_kwargs = kwargs
    else:
        exp_kwargs = {"init_schema": False}

    with agui_schema.get_session(**kwargs) as session:
        assert isinstance(session, sqla_orm.Session)
        assert session.bind is ge.return_value

        ge.assert_called_once_with(
            engine_url=config_installation.SYNC_MEMORY_ENGINE_URL,
            **exp_kwargs,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("sqlalchemy.ext.asyncio.create_async_engine")
@mock.patch("soliplex.agui.schema.metadata.create_all")
async def test_get_async_engine(
    ca,
    cae,
    init_schema,
):
    engine = cae.return_value

    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema

    found = await agui_schema.get_async_engine(**kwargs)

    assert found is cae.return_value

    cae.assert_called_once_with(
        config_installation.ASYNC_MEMORY_ENGINE_URL,
        json_serializer=util.serialize_sqla_json,
    )

    if init_schema:
        engine.begin.assert_called_once_with()
        connection = engine.begin.return_value.__aenter__.return_value
        connection.run_sync.assert_called_once_with(ca)
    else:
        engine.begin.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("init_schema", [None, False, True])
@mock.patch("soliplex.agui.schema.get_async_engine")
async def test_get_async_session(
    gae,
    init_schema,
):
    kwargs = {}

    if init_schema is not None:
        kwargs["init_schema"] = init_schema
        exp_kwargs = kwargs
    else:
        exp_kwargs = {"init_schema": False}

    session_maker = await agui_schema.get_async_session(**kwargs)

    async with session_maker as session:
        assert isinstance(session, sqla_asyncio.AsyncSession)
        assert session.bind is gae.return_value

        gae.assert_called_once_with(
            engine_url=config_installation.ASYNC_MEMORY_ENGINE_URL,
            **exp_kwargs,
        )
