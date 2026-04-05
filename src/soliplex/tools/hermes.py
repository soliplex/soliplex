"""
Hermes Agent tools for Soliplex rooms.

Two patterns:
  - run_hermes_task: Sub-agent delegation — Hermes runs its full agent
    loop (web search, terminal, code execution, etc.) and returns the result.
    Use for complex multi-step tasks.

  - hermes_tool: Direct tool dispatch — calls a single Hermes tool
    without the agent loop. Use for targeted lookups.
"""

from __future__ import annotations

import json
import typing

import httpx
import pydantic_ai

from soliplex import agents


HERMES_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def _get_hermes_url(ctx: pydantic_ai.RunContext[agents.AgentDependencies]) -> str:
    """Resolve Hermes Event Server URL from installation config."""
    installation = ctx.deps.the_installation
    url = installation.get_environment("HERMES_URL")
    if url:
        return url
    return "http://localhost:8642"


# -----------------------------------------------------------------------
# Sub-agent mode: full Hermes agent loop
# -----------------------------------------------------------------------

async def run_hermes_task(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    task: str,
    max_iterations: int = 10,
) -> str:
    """Delegate a complex task to the Hermes agent.

    Hermes has access to web search, terminal, code execution,
    file operations, 74 skills, and persistent memory. Use this
    for multi-step research, analysis, or tasks requiring tools
    you don't have.

    Args:
        task: Clear description of what to accomplish.
        max_iterations: Max tool-calling iterations (default 10).
    """
    hermes_url = _get_hermes_url(ctx)

    result_text = ""
    tool_calls = []

    async with httpx.AsyncClient(timeout=HERMES_TIMEOUT) as client:
        try:
            async with client.stream(
                "POST",
                f"{hermes_url}/v1/agent/run",
                json={
                    "message": task,
                    "config": {"max_iterations": max_iterations},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    etype = event.get("type")

                    if etype == "text_delta":
                        result_text += event.get("delta", "")
                    elif etype == "tool_start":
                        tool_calls.append(event.get("name", ""))
                    elif etype == "run_error":
                        return f"Hermes error: {event.get('message', 'unknown')}"

        except httpx.ConnectError:
            return "Error: Cannot reach Hermes agent. Is the event server running?"
        except httpx.TimeoutException:
            return f"Error: Hermes task timed out. Partial result: {result_text[:500]}"

    if tool_calls:
        result_text += f"\n\n[Hermes used: {', '.join(tool_calls)}]"

    return result_text or "Hermes returned no result."


# -----------------------------------------------------------------------
# Direct mode: single tool dispatch
# -----------------------------------------------------------------------

async def hermes_tool(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    tool_name: str,
    arguments: dict[str, typing.Any],
) -> str:
    """Call a single Hermes tool directly.

    Available tools include: web_search, web_extract, terminal,
    read_file, write_file, search_files, execute_code, and more.

    Use run_hermes_task instead for complex multi-step tasks.

    Args:
        tool_name: Name of the Hermes tool (e.g. "web_search", "terminal").
        arguments: Tool arguments as a dict.
    """
    hermes_url = _get_hermes_url(ctx)

    async with httpx.AsyncClient(timeout=HERMES_TIMEOUT) as client:
        try:
            r = await client.post(
                f"{hermes_url}/v1/agent/tool",
                json={"tool": tool_name, "args": arguments},
            )
            r.raise_for_status()
            data = r.json()

            if "error" in data:
                return f"Error: {data['error']}"

            return data.get("result", "No result")

        except httpx.ConnectError:
            return "Error: Cannot reach Hermes agent."
        except httpx.TimeoutException:
            return "Error: Hermes tool call timed out."


async def list_hermes_tools(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> str:
    """List available Hermes tools and their status.

    Call this to discover what tools Hermes has before using hermes_tool.
    """
    hermes_url = _get_hermes_url(ctx)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{hermes_url}/v1/agent/tools")
            data = r.json()
            summary = data.get("summary", {})
            available = summary.get("available_toolsets", [])
            return (
                f"Available toolsets: {', '.join(available)}\n"
                f"Total: {summary.get('available_tools', 0)} tools"
            )
        except Exception as e:
            return f"Error listing tools: {e}"
