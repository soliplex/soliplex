import datetime

import pydantic
import pytest
from opentelemetry._logs import SeverityNumber

from soliplex import log_ingest


class TestLevelToSeverity:
    def test_trace(self):
        assert log_ingest.LEVEL_TO_SEVERITY["trace"] is SeverityNumber.TRACE

    def test_debug(self):
        assert log_ingest.LEVEL_TO_SEVERITY["debug"] is SeverityNumber.DEBUG

    def test_info(self):
        assert log_ingest.LEVEL_TO_SEVERITY["info"] is SeverityNumber.INFO

    def test_warning(self):
        assert log_ingest.LEVEL_TO_SEVERITY["warning"] is SeverityNumber.WARN

    def test_error(self):
        assert log_ingest.LEVEL_TO_SEVERITY["error"] is SeverityNumber.ERROR

    def test_fatal(self):
        assert log_ingest.LEVEL_TO_SEVERITY["fatal"] is SeverityNumber.FATAL

    def test_unknown_level_returns_unspecified(self):
        result = log_ingest.LEVEL_TO_SEVERITY.get(
            "bogus", SeverityNumber.UNSPECIFIED
        )
        assert result is SeverityNumber.UNSPECIFIED


ENTRY_KWARGS = {
    "timestamp": "2026-02-07T12:00:00Z",
    "level": "info",
    "logger": "TestLogger",
    "message": "hello world",
    "installId": "inst-abc",
    "sessionId": "sess-def",
}

SERVER_TIME = datetime.datetime(2026, 2, 7, 12, 0, 1, tzinfo=datetime.UTC)


class TestMapToOtelKwargs:
    def test_basic(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS)
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["severity_number"] is SeverityNumber.INFO
        assert result["severity_text"] == "info"
        assert result["body"] == "hello world"
        assert result["attributes"]["logger"] == "TestLogger"
        assert result["attributes"]["install_id"] == "inst-abc"
        assert result["attributes"]["session_id"] == "sess-def"
        assert (
            result["attributes"]["server.received_at"]
            == SERVER_TIME.isoformat()
        )
        assert isinstance(result["timestamp"], int)
        assert result["timestamp"] > 0

    def test_with_error(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            error="NullPointerException",
            stackTrace="at com.example.Main:42",
        )
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert (
            result["attributes"]["exception.message"] == "NullPointerException"
        )
        assert (
            result["attributes"]["exception.stacktrace"]
            == "at com.example.Main:42"
        )

    def test_null_userId(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS, userId=None)
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert "user_id" not in result["attributes"]

    def test_with_userId(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS, userId="u-123")
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["attributes"]["user_id"] == "u-123"

    def test_with_attributes(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            attributes={"custom.key": "custom_value", "count": 42},
        )
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["attributes"]["custom.key"] == "custom_value"
        assert result["attributes"]["count"] == 42

    def test_server_received_at_stamped(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS)
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert "server.received_at" in result["attributes"]
        assert (
            result["attributes"]["server.received_at"]
            == "2026-02-07T12:00:01+00:00"
        )

    def test_unknown_level(self):
        entry = log_ingest.LogEntry(**{**ENTRY_KWARGS, "level": "verbose"})
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["severity_number"] is SeverityNumber.UNSPECIFIED
        assert result["severity_text"] == "verbose"

    def test_case_insensitive_level(self):
        entry = log_ingest.LogEntry(**{**ENTRY_KWARGS, "level": "INFO"})
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["severity_number"] is SeverityNumber.INFO

    def test_with_span_and_trace_ids(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            spanId="span-abc",
            traceId="trace-xyz",
        )
        result = log_ingest.map_to_otel_kwargs(entry, SERVER_TIME)

        assert result["attributes"]["span_id"] == "span-abc"
        assert result["attributes"]["trace_id"] == "trace-xyz"


class TestMapToLogfireAttrs:
    def test_basic(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS)
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["logger"] == "TestLogger"
        assert result["message"] == "hello world"
        assert result["client_timestamp"] == "2026-02-07T12:00:00Z"
        assert result["install_id"] == "inst-abc"
        assert result["session_id"] == "sess-def"
        assert result["server.received_at"] == SERVER_TIME.isoformat()

    def test_with_userId(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS, userId="u-123")
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["user_id"] == "u-123"

    def test_with_span_and_trace_ids(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            spanId="span-abc",
            traceId="trace-xyz",
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["span_id"] == "span-abc"
        assert result["trace_id"] == "trace-xyz"

    def test_with_error(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            error="NullPointerException",
            stackTrace="at com.example.Main:42",
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["exception.message"] == "NullPointerException"
        assert result["exception.stacktrace"] == "at com.example.Main:42"

    def test_with_attributes(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            attributes={"custom.key": "custom_value", "count": 42},
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["custom.key"] == "custom_value"
        assert result["count"] == 42


class TestLogPayloadValidation:
    def test_valid_payload(self):
        payload = log_ingest.LogPayload(
            logs=[log_ingest.LogEntry(**ENTRY_KWARGS)],
            resource={"service.name": "test"},
        )

        assert len(payload.logs) == 1
        assert payload.resource["service.name"] == "test"

    def test_empty_logs(self):
        payload = log_ingest.LogPayload(
            logs=[],
            resource={"service.name": "test"},
        )

        assert len(payload.logs) == 0

    def test_rejects_missing_required(self):
        with pytest.raises(pydantic.ValidationError):
            log_ingest.LogEntry(
                timestamp="2026-02-07T12:00:00Z",
                level="info",
                # missing logger, message, installId, sessionId
            )

    def test_rejects_missing_logs_key(self):
        with pytest.raises(pydantic.ValidationError):
            log_ingest.LogPayload(
                resource={"service.name": "test"},
            )
