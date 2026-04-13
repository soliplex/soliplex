# Console Logging Configuration

## Configure Python logging with a YAML file

In addition to [logging to Logfire](logfire.md), you can
configure how the Soliplex application emits logs to its standard output,
using a separate YAML file.  E.g.:

```yaml
version: 1
disable_existing_loggers: false
formatters:

  default:
    format: "$asctime|$levelname|$name|$message"
    datefmt: "%Y-%m-%dT%H:%M:%S"
    style: "$"
    validate: true
    defaults:
        some_key: null

handlers:

  console:
    class: "logging.StreamHandler"
    formatter: "default"
    stream: "ext://sys.stdout"

root:
  level: "INFO"
  handlers:
    - "console"
```

See the
[Python docs](https://docs.python.org/3/library/logging.config.html#dictionary-schema-details)
for details on the schema for this file.

To use your file, start the Soliplex server, passing the filename as the
value of the `--log-config` argument, e.g.:

```bash
soliplex-cli serve example/minimal.yaml --log-config example/logging.yaml
2026-02-09T18:16:40|INFO|uvicorn.error|Started server process [112592]
2026-02-09T18:16:40|INFO|uvicorn.error|Waiting for application startup.
2026-02-09T18:16:40|INFO|docket.worker|Starting worker 'roan#112592' with the following tasks:
2026-02-09T18:16:40|INFO|docket.worker|* trace(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* fail(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* sleep(seconds: float, ...)
2026-02-09T18:16:40|INFO|mcp.server.streamable_http_manager|StreamableHTTP session manager started
2026-02-09T18:16:40|INFO|docket.worker|Starting worker 'roan#112592' with the following tasks:
2026-02-09T18:16:40|INFO|docket.worker|* trace(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* fail(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* sleep(seconds: float, ...)
2026-02-09T18:16:40|INFO|mcp.server.streamable_http_manager|StreamableHTTP session manager started
2026-02-09T18:16:40|INFO|docket.worker|Starting worker 'roan#112592' with the following tasks:
2026-02-09T18:16:40|INFO|docket.worker|* trace(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* fail(message: str, ...)
2026-02-09T18:16:40|INFO|docket.worker|* sleep(seconds: float, ...)
2026-02-09T18:16:40|INFO|mcp.server.streamable_http_manager|StreamableHTTP session manager started
2026-02-09T18:16:40|INFO|uvicorn.error|Application startup complete.
2026-02-09T18:16:40|INFO|uvicorn.error|Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

## Configure Logging `extra` Values from Request Headers

Request header values may be useful in logging:  for instance, if a proxy
running in front of the Soliplex server injects a header, `X-Request-ID`,
into each request, we might want to display that output in a formatted log
record.

To capture one or more header values, add a `logging_headers_map`
entry to your installation configuration:

```yaml
logging_headers_map:
  request_id: "X-Request-ID"
```

## Configure Logging `extra` Values from OIDC Claims

OIDC cliams values may be useful in logging:  for instance,
we might want to display that `email` claim of the authenticated user
in a formatted log record.

To capture one or more claims values, add a `logging_claims_map`
entry to your installation configuration:

```yaml
logging_claims_map:
  user_email: "email"
```
