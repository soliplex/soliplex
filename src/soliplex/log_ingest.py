"""Core mapping logic for log ingest: Pydantic models and Logfire mapping."""

from __future__ import annotations

import datetime
from typing import Any
from typing import Literal

import pydantic


class ActiveRun(pydantic.BaseModel):
    thread_id: str
    run_id: str


class LogEntry(pydantic.BaseModel):
    timestamp: str
    level: Literal["trace", "debug", "info", "warning", "error", "fatal"]
    logger: str
    message: str
    attributes: dict[str, Any] | None = None
    install_id: str
    session_id: str
    user_id: str | None = None
    active_run: ActiveRun | None = None


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
        "install_id": entry.install_id,
        "session_id": entry.session_id,
        "server.received_at": server_received_at.isoformat(),
    }

    if entry.user_id is not None:
        attrs["user_id"] = entry.user_id

    if entry.active_run is not None:
        attrs["thread_id"] = entry.active_run.thread_id
        attrs["run_id"] = entry.active_run.run_id

    if entry.attributes:
        attrs.update(entry.attributes)

    return attrs
