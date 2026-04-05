#!/usr/bin/env python3
"""
Create a thread in a room and execute a run.

Usage:
  python create_thread_and_run.py <room_id> <message>
  python create_thread_and_run.py hermes-hybrid "What time is it?"
  python create_thread_and_run.py plain "Say hello"
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


async def main(room_id: str, message: str):
    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Create thread
        print(f"Creating thread in room '{room_id}'...")
        r = await client.post(f"{BASE}/v1/rooms/{room_id}/agui", json={})
        if r.status_code != 200:
            print(f"Error creating thread: HTTP {r.status_code}")
            print(r.text)
            return

        data = r.json()
        thread_id = data["thread_id"]
        run_id = list(data["runs"].keys())[0]
        print(f"  thread: {thread_id}")
        print(f"  run:    {run_id}")

        # 2. Build RunAgentInput
        body = {
            "threadId": thread_id,
            "runId": run_id,
            "state": {},
            "messages": [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                }
            ],
            "tools": [],
            "context": [],
            "forwardedProps": {},
        }

        # 3. Execute run and stream events
        print(f"\nSending: {message}")
        print("-" * 50)

        async with client.stream(
            "POST",
            f"{BASE}/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
            json=body,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                print(f"Error: HTTP {response.status_code}: {body.decode()}")
                return

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
                        print(event.get("delta", ""), end="", flush=True)
                    elif "TOOL_CALL_START" in etype:
                        print(
                            f"\n  [TOOL: {event.get('toolCallName', '?')}]",
                            flush=True,
                        )
                    elif "TOOL_CALL_RESULT" in etype:
                        content = event.get("content", "")[:100]
                        print(f"  [RESULT: {content}]", flush=True)
                    elif "TOOL_CALL_ARGS" in etype:
                        print(
                            f"  [ARGS: {event.get('delta', '')[:80]}]",
                            flush=True,
                        )
                    elif "RUN_ERROR" in etype:
                        print(
                            f"\n  [ERROR: {event.get('message', '?')}]",
                            flush=True,
                        )
                except json.JSONDecodeError:
                    pass

        print("\n" + "-" * 50)
        print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    asyncio.run(main(sys.argv[1], " ".join(sys.argv[2:])))
