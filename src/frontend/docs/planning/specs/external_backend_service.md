# Backend API Reference

Base URL: `http://localhost:8000`

All authenticated endpoints use `Authorization: Bearer <token>`.

## Authentication

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/login` | List OIDC providers |
| GET | `/api/login/{system}` | Initiate OIDC flow |
| GET | `/api/auth/{system}` | Complete OIDC flow (callback) |
| GET | `/api/user_info` | Get user profile |

## Rooms

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms` | List rooms |
| GET | `/api/v1/rooms/{room_id}` | Get room config |
| GET | `/api/v1/rooms/{room_id}/bg_image` | Get background image |
| GET | `/api/v1/rooms/{room_id}/mcp_token` | Get MCP token |
| GET | `/api/v1/rooms/{room_id}/documents` | List RAG documents |

## AGUI Threads

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms/{room_id}/agui` | List threads |
| POST | `/api/v1/rooms/{room_id}/agui` | Create thread → `{thread_id, runs: {run_id: ...}}` |
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Get thread + runs |
| DELETE | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Delete thread |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/meta` | Update metadata |

## AGUI Runs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Create run → `{run_id}` |
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Get run metadata |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Execute run (SSE stream) |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta` | Update metadata |

### Run Execution Request Body (RunAgentInput)

```json
{
  "threadId": "string",
  "runId": "string",
  "state": {},
  "messages": [{"id": "...", "role": "user|assistant", "content": "..."}],
  "tools": [],
  "context": []
}
```

### SSE Event Types

`RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`, `STEP_STARTED`, `STEP_FINISHED`, `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`, `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`, `TOOL_CALL_RESULT`, `STATE_SNAPSHOT`, `STATE_DELTA`, `MESSAGES_SNAPSHOT`, `ACTIVITY_SNAPSHOT`, `ACTIVITY_DELTA`

## Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/rooms/{room_id}/quiz/{quiz_id}` | Get quiz config |
| POST | `/api/v1/rooms/{room_id}/quiz/{quiz_id}/{question_uuid}` | Submit answer |
| GET | `/api/v1/installation` | Get installation config |
| GET | `/api/ok` | Health check |

## Reference

- OpenAPI docs: <http://localhost:8000/docs>
