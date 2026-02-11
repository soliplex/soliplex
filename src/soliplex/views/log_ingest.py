"""Log ingest endpoint: receives structured logs from Flutter clients."""

from __future__ import annotations

import datetime

import fastapi
import logfire

from soliplex import authn
from soliplex import installation
from soliplex import log_ingest
from soliplex import util

router = fastapi.APIRouter(tags=["telemetry"])

depend_the_installation = installation.depend_the_installation

MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


@util.logfire_span("POST /v1/logs")
@router.post("/v1/logs", status_code=200)
async def ingest_logs(
    request: fastapi.Request,
    payload: log_ingest.LogPayload,
    the_installation: installation.Installation = depend_the_installation,
    token: str = authn.oauth2_predicate,
) -> dict:
    """Accept structured log records from Flutter clients."""
    authn.authenticate(the_installation, token)

    content_length = request.headers.get("content-length")

    if content_length is not None and int(content_length) > MAX_PAYLOAD_BYTES:
        raise fastapi.HTTPException(
            status_code=413,
            detail="Payload too large",
        )

    server_received_at = datetime.datetime.now(datetime.UTC)

    first = payload.logs[0] if payload.logs else None
    with logfire.span(
        "client_log_batch",
        install_id=first.install_id if first else "",
        session_id=first.session_id if first else "",
        count=len(payload.logs),
    ):
        for entry in payload.logs:
            attrs = log_ingest.map_to_logfire_attrs(entry, server_received_at)
            msg = entry.logger + ": " + entry.message
            logfire.log(
                level=entry.level.lower(),
                msg_template=msg,
                attributes=attrs,
                tags=["client"],
                console_log=False,
            )

    return {"accepted": len(payload.logs)}
