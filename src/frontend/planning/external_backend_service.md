# Backend API Reference

Base URL: `http://localhost:8000`

## Authentication Endpoints

All authenticated endpoints use OAuth2 Bearer token (`Authorization: Bearer <token>`).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/login` | List available OIDC auth providers |
| GET | `/api/login/{system}` | Initiate OIDC token auth flow with provider |
| GET | `/api/auth/{system}` | Complete OIDC token auth flow (redirects on success) |
| GET | `/api/user_info` | Get authenticated user's profile |

### Auth Flow

1. `GET /api/login` → Returns map of available auth systems (e.g., `{"keycloak": {...}}`)
2. `GET /api/login/{system}` → Initiates OAuth flow, redirects to provider
3. `GET /api/auth/{system}` → Callback from provider, returns token
4. Use token in `Authorization: Bearer <token>` header for authenticated requests

## Room Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms` | List all available rooms |
| GET | `/api/v1/rooms/{room_id}` | Get single room configuration |
| GET | `/api/v1/rooms/{room_id}/bg_image` | Get room background image |
| GET | `/api/v1/rooms/{room_id}/mcp_token` | Get MCP client token for room |
| GET | `/api/v1/rooms/{room_id}/documents` | List documents in room's RAG database |

## AGUI Thread Endpoints

Primary API for AI agent interactions using AG-UI protocol.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms/{room_id}/agui` | List user's threads in room |
| POST | `/api/v1/rooms/{room_id}/agui` | Create new thread (returns thread_id + initial run_id) |
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Get thread metadata and runs |
| DELETE | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Delete thread (⚠️ backend uses POST, see note below) |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/meta` | Update thread metadata (name, description) |

> **Backend Issue:** Thread deletion should use DELETE method but backend incorrectly registers it as POST, conflicting with run creation. The backend code at `views/agui.py` has both handlers on the same POST path.

### Request/Response Models

**Create Thread Request:**

```json
{
  "metadata": {
    "name": "string | null",
    "description": "string | null"
  }
}
```

**Thread Response:**

```json
{
  "room_id": "string",
  "thread_id": "string",
  "runs": {"run_id": {...}},
  "created": "datetime",
  "metadata": {"name": "...", "description": "..."}
}
```

## AGUI Run Endpoints

Runs represent individual AI agent executions within a thread.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Create new run (returns run_id) |
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Get run metadata |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Execute run (streams AG-UI events) |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta` | Update run metadata (label) |

> **Note:** The `POST /api/v1/rooms/{room_id}/agui/{thread_id}` endpoint has a routing conflict in the backend. The intended behavior is to create a new run, but it may be shadowed by the delete thread handler. See backend `views/agui.py` for details.

### Create Run Request

```json
{
  "parent_run_id": "string | null",
  "metadata": {
    "label": "string | null"
  }
}
```

### Run Execution

`POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` accepts a `RunAgentInput` body and streams AG-UI events:

**Request Body (RunAgentInput):**

```json
{
  "threadId": "string",
  "runId": "string",
  "parentRunId": "string | null",
  "state": {},
  "messages": [
    {"id": "msg-1", "role": "user", "content": "Hello"},
    {"id": "msg-2", "role": "assistant", "content": "Hi!"}
  ],
  "tools": [],
  "context": [],
  "forwardedProps": {}
}
```

**Response:** Server-Sent Events (SSE) stream with AG-UI events:

- `RUN_STARTED` / `RUN_FINISHED` / `RUN_ERROR`
- `STEP_STARTED` / `STEP_FINISHED`
- `TEXT_MESSAGE_START` / `TEXT_MESSAGE_CONTENT` / `TEXT_MESSAGE_END` / `TEXT_MESSAGE_CHUNK`
- `TOOL_CALL_START` / `TOOL_CALL_ARGS` / `TOOL_CALL_END` / `TOOL_CALL_RESULT`
- `STATE_SNAPSHOT` / `STATE_DELTA`
- `MESSAGES_SNAPSHOT`
- `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA`

## Completions Endpoints

Direct LLM completion access (OpenAI-compatible).

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/chat/completions` | List available completions |
| GET | `/api/v1/chat/completions/{completion_id}` | Get completion config |
| POST | `/api/v1/chat/completions/{completion_id}` | Send chat completion request |

### Chat Completion Request

```json
{
  "model": "string",
  "messages": [{"role": "user", "content": "string"}],
  "temperature": 1.0,
  "top_p": 1.0,
  "stream": false,
  "max_tokens": null
}
```

## Quiz Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms/{room_id}/quiz/{quiz_id}` | Get quiz configuration |
| POST | `/api/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}` | Submit answer for evaluation |

## Installation Endpoint

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/installation` | Get installation's top-level configuration |

## Utility Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ok` | Health check (returns "ok") |
| GET | `/api/check-headers` | Debug: dump request headers |

## Deprecated Endpoints

Legacy conversation API (use AGUI endpoints instead):

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/convos/new/{room_id}` | Create conversation |
| GET | `/api/v1/convos` | List conversations |
| GET | `/api/v1/convos/{convo_uuid}` | Get conversation |
| POST | `/api/v1/convos/{convo_uuid}` | Send message |
| DELETE | `/api/v1/convos/{convo_uuid}` | Delete conversation |

## Reference

- OpenAPI docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
