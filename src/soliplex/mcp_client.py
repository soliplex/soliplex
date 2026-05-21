import typing

from fastmcp.client import transports as fastmcp_transports
from pydantic_ai import mcp as ai_mcp
from pydantic_ai import toolsets as ai_toolsets


def _allowed_tools_filter(
    allowed_tools: typing.Sequence[str] | None,
) -> typing.Callable | None:
    """Filter predicate for ``AbstractToolset.filtered``, or ``None``.

    A ``None`` or empty allow-list means "expose every tool the server
    offers."
    """
    if not allowed_tools:
        return None

    allowed = set(allowed_tools)

    def _filter(ctx, tool_def):
        return tool_def.name in allowed

    return _filter


def _apply_allow_list(
    toolset: ai_toolsets.AbstractToolset,
    allowed_tools: typing.Sequence[str] | None,
) -> ai_toolsets.AbstractToolset:
    filter_func = _allowed_tools_filter(allowed_tools)
    if filter_func is None:
        return toolset
    return toolset.filtered(filter_func)


def stdio_toolset(
    *,
    command: str,
    args: list[str],
    env: dict[str, str],
    allowed_tools: list[str] = None,
) -> ai_toolsets.AbstractToolset:  # pragma: NO COVER
    transport = fastmcp_transports.StdioTransport(
        command=command,
        args=args,
        env=env,
    )
    return _apply_allow_list(ai_mcp.MCPToolset(transport), allowed_tools)


def http_toolset(
    *,
    url: str,
    headers: dict[str, str],
    allowed_tools: list[str] = None,
) -> ai_toolsets.AbstractToolset:  # pragma: NO COVER
    transport = fastmcp_transports.StreamableHttpTransport(
        url=url,
        headers=headers,
    )
    return _apply_allow_list(ai_mcp.MCPToolset(transport), allowed_tools)


def sse_toolset(
    *,
    url: str,
    headers: dict[str, str],
    allowed_tools: list[str] = None,
) -> ai_toolsets.AbstractToolset:  # pragma: NO COVER
    transport = fastmcp_transports.SSETransport(
        url=url,
        headers=headers,
    )
    return _apply_allow_list(ai_mcp.MCPToolset(transport), allowed_tools)


TOOLSET_FACTORY_BY_KIND = {
    "stdio": stdio_toolset,
    "http": http_toolset,
    "sse": sse_toolset,
}
