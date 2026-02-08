# Log Ingestion

The log ingestion endpoint accepts structured log batches from clients
and forwards them to [Logfire](https://logfire.pydantic.dev/) for
observability.

## Endpoint

```
POST /api/v1/logs
```

**Authentication:** Bearer token (JWT) via `Authorization` header.

**Content-Type:** `application/json`

**Payload limit:** 1 MB (`Content-Length` checked; returns `413` if exceeded).

## Request body

```json
{
  "logs": [
    {
      "timestamp": "2026-02-07T12:00:00Z",
      "level": "info",
      "logger": "HttpClient",
      "message": "GET /api/v1/rooms 200",
      "installId": "inst-abc",
      "sessionId": "sess-def",
      "userId": "u-123",
      "attributes": {
        "http.method": "GET",
        "http.status_code": 200,
        "span_id": "span-abc",
        "trace_id": "trace-xyz"
      }
    }
  ],
  "resource": {
    "service.name": "my-client-app",
    "device.alias": "glad-raven-tundra"
  }
}
```

### `LogEntry` fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string (ISO 8601) | yes | Client-side timestamp |
| `level` | string | yes | One of: `trace`, `debug`, `info`, `warning`, `error`, `fatal` |
| `logger` | string | yes | Logger name (e.g., `HttpClient`, `AgentRunner`) |
| `message` | string | yes | Human-readable log message |
| `installId` | string | yes | Unique installation identifier |
| `sessionId` | string | yes | Unique session identifier |
| `userId` | string | no | User identifier |
| `attributes` | object | no | Arbitrary key-value metadata (see conventions below) |

#### Attribute conventions

Clients can pass any key-value pairs in `attributes`. The following
keys have conventional meaning in Logfire:

| Key | Description |
|-----|-------------|
| `exception.message` | Exception message |
| `exception.stacktrace` | Exception stack trace |
| `span_id` | Client-side span ID for correlation |
| `trace_id` | Client-side trace ID for correlation |
| `http.method` | HTTP method |
| `http.status_code` | HTTP status code |

### `LogPayload` fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `logs` | array of `LogEntry` | yes | Log entries (may be empty) |
| `resource` | object | yes | Resource attributes (e.g., `service.name`, `device.alias`) |

## Response

**200 OK:**

```json
{"accepted": 3}
```

**401 Unauthorized:** Invalid or missing JWT.

**413 Payload Too Large:** Body exceeds 1 MB.

**422 Unprocessable Entity:** Invalid request body (e.g., unknown `level` value).

## Logfire mapping

Each log entry is emitted via `logfire.log()` with:

- **level** — mapped from `entry.level`
- **msg_template** — `"{logger}: {message}"`
- **tags** — `["client"]` (use this to filter client logs in the Logfire UI)
- **console_log** — `False` (suppresses server-side stdout echo)

The full batch is wrapped in a `client_log_batch` span containing
`install_id`, `session_id`, and `count`.

### Attribute mapping

| LogEntry field | Logfire attribute |
|----------------|-------------------|
| `timestamp` | `client_timestamp` |
| `logger` | `logger` |
| `message` | `message` |
| `installId` | `install_id` |
| `sessionId` | `session_id` |
| `userId` | `user_id` |
| `attributes.*` | flattened into top-level attributes |
| *(server)* | `server.received_at` (ISO 8601) |
