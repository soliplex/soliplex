# Server API Reference

API documentation generated from source code.

## Overview

The Soliplex server provides a REST API at `/api/` with the following modules:

| Module | Base Path | Description |
|--------|-----------|-------------|
| Auth | `/login`, `/auth`, `/user_info` | OIDC authentication |
| Rooms | `/v1/rooms` | Room management |
| AG-UI | `/v1/rooms/{id}/agui` | Thread and run management |
| Quizzes | `/v1/rooms/{id}/quiz` | Quiz management |
| Completions | `/v1/chat/completions` | OpenAI-compatible API |
| Installation | `/v1/installation` | Installation info |

**Note:** Auth endpoints use `/api/` directly, while other endpoints use `/api/v1/`.

## Authentication

All `/v1/*` endpoints require a Bearer token:

```
Authorization: Bearer <token>
```

Tokens are obtained via the OIDC flow:
1. `GET /login` - List providers
2. `GET /login/{system}` - Initiate auth
3. `GET /auth/{system}` - Complete auth (callback)

## Endpoints Summary

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/login` | List OIDC providers |
| GET | `/login/{system}` | Initiate OIDC flow |
| GET | `/auth/{system}` | Complete OIDC flow |
| GET | `/user_info` | Get user profile |

### Rooms

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/rooms` | List available rooms |
| GET | `/v1/rooms/{id}` | Get room details |
| GET | `/v1/rooms/{id}/bg_image` | Get room logo |
| GET | `/v1/rooms/{id}/mcp_token` | Get MCP access token |
| GET | `/v1/rooms/{id}/documents` | List RAG documents |
| GET | `/v1/rooms/{id}/chunk/{chunk_id}` | Get chunk visualization |

### AG-UI (Threads)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/rooms/{id}/agui` | List threads |
| POST | `/v1/rooms/{id}/agui` | Create thread |
| GET | `/v1/rooms/{id}/agui/{thread_id}` | Get thread |
| POST | `/v1/rooms/{id}/agui/{thread_id}` | Create run |
| POST | `/v1/rooms/{id}/agui/{thread_id}/meta` | Update thread metadata |
| DELETE | `/v1/rooms/{id}/agui/{thread_id}` | Delete thread |

### AG-UI (Runs)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/rooms/{id}/agui/{thread_id}/{run_id}` | Get run |
| POST | `/v1/rooms/{id}/agui/{thread_id}/{run_id}` | Execute run (SSE) |
| POST | `/v1/rooms/{id}/agui/{thread_id}/{run_id}/meta` | Update run metadata |

### Completions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/chat/completions` | List completions |
| GET | `/v1/chat/completions/{id}` | Get completion |
| POST | `/v1/chat/completions/{id}` | Execute (SSE) |

### Quizzes

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/rooms/{id}/quiz/{quiz_id}` | Get quiz details |
| POST | `/v1/rooms/{id}/quiz/{quiz_id}/{question_uuid}` | Submit quiz answer |

### Installation

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/installation` | Get installation info |

## Response Formats

### Success Response

```json
{
  "id": "research",
  "name": "Research Assistant",
  "description": "AI-powered research"
}
```

### Error Response

```json
{
  "detail": "Error message"
}
```

### SSE Stream

```
event: RUN_STARTED
data: {"type": "RUN_STARTED", "run_id": "..."}

event: TEXT_MESSAGE_CONTENT
data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}

event: RUN_FINISHED
data: {"type": "RUN_FINISHED"}
```

## Rate Limiting

No built-in rate limiting. Implement at reverse proxy level.

## CORS

CORS is configured to allow the Flutter frontend. Customize for other clients.

## Source Files

| Module | Source File |
|--------|-------------|
| Auth | `src/soliplex/views/auth.py` |
| Rooms | `src/soliplex/views/rooms.py` |
| AG-UI | `src/soliplex/views/agui.py` |
| Quizzes | `src/soliplex/views/quizzes.py` |
| Completions | `src/soliplex/views/completions.py` |
| Installation | `src/soliplex/views/installation.py` |

## OpenAPI Schema

Access the auto-generated OpenAPI schema at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc
- `/openapi.json` - Raw schema
