#!/usr/bin/env python3
"""List all available Soliplex rooms."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from soliplex_client import SoliplexClient

client = SoliplexClient()
rooms = client.list_rooms()

for room_id, data in rooms.items():
    if isinstance(data, dict):
        name = data.get("name", room_id)
        desc = data.get("description", "")
        kind = data.get("agent", {}).get("kind", "default")
        tools = list(data.get("tools", {}).keys())
        print(f"{room_id} [{kind}]: {name}")
        if desc:
            print(f"  {desc}")
        if tools:
            print(f"  tools: {', '.join(tools[:5])}")
        print()
