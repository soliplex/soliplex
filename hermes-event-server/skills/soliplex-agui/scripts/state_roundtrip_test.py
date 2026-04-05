#!/usr/bin/env python3
"""
Test AG-UI state round-trip across multiple runs.

Run 1: Empty state → agent responds → STATE_SNAPSHOT emitted
Run 2: Pass state from Run 1 back → verify agent has context

Usage:
  python state_roundtrip_test.py
  python state_roundtrip_test.py hermes
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


async def run_with_state(
    client: httpx.AsyncClient,
    room_id: str,
    tid: str,
    rid: str,
    message: str,
    state: dict,
) -> tuple[str, dict]:
    """Execute one run and return (text, state_snapshot)."""
    body = {
        "threadId": tid,
        "runId": rid,
        "state": state,
        "messages": [
            {"id": str(uuid.uuid4()), "role": "user", "content": message}
        ],
        "tools": [],
        "context": [],
        "forwardedProps": {},
    }

    text_parts = []
    new_state = {}

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
                    text_parts.append(event.get("delta", ""))
                elif "STATE_SNAPSHOT" in etype:
                    new_state = event.get("snapshot", {})
            except json.JSONDecodeError:
                pass

    return "".join(text_parts), new_state


async def main(room_id: str = "hermes"):
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Create thread
        r = await client.post(
            f"{BASE}/v1/rooms/{room_id}/agui", json={}
        )
        data = r.json()
        tid = data["thread_id"]
        rid1 = list(data["runs"].keys())[0]

        print(f"Room: {room_id}")
        print(f"Thread: {tid}")
        print("=" * 50)

        # Run 1: empty state
        print("\n--- Run 1: Empty state ---")
        print("State in: {}")
        text1, state1 = await run_with_state(
            client, room_id, tid, rid1,
            "My name is Alice and I like cats.",
            {},
        )
        print(f"Response: {text1[:100]}")
        print(f"State out: {json.dumps(state1)[:200]}")

        # Create new run for same thread
        r2 = await client.post(
            f"{BASE}/v1/rooms/{room_id}/agui/{tid}",
            json={},
        )
        rid2 = r2.json().get("run_id") or list(r2.json().get("runs", {}).keys())[0] if r2.status_code == 200 else str(uuid.uuid4())

        # Run 2: pass state back
        print("\n--- Run 2: State from Run 1 ---")
        print(f"State in: {json.dumps(state1)[:200]}")
        text2, state2 = await run_with_state(
            client, room_id, tid, rid2,
            "What is my name?",
            state1,
        )
        print(f"Response: {text2[:100]}")
        print(f"State out: {json.dumps(state2)[:200]}")

        # Verify
        print("\n" + "=" * 50)
        has_session = bool(state1.get("hermes_session_id"))
        has_run_count = state2.get("run_count", 0) >= 2
        knows_name = "alice" in text2.lower()

        print(f"Session ID persisted: {'YES' if has_session else 'NO'}")
        print(f"Run count incremented: {'YES' if has_run_count else 'NO'}")
        print(f"Remembers name: {'YES' if knows_name else 'NO'}")

        if has_session and knows_name:
            print("\nPASS: State round-trip works")
        else:
            print("\nFAIL: State or context not preserved")


if __name__ == "__main__":
    room = sys.argv[1] if len(sys.argv) > 1 else "hermes"
    asyncio.run(main(room))
