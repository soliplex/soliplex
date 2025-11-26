import contextlib
import dataclasses
import datetime
import uuid
from unittest import mock

import fastapi
import pytest
from ag_ui import core as agui_core

from soliplex.agui import thread as agui_thread

UUID4 = uuid.uuid4()
NOW = datetime.datetime.now(datetime.UTC)

TEST_USER = "test-user"
TEST_THREAD_ROOMID = "test-room"
TEST_THREAD_ID = str(UUID4)
OTHER_THREAD_ID = "thread-123"
TEST_THREAD_NAME = f"Test Thread {UUID4}"
TEST_THREAD_DESC = "Test thread description"
TEST_THREAD = agui_thread.Thread(
    thread_id=TEST_THREAD_ID,
    room_id=TEST_THREAD_ROOMID,
)
TEST_THREADS = {
    TEST_THREAD_ID: TEST_THREAD,
}
TEST_PARENT_RUN_ID = "run-012"
OTHER_PARENT_RUN_ID = "run-789"
TEST_PARENT_RUN = agui_thread.Run(
    run_id=TEST_PARENT_RUN_ID,
)
TEST_RUN_ID = "run-345"
OTHER_RUN_ID = "run-567"
TEST_RUN = agui_thread.Run(
    run_id=TEST_RUN_ID,
)
TEST_RUN_LABEL = "label"
TEST_RUN_METADATA = agui_thread.RunMetadata(
    label=TEST_RUN_LABEL,
)

no_error = contextlib.nullcontext


@pytest.fixture
def run_input():
    return agui_core.RunAgentInput(
        thread_id=TEST_THREAD_ID,
        run_id=TEST_RUN_ID,
        state={},
        messages=[],
        tools=[],
        context=[],
        forwarded_props=None,
    )


@mock.patch("uuid.uuid4")
def test__make_uuid_str(uu4):
    uu4.return_value = UUID4

    assert agui_thread._make_uuid_str() == str(UUID4)


@pytest.mark.parametrize(
    "w_run_input, expected",
    [
        (False, None),
        (True, TEST_THREAD_ID),
    ],
)
def test_run_thread_id(run_input, w_run_input, expected):
    if w_run_input:
        run = dataclasses.replace(
            TEST_RUN,
            run_input=run_input,
        )
    else:
        run = TEST_RUN

    found = run.thread_id

    assert found == expected


@pytest.mark.parametrize(
    "w_run_input, expected",
    [
        (False, None),
        (True, TEST_PARENT_RUN_ID),
    ],
)
def test_run_parent_run_id(run_input, w_run_input, expected):
    if w_run_input:
        run_input = run_input.model_copy(
            update={"parent_run_id": TEST_PARENT_RUN_ID},
        )
        run = dataclasses.replace(
            TEST_RUN,
            run_input=run_input,
        )
    else:
        run = TEST_RUN

    found = run.parent_run_id

    assert found == expected


@pytest.mark.parametrize(
    "w_run_input, expected",
    [
        (False, None),
        (True, TEST_RUN_LABEL),
    ],
)
def test_run_label(run_input, w_run_input, expected):
    if w_run_input:
        run = dataclasses.replace(
            TEST_RUN,
            metadata=TEST_RUN_METADATA,
        )
    else:
        run = TEST_RUN

    found = run.label

    assert found == expected


def test_run_created():
    run = dataclasses.replace(TEST_RUN, _created=NOW)

    assert run.created == NOW


mismatch = pytest.raises(agui_thread.RunInputMismatch)


@pytest.mark.parametrize(
    "ri_kwargs, expectation",
    [
        ({}, no_error()),
        ({"thread_id": OTHER_THREAD_ID}, mismatch),
        ({"run_id": OTHER_RUN_ID}, mismatch),
        ({"parent_run_id": OTHER_PARENT_RUN_ID}, mismatch),
    ],
)
def test_run_check_run_input(run_input, ri_kwargs, expectation):
    run = dataclasses.replace(TEST_RUN, run_input=run_input)
    to_compare = run_input.model_copy(update=ri_kwargs)

    with expectation as expectation:
        run.check_run_input(to_compare)


def test_thread_created():
    thread = dataclasses.replace(TEST_THREAD, _created=NOW)

    assert thread.created == NOW


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        ("BOGUS", pytest.raises(agui_thread.UnknownRunId)),
        (TEST_RUN_ID, no_error()),
    ],
)
async def test_thread_get_run(w_run_id, expectation):
    thread = dataclasses.replace(
        TEST_THREAD,
        runs={TEST_RUN_ID: TEST_RUN},
    )

    with expectation as expected:
        found = await thread.get_run(w_run_id)

    if expected is None:
        assert found is TEST_RUN


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_parent_id, expectation",
    [
        ("BOGUS", pytest.raises(agui_thread.MissingParentRunId)),
        (None, no_error()),
        (TEST_PARENT_RUN_ID, no_error()),
    ],
)
@pytest.mark.parametrize(
    "w_metadata, exp_label",
    [
        (None, None),
        (TEST_RUN_METADATA, TEST_RUN_LABEL),
    ],
)
@mock.patch("soliplex.agui.thread._make_uuid_str")
async def test_thread_new_run(
    mus,
    w_parent_id,
    expectation,
    w_metadata,
    exp_label,
):
    mus.return_value = TEST_RUN_ID

    thread = dataclasses.replace(
        TEST_THREAD,
        runs={TEST_PARENT_RUN_ID: TEST_PARENT_RUN},
    )

    kwargs = {}

    if w_parent_id is not None:
        kwargs["parent_run_id"] = w_parent_id

    if w_metadata is not None:
        kwargs["metadata"] = w_metadata

    with expectation as expected:
        found = await thread.new_run(**kwargs)

    if expected is None:
        assert found.thread_id == TEST_THREAD_ID
        assert found.run_id == TEST_RUN_ID
        assert found.parent_run_id == w_parent_id
        assert found.label == exp_label

        assert found is thread.runs[TEST_RUN_ID]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_run_id, expectation",
    [
        ("BOGUS", pytest.raises(agui_thread.UnknownRunId)),
        (TEST_RUN_ID, no_error()),
    ],
)
@pytest.mark.parametrize(
    "w_metadata, exp_label",
    [
        (None, None),
        (TEST_RUN_METADATA, TEST_RUN_LABEL),
    ],
)
async def test_thread_update_run(
    w_run_id,
    expectation,
    w_metadata,
    exp_label,
):
    md_before = object()
    run_before = dataclasses.replace(TEST_RUN, metadata=md_before)

    thread = dataclasses.replace(
        TEST_THREAD,
        runs={TEST_RUN_ID: run_before},
    )

    with expectation as expected:
        found = await thread.update_run(run_id=w_run_id, metadata=w_metadata)

    if expected is None:
        assert found is thread.runs[TEST_RUN_ID]
        if exp_label is not None:
            assert found.metadata.label == exp_label
        else:
            assert found.metadata is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_threads, expected",
    [
        ({}, {}),
        ({TEST_USER: TEST_THREADS}, TEST_THREADS),
    ],
)
async def test_threads_user_threads(w_threads, expected):
    the_threads = agui_thread.Threads()
    the_threads._threads.update(w_threads)

    found = await the_threads.user_threads(user_name=TEST_USER)

    assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_threads, expectation",
    [
        ({}, pytest.raises(agui_thread.UnknownThread)),
        ({TEST_USER: {}}, pytest.raises(agui_thread.UnknownThread)),
        (
            {TEST_USER: TEST_THREADS},
            no_error(TEST_THREAD),
        ),
    ],
)
async def test_threads_get_thread(w_threads, expectation):
    the_threads = agui_thread.Threads()
    the_threads._threads.update(w_threads)

    with expectation as expected:
        found = await the_threads.get_thread(
            user_name=TEST_USER,
            thread_id=TEST_THREAD_ID,
        )

    if expected is TEST_THREAD:
        assert found is TEST_THREAD


@pytest.mark.anyio
@pytest.mark.parametrize("w_already", [False, True])
@mock.patch("soliplex.agui.thread._make_uuid_str")
async def test_threads_new_thread(mus, w_already):
    mus.return_value = TEST_THREAD_ID
    the_threads = agui_thread.Threads()

    user_threads_patch = {}
    if w_already:
        before = user_threads_patch[TEST_USER] = {"already": object()}

    with (
        mock.patch.dict(the_threads._threads, **user_threads_patch),
    ):
        found = await the_threads.new_thread(
            user_name=TEST_USER,
            room_id=TEST_THREAD_ROOMID,
        )
        if w_already:
            assert the_threads._threads[TEST_USER] is before

        assert the_threads._threads[TEST_USER][TEST_THREAD_ID] is found

    assert found.thread_id == TEST_THREAD_ID
    assert found.room_id == TEST_THREAD_ROOMID


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_thread_id, expectation",
    [
        ("BOGUS", pytest.raises(agui_thread.UnknownThread)),
        (TEST_THREAD_ID, no_error()),
    ],
)
@pytest.mark.parametrize(
    "w_metadata, exp_name_desc",
    [
        (None, None),
        ({"name": TEST_THREAD_NAME}, (TEST_THREAD_NAME, None)),
        (
            {
                "name": TEST_THREAD_NAME,
                "description": TEST_THREAD_DESC,
            },
            (
                TEST_THREAD_NAME,
                TEST_THREAD_DESC,
            ),
        ),
    ],
)
async def test_threads_update_thread(
    w_metadata,
    exp_name_desc,
    w_thread_id,
    expectation,
):
    the_threads = agui_thread.Threads()

    md_before = object()
    thr_before = dataclasses.replace(TEST_THREAD, metadata=md_before)

    user_threads_patch = {
        TEST_USER: {
            TEST_THREAD_ID: thr_before,
        }
    }

    if w_metadata is not None:
        metadata = agui_thread.ThreadMetadata(**w_metadata)
    else:
        metadata = None

    with (
        mock.patch.dict(the_threads._threads, **user_threads_patch),
        expectation as expected,
    ):
        found = await the_threads.update_thread(
            user_name=TEST_USER,
            thread_id=w_thread_id,
            metadata=metadata,
        )
        exp_thread = the_threads._threads[TEST_USER][TEST_THREAD_ID]

    if expected is None:
        assert found is exp_thread

        assert found.thread_id == TEST_THREAD_ID

        if exp_name_desc is None:
            assert found.metadata is None
        else:
            exp_name, exp_desc = exp_name_desc
            assert found.metadata.name == exp_name
            assert found.metadata.description == exp_desc


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_threads, expectation",
    [
        ({}, pytest.raises(agui_thread.UnknownThread)),
        ({TEST_USER: {}}, pytest.raises(agui_thread.UnknownThread)),
        ({TEST_USER: TEST_THREADS}, no_error(None)),
    ],
)
async def test_threads_delete_thread(w_threads, expectation):
    the_threads = agui_thread.Threads()

    for user_name, thread_map in list(w_threads.items()):
        new_map = {}

        for thread_id, thread in list(thread_map.items()):
            new_map[thread_id] = dataclasses.replace(thread)

        the_threads._threads[user_name] = new_map

    with expectation as expected:
        await the_threads.delete_thread(
            user_name=TEST_USER,
            thread_id=TEST_THREAD_ID,
        )

    if expected is None:
        assert the_threads._threads[TEST_USER] == {}


@pytest.mark.anyio
async def test_get_the_threads():
    expected = object()
    request = fastapi.Request(scope={"type": "http"})
    request.state.the_threads = expected

    found = await agui_thread.get_the_threads(request)

    assert found is expected
