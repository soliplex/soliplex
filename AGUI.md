# AG-UI Architecture: Lessons Learned

This document captures key insights about how the AG-UI (Agentic Generative User Interface) client and server interact in the Soliplex codebase.

## Overview

AG-UI is a protocol for AI agents to generate dynamic, interactive user interfaces in real-time. The system uses:
- **Server-Sent Events (SSE)** for streaming communication
- **Remote Flutter Widgets (RFW)** for dynamic UI rendering
- **Thread/Run model** for conversation state management

---

## Key Lessons

### 1. The Two-Step Execution Flow

Creating and executing a run requires **two separate API calls**:

```
Step 1: POST /rooms/{room_id}/agui           → Creates thread + returns initial run
Step 2: POST /rooms/{room_id}/agui/{thread}/{run} → Executes run with SSE streaming
```

**Lesson:** Don't try to create and execute in one call. The first POST returns metadata; the second POST starts the actual agent execution and returns an SSE stream.

### 2. Message History is Client-Managed

The client (not server) maintains conversation history. Each request sends the **full message history**:

```json
{
  "thread_id": "uuid",
  "run_id": "uuid",
  "messages": [
    {"role": "user", "id": "...", "content": "Hello"},
    {"role": "assistant", "id": "...", "content": "Hi!", "toolCalls": [...]},
    {"role": "tool", "id": "...", "toolCallId": "...", "content": "..."}
  ],
  "state": {},
  "forwardedProps": {}
}
```

**Lesson:** The server is stateless per-run. The client reconstructs context by sending accumulated messages each time.

### 3. The forwardedProps Field is Required

The request body **must** include `forwardedProps: {}` even if empty.

```python
# Server will error without this field
run_input = request_body.get('run_input', {})
if 'forwardedProps' not in run_input:
    raise HTTPException(500, "Missing forwardedProps")
```

**Lesson:** Always include `forwardedProps` in your request body, even as an empty object.

### 4. Use camelCase in JSON (Not snake_case)

Message fields use camelCase to match JavaScript/Dart conventions:

| Correct | Incorrect |
|---------|-----------|
| `toolCalls` | `tool_calls` |
| `toolCallId` | `tool_call_id` |
| `messageId` | `message_id` |

**Lesson:** The protocol follows JavaScript naming conventions throughout.

### 5. SSE Event Format

Events follow standard SSE format with `event:` and `data:` lines:

```
event: TEXT_MESSAGE_START
data: {"type":"TEXT_MESSAGE_START","messageId":"msg_123"}

event: TEXT_MESSAGE_CONTENT
data: {"type":"TEXT_MESSAGE_CONTENT","delta":"Hello","messageId":"msg_123"}

event: TEXT_MESSAGE_END
data: {"type":"TEXT_MESSAGE_END","messageId":"msg_123"}

```

**Lesson:** Events are separated by `\n\n`. Parse line-by-line, looking for `event:` and `data:` prefixes.

### 6. Tool Call Arguments Stream in Chunks

Tool arguments are **not** sent as complete JSON. They stream as fragments:

```
event: TOOL_CALL_ARGS
data: {"toolCallId":"call_1","delta":"{\n  \"cou"}

event: TOOL_CALL_ARGS
data: {"toolCallId":"call_1","delta":"nt\": 5\n}"}
```

**Lesson:** Buffer `delta` values until `TOOL_CALL_END`, then parse the complete JSON.

### 7. Event State Machine

Events must occur in valid sequences:

| Valid | Invalid |
|-------|---------|
| START → CONTENT → END | CONTENT without START |
| TOOL_CALL_START → ARGS → END | ARGS without START |

```python
# Parser validates state transitions
if event.type == 'TEXT_MESSAGE_CONTENT':
    if self.current_message_id is None:
        raise InvalidEventSequence("No active message")
```

**Lesson:** Track active message/tool IDs. Reject events that violate the state machine.

### 8. Thread vs Run Semantics

- **Thread:** A conversation container. Persists across multiple exchanges.
- **Run:** A single request-response cycle. Each user message creates a new run.

```
Thread (conversation) ─┬─ Run 1 (first exchange)
                       ├─ Run 2 (second exchange)
                       └─ Run 3 (with parent_run_id for branching)
```

**Lesson:** Reuse `thread_id` for multi-turn conversations. Create new `run_id` for each exchange.

### 9. Run Branching with parent_run_id

Create alternative conversation paths by specifying `parent_run_id`:

```json
{
  "run_id": "new-run-uuid",
  "parent_run_id": "original-run-uuid",
  "messages": [...messages up to branch point...]
}
```

**Lesson:** Use `parent_run_id` to explore "what if" scenarios without losing the original conversation path.

### 10. Local Tool Execution Pattern

Some tools execute on the client (e.g., geolocation, camera):

```
1. Server sends TOOL_CALL events for local tool
2. Client recognizes tool name as local
3. Client executes locally (GPS, etc.)
4. Client sends result back via sendToolResult()
5. Server continues with the result
```

**Lesson:** Define local tools in the client. When server requests them, execute locally and send results as tool messages.

---

## Event Type Reference

### Lifecycle Events
| Event | Purpose |
|-------|---------|
| `RUN_STARTED` | Run execution began |
| `RUN_FINISHED` | Run completed successfully |
| `RUN_ERROR` | Run failed with error code/message |

### Text Message Events
| Event | Purpose |
|-------|---------|
| `TEXT_MESSAGE_START` | New assistant message begins |
| `TEXT_MESSAGE_CONTENT` | Text chunk (delta) |
| `TEXT_MESSAGE_END` | Message complete |

### Tool Call Events
| Event | Purpose |
|-------|---------|
| `TOOL_CALL_START` | Tool invocation begins |
| `TOOL_CALL_ARGS` | Argument chunk (accumulate these) |
| `TOOL_CALL_END` | Tool call complete, parse accumulated args |

### State Management Events
| Event | Purpose |
|-------|---------|
| `STATE_SNAPSHOT` | Replace entire state object |
| `STATE_DELTA` | Apply JSON patch to state |
| `MESSAGES_SNAPSHOT` | Replace entire message history |

### Activity Events
| Event | Purpose |
|-------|---------|
| `ACTIVITY_SNAPSHOT` | Set activity status (e.g., "thinking...") |
| `ACTIVITY_DELTA` | Update activity status |

---

## API Endpoint Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/v1/rooms/{room}/agui` | List user's threads in room |
| `GET` | `/v1/rooms/{room}/agui/{thread}` | Get thread with all runs |
| `GET` | `/v1/rooms/{room}/agui/{thread}/{run}` | Get specific run |
| `POST` | `/v1/rooms/{room}/agui` | Create new thread + initial run |
| `POST` | `/v1/rooms/{room}/agui/{thread}` | Create new run in thread |
| `POST` | `/v1/rooms/{room}/agui/{thread}/{run}` | **Execute run (returns SSE stream)** |
| `POST` | `/v1/rooms/{room}/agui/{thread}/meta` | Update thread metadata |
| `POST` | `/v1/rooms/{room}/agui/{thread}/{run}/meta` | Update run metadata |
| `DELETE` | `/v1/rooms/{room}/agui/{thread}` | Delete thread |

---

## Common Pitfalls

### 1. Forgetting to Parse SSE Format
```dart
// WRONG: Treating response as plain JSON
final data = jsonDecode(response.body);

// RIGHT: Parse SSE line by line
for (final line in response.body.split('\n')) {
  if (line.startsWith('data: ')) {
    final data = jsonDecode(line.substring(6));
  }
}
```

### 2. Not Accumulating Tool Args
```dart
// WRONG: Parsing args on each TOOL_CALL_ARGS event
final args = jsonDecode(event.delta);  // Fails - incomplete JSON!

// RIGHT: Buffer until TOOL_CALL_END
_toolArgsBuffer[event.toolCallId] += event.delta;
// Then on TOOL_CALL_END:
final args = jsonDecode(_toolArgsBuffer[event.toolCallId]);
```

### 3. Wrong Content-Type for SSE
```dart
// WRONG
headers: {'Accept': 'application/json'}

// RIGHT
headers: {'Accept': 'text/event-stream'}
```

### 4. Not Sending Full Message History
```dart
// WRONG: Only sending new message
body: {'messages': [newUserMessage]}

// RIGHT: Send complete history
body: {'messages': _allPreviousMessages + [newUserMessage]}
```

---

## Key Files

| Path | Purpose |
|------|---------|
| `src/soliplex/views/agui.py` | Server API routes |
| `src/soliplex/agui/thread.py` | Thread/Run data models |
| `src/soliplex/agui/parser.py` | Event stream parser |
| `src/agui_chat_rfw/lib/core/services/agui_service.dart` | Client SSE handling |
| `src/agui_chat_rfw/lib/core/models/agui_events.dart` | Event type definitions |
| `src/agui_chat_rfw/lib/core/services/rfw_service.dart` | RFW rendering |

---

## RFW (Remote Flutter Widgets) Integration

When tools return UI definitions, they're rendered via RFW:

1. Tool result contains `libraryBlob` (binary) or `libraryText` (source)
2. Client decodes the RFW library
3. Widget renders with `DynamicContent` for data binding
4. Events bubble up via `onEvent` callback

**Security:** RFW payloads are validated for:
- Maximum size (5MB)
- Maximum nesting depth (50 levels)
- Disallowed widget types
- Image domain whitelisting

---

## Summary

The AG-UI protocol enables real-time, agent-generated interfaces with:

- **Stateless server:** Client owns conversation history
- **Streaming events:** SSE for progressive rendering
- **Local execution:** Client-side tools for device features
- **Dynamic UI:** RFW for agent-generated widgets

The key to success is understanding the two-step flow (create then execute), maintaining proper event state, and always sending complete message context with each request.
