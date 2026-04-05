#!/bin/bash
# List all Soliplex rooms with their names and descriptions
BASE="${SOLIPLEX_URL:-http://localhost:8000/api}"

curl -s "$BASE/v1/rooms" | python3 -c "
import sys, json
rooms = json.load(sys.stdin)
for room_id, room in rooms.items():
    if isinstance(room, dict):
        name = room.get('name', room_id)
        desc = room.get('description', '')
        agent_kind = room.get('agent', {}).get('kind', 'default')
        tools = list(room.get('tools', {}).keys())
        print(f'{room_id:20s} [{agent_kind:8s}] {name}')
        if desc:
            print(f'{\"\":20s}  {desc}')
        if tools:
            print(f'{\"\":20s}  tools: {\", \".join(tools[:5])}')
        print()
"
