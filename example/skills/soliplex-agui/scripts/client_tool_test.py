#!/usr/bin/env python3
"""
Test client-side tool injection via AG-UI.

Sends a RunAgentInput with a client-side 'confirm_action' tool.
The agent should call it, triggering an interrupt.

Usage:
  python client_tool_test.py
  python client_tool_test.py hermes "Delete all temp files"
"""

import asyncio
import json
import os
import sys
import uuid

try:
    import httpx
except ImportError:
    print("Requires: pip install httpx")
    sys.exit(1)

BASE = os.environ.get("SOLIPLEX_URL", "http://localhost:8000/api")


async def main(room_id: str = "hermes", message: str = "Delete all temporary files. Confirm with the user first."):
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Create thread
        r = await client.post(f"{BASE}/v1/rooms/{room_id}/agui", json={})
        data = r.json()
        tid = data["thread_id"]
        rid = list(data["runs"].keys())[0]

        # RunAgentInput with client-side tool
        body = {
            "threadId": tid,
            "runId": rid,
            "state": {},
            "messages": [
                {"id": str(uuid.uuid4()), "role": "user", "content": message}
            ],
            "tools": [
                {
                    "name": "confirm_action",
                    "description": "Ask the user to confirm a dangerous action before proceeding. MUST be called before any destructive operation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "description": "Description of the action to confirm",
                            },
                            "severity": {
                                "type": "string",
                                "enum": ["low", "medium", "high"],
                            },
                        },
                        "required": ["action"],
                    },
                }
            ],
            "context": [],
            "forwardedProps": {},
        }

        print(f"Room: {room_id}")
        print(f"Message: {message}")
        print(f"Client tools: [confirm_action]")
        print("-" * 50)

        async with client.stream(
            "POST",
            f"{BASE}/v1/rooms/{room_id}/agui/{tid}/{rid}",
            json=body,
        ) as response:
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                d = line[6:].strip()
                if d == "[DONE]":
                    break
                try:
                    event = json.loads(d)
                    etype = event.get("type", "")
                    if "TEXT_MESSAGE_CONTENT" in etype:
                        print(event.get("delta", ""), end="", flush=True)
                    elif "TOOL_CALL_START" in etype:
                        name = event.get("toolCallName", "?")
                        print(f"\n  [TOOL_CALL: {name}]", flush=True)
                    elif "TOOL_CALL_ARGS" in etype:
                        print(f"  [ARGS: {event.get('delta', '')}]", flush=True)
                    elif "TOOL_CALL_RESULT" in etype:
                        content = event.get("content", "")[:100]
                        print(f"  [RESULT: {content}]", flush=True)
                    elif "STATE_SNAPSHOT" in etype:
                        snapshot = event.get("snapshot", {})
                        print(f"\n  [STATE: {json.dumps(snapshot)[:100]}]", flush=True)
                    elif "RUN_FINISHED" in etype:
                        print("\n  [RUN_FINISHED]", flush=True)
                    elif "RUN_ERROR" in etype:
                        print(f"\n  [ERROR: {event.get('message', '?')}]", flush=True)
                except json.JSONDecodeError:
                    pass

        print("-" * 50)
        print(
            "\nIf confirm_action was called, the client would now show a"
            "\nconfirmation dialog. On 'Yes', send a new run with the tool"
            "\nresult in messages. On 'No', send declined result."
        )


if __name__ == "__main__":
    room = sys.argv[1] if len(sys.argv) > 1 else "hermes"
    msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Delete all temporary files. You MUST confirm with the user first."
    asyncio.run(main(room, msg))
