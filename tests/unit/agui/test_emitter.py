import asyncio
from unittest import mock

import pydantic
import pytest

from soliplex.agui import emitter

THREAD_ID = "test-thread"
RUN_ID = "test-run"


class AGUI_TestState(pydantic.BaseModel):
    foo: str
    qux: str | None = None


@pytest.mark.parametrize("w_deltas", [None, False, True])
def test_aguiemitter_ctor(w_deltas):
    if w_deltas is None:
        found = emitter.AGUIEmitter(
            thread_id=THREAD_ID,
            run_id=RUN_ID,
        )
        exp_use_deltas = True
    else:
        found = emitter.AGUIEmitter(
            thread_id=THREAD_ID,
            run_id=RUN_ID,
            use_deltas=w_deltas,
        )
        exp_use_deltas = w_deltas

    assert found.thread_id == THREAD_ID
    assert found.run_id == RUN_ID
    assert found.use_deltas == exp_use_deltas
    assert isinstance(found._queue, asyncio.Queue)
    assert not found._closed
    assert found._last_state == {}
    assert found._last_activities == {}


@pytest.mark.parametrize("w_deltas", [False, True])
@pytest.mark.parametrize("w_model", [False, True])
@pytest.mark.parametrize("w_closed", [False, True])
def test_aguiemitter_update_state(w_closed, w_model, w_deltas):
    PRIOR_STATE = {
        "foo": "bar",
        "qux": "spam",
    }

    NEW_STATE = {"foo": "baz"}

    agui_emitter = emitter.AGUIEmitter(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        use_deltas=w_deltas,
    )
    agui_emitter._queue = mock.Mock(spec_set=["put_nowait"])

    if w_closed:
        agui_emitter._closed = True

    agui_emitter._last_state = PRIOR_STATE

    if w_model:
        next_state = AGUI_TestState.model_validate(NEW_STATE)
        exp_state = next_state.model_dump()
    else:
        next_state = exp_state = NEW_STATE

    agui_emitter.update_state(next_state)

    if w_closed:
        agui_emitter._queue.put_nowait.assert_not_called()
    else:
        (called,) = agui_emitter._queue.put_nowait.call_args_list

        assert called.kwargs == {}
        (event,) = called.args

        if w_deltas:
            assert event["type"] == "STATE_DELTA"
            assert event["delta"] == exp_state
            assert agui_emitter._last_state == PRIOR_STATE | NEW_STATE
        else:
            assert event["type"] == "STATE_SNAPSHOT"
            assert event["snapshot"] == exp_state
            assert agui_emitter._last_state == exp_state


@pytest.mark.parametrize("w_activity_id", [False, True])
@pytest.mark.parametrize("w_deltas", [False, True])
@pytest.mark.parametrize("w_model", [False, True])
@pytest.mark.parametrize("w_closed", [False, True])
@mock.patch("uuid.uuid4")
def test_aguiemitter_update_activity(
    uid4,
    w_closed,
    w_model,
    w_deltas,
    w_activity_id,
):
    ACTIVITY_ID = "test-activity-id"
    ACTIVITY_TYPE = "test-activity"
    PRIOR_ACTIVITY_CONTENT = {
        "foo": "bar",
        "qux": "spam",
    }
    PRIOR_ACTIVITIES = {
        ACTIVITY_TYPE: PRIOR_ACTIVITY_CONTENT,
    }

    NEW_ACTIVITY_CONTENT = {"foo": "baz"}

    agui_emitter = emitter.AGUIEmitter(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        use_deltas=w_deltas,
    )
    agui_emitter._queue = mock.Mock(spec_set=["put_nowait"])

    if w_closed:
        agui_emitter._closed = True

    agui_emitter._last_activities = PRIOR_ACTIVITIES

    if w_model:
        next_state = AGUI_TestState.model_validate(NEW_ACTIVITY_CONTENT)
        exp_state = next_state.model_dump()
    else:
        next_state = exp_state = NEW_ACTIVITY_CONTENT

    if w_activity_id:
        exp_activity_id = ACTIVITY_ID
        agui_emitter.update_activity(
            ACTIVITY_TYPE,
            next_state,
            activity_id=ACTIVITY_ID,
        )
    else:
        exp_activity_id = str(uid4.return_value)
        agui_emitter.update_activity(ACTIVITY_TYPE, next_state)

    if w_closed:
        agui_emitter._queue.put_nowait.assert_not_called()
    else:
        (called,) = agui_emitter._queue.put_nowait.call_args_list

        assert called.kwargs == {}
        (event,) = called.args

        after_activity = agui_emitter._last_activities[ACTIVITY_TYPE]

        assert event["message_id"] == exp_activity_id

        if w_deltas:
            assert event["type"] == "ACTIVITY_DELTA"
            assert event["patch"] == exp_state
            assert after_activity == (PRIOR_ACTIVITY_CONTENT | exp_state)
        else:
            assert event["type"] == "ACTIVITY_SNAPSHOT"
            assert event["content"] == exp_state
            assert after_activity == exp_state


@pytest.mark.anyio
@pytest.mark.parametrize("w_closed", [False, True])
async def test_aguiemitter_close(w_closed):
    agui_emitter = emitter.AGUIEmitter(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )
    queue = agui_emitter._queue = mock.Mock(spec_set=["put"])
    queue.put = mock.AsyncMock(spec_set=())

    if w_closed:
        agui_emitter._closed = True

    await agui_emitter.close()

    assert agui_emitter._closed is True

    if w_closed:
        queue.put.assert_not_awaited()
    else:
        queue.put.assert_awaited_once_with(None)


@pytest.mark.asyncio
async def test_async_iteration():
    agui_emitter = emitter.AGUIEmitter(
        thread_id=THREAD_ID,
        run_id=RUN_ID,
        use_deltas=False,
    )

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
