"""
Cross-room communication tools for Soliplex.

Allows an agent in one room to invoke another room's agent via AG-UI,
getting the full event stream (tool calls, thinking, text) back.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pydantic_ai

from soliplex import agents


async def ask_room(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    room_id: str,
    message: str,
) -> str:
    """Send a message to another Soliplex room's agent and get the response.

    Each room has its own agent, tools, and skills. Use this to leverage
    a specialized room's capabilities from your current conversation.

    Examples:
      - ask_room("search", "find documents about authentication")
      - ask_room("analysis", "analyze the trend data in our knowledge base")

    Args:
        room_id: The ID of the target room (e.g. "search", "chat", "analysis").
        message: The message/question to send to that room's agent.
    """
    installation = ctx.deps.the_installation
    base_url = installation.get_environment("SOLIPLEX_INTERNAL_URL")
    if not base_url:
        base_url = "http://localhost:8000/api"

    thread_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    # AG-UI RunAgentInput format
    run_input = {
        "threadId": thread_id,
        "runId": run_id,
        "state": {},
        "messages": [
            {"id": msg_id, "role": "user", "content": message}
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }

    text_parts = []
    tool_calls = []
    error = None

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        try:
            # Create thread in target room
            create_resp = await client.post(
                f"{base_url}/v1/rooms/{room_id}/agui",
                json={},
            )
            if create_resp.status_code != 200:
                return (
                    f"Error: Cannot access room '{room_id}' "
                    f"(HTTP {create_resp.status_code})"
                )

            create_data = create_resp.json()
            thread_id = create_data["thread_id"]
            run_id = list(create_data["runs"].keys())[0]

            # Update run_input with actual IDs
            run_input["threadId"] = thread_id
            run_input["runId"] = run_id

            # Send the AG-UI run
            async with client.stream(
                "POST",
                f"{base_url}/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
                json=run_input,
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    return (
                        f"Error: Room '{room_id}' returned HTTP "
                        f"{response.status_code}: {body.decode()[:200]}"
                    )

                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[6:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                        etype = event.get("type", "")

                        if "TEXT_MESSAGE_CONTENT" in etype:
                            text_parts.append(event.get("delta", ""))

                        elif "TOOL_CALL_START" in etype:
                            tool_calls.append(
                                event.get("toolCallName", "unknown")
                            )

                        elif "TOOL_CALL_RESULT" in etype:
                            tool_calls.append(
                                f"→ {event.get('content', '')[:100]}"
                            )

                        elif "RUN_ERROR" in etype:
                            error = event.get("message", "Unknown error")

                    except json.JSONDecodeError:
                        pass

        except httpx.ConnectError:
            return f"Error: Cannot connect to Soliplex at {base_url}"
        except httpx.TimeoutException:
            partial = "".join(text_parts)
            return (
                f"Error: Room '{room_id}' timed out. "
                f"Partial: {partial[:300]}"
            )

    if error:
        return f"Room '{room_id}' error: {error}"

    result = "".join(text_parts)

    if tool_calls:
        tools_used = [t for t in tool_calls if not t.startswith("→")]
        result += f"\n\n[Room '{room_id}' used tools: {', '.join(tools_used)}]"

    return result or f"Room '{room_id}' returned no response."


async def list_rooms(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
) -> str:
    """List available Soliplex rooms that you can communicate with.

    Each room has its own agent, tools, and specialization.
    Use ask_room to send messages to any of these rooms.
    """
    installation = ctx.deps.the_installation
    base_url = installation.get_environment("SOLIPLEX_INTERNAL_URL")
    if not base_url:
        base_url = "http://localhost:8000/api"

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.get(f"{base_url}/v1/rooms")
            rooms = r.json()

            lines = []
            for room_id, room_data in rooms.items():
                if isinstance(room_data, dict):
                    name = room_data.get("name", room_id)
                    desc = room_data.get("description", "")
                    lines.append(f"- **{room_id}**: {name} — {desc}")
                else:
                    lines.append(f"- **{room_id}**")

            return "\n".join(lines) if lines else "No rooms found."

        except Exception as e:
            return f"Error listing rooms: {e}"
