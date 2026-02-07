"""Log ingest endpoint: receives structured logs from Flutter clients."""

from __future__ import annotations

import datetime

import fastapi
from opentelemetry._logs import get_logger_provider

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

    logger_provider = get_logger_provider()
    logger = logger_provider.get_logger("soliplex.log_ingest")

    for entry in payload.logs:
        kwargs = log_ingest.map_to_otel_kwargs(entry, server_received_at)
        logger.emit(**kwargs)

    return {"accepted": len(payload.logs)}
