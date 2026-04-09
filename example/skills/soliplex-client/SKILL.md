---
name: soliplex-client
description: Connect to and interact with a Soliplex server — browse rooms, have conversations, manage threads, and consume AG-UI streaming responses via the REST API
---

# Soliplex Client

This skill teaches you how to interact with a Soliplex server as a consumer. Soliplex is an AI-powered RAG system with rooms (chat environments), conversation threads, and real-time streaming via the AG-UI protocol.

## Connection

The server URL is provided by the user or read from the `SOLIPLEX_URL` environment variable.

All API endpoints are prefixed with `/api`. The versioned API lives at `/api/v1`.

### Authentication

Soliplex supports two modes:

**No-auth mode** (development/demo): No token required. All API calls work without an `Authorization` header.

**OIDC mode** (production): Requires a Bearer token in the `Authorization` header.

To authenticate with OIDC:

1. Discover available providers:

```bash
curl ${SOLIPLEX_URL}/api/login
```

Response: a dict of provider objects, each with `id`, `title`, `server_url`, `client_id`, and optionally `scope`.

2. Obtain a token via the OIDC password grant:

```bash
curl -X POST "${PROVIDER_SERVER_URL}/protocol/openid-connect/token" \
  -d "client_id=${CLIENT_ID}" \
  -d "grant_type=password" \
  -d "username=${USERNAME}" \
  -d "password=${PASSWORD}"
```

Response includes `access_token`, `refresh_token`, `expires_in`, `refresh_expires_in`.

3. Use the access token on all subsequent requests:

```bash
-H "Authorization: Bearer ${ACCESS_TOKEN}"
```

If the token is already known, it can be set in the `SOLIPLEX_ACCESS_TOKEN` environment variable.

## Server Info

Get installation metadata:

```bash
curl ${SOLIPLEX_URL}/api/v1/installation
```

Get installed package versions:

```bash
curl ${SOLIPLEX_URL}/api/v1/installation/versions
```

Get available LLM providers and models:

```bash
curl ${SOLIPLEX_URL}/api/v1/installation/providers
```

## Rooms

Rooms are independent chat environments, each with their own agent, tools, skills, and knowledge base.

### List Rooms

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms
```

Returns a dict of room objects keyed by room ID. Each room has:
- `id`, `name`, `description`, `welcome_message`
- `suggestions` — example prompts
- `tools` — available tools
- `skills` — available skills
- `agent` — the room's agent configuration
- `allow_mcp` — whether MCP access is enabled

### Get Room Details

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}
```

### List Room Documents (RAG)

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/documents
```

Returns `{room_id, document_set: {doc_id: {id, uri, title, metadata, created_at, updated_at}}}`.

## Conversations

Conversations use the AG-UI protocol. The flow is: **create a thread** -> **create a run** -> **execute the run** (streaming) -> **parse SSE events**.

### List Threads

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui
```

Returns `{threads: [{room_id, thread_id, created, metadata: {name, description}}]}`.

### Get Thread Details

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}
```

Returns the thread with all its runs: `{room_id, thread_id, created, metadata, runs: {run_id: {thread_id, run_id, parent_run_id, created, finished, run_input, events, metadata, usage}}}`.

### Create a New Thread (First Message)

When starting a new conversation, create a thread. This also creates the initial (empty) run:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"name": "My conversation topic"}}'
```

Response:

```json
{
  "room_id": "chat",
  "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "created": "2025-01-01T00:00:00Z",
  "metadata": {"name": "My conversation topic", "description": null},
  "runs": {
    "11111111-2222-3333-4444-555555555555": {
      "thread_id": "aaaaaaaa-...",
      "run_id": "11111111-...",
      "parent_run_id": null,
      "run_input": {
        "thread_id": "aaaaaaaa-...",
        "run_id": "11111111-...",
        "state": {},
        "messages": [],
        "tools": [],
        "context": [],
        "forwarded_props": null
      },
      "events": [],
      "metadata": null,
      "usage": null
    }
  }
}
```

Extract `thread_id` and the single `run_id` from the `runs` dict. The `run_input.state` contains the initial AG-UI feature state — preserve it.

### Create a Follow-Up Run

For subsequent messages in the same thread, create a new run:

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id} \
  -H "Content-Type: application/json" \
  -d '{}'
```

Response:

```json
{
  "thread_id": "aaaaaaaa-...",
  "run_id": "66666666-...",
  "parent_run_id": "11111111-...",
  "created": "2025-01-01T00:01:00Z",
  "run_input": null,
  "events": [],
  "metadata": null,
  "usage": null
}
```

### Execute a Run (Send a Message)

This is the core operation. POST a `RunAgentInput` to the run endpoint. The response is an SSE stream of AG-UI events.

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id} \
  -H "Content-Type: application/json" \
  -d '{
    "threadId": "aaaaaaaa-...",
    "runId": "11111111-...",
    "state": {},
    "messages": [
      {"id": "user_001", "role": "user", "content": "Hello, what can you help me with?"}
    ],
    "tools": [],
    "context": [],
    "forwardedProps": {}
  }'
```

#### RunAgentInput Schema

```json
{
  "threadId": "<uuid>",
  "runId": "<uuid>",
  "state": {},
  "messages": [
    {"id": "user_001", "role": "user", "content": "first message"},
    {"id": "assistant_001", "role": "assistant", "content": "first response"},
    {"id": "user_002", "role": "user", "content": "follow-up message"}
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

**Critical: Message Accumulation**

You MUST include all prior messages in the `messages` array for each run. The server does not maintain message history across runs — the client is responsible for accumulating the conversation.

For each turn:
1. Append the user's new message with `role: "user"` and an incrementing ID like `user_001`, `user_002`, etc.
2. After receiving the response, append the assistant's reply with `role: "assistant"` and ID like `assistant_001`, `assistant_002`, etc.
3. On the next turn, send all accumulated messages.

**Note on field names:** The RunAgentInput uses camelCase in JSON (`threadId`, `runId`, `forwardedProps`), matching the AG-UI protocol specification.

#### Parsing the SSE Stream

The response is a Server-Sent Events stream. Each line is either:
- A comment starting with `:` — keepalive, ignore it
- A data line starting with `data: ` — strip the prefix and JSON-parse the remainder

Each event is a JSON object with a `type` field.

**Text response events** — assemble these to build the agent's reply:

| Event Type | Key Fields | Description |
|---|---|---|
| `TEXT_MESSAGE_START` | `messageId` | Response text begins |
| `TEXT_MESSAGE_CONTENT` | `messageId`, `delta` | Text chunk — append `delta` to build the response |
| `TEXT_MESSAGE_END` | `messageId` | Response text complete |

**Thinking events** — the agent's internal reasoning (optional, may not appear):

| Event Type | Key Fields | Description |
|---|---|---|
| `THINKING_START` | — | Reasoning begins |
| `THINKING_TEXT_MESSAGE_CONTENT` | `delta` | Reasoning text chunk |
| `THINKING_END` | — | Reasoning complete |

**Tool call events** — the agent using tools:

| Event Type | Key Fields | Description |
|---|---|---|
| `TOOL_CALL_START` | `toolCallId`, `toolCallName`, `parentMessageId` | Tool invocation begins |
| `TOOL_CALL_ARGS` | `toolCallId`, `delta` | Tool argument chunk |
| `TOOL_CALL_END` | `toolCallId` | Tool call complete |
| `TOOL_CALL_RESULT` | `toolCallId`, `result` | Tool result |

**State events** — AG-UI feature state updates:

| Event Type | Key Fields | Description |
|---|---|---|
| `STATE_SNAPSHOT` | `snapshot` | Complete state replacement |
| `STATE_DELTA` | `delta` | JSON Patch update to state |

**Activity events**:

| Event Type | Key Fields | Description |
|---|---|---|
| `ACTIVITY_SNAPSHOT` | `content` | Activity info |
| `ACTIVITY_DELTA` | `patch` | Activity update |

**Lifecycle events**:

| Event Type | Key Fields | Description |
|---|---|---|
| `RUN_STARTED` | — | Run begins |
| `RUN_FINISHED` | — | Run completed successfully — stop reading |
| `RUN_ERROR` | `message` | Run failed — stop reading, report the error |
| `STEP_STARTED` | — | Processing step begins |
| `STEP_FINISHED` | — | Processing step ends |

#### Example: Assembling a Response

```
: keepalive                              ← ignore
data: {"type": "RUN_STARTED"}           ← run begins
data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "Hello! "}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "I can help "}
data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "with many things."}
data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}
data: {"type": "RUN_FINISHED"}          ← done, assembled text: "Hello! I can help with many things."
```

After assembling the response, add an assistant message to the accumulating messages array:

```json
{"id": "assistant_001", "role": "assistant", "content": "Hello! I can help with many things."}
```

### Complete Conversation Example

**Turn 1 (new conversation):**

1. Create thread: `POST /api/v1/rooms/chat/agui` with `{"metadata": {"name": "chat: Hello"}}` → get `thread_id`, `run_id`, `state`
2. Execute run: `POST /api/v1/rooms/chat/agui/{thread_id}/{run_id}` with:
   ```json
   {"threadId": "...", "runId": "...", "state": {}, "messages": [{"id": "user_001", "role": "user", "content": "Hello"}], "tools": [], "context": [], "forwardedProps": {}}
   ```
3. Parse SSE → assemble response text
4. Store: `messages = [user_001, assistant_001]`

**Turn 2 (follow-up):**

1. Create new run: `POST /api/v1/rooms/chat/agui/{thread_id}` with `{}` → get new `run_id`, `parent_run_id`
2. Execute run: `POST /api/v1/rooms/chat/agui/{thread_id}/{new_run_id}` with:
   ```json
   {"threadId": "...", "runId": "...", "state": {}, "messages": [{"id": "user_001", "role": "user", "content": "Hello"}, {"id": "assistant_001", "role": "assistant", "content": "Hi there!"}, {"id": "user_002", "role": "user", "content": "Tell me more"}], "tools": [], "context": [], "forwardedProps": {}}
   ```
3. Parse SSE → assemble response text
4. Store: `messages = [user_001, assistant_001, user_002, assistant_002]`

### Delete a Thread

```bash
curl -X DELETE ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}
```

### Update Thread Metadata

```bash
curl -X POST ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}/meta \
  -H "Content-Type: application/json" \
  -d '{"name": "New thread name", "description": "Optional description"}'
```

Returns HTTP 205 on success.

### Get a Specific Run

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}
```

Returns: `{thread_id, run_id, parent_run_id, created, finished, run_input, events, metadata, usage}`.

The `usage` field (when present): `{input_tokens, output_tokens, requests, tool_calls}`.

### MCP Room Token

For rooms with `allow_mcp: true`, get a token for direct MCP tool access:

```bash
curl ${SOLIPLEX_URL}/api/v1/rooms/{room_id}/mcp_token
```

Returns: `{room_id, mcp_token}`. Use this token to connect an MCP client to `${SOLIPLEX_URL}/mcp/{room_id}/`.
