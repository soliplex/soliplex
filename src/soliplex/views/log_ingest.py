"""Log ingest endpoint: receives structured logs from Flutter clients."""

from __future__ import annotations

import datetime

import fastapi
import logfire

from soliplex import authn
from soliplex import installation
from soliplex import log_ingest
from soliplex import loggers
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["telemetry"])

depend_the_installation = installation.depend_the_installation
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger

MAX_PAYLOAD_BYTES = 1_048_576  # 1 MB


@util.logfire_span("POST /v1/logs")
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
