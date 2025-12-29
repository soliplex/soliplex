from unittest import mock

import pytest
from fastmcp import tools as fmcp_tools

from soliplex import config
from soliplex import installation
from soliplex import mcp_server

ROOM_ID = "testing"


def tool_for_testing():
    """This is a test"""


TOOL_CONFIG_WO_MCP = mock.create_autospec(
    config.ToolConfig,
    kind="testing",
    tool_name="soliplex.config.testing",
    tool=tool_for_testing,
    tool_id="mcp_false_bare",
    allow_mcp=False,
    tool_requires=config.ToolRequires.BARE,
)
TOOL_CONFIG_W_MCP_WO_REQ_CTX = mock.create_autospec(
    config.ToolConfig,
    kind="testing",
    tool_name="soliplex.tools.testing",
    tool=tool_for_testing,
    allow_mcp=True,
    tool_id="mcp_true_bare",
    tool_requires=config.ToolRequires.BARE,
)
TOOL_CONFIG_W_MCP_W_REQ_CTX = mock.create_autospec(
    config.ToolConfig,
    kind="testing",
    tool_name="soliplex.tools.testing",
    tool=tool_for_testing,
    tool_id="mcp_true_w_ctx",
    allow_mcp=True,
    tool_requires=config.ToolRequires.FASTAPI_CONTEXT,
)

SDTC_WO_MCP = mock.create_autospec(
    config.SearchDocumentsToolConfig,
    kind="search_documents",
    tool_name="soliplex.tools.search_documents",
    tool=tool_for_testing,
    allow_mcp=False,
    tool_id="mcp_false_sdtc",
    tool_requires=config.ToolRequires.TOOL_CONFIG,
)
SDTC_W_MCP = mock.create_autospec(
    config.SearchDocumentsToolConfig,
    kind="search_documents",
    tool_name="soliplex.tools.search_documents",
    tool=tool_for_testing,
    allow_mcp=True,
    tool_id="mcp_true_sdtc",
    tool_requires=config.ToolRequires.TOOL_CONFIG,
)

MCP_TOOL = object()


@pytest.mark.parametrize(
    "tool_config, hit, wrapper_type",
    [
        (TOOL_CONFIG_WO_MCP, False, None),
        (TOOL_CONFIG_W_MCP_W_REQ_CTX, False, None),
        (TOOL_CONFIG_W_MCP_WO_REQ_CTX, True, None),
        (SDTC_WO_MCP, False, None),
        (SDTC_W_MCP, True, config.WithQueryMCPWrapper),
    ],
)
def test_mcp_tool(tool_config, hit, wrapper_type):
    found = mcp_server.mcp_tool(tool_config)

    if not hit:
        assert found is None

    else:
        assert isinstance(found, fmcp_tools.Tool)

        if wrapper_type is not None:
            wrapper = found.fn.__self__
            assert isinstance(wrapper, wrapper_type)
            assert wrapper._func is tool_config.tool
            assert wrapper._tool_config is tool_config

        else:
            assert found.fn is tool_config.tool


@pytest.mark.parametrize("allow_mcp", [False, True])
@pytest.mark.parametrize(
    "tool_configs, exp_mcp_tools",
    [
        ({}, []),
        ({"tool": TOOL_CONFIG_WO_MCP}, []),
        ({"tool": TOOL_CONFIG_W_MCP_WO_REQ_CTX}, [MCP_TOOL]),
        (
            {
                "tool1": TOOL_CONFIG_WO_MCP,
                "tool2": TOOL_CONFIG_W_MCP_WO_REQ_CTX,
            },
            [MCP_TOOL],
        ),
    ],
)
@mock.patch("soliplex.mcp_server.mcp_tool")
def test_room_mcp_tools(mcp_tool, tool_configs, exp_mcp_tools, allow_mcp):
    mcp_tool.side_effect = lambda tc: MCP_TOOL if tc.allow_mcp else None
    room_config = mock.create_autospec(config.RoomConfig)
    room_config.allow_mcp = allow_mcp
    room_config.tool_configs = tool_configs

    found = mcp_server.room_mcp_tools(room_config)

    if allow_mcp:
        for f_tool, e_tool in zip(found, exp_mcp_tools, strict=True):
            assert f_tool is e_tool

    else:
        assert len(found) == 0


@pytest.mark.parametrize("w_max_age", [None, "3600"])
@mock.patch("soliplex.mcp_server.room_mcp_tools")
@mock.patch("soliplex.mcp_auth.FastMCPTokenProvider")
@mock.patch("fastmcp.server.FastMCP")
def test_setup_mcp_for_rooms(fmcp_klass, fmtp_klass, rmt, w_max_age):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = room_configs = {
        "room1": mock.create_autospec(config.RoomConfig, allow_mcp=True),
        "room2": mock.create_autospec(config.RoomConfig, allow_mcp=True),
        "room3": mock.create_autospec(config.RoomConfig, allow_mcp=False),
    }
    the_installation = mock.create_autospec(installation.Installation)
    the_installation._config = i_config
    the_installation.get_environment.return_value = w_max_age

    if w_max_age is not None:
        exp_max_age = int(w_max_age)
    else:
        exp_max_age = None

    found = mcp_server.setup_mcp_for_rooms(the_installation)

    assert set(found) == set(room_configs) - set(["room3"])  # keys

    for f_key, f_mcp_http in found.items():
        assert f_mcp_http is fmcp_klass.return_value.http_app.return_value
        assert (
            mock.call(
                f_key, tools=rmt.return_value, auth=fmtp_klass.return_value
            )
            in fmcp_klass.call_args_list
        )
        assert mock.call(room_configs[f_key]) in rmt.call_args_list

        assert (
            mock.call(
                room_id=f_key,
                the_installation=the_installation,
                max_age=exp_max_age,
            )
            in fmtp_klass.call_args_list
        )
