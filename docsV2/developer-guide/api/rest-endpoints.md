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
    "display_name": "Google",
    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth"
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
    "description": "Research assistant room",
    "has_rag": true,
    "has_quizzes": false
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
  "description": "Research assistant room",
  "has_rag": true,
  "has_quizzes": false
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
        "title": "Research session"
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
    "title": "New research session"
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
    "title": "New research session"
  },
  "runs": {
    "run-1": {
      "run_id": "run-1",
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
  "metadata": {},
  "runs": {
    "run-1": {
      "run_id": "run-1",
      "created": "2024-01-15T10:30:00Z",
      "metadata": {}
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
  "metadata": {}
}
```

**Response:**
```json
{
  "room_id": "research",
  "thread_id": "thread-123",
  "run_id": "run-2",
  "parent_run_id": "run-1",
  "created": "2024-01-15T10:35:00Z"
}
```

### POST /v1/rooms/{room_id}/agui/{thread_id}/meta

Update thread metadata.

**Request Body:**
```json
{
  "title": "Updated title"
}
```

**Response:** 205 Reset Content

### GET /v1/rooms/{room_id}/agui/{thread_id}/{run_id}

Get run details including events.

**Response:**
```json
{
  "room_id": "research",
  "thread_id": "thread-123",
  "run_id": "run-1",
  "created": "2024-01-15T10:30:00Z",
  "run_input": {
    "messages": [...]
  },
  "events": [...]
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
event: RUN_STARTED
data: {"type": "RUN_STARTED", "run_id": "run-1"}

event: TEXT_MESSAGE_START
data: {"type": "TEXT_MESSAGE_START", "message_id": "msg-1"}

event: TEXT_MESSAGE_CONTENT
data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "RAG stands for..."}

event: TEXT_MESSAGE_END
data: {"type": "TEXT_MESSAGE_END"}

event: RUN_FINISHED
data: {"type": "RUN_FINISHED"}
```

### POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta

Update run metadata.

**Request Body:**
```json
{
  "status": "completed"
}
```

**Response:** 205 Reset Content

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
    "model_name": "gpt-oss:latest"
  }
}
```

### GET /v1/chat/completions/{completion_id}

Get a specific completion configuration.

**Response:**
```json
{
  "id": "default",
  "model_name": "gpt-oss:latest"
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

### GET /v1/rooms/{room_id}/quizzes

List available quizzes in a room.

### GET /v1/rooms/{room_id}/quizzes/{quiz_id}

Get a specific quiz.

---

## Installation Endpoint

### GET /v1/installation

Get installation configuration.

**Response:**
```json
{
  "id": "my-installation",
  "title": "Soliplex"
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

- Auth views: `src/soliplex/views/auth.py`
- Room views: `src/soliplex/views/rooms.py`
- AGUI views: `src/soliplex/views/agui.py`
- Completions views: `src/soliplex/views/completions.py`
