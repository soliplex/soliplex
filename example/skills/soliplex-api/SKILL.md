---
name: soliplex-api
description: Soliplex REST API reference — room endpoints, completions, threads, MCP tokens, and health checks with curl and Python examples
---

# Soliplex API Reference

Use this skill when you need to interact with the Soliplex REST API
programmatically — via curl, Python httpx/requests, or any HTTP client.

## Base URL

The Soliplex API is available at `http://localhost:8000/api` (default).
All endpoints are prefixed with `/api`.

## Authentication

In no-auth mode, no credentials are needed.
With OIDC enabled, pass a Bearer token: `Authorization: Bearer <jwt>`.

## Rooms

### List rooms
```bash
curl http://localhost:8000/api/v1/rooms
```

### Get room details
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}
```

### Get room background image
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}/bg_image
```

### Get room documents (RAG)
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}/documents
```

### Get MCP token for room
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}/mcp_token
```

## AG-UI Threads

### List threads in a room
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}/agui
```

### Create a new thread
```bash
curl -X POST http://localhost:8000/api/v1/rooms/{room_id}/agui \
  -H "Content-Type: application/json" \
  -d '{}'
```
Returns: `{thread_id, runs: {run_id: {...}}}`

### Get thread details
```bash
curl http://localhost:8000/api/v1/rooms/{room_id}/agui/{thread_id}
```

### Delete a thread
```bash
curl -X DELETE http://localhost:8000/api/v1/rooms/{room_id}/agui/{thread_id}
```

### Execute an AG-UI run
```bash
curl -N http://localhost:8000/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id} \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "...",
    "runId": "...",
    "state": {},
    "messages": [{"id": "msg-1", "role": "user", "content": "Hello"}],
    "tools": [],
    "context": [],
    "forwardedProps": {}
  }'
```
Returns: SSE stream of AG-UI events.

### Python example — create thread and run
```python
import httpx, json, uuid

BASE = "http://localhost:8000/api"
ROOM = "hermes-hybrid"

async def run_conversation(message):
    async with httpx.AsyncClient(timeout=120.0) as c:
        # Create thread
        r = await c.post(f"{BASE}/v1/rooms/{ROOM}/agui", json={})
        d = r.json()
        tid = d["thread_id"]
        rid = list(d["runs"].keys())[0]

        # Run
        body = {
            "threadId": tid, "runId": rid,
            "state": {},
            "messages": [{"id": str(uuid.uuid4()), "role": "user", "content": message}],
            "tools": [], "context": [], "forwardedProps": {},
        }

        text = ""
        async with c.stream("POST", f"{BASE}/v1/rooms/{ROOM}/agui/{tid}/{rid}", json=body) as r:
            async for line in r.aiter_lines():
                if line.startswith("data:"):
                    data = line[6:].strip()
                    if data == "[DONE]": break
                    e = json.loads(data)
                    if "delta" in e and "CONTENT" in e.get("type", ""):
                        text += e["delta"]
        return text
```

## Completions (OpenAI-compatible)

### List completions
```bash
curl http://localhost:8000/api/v1/chat/completions
```

### Execute completion
```bash
curl -N http://localhost:8000/api/v1/chat/completions/{completion_id} \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss:latest",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

## Health

```bash
curl http://localhost:8000/api/ok
```

## Hermes Event Server (if configured)

```bash
# Health
curl http://localhost:8642/health

# Available tools
curl http://localhost:8642/v1/agent/tools

# Available skills
curl http://localhost:8642/v1/agent/skills

# Agent memory
curl http://localhost:8642/v1/agent/memory

# Run agent
curl -N http://localhost:8642/v1/agent/run \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "config": {"max_iterations": 5}}'

# Call single tool
curl http://localhost:8642/v1/agent/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "terminal", "args": {"command": "date"}}'
```

## Python Client: TUI_REST_API

Soliplex includes a ready-made Python REST client at `soliplex.tui.rest_api.TUI_REST_API`.
Use it instead of raw httpx/requests:

```python
from soliplex.tui.rest_api import TUI_REST_API

api = TUI_REST_API(soliplex_url="http://localhost:8000")

# List rooms
rooms = api.get_rooms()

# Get room details
room = api.get_room("hermes-hybrid")

# Get room documents (RAG)
docs = api.get_room_documents("search")

# Get MCP token for a room
token = api.get_room_mcp_token("search")

# Thread lifecycle
thread = api.post_new_thread("hermes-hybrid", {})
thread_id = thread["thread_id"]
run_id = list(thread["runs"].keys())[0]

# Get thread details
details = api.get_thread("hermes-hybrid", thread_id)

# Start a run (returns streaming response)
from ag_ui.core import RunAgentInput, UserMessage
run_input = RunAgentInput(
    thread_id=thread_id,
    run_id=run_id,
    state={},
    messages=[UserMessage(id="m1", role="user", content="Hello")],
    tools=[], context=[], forwarded_props={},
)
response = api.post_start_run("hermes-hybrid", thread_id, run_id, run_input)
for line in response.iter_lines():
    print(line)

# File uploads
api.post_room_file_upload("hermes-hybrid", Path("data.csv"))
api.post_thread_file_upload("hermes-hybrid", thread_id, Path("notes.txt"))

# Thread metadata
api.post_thread_metadata("hermes-hybrid", thread_id, {"name": "Research session"})

# Run feedback
api.post_run_feedback("hermes-hybrid", thread_id, run_id, {"rating": "good"})
```

Available methods:
- `get_rooms()`, `get_room(id)`, `get_room_documents(id)`, `get_room_mcp_token(id)`
- `get_installation()`, `get_installed_versions()`, `get_provider_models()`
- `post_new_thread(room, request)`, `get_thread(room, tid)`, `get_room_threads(room)`
- `post_new_run(room, tid, request)`, `get_run(room, tid, rid)`
- `post_start_run(room, tid, rid, input)` — returns streaming response
- `post_room_file_upload(room, path)`, `post_thread_file_upload(room, tid, path)`
- `post_thread_metadata(room, tid, meta)`, `post_run_metadata(room, tid, rid, meta)`
- `post_run_feedback(room, tid, rid, feedback)`
