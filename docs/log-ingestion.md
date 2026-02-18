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
      "active_run": {"thread_id": "t-1", "run_id": "r-1"},
      "attributes": {
        "http.method": "GET",
        "http.status_code": 200,
        "http.request_id": "req-abc",
        "http.type": "request"
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
| `resource` | Object | Yes | Resource attributes. See below. |

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
| `active_run` | Object | No | Groups logs under an agent run. See below. |
| `attributes` | Object | No | Arbitrary key-value pairs for additional context. |

### Resource Keys

| Key | Description |
|---|---|
| `service.name` | Application name. |
| `device.alias` | Human-readable device name (e.g., `glad-raven-tundra`). Used as the top-level span label in Logfire. |

### `active_run`

When present, logs in the batch that share the same `run_id` are grouped under a collapsible **ActiveRun** span in Logfire.

| Field | Type | Required | Description |
|---|---|---|---|
| `thread_id` | String | Yes | Thread identifier for the agent run. |
| `run_id` | String | Yes | Unique run identifier. |

### Attribute Conventions

The `attributes` object can contain arbitrary data. Use these conventional keys where applicable:

| Key | Description |
|---|---|
| `span_id` | Client-side span ID |
| `trace_id` | Client-side trace ID |
| `exception.message` | Exception message text |
| `exception.stacktrace` | Full exception stack trace |

#### HTTP Pairing

HTTP request/response logs can be paired by setting `http.request_id` and `http.type`. When a batch contains a request and its matching response (or error), the response is nested under the request span in Logfire.

| Key | Description |
|---|---|
| `http.request_id` | Shared ID linking a request to its response. |
| `http.type` | One of: `request`, `response`, `error`. |
| `http.method` | HTTP method (e.g., `GET`). |
| `http.status_code` | HTTP status code (e.g., `200`). |

## Logfire

This endpoint creates its own structured spans (ActiveRun bucketing, HTTP
request/response pairing) so the auto-generated FastAPI span is redundant.
To suppress it, add the endpoint to `excluded_urls` in your installation YAML:

```yaml
logfire:
  instrument_fast_api:
    excluded_urls:
      - "/api/v1/logs"
```

## Responses

### 200 OK

```json
{"accepted": 1}
```

### Errors

- **401 Unauthorized:** Missing or invalid bearer token.
- **413 Payload Too Large:** Body exceeds 1 MB.
- **422 Unprocessable Entity:** Malformed body or invalid field value (e.g., unknown `level`).
