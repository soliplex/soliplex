import asyncio

import pydantic
import pytest
from ag_ui import core as agui_core

from soliplex.agui import emitter


class MockState(pydantic.BaseModel):
    value: str = "test"


@pytest.fixture
def agui_emitter():
    return emitter.AGUIEmitter(
        thread_id="test-thread",
        run_id="test-run",
        use_deltas=True,
    )


def test_agui_emitter_init():
    em = emitter.AGUIEmitter(
        thread_id="t1",
        run_id="r1",
        use_deltas=False,
    )
    assert em.thread_id == "t1"
    assert em.run_id == "r1"
    assert em.use_deltas is False
    assert em._closed is False


def test_update_state_w_dict(agui_emitter):
    state_dict = {"key": "value"}
    agui_emitter.update_state(state_dict)

    assert not agui_emitter._queue.empty()
    event = agui_emitter._queue.get_nowait()
    assert event["type"] == agui_core.EventType.STATE_SNAPSHOT.value
    assert event["snapshot"] == state_dict


def test_update_state_w_pydantic_model(agui_emitter):
    state = MockState(value="pydantic-test")
    agui_emitter.update_state(state)

    assert not agui_emitter._queue.empty()
    event = agui_emitter._queue.get_nowait()
    assert event["type"] == agui_core.EventType.STATE_SNAPSHOT.value
    assert event["snapshot"] == {"value": "pydantic-test"}


def test_update_state_when_closed(agui_emitter):
    agui_emitter._closed = True
    agui_emitter.update_state({"key": "value"})

    assert agui_emitter._queue.empty()


def test_update_activity(agui_emitter):
    agui_emitter.update_activity(
        activity_type="thinking",
        content={"message": "processing"},
        activity_id="act-1",
    )

    assert not agui_emitter._queue.empty()
    event = agui_emitter._queue.get_nowait()
    assert event["type"] == agui_core.EventType.ACTIVITY_SNAPSHOT.value
    assert event["message_id"] == "act-1"
    assert event["activity_type"] == "thinking"
    assert event["content"] == {"message": "processing"}


def test_update_activity_generates_id(agui_emitter):
    agui_emitter.update_activity(
        activity_type="searching",
        content={"query": "test"},
    )

    event = agui_emitter._queue.get_nowait()
    assert event["message_id"] is not None
    assert len(event["message_id"]) > 0


def test_update_activity_when_closed(agui_emitter):
    agui_emitter._closed = True
    agui_emitter.update_activity("thinking", {"message": "test"})

    assert agui_emitter._queue.empty()


@pytest.mark.asyncio
async def test_close(agui_emitter):
    assert agui_emitter._closed is False
    await agui_emitter.close()
    assert agui_emitter._closed is True


@pytest.mark.asyncio
async def test_async_iteration(agui_emitter):
    agui_emitter.update_state({"event": 1})
    agui_emitter.update_state({"event": 2})
    await agui_emitter.close()

    events = []
    async for event in agui_emitter:
        events.append(event)

    assert len(events) == 2
    assert events[0]["snapshot"] == {"event": 1}
    assert events[1]["snapshot"] == {"event": 2}


@pytest.mark.asyncio
async def test_async_iteration_empty_closed():
    em = emitter.AGUIEmitter(
        thread_id="t1",
        run_id="r1",
    )
    await em.close()

    events = []
    async for event in em:
        events.append(event)  # pragma: NO COVER - loop body never executes

    assert events == []


@pytest.mark.asyncio
async def test_async_iteration_timeout_when_not_closed():
    em = emitter.AGUIEmitter(
        thread_id="t1",
        run_id="r1",
    )

    async def close_later():
        await asyncio.sleep(0.15)
        await em.close()

    asyncio.create_task(close_later())

    events = []
    async for event in em:
        events.append(event)  # pragma: NO COVER - loop body never executes

    assert events == []
