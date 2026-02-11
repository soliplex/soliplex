import datetime

import pydantic
import pytest

from soliplex import log_ingest

ENTRY_KWARGS = {
    "timestamp": "2026-02-07T12:00:00Z",
    "level": "info",
    "logger": "TestLogger",
    "message": "hello world",
    "install_id": "inst-abc",
    "session_id": "sess-def",
}

SERVER_TIME = datetime.datetime(2026, 2, 7, 12, 0, 1, tzinfo=datetime.UTC)


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

    def test_with_user_id(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS, user_id="u-123")
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["user_id"] == "u-123"

    def test_null_user_id(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS, user_id=None)
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert "user_id" not in result

    def test_with_attributes(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            attributes={"custom.key": "custom_value", "count": 42},
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["custom.key"] == "custom_value"
        assert result["count"] == 42

    def test_error_via_attributes(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            attributes={
                "exception.message": "NullPointerException",
                "exception.stacktrace": "at com.example.Main:42",
            },
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["exception.message"] == "NullPointerException"
        assert result["exception.stacktrace"] == "at com.example.Main:42"

    def test_span_and_trace_via_attributes(self):
        entry = log_ingest.LogEntry(
            **ENTRY_KWARGS,
            attributes={"span_id": "span-abc", "trace_id": "trace-xyz"},
        )
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["span_id"] == "span-abc"
        assert result["trace_id"] == "trace-xyz"

    def test_server_received_at_stamped(self):
        entry = log_ingest.LogEntry(**ENTRY_KWARGS)
        result = log_ingest.map_to_logfire_attrs(entry, SERVER_TIME)

        assert result["server.received_at"] == "2026-02-07T12:00:01+00:00"


class TestLogEntryValidation:
    def test_rejects_invalid_level(self):
        with pytest.raises(pydantic.ValidationError):
            log_ingest.LogEntry(**{**ENTRY_KWARGS, "level": "verbose"})

    def test_accepts_all_valid_levels(self):
        for level in ("trace", "debug", "info", "warning", "error", "fatal"):
            entry = log_ingest.LogEntry(**{**ENTRY_KWARGS, "level": level})
            assert entry.level == level

    def test_rejects_missing_required(self):
        with pytest.raises(pydantic.ValidationError):
            log_ingest.LogEntry(
                timestamp="2026-02-07T12:00:00Z",
                level="info",
                # missing logger, message, install_id, session_id
            )


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

    def test_rejects_missing_logs_key(self):
        with pytest.raises(pydantic.ValidationError):
            log_ingest.LogPayload(
                resource={"service.name": "test"},
            )
