"""Tests for soliplex.agents.scm.gitea module."""

from unittest.mock import patch

import pytest

from soliplex.agents.scm.gitea import GiteaProvider


@pytest.fixture
def gitea_provider(mock_settings):
    """Create GiteaProvider instance."""
    return GiteaProvider()


@pytest.fixture
def gitea_provider_custom_owner(mock_settings):
    """Create GiteaProvider instance with custom owner."""
    return GiteaProvider(owner="custom_owner")


def test_init_default_owner(gitea_provider, mock_settings):
    """Test GiteaProvider initialization with default owner."""
    assert gitea_provider.owner == "test_owner"


def test_init_custom_owner(gitea_provider_custom_owner):
    """Test GiteaProvider initialization with custom owner."""
    assert gitea_provider_custom_owner.owner == "custom_owner"


def test_get_default_owner(gitea_provider, mock_settings):
    """Test get_default_owner returns settings value."""
    assert gitea_provider.get_default_owner() == "test_owner"


def test_get_base_url(gitea_provider, mock_settings):
    """Test get_base_url returns Gitea URL."""
    assert gitea_provider.get_base_url() == "https://gitea.example.com/api/v1"


def test_get_auth_token(gitea_provider, mock_settings):
    """Test get_auth_token returns Gitea token."""
    assert gitea_provider.get_auth_token() == "test_gitea_token"


def test_get_last_updated_with_date(gitea_provider):
    """Test get_last_updated extracts date from record."""
    rec = {"last_committer_date": "2024-01-01T00:00:00Z", "other_field": "value"}
    result = gitea_provider.get_last_updated(rec)
    assert result == "2024-01-01T00:00:00Z"


def test_get_last_updated_without_date(gitea_provider):
    """Test get_last_updated returns None when date not present."""
    rec = {"other_field": "value"}
    result = gitea_provider.get_last_updated(rec)
    assert result is None


def test_get_last_updated_empty_record(gitea_provider):
    """Test get_last_updated with empty record."""
    rec = {}
    result = gitea_provider.get_last_updated(rec)
    assert result is None


def test_build_url(gitea_provider, mock_settings):
    """Test build_url constructs correct Gitea URL."""
    url = gitea_provider.build_url("/repos/owner/repo")
    assert url == "https://gitea.example.com/api/v1/repos/owner/repo"


@pytest.mark.asyncio
async def test_get_session_has_auth_header(gitea_provider):
    """Test get_session creates session with correct auth header."""
    async with gitea_provider.get_session() as session:
        assert session.headers["Authorization"] == "token test_gitea_token"


@pytest.mark.asyncio
async def test_list_issues(gitea_provider, mock_response, sample_issue):
    """Test list_issues integration."""
    with patch.object(gitea_provider, "paginate") as mock_paginate:
        mock_paginate.return_value = [sample_issue]

        result = await gitea_provider.list_issues("test_repo")

        assert len(result) == 1
        assert result[0]["title"] == "Test Issue"


@pytest.mark.asyncio
async def test_list_repo_files(gitea_provider, mock_response, mock_settings):
    """Test list_repo_files integration."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    api_response = [
        {"name": "file1.md", "type": "file", "url": "https://gitea.example.com/file1"},
    ]

    with patch.object(gitea_provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp = mock_response(200, api_response)
        mock_session.get.return_value = create_async_context_manager(mock_resp)
        mock_get_session.return_value = create_async_context_manager(mock_session)

        with patch.object(gitea_provider, "validate_response"):
            with patch.object(gitea_provider, "get_data_from_url") as mock_get_data:
                mock_get_data.return_value = {"name": "file1.md", "uri": "file1.md"}

                result = await gitea_provider.list_repo_files("test_repo")

                assert len(result) == 1


def test_parse_file_rec(gitea_provider, sample_file_record):
    """Test parse_file_rec with Gitea file record."""
    result = gitea_provider.parse_file_rec(sample_file_record)

    assert result["name"] == "test.md"
    assert result["uri"] == "docs/test.md"
    assert "file_bytes" in result
    assert "sha256" in result
    assert result["last_updated"] == "2024-01-01T00:00:00Z"


def test_parse_file_rec_without_date(gitea_provider):
    """Test parse_file_rec without last_committer_date."""
    rec = {
        "name": "test.md",
        "path": "test.md",
        "url": "https://gitea.example.com/file",
        "content": "VGVzdA==",
    }

    result = gitea_provider.parse_file_rec(rec)

    assert result["name"] == "test.md"
    assert result["last_updated"] is None


@pytest.mark.asyncio
async def test_inheritance_from_base(gitea_provider):
    """Test GiteaProvider inherits from BaseSCMProvider."""
    from soliplex.agents.scm.base import BaseSCMProvider

    assert isinstance(gitea_provider, BaseSCMProvider)


@pytest.mark.asyncio
async def test_paginate_integration(gitea_provider, mock_response):
    """Test paginate works correctly with Gitea."""
    from unittest.mock import MagicMock

    from tests.unit.conftest import create_async_context_manager

    page1_data = [{"id": 1, "name": "item1"}]

    with patch.object(gitea_provider, "get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_resp1 = mock_response(200, page1_data)
        mock_resp2 = mock_response(200, [])

        mock_session.get.side_effect = [
            create_async_context_manager(mock_resp1),
            create_async_context_manager(mock_resp2),
        ]
        mock_get_session.return_value = create_async_context_manager(mock_session)

        url_template = gitea_provider.build_url("/repos/{owner}/{repo}/issues?page={page}")
        result = await gitea_provider.paginate(url_template, "test_owner", "test_repo")

        assert len(result) == 1
        assert result[0]["name"] == "item1"
