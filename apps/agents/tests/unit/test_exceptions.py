"""Tests for soliplex.agents.scm exception classes."""

import pytest

from soliplex.agents import ValidationError
from soliplex.agents.scm import APIFetchError
from soliplex.agents.scm import GitHubAPIError
from soliplex.agents.scm import SCMException
from soliplex.agents.scm import UnexpectedResponseError


def test_scm_exception():
    """Test SCMException can be raised with custom message."""
    with pytest.raises(SCMException, match="Custom"):
        raise SCMException("Custom")  


def test_scm_exception_inheritance():
    """Test SCMException inherits from Exception."""
    exc = SCMException("test")
    assert isinstance(exc, Exception)


def test_api_fetch_error():
    """Test APIFetchError has correct message."""
    with pytest.raises(APIFetchError, match="Failed to fetch from API"):
        raise APIFetchError


def test_api_fetch_error_inheritance():
    """Test APIFetchError inherits from SCMException."""
    exc = APIFetchError()
    assert isinstance(exc, SCMException)


def test_github_api_error():
    """Test GitHubAPIError has correct message."""
    with pytest.raises(GitHubAPIError, match="GitHub API error"):
        raise GitHubAPIError


def test_github_api_error_inheritance():
    """Test GitHubAPIError inherits from SCMException."""
    exc = GitHubAPIError()
    assert isinstance(exc, SCMException)


def test_unexpected_response_error():
    """Test UnexpectedResponseError has correct message."""
    with pytest.raises(UnexpectedResponseError, match="Unexpected response status"):
        raise UnexpectedResponseError


def test_unexpected_response_error_inheritance():
    """Test UnexpectedResponseError inherits from Exception."""
    exc = UnexpectedResponseError()
    assert isinstance(exc, Exception)


def test_validation_error():
    """Test ValidationError has correct message."""
    config = {"invalid": "config"}
    with pytest.raises(ValidationError, match="Invalid config"):
        raise ValidationError(config)


def test_validation_error_inheritance():
    """Test ValidationError inherits from Exception."""
    exc = ValidationError({"test": "config"})
    assert isinstance(exc, Exception)
