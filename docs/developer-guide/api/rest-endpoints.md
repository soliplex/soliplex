# REST Endpoints

Complete reference for Soliplex REST API endpoints.

## Base URL

All API endpoints are prefixed with `/api`:

```
http://localhost:8000/api/v1/...
```

## Authentication

Most endpoints require a Bearer token:

```bash
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/v1/rooms
```

---

## Authentication Endpoints

### GET /login

Get available OIDC authentication providers.

**Response:**
```json
{
  "google": {
    "id": "google",
    "title": "Google",
    "server_url": "https://accounts.google.com",
    "token_validation_pem": "-----BEGIN PUBLIC KEY-----...",
    "client_id": "your-client-id",
    "scope": "openid email profile"
  }
}
```

### GET /login/{system}

Initiate OIDC token auth flow with a provider.

**Parameters:**
- `system` - Provider ID (e.g., "google", "keycloak")
- `return_to` - URL to redirect after authentication (query param)

**Response:** 302 redirect to provider's authorization URL

### GET /auth/{system}

Complete OIDC token auth flow. Called by the provider after user authorization.

**Response:** 302 redirect to `return_to` URL with tokens in query params:
- `token` - Access token
- `refresh_token` - Refresh token
- `expires_in` - Token expiration in seconds
- `refresh_expires_in` - Refresh token expiration

### GET /user_info

Get the authenticated user's profile.

**Response:**
```json
{
  "preferred_username": "user@example.com",
  "given_name": "John",
  "family_name": "Doe",
  "email": "user@example.com"
}
```

---

## Room Endpoints

### GET /v1/rooms

Get available rooms for the authenticated user.

**Response:**
```json
{
  "research": {
    "id": "research",
    "name": "Research Room",
    "description": "Research assistant room",
    "welcome_message": "Welcome! How can I help?",
    "suggestions": ["Search documents", "Summarize content"],
    "enable_attachments": false,
    "tools": {...},
    "mcp_client_toolsets": {...},
    "quizzes": {...},
    "agent": {...},
    "allow_mcp": true
  }
}
```

### GET /v1/rooms/{room_id}

Get a specific room's configuration.

**Parameters:**
- `room_id` - Room identifier

**Response:**
```json
{
  "id": "research",
  "name": "Research Room",
  "description": "Research assistant room",
  "welcome_message": "Welcome! How can I help?",
  "suggestions": ["Search documents", "Summarize content"],
  "enable_attachments": false,
  "tools": {...},
  "mcp_client_toolsets": {...},
  "quizzes": {...},
  "agent": {...},
  "allow_mcp": true
}
```

### GET /v1/rooms/{room_id}/bg_image

Get a room's background/logo image.

**Response:** Image file (FileResponse)

### GET /v1/rooms/{room_id}/mcp_token

Get an MCP token for accessing the room via MCP client.

**Response:**
```json
{
  "room_id": "research",
  "mcp_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### GET /v1/rooms/{room_id}/documents

List documents in the room's RAG database.

**Response:**
```json
{
  "room_id": "research",
  "document_set": {
    "doc-1": {
      "id": "doc-1",
      "uri": "file:///docs/guide.pdf",
      "title": "User Guide",
      "metadata": {},
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

### GET /v1/rooms/{room_id}/chunk/{chunk_id}

Get visual representation of a document chunk with highlighted text.

**Parameters:**
- `room_id` - Room identifier
- `chunk_id` - Chunk identifier

**Response:**
```json
{
  "chunk_id": "chunk-abc123",
  "document_uri": "file:///docs/guide.pdf",
  "images_base_64": ["iVBORw0KGgo..."]
}
```

---

## AG-UI Endpoints

### GET /v1/rooms/{room_id}/agui

List user's threads in a room.

**Response:**
```json
{
  "threads": [
    {
      "room_id": "research",
      "thread_id": "thread-123",
      "created": "2024-01-15T10:30:00Z",
      "metadata": {
        "name": "Research session",
        "description": null
      }
    }
  ]
}
```

### POST /v1/rooms/{room_id}/agui

Create a new thread in a room.

**Request Body:**
```json
{
  "metadata": {
    "name": "New research session",
    "description": "Optional description"
  }
}
```

**Response:**
```json
{
  "room_id": "research",
  "thread_id": "thread-456",
  "created": "2024-01-15T10:35:00Z",
  "metadata": {
    "name": "New research session",
    "description": "Optional description"
  },
  "runs": {
    "run-1": {
      "run_id": "run-1",
      "thread_id": "thread-456",
      "created": "2024-01-15T10:35:00Z"
    }
  }
}
```

### GET /v1/rooms/{room_id}/agui/{thread_id}

Get thread details including all runs.

**Response:**
```json
{
  "room_id": "research",
  "thread_id": "thread-123",
  "created": "2024-01-15T10:30:00Z",
  "metadata": {
    "name": null,
    "description": null
  },
  "runs": {
    "run-1": {
      "run_id": "run-1",
      "thread_id": "thread-123",
      "created": "2024-01-15T10:30:00Z",
      "metadata": {
        "label": null
      }
    }
  }
}
```

### POST /v1/rooms/{room_id}/agui/{thread_id}

Create a new run in a thread.

**Request Body:**
```json
{
  "parent_run_id": "run-1",
  "metadata": {
    "label": null
  }
}
```

**Response:**
```json
{
  "thread_id": "thread-123",
  "run_id": "run-2",
  "parent_run_id": "run-1",
  "created": "2024-01-15T10:35:00Z",
  "finished": null,
  "metadata": {
    "label": null
  }
}
```

### POST /v1/rooms/{room_id}/agui/{thread_id}/meta

Update thread metadata.

**Request Body:**
```json
{
  "name": "Updated name",
  "description": "Updated description"
}
```

**Response:** 205 Reset Content

### GET /v1/rooms/{room_id}/agui/{thread_id}/{run_id}

Get run details including events.

**Response:**
```json
{
  "thread_id": "thread-123",
  "run_id": "run-1",
  "parent_run_id": null,
  "created": "2024-01-15T10:30:00Z",
  "finished": "2024-01-15T10:31:00Z",
  "run_input": {
    "messages": [...]
  },
  "events": [...],
  "metadata": {
    "label": null
  },
  "usage": {
    "input_tokens": 100,
    "output_tokens": 200,
    "requests": 1,
    "tool_calls": 2
  }
}
```

### POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}

Execute a run. Returns SSE stream of AG-UI events.

**Request Body:** AG-UI RunAgentInput
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What is RAG?"
    }
  ],
  "state": {}
}
```

**Response:** SSE stream (text/event-stream)
```
data: {"type": "RUN_STARTED", "run_id": "run-1", "thread_id": "thread-123"}

data: {"type": "TEXT_MESSAGE_START", "message_id": "msg-1"}

data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "RAG stands for..."}

data: {"type": "TEXT_MESSAGE_END"}

data: {"type": "RUN_FINISHED"}
```

Event type is identified via the `type` field in the JSON payload.

### POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta

Update run metadata.

**Request Body:**
```json
{
  "label": "Completed successfully"
}
```

**Response:** 205 Reset Content

### POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback

Submit or update feedback for a completed run.

**Request Body:**
```json
{
  "feedback": "positive",
  "reason": "Helpful response"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| feedback | string | Yes | Feedback value (e.g., "positive", "negative") |
| reason | string | No | Optional reason for the feedback |

**Response:** 205 Reset Content

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/rooms/haiku/agui/thread123/run456/feedback" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"feedback": "positive", "reason": "Helpful response"}'
```

### DELETE /v1/rooms/{room_id}/agui/{thread_id}

Delete a thread and all its runs.

**Response:** 204 No Content

---

## Completions Endpoints

OpenAI-compatible chat completions API.

### GET /v1/chat/completions

List available completion configurations.

**Response:**
```json
{
  "default": {
    "id": "default",
    "name": "Default Completion",
    "tools": {...},
    "agent": {...}
  }
}
```

### GET /v1/chat/completions/{completion_id}

Get a specific completion configuration.

**Response:**
```json
{
  "id": "default",
  "name": "Default Completion",
  "tools": {...},
  "agent": {...}
}
```

### POST /v1/chat/completions/{completion_id}

Execute a chat completion. Returns SSE stream.

**Request Body:**
```json
{
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true
}
```

**Response:** SSE stream (OpenAI format)
```
data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"Hello"}}]}
data: {"id":"chatcmpl-123","choices":[{"delta":{"content":"!"}}]}
data: [DONE]
```

---

## Quiz Endpoints

### GET /v1/rooms/{room_id}/quiz/{quiz_id}

Get a specific quiz for the room.

**Parameters:**
- `room_id` - Room identifier
- `quiz_id` - Quiz identifier

**Response:**
```json
{
  "id": "quiz-1",
  "title": "Knowledge Check",
  "randomize": true,
  "max_questions": 10,
  "questions": [...]
}
```

### POST /v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}

Submit an answer to a quiz question.

**Parameters:**
- `room_id` - Room identifier
- `quiz_id` - Quiz identifier
- `question_uuid` - Question UUID

**Request Body:**
```json
{
  "text": "User's answer text"
}
```

**Response:**
```json
{
  "correct": "true",
  "expected_output": "Expected answer"
}
```

---

## Installation Endpoint

### GET /v1/installation

Get installation configuration.

**Response:**
```json
{
  "id": "my-installation",
  "secrets": [...],
  "environment": {...},
  "haiku_rag_config_file": null,
  "agents": [...],
  "oidc_paths": [...],
  "room_paths": [...],
  "completion_paths": [...],
  "quizzes_paths": [...],
  "oidc_auth_systems": [...],
  "thread_persistence_dburi_sync": "sqlite:///...",
  "thread_persistence_dburi_async": "sqlite+aiosqlite:///..."
}
```

---

## Debug & Health Endpoints

### GET /ok

Process control health check endpoint.

**Response:** `200 OK` with text body `"ok"`

**Example:**
```bash
curl http://localhost:8000/api/ok
# ok
```

### GET /check-headers

Debug endpoint that echoes request headers. Useful for debugging authentication and proxy configurations.

**Response:**
```json
{
  "host": "localhost:8000",
  "user-agent": "curl/8.1.2",
  "accept": "*/*",
  "authorization": "Bearer eyJ..."
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common status codes:
- `400` - Bad request (invalid input)
- `401` - Unauthorized (missing or invalid token)
- `404` - Not found (room, thread, or resource doesn't exist)
- `500` - Internal server error

## Source Code

- Debug/health views: `src/soliplex/views/__init__.py`
- Auth views: `src/soliplex/views/auth.py`
- Room views: `src/soliplex/views/rooms.py`
- AGUI views: `src/soliplex/views/agui.py`
- Completions views: `src/soliplex/views/completions.py`
- Quiz views: `src/soliplex/views/quizzes.py`
- Installation views: `src/soliplex/views/installation.py`
