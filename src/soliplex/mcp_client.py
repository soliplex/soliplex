import typing

from mcp import types as mcp_types
from pydantic_ai import mcp as ai_mcp


def _filter_tools(offered_tools, allowed_tools):

    if allowed_tools:
        tools = [
            tool for tool in offered_tools if tool.name in allowed_tools
        ]

    else:
        tools = offered_tools

    return tools


class Stdio_MCP_Client_Toolset(ai_mcp.MCPServerStdio):

    def __init__(
        self,
        command: str,
        args: list[str],
        env: dict[str, str],
        allowed_tools: list[str]=None,
    ):  # pragma: NO COVER
        super().__init__(command=command, args=args, env=env)
        self._allowed_tools = allowed_tools or ()

    @property
    def _params(self):
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def allowed_tools(self) -> list[str] | None:  # pragma: NO COVER
        return list(self._allowed_tools)

    async def list_tools(self) -> list[mcp_types.Tool]:  # pragma: NO COVER
        """Retrieve tools that are currently active on the server.

        Filter the tools offered by the server using our list of allowed
        tools.

        Note:
        - We don't cache tools as they might change.
        - We also don't subscribe to the server to avoid complexity.
        """
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)


class HTTP_MCP_Client_Toolset(ai_mcp.MCPServerStreamableHTTP):

    def __init__(
        self,
        url: str,
        headers: dict[str, typing.Any],
        allowed_tools: list[str] = None,
    ):  # pragma: NO COVER
        super().__init__(url=url, headers=headers)
        self._allowed_tools = allowed_tools or ()

    @property
    def _params(self):
        return {
            "url": self.url,
            "headers": self.headers,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def allowed_tools(self) -> list[str] | None:  # pragma: NO COVER
        return list(self._allowed_tools)

    async def list_tools(self) -> list[mcp_types.Tool]:  # pragma: NO COVER
        """Retrieve tools that are currently active on the server.

        Filter the tools offered by the server using our list of allowed
        tools.

        Note:
        - We don't cache tools as they might change.
        - We also don't subscribe to the server to avoid complexity.
        """
        offered_tools = await super().list_tools()
        return _filter_tools(offered_tools, self.allowed_tools)


TOOLSET_CLASS_BY_KIND = {
    "stdio": Stdio_MCP_Client_Toolset,
    "http": HTTP_MCP_Client_Toolset,
}
