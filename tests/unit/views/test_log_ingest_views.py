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
