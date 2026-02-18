"""Log ingest endpoint: receives structured logs from Flutter clients."""

from __future__ import annotations

import datetime
from collections import defaultdict

import fastapi
import logfire

from soliplex import authn
from soliplex import installation
from soliplex import log_ingest
from soliplex import loggers
from soliplex import views

router = fastapi.APIRouter(tags=["telemetry"])

depend_the_installation = installation.depend_the_installation
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger

MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


def _emit_entry(
    entry: log_ingest.LogEntry,
    server_received_at: datetime.datetime,
) -> None:
    """Emit a single log entry to Logfire."""
    attrs = log_ingest.map_to_logfire_attrs(entry, server_received_at)
    msg = entry.logger + ": " + entry.message
    logfire.log(
        level=entry.level.lower(),
        msg_template=msg,
        attributes=attrs,
        tags=["client"],
        console_log=False,
    )


def _emit_entries(
    entries: list[log_ingest.LogEntry],
    server_received_at: datetime.datetime,
) -> None:
    """Emit entries with HTTP request/response nesting.

    HTTP response and error logs are nested under their corresponding
    request log via ``http.request_id``. Non-HTTP entries and unpaired
    entries are emitted flat.
    """
    # Separate HTTP entries by request_id for pairing.
    http_requests: dict[str, log_ingest.LogEntry] = {}
    http_children: dict[str, list[log_ingest.LogEntry]] = defaultdict(list)
    other: list[log_ingest.LogEntry] = []

    for entry in entries:
        request_id = (entry.attributes or {}).get("http.request_id")
        http_type = (entry.attributes or {}).get("http.type")

        if request_id and http_type == "request":
            http_requests[request_id] = entry
        elif request_id and http_type in ("response", "error"):
            http_children[request_id].append(entry)
        else:
            other.append(entry)

    # Emit HTTP request spans with nested response/error children.
    emitted_request_ids: set[str] = set()
    for entry in entries:
        request_id = (entry.attributes or {}).get("http.request_id")
        http_type = (entry.attributes or {}).get("http.type")

        if request_id and http_type == "request":
            emitted_request_ids.add(request_id)
            children = http_children.get(request_id, [])
            if children:
                attrs = log_ingest.map_to_logfire_attrs(
                    entry,
                    server_received_at,
                )
                with logfire.span(
                    entry.logger + ": " + entry.message,
                    **attrs,
                    _tags=["client"],
                ):
                    for child in children:
                        _emit_entry(child, server_received_at)
            else:
                _emit_entry(entry, server_received_at)

        elif request_id and http_type in ("response", "error"):
            # Skip — already emitted as child of its request span.
            if request_id in emitted_request_ids:
                continue
            # Orphaned response (request was in a previous batch).
            _emit_entry(entry, server_received_at)

        else:
            _emit_entry(entry, server_received_at)


# No @logfire.span decorator: this endpoint creates its own manual
# spans below for structured nesting (ActiveRun bucketing, HTTP
# pairing).  To avoid a redundant auto-generated span, add
# "/api/v1/logs" to logfire.instrument_fast_api.excluded_urls in
# your installation YAML.
@router.post("/v1/logs", status_code=200)
async def ingest_logs(
    request: fastapi.Request,
    payload: log_ingest.LogPayload,
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> dict:
    """Accept structured log records from Flutter clients."""
    the_logger.debug(loggers.LOG_INGEST_INGEST_LOGS)

    content_length = request.headers.get("content-length")

    if content_length is not None and int(content_length) > MAX_PAYLOAD_BYTES:
        the_logger.error(loggers.LOG_INGEST_PAYLOAD_TOO_BIG)
        raise fastapi.HTTPException(
            status_code=413,
            detail=loggers.LOG_INGEST_PAYLOAD_TOO_BIG,
        )

    server_received_at = datetime.datetime.now(datetime.UTC)

    first = payload.logs[0] if payload.logs else None
    device_alias = payload.resource.get("device.alias", "unknown")
    with logfire.span(
        "client: " + device_alias,
        device_alias=device_alias,
        install_id=first.install_id if first else "",
        session_id=first.session_id if first else "",
        count=len(payload.logs),
    ):
        # Group entries by active run.
        run_buckets: dict[str | None, list[log_ingest.LogEntry]] = defaultdict(
            list,
        )
        for entry in payload.logs:
            run_id = entry.active_run.run_id if entry.active_run else None
            run_buckets[run_id].append(entry)

        for run_id, entries in run_buckets.items():
            if run_id is not None:
                run = entries[0].active_run
                assert run is not None  # noqa: S101 — guaranteed by grouping
                with logfire.span(
                    "ActiveRun",
                    thread_id=run.thread_id,
                    run_id=run.run_id,
                ):
                    _emit_entries(entries, server_received_at)
            else:
                _emit_entries(entries, server_received_at)

    return {"accepted": len(payload.logs)}
