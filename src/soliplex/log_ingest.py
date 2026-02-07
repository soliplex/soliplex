"""Core mapping logic for log ingest: Pydantic models and OTel mapping."""

from __future__ import annotations

import datetime
from typing import Any

import pydantic
from opentelemetry._logs import SeverityNumber

LEVEL_TO_SEVERITY: dict[str, SeverityNumber] = {
    "trace": SeverityNumber.TRACE,
    "debug": SeverityNumber.DEBUG,
    "info": SeverityNumber.INFO,
    "warning": SeverityNumber.WARN,
    "error": SeverityNumber.ERROR,
    "fatal": SeverityNumber.FATAL,
}


class LogEntry(pydantic.BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str
    attributes: dict[str, Any] | None = None
    error: str | None = None
    stackTrace: str | None = None
    spanId: str | None = None
    traceId: str | None = None
    installId: str
    sessionId: str
    userId: str | None = None


class LogPayload(pydantic.BaseModel):
    logs: list[LogEntry]
    resource: dict[str, str]


def map_to_otel_kwargs(
    entry: LogEntry,
    server_received_at: datetime.datetime,
) -> dict[str, Any]:
    """Map a LogEntry to keyword arguments for Logger.emit()."""
    severity = LEVEL_TO_SEVERITY.get(
        entry.level.lower(),
        SeverityNumber.UNSPECIFIED,
    )

    attrs: dict[str, Any] = {
        "logger": entry.logger,
        "install_id": entry.installId,
        "session_id": entry.sessionId,
        "server.received_at": server_received_at.isoformat(),
    }

    if entry.userId is not None:
        attrs["user_id"] = entry.userId

    if entry.spanId is not None:
        attrs["span_id"] = entry.spanId

    if entry.traceId is not None:
        attrs["trace_id"] = entry.traceId

    if entry.error is not None:
        attrs["exception.message"] = entry.error

    if entry.stackTrace is not None:
        attrs["exception.stacktrace"] = entry.stackTrace

    if entry.attributes:
        for key, value in entry.attributes.items():
            attrs[key] = value

    ts = datetime.datetime.fromisoformat(entry.timestamp)
    timestamp_ns = int(ts.timestamp() * 1_000_000_000)

    return {
        "timestamp": timestamp_ns,
        "severity_number": severity,
        "severity_text": entry.level,
        "body": entry.message,
        "attributes": attrs,
    }


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

    if entry.spanId is not None:
        attrs["span_id"] = entry.spanId

    if entry.traceId is not None:
        attrs["trace_id"] = entry.traceId

    if entry.error is not None:
        attrs["exception.message"] = entry.error

    if entry.stackTrace is not None:
        attrs["exception.stacktrace"] = entry.stackTrace

    if entry.attributes:
        for key, value in entry.attributes.items():
            attrs[key] = value

    return attrs
