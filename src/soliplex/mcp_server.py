from __future__ import annotations

import inspect

from fastmcp import server as fmcp_server
from fastmcp import tools as fmcp_tools

from soliplex import mcp_auth
from soliplex.config import rooms as config_rooms
from soliplex.config import tools as config_tools


def mcp_tool(tool_config: config_tools.ToolConfig) -> fmcp_tools.Tool | None:
    if (
        tool_config.allow_mcp
        and tool_config.tool_requires
        != config_tools.ToolRequires.FASTAPI_CONTEXT
    ):
        wrapper_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        wrapper_type = wrapper_registry.get(
            tool_config.tool_name,
        )

        if wrapper_type is not None:
            tool_wrapper = wrapper_type(
                func=tool_config.tool,
                tool_config=tool_config,
            )
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


def room_mcp_tools(
    room_config: config_rooms.RoomConfig,
) -> list[fmcp_tools.Tool]:
    """Return room tools which do not require the FastAPI context"""

    if room_config.allow_mcp:
        tool_configs = room_config.tool_configs
        tools = [
            mcpt
            for mcpt in [
                mcp_tool(tool_config) for tool_config in tool_configs.values()
            ]
            if mcpt is not None
        ]
    else:
        tools = ()

    return tools


def setup_mcp_for_rooms(
    available_rooms: list[config_rooms.RoomConfig],
    auth_disabled: bool,
    url_safe_token_secret: str,
    max_token_age_secs: int | str,
):
    """Setup MCP servers for all available rooms.

    Args:
        available_rooms:
            list of room configs in the installation

        auth_disabled:
            whether the installation is running in '--no-auth-mode'

        url_safe_token_secret:
            the 'URL_SAFE_TOKEN_SECRET' installation secret

        max_token_age_secs:
            installation's environment value for 'MCP_TOKEN_MAX_AGE',
            already converted (if needed) to an integer.

    Returns:
        mcp_apps dict
    """
    mcp_apps = {}

    for key, room_config in available_rooms.items():
        if room_config.allow_mcp:
            mcp = fmcp_server.FastMCP(
                key,
                tools=room_mcp_tools(room_config),
                auth=mcp_auth.FastMCPTokenProvider(
                    room_id=key,
                    # the_installation=the_installation,
                    auth_disabled=auth_disabled,
                    secret_key=url_safe_token_secret,
                    max_age=max_token_age_secs,
                ),
            )

            mcp_app = mcp.http_app(path="/")
            mcp_apps[key] = mcp_app

    return mcp_apps
