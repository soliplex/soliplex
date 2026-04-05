"""
Lightweight Soliplex REST client for Hermes skills.

Standalone — only needs `requests` (included in Hermes container).
Mirrors the subset of soliplex.tui.rest_api.TUI_REST_API needed
for cross-room communication.

Usage:
    from soliplex_client import SoliplexClient
    client = SoliplexClient()
    rooms = client.list_rooms()
    result = client.ask_room("plain", "What time is it?")
"""

import json
import os
import uuid

import requests

SOLIPLEX_URL = os.environ.get(
    "SOLIPLEX_URL", "http://host.docker.internal:8000/api"
)


class SoliplexClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or SOLIPLEX_URL

    def list_rooms(self) -> dict:
        """List all rooms with names, descriptions, tools."""
        r = requests.get(f"{self.base_url}/v1/rooms", timeout=10)
        r.raise_for_status()
        return r.json()

    def get_room(self, room_id: str) -> dict:
        """Get details for a specific room."""
        r = requests.get(
            f"{self.base_url}/v1/rooms/{room_id}", timeout=10
        )
        r.raise_for_status()
        return r.json()

    def create_thread(self, room_id: str) -> tuple[str, str]:
        """Create a new thread. Returns (thread_id, run_id)."""
        r = requests.post(
            f"{self.base_url}/v1/rooms/{room_id}/agui",
            json={},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        tid = data["thread_id"]
        rid = list(data["runs"].keys())[0]
        return tid, rid

    def run_agui(
        self,
        room_id: str,
        thread_id: str,
        run_id: str,
        message: str,
        state: dict = None,
    ) -> str:
        """Execute an AG-UI run and collect the text response."""
        body = {
            "threadId": thread_id,
            "runId": run_id,
            "state": state or {},
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

        r = requests.post(
            f"{self.base_url}/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
            json=body,
            stream=True,
            timeout=120,
        )
        r.raise_for_status()

        text_parts = []
        tool_calls = []
        for raw_line in r.iter_lines():
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data:"):
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
            except json.JSONDecodeError:
                pass

        result = "".join(text_parts)
        if tool_calls:
            result += f"\n[Used: {', '.join(tool_calls)}]"
        return result

    def ask_room(self, room_id: str, message: str) -> str:
        """Create thread + run in one call. Returns text response."""
        tid, rid = self.create_thread(room_id)
        return self.run_agui(room_id, tid, rid, message)
