"""Core mapping logic for log ingest: Pydantic models and Logfire mapping."""

from __future__ import annotations

import datetime
from typing import Any
from typing import Literal

import pydantic


class LogEntry(pydantic.BaseModel):
    timestamp: str
    level: Literal["trace", "debug", "info", "warning", "error", "fatal"]
    logger: str
    message: str
    attributes: dict[str, Any] | None = None
    installId: str
    sessionId: str
    userId: str | None = None


class LogPayload(pydantic.BaseModel):
    logs: list[LogEntry]
    resource: dict[str, str]


def map_to_logfire_attrs(
    entry: LogEntry,
    server_received_at: datetime.datetime,
) -> dict[str, Any]:
    """Map a LogEntry to attributes for logfire.log()."""
    attrs: dict[str, Any] = {
        "logger": entry.logger,
        "message": entry.message,
        "client_timestamp": entry.timestamp,
        "install_id": entry.installId,
        "session_id": entry.sessionId,
        "server.received_at": server_received_at.isoformat(),
    }

    if entry.userId is not None:
        attrs["user_id"] = entry.userId

    if entry.attributes:
        attrs.update(entry.attributes)

    return attrs
