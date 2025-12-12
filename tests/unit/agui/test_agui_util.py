import contextlib
from unittest import mock

import pytest
from ag_ui import core as agui_core

from soliplex import agui as agui_package
from soliplex.agui import util as agui_util

TEST_THREAD_ID = "thread-987"
OTHER_THREAD_ID = "thread-123"
TEST_PARENT_RUN_ID = "run-012"
OTHER_PARENT_RUN_ID = "run-789"
TEST_RUN_ID = "run-345"
OTHER_RUN_ID = "run-567"

TEST_RUN_INPUT = agui_core.RunAgentInput(
    thread_id=TEST_THREAD_ID,
    run_id=TEST_RUN_ID,
    parent_run_id=TEST_PARENT_RUN_ID,
    state={},
    messages=[],
    tools=[],
    context=[],
    forwarded_props=None,
)

no_error = contextlib.nullcontext
raises_run_input_mismatch = pytest.raises(agui_package.RunInputMismatch)


@mock.patch("uuid.uuid4")
def test__make_uuid_str(u4):
    expected_uuid = u4.return_value = object()

    found = agui_util._make_uuid_str()

    assert found == str(expected_uuid)

    u4.assert_called_once_with()


@mock.patch("datetime.timezone")
@mock.patch("datetime.datetime")
def test__timestamp(dt, tz):
    found = agui_util._timestamp()

    assert found is dt.now.return_value

    dt.now.assert_called_once_with(tz.utc)


@pytest.mark.parametrize(
    "rhs_kwargs, expectation",
    [
        ({}, no_error()),
        ({"thread_id": OTHER_THREAD_ID}, raises_run_input_mismatch),
        ({"run_id": OTHER_RUN_ID}, raises_run_input_mismatch),
        ({"parent_run_id": OTHER_PARENT_RUN_ID}, raises_run_input_mismatch),
    ],
)
@pytest.mark.parametrize("w_lhs_none", [False, True])
def test_check_run_input(w_lhs_none, rhs_kwargs, expectation):
    if w_lhs_none:
        lhs = None
        expectation = no_error()
    else:
        lhs = TEST_RUN_INPUT

    rhs = TEST_RUN_INPUT.model_copy(update=rhs_kwargs)

    with expectation as expectation:
        agui_util.check_run_input(lhs, rhs)
