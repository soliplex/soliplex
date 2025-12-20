# API Reference

Soliplex exposes a REST API for all client interactions. This section documents the endpoints, protocols, and data models.

## Overview

| Aspect | Details |
|--------|---------|
| **Base URL** | `http://localhost:8000/api/v1/` |
| **Authentication** | Bearer token (OAuth2) |
| **Streaming** | Server-Sent Events (SSE) |
| **Protocol** | AG-UI for agent streaming |

## Sections

- **[REST Endpoints](rest-endpoints.md)** - Complete endpoint documentation (25 endpoints)
- **[AG-UI Protocol](agui-protocol.md)** - Streaming protocol for agent events
- **[Models](models.md)** - Request/response Pydantic models

## Quick Reference

### Authentication

All endpoints except `/login/*` and `/auth/*` require Bearer token:

```http
GET /api/v1/rooms HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

### Endpoint Summary

| Module | Count | Key Endpoints |
|--------|-------|---------------|
| **AGUI** | 9 | Thread/run management |
| **Rooms** | 6 | Room config, documents, chunks, images |
| **Completions** | 3 | OpenAI-compatible completions |
| **Auth** | 4 | OIDC flow, user info |
| **Quizzes** | 2 | Quiz access |
| **Installation** | 1 | Server config |

### Core Endpoints

```http
# List rooms
GET /api/v1/rooms

# Create thread
POST /api/v1/rooms/{room_id}/agui
Content-Type: application/json
{"metadata": {"name": "My Thread"}}

# Execute run (SSE stream)
POST /api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}
Accept: text/event-stream
```

### Response Patterns

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 204 | Deleted successfully |
| 205 | Metadata updated |
| 400 | Bad request |
| 401 | Unauthorized |
| 404 | Not found |

## Streaming Responses

AGUI run execution returns Server-Sent Events:

```
data: {"type": "TEXT_MESSAGE_START", "message_id": "msg-1"}

data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}

data: {"type": "TEXT_MESSAGE_END"}

data: {"type": "RUN_FINISHED"}
```

Event type is identified via the `type` field in the JSON payload.

## Source Files

| File | Purpose |
|------|---------|
| `src/soliplex/views/agui.py` | AGUI endpoints |
| `src/soliplex/views/rooms.py` | Room endpoints |
| `src/soliplex/views/completions.py` | Completions endpoints |
| `src/soliplex/views/auth.py` | Auth endpoints |
| `src/soliplex/views/quizzes.py` | Quiz endpoints |
| `src/soliplex/views/installation.py` | Installation endpoint |
| `src/soliplex/models.py` | Pydantic models |
