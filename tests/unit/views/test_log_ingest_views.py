import datetime
from unittest import mock

import fastapi
import pytest

from soliplex import installation
from soliplex import log_ingest
from soliplex import loggers
from soliplex.views import log_ingest as log_ingest_views

ENTRY_KWARGS = {
    "timestamp": "2026-02-07T12:00:00Z",
    "level": "info",
    "logger": "TestLogger",
    "message": "hello world",
    "install_id": "inst-abc",
    "session_id": "sess-def",
}

USER_EMAIL = "user@example.com"
THE_USER_CLAIMS = {
    "email": USER_EMAIL,
}


def _make_payload(n_entries=1):
    return log_ingest.LogPayload(
        logs=[log_ingest.LogEntry(**ENTRY_KWARGS) for _ in range(n_entries)],
        resource={"service.name": "test"},
    )


def _make_request(content_length=None):
    request = mock.create_autospec(fastapi.Request)
    headers = {}

    if content_length is not None:
        headers["content-length"] = str(content_length)

    request.headers = headers
    return request


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_ingest_logs_success(mock_logfire):
    payload = _make_payload(2)
    request = _make_request(content_length=100)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 2}
    assert mock_logfire.log.call_count == 2

    the_logger.debug.assert_called_once_with(
        loggers.LOG_INGEST_INGEST_LOGS,
    )
    the_logger.error.assert_not_called()


@pytest.mark.anyio
async def test_ingest_logs_payload_too_large():
    payload = _make_payload()
    request = _make_request(
        content_length=log_ingest_views.MAX_PAYLOAD_BYTES + 1,
    )
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with pytest.raises(fastapi.HTTPException) as exc:
        await log_ingest_views.ingest_logs(
            request,
            payload=payload,
            the_installation=the_installation,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    assert exc.value.status_code == 413

    the_logger.debug.assert_called_once_with(
        loggers.LOG_INGEST_INGEST_LOGS,
    )
    the_logger.error.assert_called_once_with(
        loggers.LOG_INGEST_PAYLOAD_TOO_BIG,
    )


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_ingest_logs_empty_logs(mock_logfire):
    payload = _make_payload(0)
    request = _make_request(content_length=50)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 0}
    mock_logfire.log.assert_not_called()

    the_logger.debug.assert_called_once_with(
        loggers.LOG_INGEST_INGEST_LOGS,
    )
    the_logger.error.assert_not_called()


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
@mock.patch("soliplex.log_ingest.map_to_logfire_attrs")
async def test_ingest_logs_logfire_mapping_called(map_fn, mock_logfire):
    payload = _make_payload(3)
    request = _make_request(content_length=200)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    map_fn.return_value = {
        "logger": "TestLogger",
        "message": "test",
        "client_timestamp": "2026-02-07T12:00:00Z",
        "install_id": "inst-abc",
        "session_id": "sess-def",
        "server.received_at": "2026-02-07T12:00:00+00:00",
    }

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 3}
    assert map_fn.call_count == 3

    for call in map_fn.call_args_list:
        entry, server_time = call.args
        assert isinstance(entry, log_ingest.LogEntry)
        assert isinstance(server_time, datetime.datetime)

    the_logger.debug.assert_called_once_with(
        loggers.LOG_INGEST_INGEST_LOGS,
    )
    the_logger.error.assert_not_called()


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_ingest_logs_no_content_length(mock_logfire):
    """No content-length header should not raise 413."""
    payload = _make_payload()
    request = _make_request(content_length=None)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 1}

    the_logger.debug.assert_called_once_with(
        loggers.LOG_INGEST_INGEST_LOGS,
    )
    the_logger.error.assert_not_called()


def _make_http_entry(http_type, request_id="req-1", **overrides):
    """Create a LogEntry with HTTP attributes."""
    kwargs = {
        **ENTRY_KWARGS,
        "attributes": {
            "http.request_id": request_id,
            "http.type": http_type,
        },
    }
    kwargs.update(overrides)
    return log_ingest.LogEntry(**kwargs)


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_http_pairing_nests_response_under_request(mock_logfire):
    """Response log nests under its request span."""
    req_entry = _make_http_entry("request")
    resp_entry = _make_http_entry("response")
    payload = log_ingest.LogPayload(
        logs=[req_entry, resp_entry],
        resource={"service.name": "test"},
    )
    request = _make_request(content_length=200)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 2}
    # Parent span for the HTTP request, plus logfire.log for the child
    mock_logfire.span.assert_called()
    mock_logfire.log.assert_called()


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_http_request_without_response_emits_flat(mock_logfire):
    """Request with no matching response emits as a flat log."""
    req_entry = _make_http_entry("request")
    payload = log_ingest.LogPayload(
        logs=[req_entry],
        resource={"service.name": "test"},
    )
    request = _make_request(content_length=100)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 1}
    mock_logfire.log.assert_called_once()


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_orphaned_response_emits_flat(mock_logfire):
    """Response with no matching request emits as a flat log."""
    resp_entry = _make_http_entry("response")
    payload = log_ingest.LogPayload(
        logs=[resp_entry],
        resource={"service.name": "test"},
    )
    request = _make_request(content_length=100)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 1}
    mock_logfire.log.assert_called_once()


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_active_run_bucketing(mock_logfire):
    """Entries with active_run are grouped under an ActiveRun span."""
    entry = log_ingest.LogEntry(
        **ENTRY_KWARGS,
        active_run={"thread_id": "t-1", "run_id": "r-1"},
    )
    payload = log_ingest.LogPayload(
        logs=[entry],
        resource={"service.name": "test"},
    )
    request = _make_request(content_length=100)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 1}
    # Should have span calls for both "client: unknown" and "ActiveRun"
    span_calls = [
        c
        for c in mock_logfire.span.call_args_list
        if c.args and c.args[0] == "ActiveRun"
    ]
    assert len(span_calls) == 1
    assert span_calls[0].kwargs["thread_id"] == "t-1"
    assert span_calls[0].kwargs["run_id"] == "r-1"


@pytest.mark.anyio
@mock.patch("soliplex.views.log_ingest.logfire")
async def test_http_error_nests_under_request(mock_logfire):
    """HTTP error log nests under its request span."""
    req_entry = _make_http_entry("request")
    err_entry = _make_http_entry("error")
    payload = log_ingest.LogPayload(
        logs=[req_entry, err_entry],
        resource={"service.name": "test"},
    )
    request = _make_request(content_length=200)
    the_installation = mock.create_autospec(installation.Installation)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    result = await log_ingest_views.ingest_logs(
        request,
        payload=payload,
        the_installation=the_installation,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )

    assert result == {"accepted": 2}
    mock_logfire.span.assert_called()
    mock_logfire.log.assert_called()
