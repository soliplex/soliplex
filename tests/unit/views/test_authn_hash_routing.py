"""Test authn views with hash-based routing."""

from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi import responses

from soliplex.views import authn as authn_views


@pytest.mark.anyio
async def test_get_authn_system_with_hash_routing():
    """Test that authn callback handles hash-based routing correctly."""

    # Mock request with hash-based return_to URL
    request = Mock()
    request.query_params = {"return_to": "/#/authn/callback"}
    request.url_for = Mock(
        return_value=Mock(
            replace_query_params=Mock(return_value="http://test/authn/system")
        )
    )

    # Mock installation with empty oidc_auth_system_configs
    installation = Mock()
    installation.auth_disabled = False
    installation.oidc_auth_system_configs = []

    # Mock OAuth components
    oauth = Mock()
    oauth_app = Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
    }

    oauth_app.authorize_access_token = AsyncMock(return_value=tokendict)
    oauth.create_client = Mock(return_value=oauth_app)

    # Patch auth functions
    with (
        patch("soliplex.authn.get_oauth", return_value=oauth),
        patch("soliplex.authn.authenticate"),
    ):
        # Call the function
        result = await authn_views.get_auth_system(
            request, "pydio", installation
        )

    # Check that the redirect URL has query params before the hash
    assert isinstance(result, responses.RedirectResponse)
    redirect_url = result.headers.get("location")

    # Should be /?token=xxx&refresh_token=xxx#/authn/callback
    # Not /#/authn/callback?token=xxx
    assert redirect_url.startswith("/")
    assert "?token=test_access_token" in redirect_url
    assert "&refresh_token=test_refresh_token" in redirect_url
    assert redirect_url.endswith("#/authn/callback")

    # Verify the correct structure
    parts = redirect_url.split("#")
    assert len(parts) == 2
    assert "?token=" in parts[0]  # Query params before hash
    assert parts[1] == "/authn/callback"  # Hash fragment preserved


@pytest.mark.anyio
async def test_get_authn_system_without_hash():
    """Test that authn callback still works without hash routing."""

    # Mock request without hash in return_to
    request = Mock()
    request.query_params = {"return_to": "/dashboard"}
    request.url_for = Mock(
        return_value=Mock(
            replace_query_params=Mock(return_value="http://test/authn/system")
        )
    )

    # Mock installation with empty oidc_auth_system_configs
    installation = Mock()
    installation.auth_disabled = False
    installation.oidc_auth_system_configs = []

    # Mock OAuth components
    oauth = Mock()
    oauth_app = Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
    }

    oauth_app.authorize_access_token = AsyncMock(return_value=tokendict)
    oauth.create_client = Mock(return_value=oauth_app)

    # Patch auth functions
    with (
        patch("soliplex.authn.get_oauth", return_value=oauth),
        patch("soliplex.authn.authenticate"),
    ):
        # Call the function
        result = await authn_views.get_auth_system(
            request, "pydio", installation
        )

    # Check that the redirect URL has standard query params
    assert isinstance(result, responses.RedirectResponse)
    redirect_url = result.headers.get("location")

    # Should be /dashboard?token=xxx&refresh_token=xxx
    assert redirect_url.startswith("/dashboard")
    assert "?token=test_access_token" in redirect_url
    assert "&refresh_token=test_refresh_token" in redirect_url
    assert "#" not in redirect_url  # No hash fragment
