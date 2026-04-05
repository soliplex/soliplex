---
name: soliplex-rooms
description: Discover and communicate with Soliplex rooms — list rooms, send messages to other room agents, query room capabilities
version: 1.0.0
author: Soliplex
metadata:
  hermes:
    tags: [Soliplex, Rooms, Cross-Room, AG-UI]
    requires_toolsets: [soliplex]
---

# Soliplex Rooms

You are running inside the Soliplex platform. You have access to tools that let you
discover and communicate with other Soliplex rooms.

## Tools

You have two registered tools for Soliplex integration:

- **soliplex_list_rooms** — list all rooms with names, descriptions, tools
- **soliplex_ask_room** — send a message to another room's agent

## Scripts

This skill also includes Python scripts you can run via terminal:

### List rooms
```bash
python3 /opt/data/skills/soliplex/soliplex-rooms/scripts/list_rooms.py
```

### Ask another room
```bash
python3 /opt/data/skills/soliplex/soliplex-rooms/scripts/ask_room.py plain "What time is it?"
python3 /opt/data/skills/soliplex/soliplex-rooms/scripts/ask_room.py search "Find docs about auth"
```

### Use the client in custom code
```python
import sys; sys.path.insert(0, "/opt/data/skills/soliplex/soliplex-rooms/scripts")
from soliplex_client import SoliplexClient

client = SoliplexClient()
rooms = client.list_rooms()
result = client.ask_room("plain", "What time is it?")
```

## Examples

### List available rooms
```
Use tool: soliplex_list_rooms
OR run: python3 /opt/data/skills/soliplex/soliplex-rooms/scripts/list_rooms.py
```

### Ask another room a question
```
Use tool: soliplex_ask_room(room_id="plain", message="What time is it?")
OR run: python3 /opt/data/skills/soliplex/soliplex-rooms/scripts/ask_room.py plain "What time is it?"
```

### Cross-room research
```
1. soliplex_list_rooms → find the right room
2. soliplex_ask_room(room_id="search", message="find documents about authentication")
3. Use the results in your response
```

## Room Types

- **default** rooms: Standard pydantic-ai agents with Soliplex tools
- **hermes** rooms: Hermes agent rooms with tools, skills, and memory
- **hermes-hybrid** rooms: Both pydantic-ai and Hermes tools available
