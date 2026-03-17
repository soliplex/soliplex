import datetime
from unittest import mock

import pytest

from soliplex import agents
from soliplex import installation
from soliplex import tools

USER = {
    "full_name": "Phreddy Phlyntstone",
    "email": "phreddy@example.com",
}


@pytest.fixture
def the_installation():
    return mock.create_autospec(installation.Installation)


@pytest.mark.anyio
@mock.patch("soliplex.tools.datetime")
async def test_get_current_datetime(dt_module):
    NOW = datetime.datetime(2025, 8, 7, 11, 32, 41, tzinfo=datetime.UTC)
    now = dt_module.datetime.now
    now.return_value = NOW

    found = await tools.get_current_datetime()

    assert found == NOW.isoformat()

    now.assert_called_once_with(dt_module.UTC)


@pytest.mark.anyio
async def test_get_current_user(the_installation):
    deps = agents.AgentDependencies(
        the_installation=the_installation,
        user=USER,
    )
    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.get_current_user(ctx)

    assert found is deps.user


@pytest.mark.anyio
@pytest.mark.parametrize("w_state", [False, True])
async def test_agui_state(the_installation, w_state):
    state = {
        "foo": "Foo",
        "bar": {
            "baz": "Baz",
        },
    }
    if w_state:
        deps = agents.AgentDependencies(
            the_installation=the_installation,
            user=USER,
            tool_configs={},
            state=state,
        )
        expected = state
    else:
        deps = agents.AgentDependencies(
            the_installation=the_installation,
            user=USER,
            tool_configs={},
        )
        expected = {}

    ctx = mock.Mock(spec_set=(["deps"]), deps=deps)

    found = await tools.agui_state(ctx=ctx)

    assert found == expected
