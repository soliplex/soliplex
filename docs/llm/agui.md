# AG-UI Protocol: Complete System Analysis

## Overview

AG-UI (Agent GUI) is a **thread-based conversational streaming protocol** that manages agent interactions through a hierarchical structure: **Room → Thread → Run → Events**.

## Core Concepts

### 1. Resource Hierarchy

```
Room (static config)
  └── Thread (conversation container)
        └── Run (single agent invocation)
              └── Events (SSE stream)
```

### 2. API Flow Rules

| Step | Action | Endpoint | Returns |
|------|--------|----------|---------|
| 1 | Create thread | `POST /rooms/{room_id}/agui` | Thread + **first Run UUID** |
| 2 | Execute first run | `POST /rooms/{room_id}/agui/{thread_id}/{run_id}` | SSE event stream |
| 3 | Create subsequent run | `POST /rooms/{room_id}/agui/{thread_id}` | New Run UUID |
| 4 | Execute subsequent run | `POST /rooms/{room_id}/agui/{thread_id}/{new_run_id}` | SSE event stream |

**Critical constraints:**
- A run can only be POSTed **once** (returns error if reused)
- Thread creation includes the first run UUID to save a round-trip
- The client manages message history and sends the full context with each run

## Data Models

### Thread
```json
{
  "room_id": "string",
  "thread_id": "uuid",
  "runs": { "run_uuid": Run, ... },
  "created": "datetime",
  "metadata": { "name": "string", "description": "string" }
}
```

### Run
```json
{
  "thread_id": "uuid",
  "run_id": "uuid",
  "parent_run_id": "uuid | null",
  "run_input": RunAgentInput,
  "created": "datetime",
  "events": [Event, ...],
  "metadata": {}
}
```

### RunAgentInput (request body for run execution)
```json
{
  "threadId": "uuid",
  "runId": "uuid",
  "state": {},           // Arbitrary client state
  "messages": [Message], // Full conversation history
  "tools": [Tool],       // Available tools
  "context": [Context],  // Additional context
  "forwardedProps": {}   // Pass-through properties
}
```

### Message Types
- `UserMessage`: `{ id, role: "user", content: string | ContentPart[] }`
- `AssistantMessage`: `{ id, role: "assistant", content, toolCalls? }`
- `ToolMessage`: `{ id, role: "tool", toolCallId, content }`
- `SystemMessage`, `DeveloperMessage`, `ActivityMessage`

## Event Stream (SSE)

Format: `data: {JSON event}\n\n`

### Event Lifecycle

```
RUN_STARTED
  → THINKING_START → THINKING_TEXT_MESSAGE_* → THINKING_END
  → TOOL_CALL_START → TOOL_CALL_ARGS → TOOL_CALL_END
  → TOOL_CALL_RESULT (if server-side tool)
  → TEXT_MESSAGE_START → TEXT_MESSAGE_CONTENT* → TEXT_MESSAGE_END
RUN_FINISHED | RUN_ERROR
```

### Event Types Reference

| Category | Events | Purpose |
|----------|--------|---------|
| Run lifecycle | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR` | Run boundaries |
| Text streaming | `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END` | Assistant response |
| Tool calls | `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `TOOL_CALL_RESULT` | Function invocation |
| Thinking | `THINKING_START`, `THINKING_TEXT_MESSAGE_*`, `THINKING_END` | Extended thinking |
| State | `STATE_SNAPSHOT`, `STATE_DELTA` | Client state sync |
| Activity | `ACTIVITY_SNAPSHOT`, `ACTIVITY_DELTA` | Status indicators |
| Steps | `STEP_STARTED`, `STEP_FINISHED` | Multi-step operations |

### Sample Event Stream
```
data: {"type":"RUN_STARTED","threadId":"uuid","runId":"uuid"}
data: {"type":"TOOL_CALL_START","toolCallId":"call_xxx","toolCallName":"joke_factory","parentMessageId":"uuid"}
data: {"type":"TOOL_CALL_ARGS","toolCallId":"call_xxx","delta":"{\"count\":1,\"topic\":\"cats\"}"}
data: {"type":"TOOL_CALL_END","toolCallId":"call_xxx"}
data: {"type":"TOOL_CALL_RESULT","messageId":"uuid","toolCallId":"call_xxx","content":"[...]","role":"tool"}
data: {"type":"TEXT_MESSAGE_START","messageId":"uuid","role":"assistant"}
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"uuid","delta":"Here's"}
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"uuid","delta":" a joke..."}
data: {"type":"TEXT_MESSAGE_END","messageId":"uuid"}
data: {"type":"RUN_FINISHED","threadId":"uuid","runId":"uuid"}
```

## Client Implementation Pattern

```python
# 1. Create thread (get first run free)
thread = POST /rooms/{room}/agui  # body: {}
thread_id = thread["thread_id"]
run_id = list(thread["runs"].keys())[0]

# 2. Execute first run
messages = [{"id": "1", "role": "user", "content": "Hello"}]
stream = POST /rooms/{room}/agui/{thread_id}/{run_id}
         body: { threadId, runId, state: {}, messages, tools: [], context: [], forwardedProps: {} }

# 3. Process SSE events, accumulate assistant response

# 4. For follow-up: create new run
new_run = POST /rooms/{room}/agui/{thread_id}  # body: {}
new_run_id = new_run["run_id"]

# 5. Execute with full history
messages.append({"id": "2", "role": "assistant", "content": accumulated_response})
messages.append({"id": "3", "role": "user", "content": "Follow up question"})
stream = POST /rooms/{room}/agui/{thread_id}/{new_run_id}
         body: { threadId, runId: new_run_id, ... messages ... }
```

## Key Design Decisions

1. **Client-owned history**: The client sends the full message history with each run; the server doesn't maintain conversation state across runs.

2. **One-shot runs**: Each run UUID can only be executed once, preventing duplicate processing.

3. **Pre-allocated first run**: Thread creation returns the first run UUID, eliminating a round-trip.

4. **Server-side tool execution**: Tools like `joke_factory` execute on the server; `TOOL_CALL_RESULT` events are injected into the stream.

5. **Message ID correlation**: Events reference `messageId` for correlating streaming chunks with messages.

## Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/rooms/{room_id}/agui` | List all threads in room |
| POST | `/rooms/{room_id}/agui` | Create new thread (includes first run) |
| GET | `/rooms/{room_id}/agui/{thread_id}` | Get thread with all runs |
| POST | `/rooms/{room_id}/agui/{thread_id}` | Create new run in thread |
| GET | `/rooms/{room_id}/agui/{thread_id}/{run_id}` | Get run metadata |
| POST | `/rooms/{room_id}/agui/{thread_id}/{run_id}` | Execute run (SSE stream) |
