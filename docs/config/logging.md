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

## CLI Audit Logging

Privileged `soliplex-cli` operations (the `admin-users` and `room-authz`
mutations and security-object reads) emit audit records to the dedicated
`soliplex-audit` logger, the same way the REST API does. By default the CLI
**suppresses** these records so they do not intermingle with normal command
output during interactive use — the installation's own `logging_config_file`
(which typically targets `sys.stdout`, for the *server*) is deliberately
**not** applied to the CLI.

To capture the CLI audit trail, pass a dedicated
Python logging-config YAML — one that routes the `soliplex-audit`
logger to the appropriate sink — via the `--cli-log-config` option
(or set the `SOLIPLEX_CLI_LOG_CONFIG` environment variable).

The option is a **group-level** option on the `admin-users`, `room-authz`,
and `audit` command groups, so it must appear **before** the subcommand name:

```bash
# via the option (before the subcommand):
soliplex-cli room-authz --cli-log-config cli-audit-logging.yaml \
    make-private example/minimal.yaml faux

# or via the environment variable:
SOLIPLEX_CLI_LOG_CONFIG=cli-audit-logging.yaml \
    soliplex-cli admin-users add example/minimal.yaml alice@example.com
```

Example audit log config:

```yaml
# cli-audit-logging.yaml
version: 1
disable_existing_loggers: false
formatters:
  audit:
    format: "%(asctime)s|%(levelname)s|%(outcome)s|%(message)s"
handlers:
  audit_file:
    class: "logging.FileHandler"
    filename: "/var/log/soliplex/audit.log"
    formatter: "audit"
loggers:
  soliplex-audit:
    level: "INFO"
    handlers: ["audit_file"]
    propagate: false
```

Each record carries an `outcome` field (`success`, `denied`, or `error`)
and an `audit-scope` field, so failed and denied operations are audited
alongside successful ones.

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

OIDC claims values may be useful in logging:  for instance,
we might want to display that `email` claim of the authenticated user
in a formatted log record.

To capture one or more claims values, add a `logging_claims_map`
entry to your installation configuration:

```yaml
logging_claims_map:
  user_email: "email"
```
