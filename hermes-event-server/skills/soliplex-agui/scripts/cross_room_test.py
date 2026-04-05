#!/usr/bin/env python3
"""
Test cross-room communication: hybrid room asks another room a question.

Usage:
  python cross_room_test.py
  python cross_room_test.py "search" "find documents about auth"
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
SOURCE_ROOM = "hermes-hybrid"


async def main(target_room: str = "plain", question: str = "What time is it?"):
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Create thread in source room
        r = await client.post(
            f"{BASE}/v1/rooms/{SOURCE_ROOM}/agui", json={}
        )
        data = r.json()
        tid = data["thread_id"]
        rid = list(data["runs"].keys())[0]

        # Ask the source room to call the target room
        message = (
            f'Use the ask_room tool to send this message to the '
            f'"{target_room}" room: "{question}"'
        )

        body = {
            "threadId": tid,
            "runId": rid,
            "state": {},
            "messages": [
                {"id": str(uuid.uuid4()), "role": "user", "content": message}
            ],
            "tools": [],
            "context": [],
            "forwardedProps": {},
        }

        print(f"Hybrid room → {target_room}: {question}")
        print("-" * 50)

        async with client.stream(
            "POST",
            f"{BASE}/v1/rooms/{SOURCE_ROOM}/agui/{tid}/{rid}",
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
                        print(
                            f"\n  [TOOL: {event.get('toolCallName', '?')}]",
                            flush=True,
                        )
                    elif "TOOL_CALL_RESULT" in etype:
                        print(
                            f"\n  [RESULT: {event.get('content', '')[:150]}]",
                            flush=True,
                        )
                except json.JSONDecodeError:
                    pass

        print("\n" + "-" * 50)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "plain"
    question = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "What time is it?"
    asyncio.run(main(target, question))
