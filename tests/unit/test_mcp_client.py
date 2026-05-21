from unittest import mock

import pytest

from soliplex import mcp_client


class _ToolDef:
    def __init__(self, name):
        self.name = name


@pytest.mark.parametrize(
    "allowed_tools",
    [None, []],
)
def test__allowed_tools_filter_empty(allowed_tools):
    assert mcp_client._allowed_tools_filter(allowed_tools) is None


def test__allowed_tools_filter_predicate():
    f = mcp_client._allowed_tools_filter(["tool_a", "tool_c"])

    ctx = mock.sentinel.ctx
    assert f(ctx, _ToolDef("tool_a")) is True
    assert f(ctx, _ToolDef("tool_b")) is False
    assert f(ctx, _ToolDef("tool_c")) is True


@pytest.mark.parametrize(
    "allowed_tools",
    [None, []],
)
def test__apply_allow_list_passthrough(allowed_tools):
    toolset = mock.Mock()
    found = mcp_client._apply_allow_list(toolset, allowed_tools)

    assert found is toolset
    toolset.filtered.assert_not_called()


def test__apply_allow_list_wraps():
    toolset = mock.Mock()
    allowed = ["tool_a"]

    found = mcp_client._apply_allow_list(toolset, allowed)

    assert found is toolset.filtered.return_value
    toolset.filtered.assert_called_once()
    (filter_func,) = toolset.filtered.call_args.args
    ctx = mock.sentinel.ctx
    assert filter_func(ctx, _ToolDef("tool_a")) is True
    assert filter_func(ctx, _ToolDef("tool_b")) is False
