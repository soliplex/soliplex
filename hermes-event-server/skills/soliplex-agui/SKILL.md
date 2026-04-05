---
name: soliplex-agui
description: AG-UI protocol reference — thread lifecycle, run execution, event types, state management, and cross-room communication patterns
---

# AG-UI Protocol in Soliplex

Use this skill when you need to understand how conversations work in
Soliplex, how to create threads and runs programmatically, or how to
work with the AG-UI event stream.

## Thread Lifecycle

```
1. Create thread     POST /api/v1/rooms/{room}/agui
   → {thread_id, runs: {run_id: ...}}

2. Execute run       POST /api/v1/rooms/{room}/agui/{thread_id}/{run_id}
   → SSE stream of events

3. (optional) Create new run for same thread
   POST /api/v1/rooms/{room}/agui/{thread_id}
   → {run_id: ...}

4. Execute new run   POST /api/v1/rooms/{room}/agui/{thread_id}/{new_run_id}
   → SSE stream with conversation history
```

Each thread can have multiple runs. Each run is one user message + agent response.

## RunAgentInput (request body for a run)

```json
{
  "threadId": "uuid",
  "runId": "uuid",
  "state": {},
  "messages": [
    {"id": "uuid", "role": "user", "content": "Hello"}
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

Fields:
- **threadId/runId**: Must match the URL path
- **state**: AG-UI state from the prior run's STATE_SNAPSHOT (round-trips)
- **messages**: Full conversation history — all prior user + assistant messages
- **tools**: Client-side tools (Flutter registers these for callbacks)
- **context**: Additional context objects
- **forwardedProps**: Passed through to the agent

## AG-UI Event Types

The SSE stream returns events in this format:
```
data: {"type":"EVENT_TYPE","field":"value",...}
```

### Run lifecycle
| Event | When | Key fields |
|-------|------|------------|
| RUN_STARTED | First event | threadId, runId |
| RUN_FINISHED | Last event (success) | threadId, runId |
| RUN_ERROR | Last event (failure) | message |

### Text messages
| Event | When | Key fields |
|-------|------|------------|
| TEXT_MESSAGE_START | Agent begins text | messageId, role |
| TEXT_MESSAGE_CONTENT | Streaming token | messageId, delta |
| TEXT_MESSAGE_END | Text block done | messageId |

### Tool calls
| Event | When | Key fields |
|-------|------|------------|
| TOOL_CALL_START | Agent calls a tool | toolCallId, toolCallName |
| TOOL_CALL_ARGS | Tool arguments | toolCallId, delta (JSON) |
| TOOL_CALL_END | Args complete | toolCallId |
| TOOL_CALL_RESULT | Tool returns | toolCallId, content |

### Thinking (optional)
| Event | When | Key fields |
|-------|------|------------|
| THINKING_TEXT_MESSAGE_START | Agent reasoning | messageId |
| THINKING_TEXT_MESSAGE_CONTENT | Reasoning text | messageId, delta |
| THINKING_TEXT_MESSAGE_END | Reasoning done | messageId |

### Steps (optional)
| Event | When | Key fields |
|-------|------|------------|
| STEP_STARTED | New iteration begins | stepName |
| STEP_FINISHED | Iteration complete | stepName |

### State
| Event | When | Key fields |
|-------|------|------------|
| STATE_SNAPSHOT | Full state update | snapshot (dict) |
| STATE_DELTA | Incremental update | delta (JSON patch) |

## State Round-Trip

State persists across runs within a thread:

```
Run 1: Flutter sends state={}
       Agent works → emits STATE_SNAPSHOT {session_id, run_count: 1}
       Flutter stores the snapshot

Run 2: Flutter sends state={session_id, run_count: 1}
       Agent reads state → knows context from Run 1
       Agent works → emits STATE_SNAPSHOT {session_id, run_count: 2}
```

Use state for:
- Session IDs (Hermes session continuity)
- Artifact tracking (files created)
- Usage metrics
- Custom per-room data

## Cross-Room Communication

Rooms can call each other via AG-UI:

```python
# From a tool in Room A, call Room B
async def ask_room(ctx, room_id, message):
    # 1. Create thread in target room
    r = await client.post(f"{BASE}/v1/rooms/{room_id}/agui", json={})
    tid = r.json()["thread_id"]
    rid = list(r.json()["runs"].keys())[0]

    # 2. Send RunAgentInput
    body = {
        "threadId": tid, "runId": rid,
        "state": {},
        "messages": [{"id": "...", "role": "user", "content": message}],
        "tools": [], "context": [], "forwardedProps": {},
    }

    # 3. Consume AG-UI stream from target room
    text = ""
    async with client.stream("POST", f"{BASE}/v1/rooms/{room_id}/agui/{tid}/{rid}", json=body) as r:
        async for line in r.aiter_lines():
            # Parse SSE events, collect text + tool results
```

This enables:
- **Research room** asks **search room** to find documents
- **Hybrid room** asks **hermes room** for web research
- **Analysis room** asks **data room** for metrics

Each room is a specialized agent microservice.

## Client-Side Tools

Flutter can register tools that the agent calls back to the client:

```json
{
  "tools": [
    {
      "name": "confirm_action",
      "description": "Ask user to confirm before destructive action",
      "parameters": {"type": "object", "properties": {"action": {"type": "string"}}}
    }
  ]
}
```

When the agent calls a client tool:
1. Agent emits TOOL_CALL events for the client tool
2. Run finishes (RUN_FINISHED)
3. Flutter executes the tool locally
4. Flutter sends a new run with the tool result in messages
5. Agent continues

This is the AG-UI multi-run pattern — no WebSocket needed.
