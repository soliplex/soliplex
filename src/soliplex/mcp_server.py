from __future__ import annotations

import dataclasses
import inspect
import typing
from collections import abc

from fastmcp import server as fmcp_server
from fastmcp import tools as fmcp_tools

from soliplex import config
from soliplex import installation
from soliplex import mcp_auth


@dataclasses.dataclass
class NoArgsMCPWrapper:
    _func: abc.Callable[..., typing.Any]
    _tool_config: config.ToolConfig

    def __call__(self):
        return self._func(tool_config=self._tool_config)


@dataclasses.dataclass
class WithQueryMCPWrapper:
    _func: abc.Callable[..., typing.Any]
    _tool_config: config.ToolConfig

    def __call__(self, query):
        return self._func(query, tool_config=self._tool_config)


TOOL_CONFIG_WRAPPERS_BY_KIND = {
    config.SearchDocumentsToolConfig.kind: WithQueryMCPWrapper,
}


def mcp_tool(tool_config: config.ToolConfig) -> fmcp_tools.Tool | None:
    if (
        tool_config.allow_mcp and
        tool_config.tool_requires != config.ToolRequires.FASTAPI_CONTEXT
    ):
        wrapper_type = TOOL_CONFIG_WRAPPERS_BY_KIND.get(tool_config.kind)

        if wrapper_type is not None:
            tool_wrapper = wrapper_type(tool_config.tool, tool_config)
            tool_doc = inspect.getdoc(tool_config.tool)

            return fmcp_tools.Tool.from_function(
                tool_wrapper,
                name=tool_config.tool_id,
                description=tool_doc,
            )
        else:
            return fmcp_tools.Tool.from_function(
                tool_config.tool,
                name=tool_config.tool_id,
            )


def room_mcp_tools(room_config: config.RoomConfig) -> list[fmcp_tools.Tool]:
    """Return room tools which do not require the FastAPI context"""

    if room_config.allow_mcp:
        tool_configs = room_config.tool_configs
        tools = [
            mcpt for mcpt in [
                mcp_tool(tool_config)
                for tool_config in tool_configs.values()
            ]
            if mcpt is not None
        ]
    else:
        tools = ()

    return tools


def setup_mcp_for_rooms(the_installation: installation.Installation):
    """Setup MCP servers for all available rooms.

    Args:
        fastapi_context: dict created via the fastapi app's lifespan:
                         key 'the_rooms' holds the installation's
                         RoomConfigs instance with loaded room configurations

    Returns:
        mcp_apps dict
    """
    mcp_apps = {}

    # Deliberately bypass autz check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs
    max_age = the_installation.get_environment("MCP_TOKEN_MAX_AGE")

    for key, room_config in available_rooms.items():
        if room_config.allow_mcp:

            mcp = fmcp_server.FastMCP(
                key,
                tools=room_mcp_tools(room_config),
                auth=mcp_auth.FastMCPTokenProvider(
                    room_id=key,
                    the_installation=the_installation,
                    max_age=max_age,
                ),
            )

            mcp_app = mcp.http_app(path="/")
            mcp_apps[key] = mcp_app

    return mcp_apps
