import pytest

from soliplex import mcp_client


class _Tool:
    def __init__(self, name):
        self.name = name


@pytest.fixture
def offered_tools():
    return [_Tool(f"tool_{i_tool}") for i_tool in range(10)]


@pytest.mark.parametrize(
    "w_allowed, expected_indexes",
    [
        (None, list(range(10))),
        ([], list(range(10))),
        (["tool_1"], [1]),
        (["tool_3", "tool_5", "tool_9"], [3, 5, 9]),
    ],
)
def test__filter_tools(offered_tools, w_allowed, expected_indexes):
    found = mcp_client._filter_tools(offered_tools, w_allowed)

    assert len(found) == len(expected_indexes)
    f_names = set([f_tool.name for f_tool in found])
    e_names = set([f"tool_{e_index}" for e_index in expected_indexes])

    assert f_names == e_names
