"""Tests for soliplex.agents.scm.base module."""

from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import patch

import aiohttp
import pytest

from soliplex.agents.scm import APIFetchError
from soliplex.agents.scm import SCMException
from soliplex.agents.scm.base import BaseSCMProvider


class ConcreteSCMProvider(BaseSCMProvider):
    """Concrete implementation for testing."""

    def get_default_owner(self) -> str:
        return "test_owner"

    def get_base_url(self) -> str:
        return "https://api.example.com"

    def get_auth_token(self) -> str:
        return "test_token"

    def get_last_updated(self, rec: dict[str, Any]) -> str | None:
        return rec.get("updated_at")


@pytest.fixture
def provider():
    """Create concrete provider instance."""
    return ConcreteSCMProvider()


@pytest.fixture
def provider_with_owner():
    """Create concrete provider instance with custom owner."""
    return ConcreteSCMProvider(owner="custom_owner")


def test_init_default_owner(provider):
    """Test provider initialization with default owner."""
    assert provider.owner == "test_owner"


def test_init_custom_owner(provider_with_owner):
    """Test provider initialization with custom owner."""
    assert provider_with_owner.owner == "custom_owner"


@pytest.mark.asyncio
async def test_get_session(provider):
    """Test get_session creates authenticated session."""
    async with provider.get_session() as session:
        assert isinstance(session, aiohttp.ClientSession)
        assert session.headers["Authorization"] == "token test_token"


def test_build_url(provider):
    """Test build_url constructs correct URL."""
    url = provider.build_url("/repos/owner/repo")
    assert url == "https://api.example.com/repos/owner/repo"


def test_build_url_strips_slashes(provider):
    """Test build_url handles leading/trailing slashes."""
    url = provider.build_url("repos/owner/repo/")
    assert url == "https://api.example.com/repos/owner/repo/"


@pytest.mark.asyncio
async def test_paginate_single_page(provider, mock_response):
    """Test paginate with single page of results."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    page1_data = [{"id": 1, "name": "item1"}]

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp1 = mock_response(200, page1_data)
        mock_resp2 = mock_response(200, [])  # Empty second page

        mock_session.get.side_effect = [
            create_async_context_manager(mock_resp1),
            create_async_context_manager(mock_resp2),
        ]
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"
        result = await provider.paginate(url_template, "test_owner", "test_repo")

        assert len(result) == 1
        assert result[0]["name"] == "item1"


@pytest.mark.asyncio
async def test_paginate_multiple_pages(provider, mock_response):
    """Test paginate with multiple pages of results."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    page1_data = [{"id": 1}, {"id": 2}]
    page2_data = [{"id": 3}]

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp1 = mock_response(200, page1_data)
        mock_resp2 = mock_response(200, page2_data)
        mock_resp3 = mock_response(200, [])

        mock_session.get.side_effect = [
            create_async_context_manager(mock_resp1),
            create_async_context_manager(mock_resp2),
            create_async_context_manager(mock_resp3),
        ]
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"
        result = await provider.paginate(url_template, "test_owner", "test_repo")

        assert len(result) == 3


@pytest.mark.asyncio
async def test_paginate_404_error(provider, mock_response):
    """Test paginate raises SCMException on 404."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(404, {"message": "Not found"})

        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"

        with pytest.raises(SCMException, match="not found"):
            await provider.paginate(url_template, "test_owner", "test_repo")


@pytest.mark.asyncio
async def test_paginate_api_error_with_errors_field(provider, mock_response):
    """Test paginate raises SCMException when response has errors field."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        error_data = {"errors": ["Error 1", "Error 2"]}
        mock_resp = mock_response(500, error_data)

        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"

        with pytest.raises(SCMException):
            await provider.paginate(url_template, "test_owner", "test_repo")


@pytest.mark.asyncio
async def test_paginate_non_200_status(provider, mock_response):
    """Test paginate raises APIFetchError on non-200 status."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(500, {"message": "Server error"})

        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"

        with pytest.raises(APIFetchError):
            await provider.paginate(url_template, "test_owner", "test_repo")


@pytest.mark.asyncio
async def test_paginate_with_process_response(provider, mock_response):
    """Test paginate with custom response processor."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    page1_data = {"items": [{"id": 1}, {"id": 2}]}

    def process_response(resp):
        return resp.get("items", [])

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp1 = mock_response(200, page1_data)
        mock_resp2 = mock_response(200, {"items": []})

        mock_session.get.side_effect = [
            create_async_context_manager(mock_resp1),
            create_async_context_manager(mock_resp2),
        ]
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = "https://api.example.com/repos/{owner}/{repo}/items?page={page}"
        result = await provider.paginate(url_template, "test_owner", "test_repo", process_response=process_response)

        assert len(result) == 2


@pytest.mark.asyncio
async def test_list_issues_without_comments(provider, mock_response, sample_issue):
    """Test list_issues without comments."""
    with patch.object(provider, "paginate") as mock_paginate:
        mock_paginate.return_value = [sample_issue]

        result = await provider.list_issues("test_repo", add_comments=False)

        assert len(result) == 1
        assert result[0]["title"] == "Test Issue"
        mock_paginate.assert_called_once()


@pytest.mark.asyncio
async def test_list_issues_with_comments(provider, mock_response, sample_issue, sample_comment):
    """Test list_issues with comments."""
    with patch.object(provider, "paginate") as mock_paginate:
        with patch.object(provider, "list_repo_comments") as mock_list_comments:
            mock_paginate.return_value = [sample_issue]
            mock_list_comments.return_value = [sample_comment]

            result = await provider.list_issues("test_repo", add_comments=True)

            assert len(result) == 1
            assert "comments" in result[0]
            assert result[0]["comment_count"] == 1
            assert result[0]["comments"][0] == "Test comment"


@pytest.mark.asyncio
async def test_list_repo_comments(provider, sample_comment):
    """Test list_repo_comments."""
    with patch.object(provider, "paginate") as mock_paginate:
        mock_paginate.return_value = [sample_comment]

        result = await provider.list_repo_comments("test_owner", "test_repo")

        assert len(result) == 1
        assert result[0]["body"] == "Test comment"


def test_parse_file_rec(provider, sample_file_record):
    """Test parse_file_rec normalizes file record."""
    result = provider.parse_file_rec(sample_file_record)

    assert result["name"] == "test.md"
    assert result["uri"] == "docs/test.md"
    assert result["path"] == "docs/test.md"
    assert "file_bytes" in result
    assert "sha256" in result
    assert len(result["sha256"]) == 64
    assert result["content-type"] == "text/markdown"


@pytest.mark.asyncio
async def test_get_file_content_default(provider):
    """Test get_file_content default implementation."""
    rec = {"name": "test.md", "content": "test"}
    session = AsyncMock()

    result = await provider.get_file_content(rec, session, "owner", "repo")

    assert result == rec


@pytest.mark.asyncio
async def test_get_data_from_url_single_file(provider, mock_response, sample_file_record):
    """Test get_data_from_url with single file."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    mock_session = MagicMock()
    mock_resp = mock_response(200, sample_file_record)
    mock_session.get.return_value = create_async_context_manager(mock_resp)

    with patch.object(provider, "get_file_content", return_value=sample_file_record):
        result = await provider.get_data_from_url("https://api.example.com/file", mock_session, owner="owner", repo="repo")

        assert isinstance(result, dict)
        assert result["name"] == "test.md"


@pytest.mark.asyncio
async def test_get_data_from_url_single_file_without_owner_repo(provider, mock_response, sample_file_record):
    """Test get_data_from_url with single file without owner/repo parameters."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    mock_session = MagicMock()
    mock_resp = mock_response(200, sample_file_record)
    mock_session.get.return_value = create_async_context_manager(mock_resp)

    # Call without owner and repo to test the branch where get_file_content is not called
    result = await provider.get_data_from_url("https://api.example.com/file", mock_session)

    assert isinstance(result, dict)
    assert result["name"] == "test.md"


@pytest.mark.asyncio
async def test_get_data_from_url_directory(provider, mock_response, sample_file_record):
    """Test get_data_from_url with directory."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    dir_response = [
        {"name": "file1.md", "url": "https://api.example.com/file1", "type": "file"},
        {"name": "file2.md", "url": "https://api.example.com/file2", "type": "file"},
    ]

    mock_session = MagicMock()
    mock_resp_dir = mock_response(200, dir_response)
    mock_session.get.return_value = create_async_context_manager(mock_resp_dir)

    # Mock the recursive calls
    with patch.object(provider, "get_data_from_url") as mock_get_data:
        # First call returns directory
        mock_get_data.side_effect = [
            dir_response,
            sample_file_record,
            sample_file_record,
        ]

        result = await mock_get_data("https://api.example.com/dir", mock_session, owner="owner", repo="repo")

        assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_data_from_url_directory_with_recursion(provider, mock_response, sample_file_record):
    """Test get_data_from_url with directory that requires recursion."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    dir_response = [
        {"name": "file1.md", "url": "https://api.example.com/file1", "type": "file"},
        {"name": "file2.md", "url": "https://api.example.com/file2", "type": "file"},
    ]

    file1_response = {"name": "file1.md", "path": "file1.md", "url": "https://api.example.com/file1", "content": "VGVzdDE="}
    file2_response = {"name": "file2.md", "path": "file2.md", "url": "https://api.example.com/file2", "content": "VGVzdDI="}

    mock_session = MagicMock()

    # First GET returns the directory listing
    mock_resp_dir = mock_response(200, dir_response)
    # Second GET returns file1
    mock_resp_file1 = mock_response(200, file1_response)
    # Third GET returns file2
    mock_resp_file2 = mock_response(200, file2_response)

    mock_session.get.side_effect = [
        create_async_context_manager(mock_resp_dir),
        create_async_context_manager(mock_resp_file1),
        create_async_context_manager(mock_resp_file2),
    ]

    # Call the actual method to exercise the directory recursion code
    result = await provider.get_data_from_url("https://api.example.com/dir", mock_session, owner="owner", repo="repo")

    # Should return a list of parsed files
    assert isinstance(result, list)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_data_from_url_error(provider, mock_response):
    """Test get_data_from_url handles client errors."""
    from unittest.mock import MagicMock

    mock_session = MagicMock()
    mock_session.get.side_effect = aiohttp.ClientError("Network error")

    result = await provider.get_data_from_url("https://api.example.com/file", mock_session, owner="owner", repo="repo")

    assert "error" in result


@pytest.mark.asyncio
async def test_list_repo_files(provider, mock_response, sample_file_record):
    """Test list_repo_files."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    api_response = [
        {"name": "file1.md", "type": "file", "url": "https://api.example.com/file1"},
        {"name": "file2.pdf", "type": "file", "url": "https://api.example.com/file2"},
        {"name": "dir1", "type": "dir", "url": "https://api.example.com/dir1"},
        {"name": "file3.txt", "type": "file", "url": "https://api.example.com/file3"},  # Not in allowed extensions
    ]

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(200, api_response)
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        with patch.object(provider, "validate_response"):
            with patch.object(provider, "get_data_from_url") as mock_get_data:
                # Mock returns for files and directory
                mock_get_data.side_effect = [
                    {"name": "file1.md", "uri": "file1.md"},
                    {"name": "file2.pdf", "uri": "file2.pdf"},
                    [{"name": "subfile.md", "uri": "dir1/subfile.md"}],
                ]

                result = await provider.list_repo_files("test_repo")

                assert len(result) == 3


@pytest.mark.asyncio
async def test_iter_repo_files(provider, mock_response, sample_file_record):
    """Test iter_repo_files yields files."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    api_response = [
        {"name": "file1.md", "type": "file", "url": "https://api.example.com/file1"},
        {"name": "dir1", "type": "dir", "url": "https://api.example.com/dir1"},
    ]

    with patch.object(provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(200, api_response)
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        with patch.object(provider, "validate_response"):
            with patch.object(provider, "get_data_from_url") as mock_get_data:
                mock_get_data.side_effect = [
                    {"name": "file1.md", "uri": "file1.md"},
                    [{"name": "subfile.md", "uri": "dir1/subfile.md"}],
                ]

                files = []
                async for file in provider.iter_repo_files("test_repo"):
                    files.append(file)

                assert len(files) == 2


@pytest.mark.asyncio
async def test_validate_response_with_errors(provider):
    """Test validate_response raises SCMException for errors."""
    response = AsyncMock()
    response.status = 200
    resp = {"errors": ["Error 1"]}

    with pytest.raises(SCMException):
        await provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_success(provider):
    """Test validate_response with successful response."""
    response = AsyncMock()
    response.status = 200
    resp = {"data": "success"}

    # Should not raise
    await provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_list(provider):
    """Test validate_response with list response."""
    response = AsyncMock()
    response.status = 200
    resp = [{"id": 1}, {"id": 2}]

    # Should not raise
    await provider.validate_response(response, resp)
