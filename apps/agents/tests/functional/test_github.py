"""Tests for soliplex.agents.scm.github module."""

from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from soliplex.agents.scm import GitHubAPIError
from soliplex.agents.scm import SCMException
from soliplex.agents.scm.github import GitHubProvider


@pytest.fixture
def github_provider(mock_settings):
    """Create GitHubProvider instance."""
    return GitHubProvider()


@pytest.fixture
def github_provider_custom_owner(mock_settings):
    """Create GitHubProvider instance with custom owner."""
    return GitHubProvider(owner="custom_owner")


def test_init_default_owner(github_provider, mock_settings):
    """Test GitHubProvider initialization with default owner."""
    assert github_provider.owner == "test_gh_owner"


def test_init_custom_owner(github_provider_custom_owner):
    """Test GitHubProvider initialization with custom owner."""
    assert github_provider_custom_owner.owner == "custom_owner"


def test_get_default_owner(github_provider, mock_settings):
    """Test get_default_owner returns settings value."""
    assert github_provider.get_default_owner() == "test_gh_owner"


def test_get_base_url(github_provider):
    """Test get_base_url returns GitHub API URL."""
    assert github_provider.get_base_url() == "https://api.github.com"


def test_get_auth_token(github_provider, mock_settings):
    """Test get_auth_token returns GitHub token."""
    assert github_provider.get_auth_token() == "test_gh_token"


def test_get_last_updated(github_provider):
    """Test get_last_updated returns None for GitHub."""
    rec = {"some_field": "value"}
    result = github_provider.get_last_updated(rec)
    assert result is None


def test_get_last_updated_with_irrelevant_fields(github_provider):
    """Test get_last_updated ignores all fields and returns None."""
    rec = {"updated_at": "2024-01-01", "last_modified": "2024-01-02"}
    result = github_provider.get_last_updated(rec)
    assert result is None


def test_build_url(github_provider):
    """Test build_url constructs correct GitHub URL."""
    url = github_provider.build_url("/repos/owner/repo")
    assert url == "https://api.github.com/repos/owner/repo"


@pytest.mark.asyncio
async def test_get_session_has_auth_header(github_provider):
    """Test get_session creates session with correct auth header."""
    async with github_provider.get_session() as session:
        assert session.headers["Authorization"] == "token test_gh_token"


@pytest.mark.asyncio
async def test_validate_response_success(github_provider, mock_response):
    """Test validate_response with successful 200 response."""
    response = mock_response(200, {"data": "success"})
    resp = {"data": "success"}

    # Should not raise
    await github_provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_non_200_with_message(github_provider, mock_response):
    """Test validate_response raises SCMException on non-200 with message."""
    response = mock_response(404, {"message": "Not Found"})
    resp = {"message": "Not Found"}

    with pytest.raises(SCMException, match="Not Found"):
        await github_provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_non_200_without_message(github_provider, mock_response):
    """Test validate_response raises GitHubAPIError on non-200 without message."""
    response = mock_response(500, {"error": "Internal Server Error"})
    resp = {"error": "Internal Server Error"}

    with pytest.raises(GitHubAPIError):
        await github_provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_with_errors_field(github_provider, mock_response):
    """Test validate_response raises SCMException when errors field present."""
    response = mock_response(200, {"errors": ["Error 1", "Error 2"]})
    resp = {"errors": ["Error 1", "Error 2"]}

    with pytest.raises(SCMException):
        await github_provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_validate_response_list(github_provider, mock_response):
    """Test validate_response with list response."""
    response = mock_response(200, [{"id": 1}])
    resp = [{"id": 1}]

    # Should not raise
    await github_provider.validate_response(response, resp)


@pytest.mark.asyncio
async def test_get_file_content_with_content(github_provider):
    """Test get_file_content when content is present."""
    rec = {"name": "test.md", "content": "VGVzdCBjb250ZW50"}
    session = AsyncMock()

    result = await github_provider.get_file_content(rec, session, "owner", "repo")

    assert result == rec
    assert result["content"] == "VGVzdCBjb250ZW50"


@pytest.mark.asyncio
async def test_get_file_content_missing_content(github_provider, mock_response):
    """Test get_file_content fetches blob when content is missing."""
    rec = {"name": "test.md", "sha": "abc123"}
    session = AsyncMock()

    with patch.object(github_provider, "get_blob") as mock_get_blob:
        mock_get_blob.return_value = b"blob content"

        result = await github_provider.get_file_content(rec, session, "owner", "repo")

        assert result["content"] == b"blob content"
        mock_get_blob.assert_called_once_with("repo", "owner", rec, session)


@pytest.mark.asyncio
async def test_get_file_content_none_content(github_provider):
    """Test get_file_content fetches blob when content is None."""
    rec = {"name": "test.md", "content": None, "sha": "abc123"}
    session = AsyncMock()

    with patch.object(github_provider, "get_blob") as mock_get_blob:
        mock_get_blob.return_value = b"blob content"

        result = await github_provider.get_file_content(rec, session, "owner", "repo")

        assert result["content"] == b"blob content"


@pytest.mark.asyncio
async def test_get_file_content_empty_content(github_provider):
    """Test get_file_content fetches blob when content is empty string."""
    rec = {"name": "test.md", "content": "", "sha": "abc123"}
    session = AsyncMock()

    with patch.object(github_provider, "get_blob") as mock_get_blob:
        mock_get_blob.return_value = b"blob content"

        result = await github_provider.get_file_content(rec, session, "owner", "repo")

        assert result["content"] == b"blob content"


@pytest.mark.asyncio
async def test_get_blob(github_provider, mock_response):
    """Test get_blob fetches blob content from API."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    rec = {"sha": "abc123"}
    session = MagicMock()
    blob_content = b"test blob content"

    mock_resp = mock_response(200, None, "test blob content")
    session.get.return_value = create_async_context_manager(mock_resp)

    result = await github_provider.get_blob("test_repo", "test_owner", rec, session)

    assert result == blob_content
    session.get.assert_called_once()
    call_url = session.get.call_args[0][0]
    assert "abc123" in call_url


@pytest.mark.asyncio
async def test_list_issues(github_provider, mock_response, sample_issue):
    """Test list_issues integration."""
    with patch.object(github_provider, "paginate") as mock_paginate:
        mock_paginate.return_value = [sample_issue]

        result = await github_provider.list_issues("test_repo")

        assert len(result) == 1
        assert result[0]["title"] == "Test Issue"


@pytest.mark.asyncio
async def test_list_repo_files(github_provider, mock_response, mock_settings):
    """Test list_repo_files integration."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    api_response = [
        {"name": "file1.md", "type": "file", "url": "https://api.github.com/file1"},
    ]

    with patch.object(github_provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(200, api_response)
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        with patch.object(github_provider, "validate_response"):
            with patch.object(github_provider, "get_data_from_url") as mock_get_data:
                mock_get_data.return_value = {"name": "file1.md", "uri": "file1.md"}

                result = await github_provider.list_repo_files("test_repo")

                assert len(result) == 1


def test_parse_file_rec(github_provider, sample_file_record):
    """Test parse_file_rec with GitHub file record."""
    result = github_provider.parse_file_rec(sample_file_record)

    assert result["name"] == "test.md"
    assert result["uri"] == "docs/test.md"
    assert "file_bytes" in result
    assert "sha256" in result
    assert result["last_updated"] is None  # GitHub returns None


@pytest.mark.asyncio
async def test_inheritance_from_base(github_provider):
    """Test GitHubProvider inherits from BaseSCMProvider."""
    from soliplex.agents.scm.base import BaseSCMProvider

    assert isinstance(github_provider, BaseSCMProvider)


@pytest.mark.asyncio
async def test_paginate_integration(github_provider, mock_response):
    """Test paginate works correctly with GitHub."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    page1_data = [{"id": 1, "name": "item1"}]

    with patch.object(github_provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp1 = mock_response(200, page1_data)
        mock_resp2 = mock_response(200, [])

        mock_session.get.side_effect = [
            create_async_context_manager(mock_resp1),
            create_async_context_manager(mock_resp2),
        ]
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = github_provider.build_url("/repos/{owner}/{repo}/issues?page={page}")
        result = await github_provider.paginate(url_template, "test_owner", "test_repo")

        assert len(result) == 1
        assert result[0]["name"] == "item1"


@pytest.mark.asyncio
async def test_get_data_from_url_with_empty_content(github_provider, mock_response):
    """Test get_data_from_url properly handles files with empty content via get_file_content."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    file_record = {
        "name": "large_file.md",
        "path": "docs/large_file.md",
        "url": "https://api.github.com/repos/owner/repo/contents/docs/large_file.md",
        "type": "file",
        "content": "",  # Empty content - should trigger blob fetch
        "sha": "def456",
    }

    session = MagicMock()
    mock_resp = mock_response(200, file_record)
    session.get.return_value = create_async_context_manager(mock_resp)

    with patch.object(github_provider, "get_blob") as mock_get_blob:
        mock_get_blob.return_value = b"actual large file content"

        result = await github_provider.get_data_from_url(
            "https://api.github.com/repos/owner/repo/contents/docs/large_file.md",
            session,
            owner="owner",
            repo="repo",
        )

        # Should have fetched the blob
        mock_get_blob.assert_called_once()
        assert isinstance(result, dict)
        assert result["name"] == "large_file.md"
