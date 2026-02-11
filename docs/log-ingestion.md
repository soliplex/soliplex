# Log Ingestion

Accepts batches of structured logs from clients for observability.

## Endpoint

- **Method:** `POST`
- **Path:** `/api/v1/logs`
- **Authentication:** `Authorization: Bearer <JWT>`
- **Content-Type:** `application/json`
- **Body Limit:** 1 MB

## Request Body

```json
{
  "logs": [
    {
      "timestamp": "2026-02-07T12:00:00Z",
      "level": "info",
      "logger": "HttpClient",
      "message": "GET /api/v1/rooms 200",
      "install_id": "inst-abc",
      "session_id": "sess-def",
      "user_id": "u-123",
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

### Top-Level Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `logs` | Array of `LogEntry` | Yes | Log entries. May be empty. |
| `resource` | Object | Yes | Key-value attributes describing the client application. |

### `LogEntry` Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `timestamp` | String (ISO 8601) | Yes | Client-side timestamp. |
| `level` | String | Yes | One of: `trace`, `debug`, `info`, `warning`, `error`, `fatal`. |
| `logger` | String | Yes | Logger name (e.g., `HttpClient`, `AgentRunner`). |
| `message` | String | Yes | The log message. |
| `install_id` | String | Yes | Unique identifier for the client installation. |
| `session_id` | String | Yes | Unique identifier for the client session. |
| `user_id` | String | No | Identifier for the authenticated user. |
| `attributes` | Object | No | Arbitrary key-value pairs for additional context. |

#### Attribute Conventions

The `attributes` object can contain arbitrary data. Use these conventional keys where applicable:

| Key | Description |
|---|---|
| `span_id` | Client-side span ID |
| `trace_id` | Client-side trace ID |
| `http.method` | HTTP method (e.g., `GET`) |
| `http.status_code` | HTTP status code (e.g., `200`) |
| `exception.message` | Exception message text |
| `exception.stacktrace` | Full exception stack trace |

## Responses

### 200 OK

```json
{"accepted": 1}
```

### Errors

- **401 Unauthorized:** Missing or invalid bearer token.
- **413 Payload Too Large:** Body exceeds 1 MB.
- **422 Unprocessable Entity:** Malformed body or invalid field value (e.g., unknown `level`).
