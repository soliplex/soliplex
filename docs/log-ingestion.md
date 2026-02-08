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
      "spanId": "span-abc",
      "traceId": "trace-xyz",
      "error": null,
      "stackTrace": null,
      "attributes": {
        "http.method": "GET",
        "http.status_code": 200
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
| `level` | string | yes | `trace`, `debug`, `info`, `warning`, `error`, or `fatal` |
| `logger` | string | yes | Logger name (e.g., `HttpClient`, `AgentRunner`) |
| `message` | string | yes | Human-readable log message |
| `installId` | string | yes | Unique installation identifier |
| `sessionId` | string | yes | Unique session identifier |
| `userId` | string | no | User identifier |
| `spanId` | string | no | Client-side span ID for correlation |
| `traceId` | string | no | Client-side trace ID for correlation |
| `error` | string | no | Exception message |
| `stackTrace` | string | no | Exception stack trace |
| `attributes` | object | no | Arbitrary key-value metadata |

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

## Logfire mapping

Each log entry is emitted via `logfire.log()` with:

- **level** — mapped from `entry.level` (lowercased)
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
| `spanId` | `span_id` |
| `traceId` | `trace_id` |
| `error` | `exception.message` |
| `stackTrace` | `exception.stacktrace` |
| `attributes.*` | flattened into top-level attributes |
| *(server)* | `server.received_at` (ISO 8601) |
