"""Tests for soliplex.agents.client module."""

from unittest.mock import MagicMock
from unittest.mock import patch

import aiohttp
import pytest

from soliplex.agents import client
from soliplex.agents.scm import UnexpectedResponseError


@pytest.mark.asyncio
async def test_get_session():
    """Test get_session creates session with correct headers."""
    async with client.get_session() as session:
        assert isinstance(session, aiohttp.ClientSession)
        assert session.headers["User-Agent"] == "soliplex-agent"


def test_build_url():
    """Test _build_url constructs correct URL."""
    url = client._build_url("/test/path")
    assert "/api/v1/test/path" in url


@pytest.mark.asyncio
async def test_post_request_success(mock_response):
    """Test _post_request with successful response."""
    from tests.unit.conftest import create_async_context_manager

    response_data = {"batch_id": 123}
    mock_resp = mock_response(201, response_data)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        form_data = aiohttp.FormData()
        form_data.add_field("test", "value")

        result = await client._post_request("/test", form_data, expected_status=201)

        assert result == response_data
        mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_post_request_error_in_response(mock_response):
    """Test _post_request raises ValueError when response contains error."""
    from tests.unit.conftest import create_async_context_manager

    response_data = {"error": "Something went wrong"}
    mock_resp = mock_response(400, response_data)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        form_data = aiohttp.FormData()

        with pytest.raises(ValueError, match="Something went wrong"):
            await client._post_request("/test", form_data)


@pytest.mark.asyncio
async def test_post_request_unexpected_status(mock_response):
    """Test _post_request raises UnexpectedResponseError for wrong status."""
    from tests.unit.conftest import create_async_context_manager

    response_data = {"message": "unexpected"}
    mock_resp = mock_response(500, response_data)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        form_data = aiohttp.FormData()

        with pytest.raises(UnexpectedResponseError):
            await client._post_request("/test", form_data, expected_status=201)


@pytest.mark.asyncio
async def test_create_batch():
    """Test create_batch returns batch ID."""
    with patch("soliplex.agents.client._post_request") as mock_post:
        mock_post.return_value = {"batch_id": 456}

        batch_id = await client.create_batch("test_source", "test_batch")

        assert batch_id == 456
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "/batch/"


@pytest.mark.asyncio
async def test_do_start_workflows_minimal():
    """Test do_start_workflows with minimal parameters."""
    with patch("soliplex.agents.client._post_request") as mock_post:
        mock_post.return_value = {"status": "started"}

        result = await client.do_start_workflows(batch_id=123, workflow_definition_id=None, param_id=None, priority=5)

        assert result == {"status": "started"}
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "/batch/start-workflows"


@pytest.mark.asyncio
async def test_do_start_workflows_with_optional_params():
    """Test do_start_workflows with all parameters."""
    with patch("soliplex.agents.client._post_request") as mock_post:
        mock_post.return_value = {"status": "started"}

        result = await client.do_start_workflows(
            batch_id=123, workflow_definition_id="wf_123", param_id="param_456", priority=10
        )

        assert result == {"status": "started"}


@pytest.mark.asyncio
async def test_check_status(mock_response):
    """Test check_status returns files needing processing."""
    from tests.unit.conftest import create_async_context_manager

    file_info = [
        {"uri": "file1.md", "sha256": "hash1"},
        {"uri": "file2.md", "sha256": "hash2"},
        {"uri": "file3.md", "sha256": "hash3"},
    ]

    response_data = {
        "file1.md": {"status": "new"},
        "file2.md": {"status": "mismatch"},
        "file3.md": {"status": "processed"},
    }

    mock_resp = mock_response(200, response_data)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.check_status(file_info, "test_source")

        # Should only return files with 'new' or 'mismatch' status
        assert len(result) == 2
        assert result[0]["uri"] == "file1.md"
        assert result[1]["uri"] == "file2.md"


@pytest.mark.asyncio
async def test_check_status_empty(mock_response):
    """Test check_status with no files needing processing."""
    from tests.unit.conftest import create_async_context_manager

    file_info = [{"uri": "file1.md", "sha256": "hash1"}]
    response_data = {"file1.md": {"status": "processed"}}

    mock_resp = mock_response(200, response_data)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.check_status(file_info, "test_source")

        assert len(result) == 0


@pytest.mark.asyncio
async def test_do_ingest_success_with_bytes(mock_response):
    """Test do_ingest with successful ingestion using bytes."""
    from tests.unit.conftest import create_async_context_manager

    mock_resp = mock_response(201, {"document_id": 789})

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.do_ingest(
            doc_body=b"test content",
            uri="/docs/test.md",
            meta={"author": "test"},
            source="test_source",
            batch_id=123,
            mime_type="text/markdown",
        )

        assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_do_ingest_success_with_string(mock_response):
    """Test do_ingest with successful ingestion using string."""
    from tests.unit.conftest import create_async_context_manager

    mock_resp = mock_response(201, {"document_id": 789})

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.do_ingest(
            doc_body="test content",
            uri="/docs/test.md",
            meta={"author": "test"},
            source="test_source",
            batch_id=123,
            mime_type="text/markdown",
        )

        assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_do_ingest_failure(mock_response):
    """Test do_ingest with failed ingestion."""
    from tests.unit.conftest import create_async_context_manager

    mock_resp = mock_response(400, {"error": "Invalid document"})

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.do_ingest(
            doc_body=b"test content",
            uri="/docs/test.md",
            meta={},
            source="test_source",
            batch_id=123,
            mime_type="text/markdown",
        )

        assert result == {"error": "Invalid document"}


@pytest.mark.asyncio
async def test_do_ingest_exception():
    """Test do_ingest handles exceptions gracefully."""
    from tests.unit.conftest import create_async_context_manager

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.post.side_effect = Exception("Network error")
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.do_ingest(
            doc_body=b"test content",
            uri="/docs/test.md",
            meta={},
            source="test_source",
            batch_id=123,
            mime_type="text/markdown",
        )

        assert "error" in result
        assert "Network error" in result["error"]


@pytest.mark.asyncio
async def test_find_batch_for_source_found(mock_response):
    """Test find_batch_for_source returns batch ID when source is found."""
    from tests.unit.conftest import create_async_context_manager

    batches = [
        {"id": 1, "source": "github", "name": "batch1"},
        {"id": 2, "source": "gitlab", "name": "batch2"},
        {"id": 3, "source": "bitbucket", "name": "batch3"},
    ]
    mock_resp = mock_response(200, batches)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.find_batch_for_source("gitlab")

        assert result == 2
        mock_session.get.assert_called_once()


@pytest.mark.asyncio
async def test_find_batch_for_source_not_found(mock_response):
    """Test find_batch_for_source returns None when source is not found."""
    from tests.unit.conftest import create_async_context_manager

    batches = [
        {"id": 1, "source": "github", "name": "batch1"},
        {"id": 2, "source": "gitlab", "name": "batch2"},
    ]
    mock_resp = mock_response(200, batches)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.find_batch_for_source("nonexistent")

        assert result is None


@pytest.mark.asyncio
async def test_find_batch_for_source_empty_list(mock_response):
    """Test find_batch_for_source returns None when no batches exist."""
    from tests.unit.conftest import create_async_context_manager

    batches = []
    mock_resp = mock_response(200, batches)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.find_batch_for_source("github")

        assert result is None


@pytest.mark.asyncio
async def test_find_batch_for_source_multiple_found(mock_response, caplog):
    """Test find_batch_for_source returns first batch ID when multiple matches found."""
    import logging

    from tests.unit.conftest import create_async_context_manager

    caplog.set_level(logging.WARNING)

    batches = [
        {"id": 10, "source": "github", "name": "batch1"},
        {"id": 20, "source": "github", "name": "batch2"},
        {"id": 30, "source": "github", "name": "batch3"},
    ]
    mock_resp = mock_response(200, batches)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        result = await client.find_batch_for_source("github")

        assert result == 10
        assert "Multiple batches found 3 for source github using first one" in caplog.text


@pytest.mark.asyncio
async def test_find_batch_for_source_http_error(mock_response):
    """Test find_batch_for_source handles HTTP errors."""
    from tests.unit.conftest import create_async_context_manager

    mock_resp = mock_response(500, {"error": "Internal server error"})
    mock_resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=500, message="Internal Server Error"
    )

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        with pytest.raises(aiohttp.ClientResponseError):
            await client.find_batch_for_source("github")


@pytest.mark.asyncio
async def test_find_batch_for_source_url_construction(mock_response):
    """Test find_batch_for_source uses correct endpoint."""
    from tests.unit.conftest import create_async_context_manager

    batches = [{"id": 1, "source": "github", "name": "batch1"}]
    mock_resp = mock_response(200, batches)

    with patch("soliplex.agents.client.get_session") as mock_get_session:
        with patch("soliplex.agents.client._build_url") as mock_build_url:
            mock_build_url.return_value = "http://127.0.0.1:8000/api/v1/batch/"

            mock_session = MagicMock()
            mock_session.get.return_value = create_async_context_manager(mock_resp)
            mock_get_session.return_value = create_async_context_manager(mock_session)

            await client.find_batch_for_source("github")

            mock_build_url.assert_called_once_with("/batch/")
            mock_session.get.assert_called_once_with("http://127.0.0.1:8000/api/v1/batch/")


def test_constants():
    """Test module constants are defined correctly."""
    assert client.STATUS_NEW == "new"
    assert client.STATUS_MISMATCH == "mismatch"
    assert client.PROCESSABLE_STATUSES == {"new", "mismatch"}
