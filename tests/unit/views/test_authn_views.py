from unittest import mock

import fastapi
import pytest
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.views import authn as authn_views

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}


@pytest.mark.anyio
async def test_get_login(with_auth_systems):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    found = await authn_views.get_login(
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    with_auth_systems_map = {asys.id: asys for asys in with_auth_systems}

    for (f_key, f_val), (e_key, e_val) in zip(
        sorted(found.items()),
        sorted(with_auth_systems_map.items()),
        strict=True,
    ):
        assert isinstance(f_val, models.OIDCAuthSystem)
        assert f_key == e_key
        assert f_val.title == e_val.title

    the_unauth_logger.debug.assert_called_once_with(loggers.AUTHN_GET_LOGIN)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@mock.patch("soliplex.authn.get_oauth")
async def test_get_login_system(get_oauth, w_return_to, w_auth_disabled):
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)
    bound_logger = the_unauth_logger.bind.return_value

    cc = get_oauth.return_value.create_client
    oidc = cc.return_value
    ar = oidc.authorize_redirect = mock.AsyncMock()

    if w_return_to:
        exp_path = "/another/path"
        qs = f"return_to={exp_path}"
    else:
        qs = ""
        exp_path = "/"

    request = fastapi.Request(
        scope={
            "type": "http",
            "query_string": qs,
        }
    )
    ruf = request.url_for = mock.Mock(spec_set=())
    rqp = ruf.return_value.replace_query_params

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_login_system(
                request=request,
                system=system,
                the_installation=the_installation,
                the_unauth_logger=the_unauth_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.AUTHN_NO_AUTH_MODE
        bound_logger.error.assert_called_once_with(loggers.AUTHN_NO_AUTH_MODE)

        oidc.authorize_redirect.assert_not_called()
        ar.assert_not_awaited()
        rqp.assert_not_called()
        ruf.assert_not_called()
        cc.assert_not_called()

    else:
        found = await authn_views.get_login_system(
            request=request,
            system=system,
            the_installation=the_installation,
            the_unauth_logger=the_unauth_logger,
        )

        assert found is oidc.authorize_redirect.return_value

        ar.assert_awaited_once_with(request, rqp.return_value)
        rqp.assert_called_once_with(return_to=exp_path)
        ruf.assert_called_once_with("get_auth_system", system=system)
        cc.assert_called_once_with(system)

        bound_logger.debug.assert_called_once_with(
            loggers.AUTHN_GET_LOGIN_SYSTEM
        )

    the_unauth_logger.bind.assert_called_once_with(
        oidc_system=system,
    )


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@pytest.mark.parametrize("w_error", [None, "aat", "authenticate"])
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn.authenticate")
async def test_get_auth_system(
    auth_fn,
    get_oauth,
    w_error,
    w_return_to,
    w_auth_disabled,
):
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)
    bound_logger = the_unauth_logger.bind.return_value

    cc = get_oauth.return_value.create_client
    oidc = cc.return_value
    aat = oidc.authorize_access_token = mock.AsyncMock()

    if w_error == "aat":
        aat.side_effect = starlette_client.OAuthError("testing")
    else:
        aat.return_value = {
            "access_token": "TOKEN",
            "refresh_token": "RTOKEN",
            "expires_in": "EXPIRES_IN",
        }

    if w_error == "authenticate":
        auth_fn.side_effect = fastapi.HTTPException(status_code=401)
    else:
        auth_fn.return_value = {
            "name": "Phreddy Phlyntstone",
            "email": "phreddy@example.com",
        }

    session = {}

    if w_return_to:
        exp_path = (
            "/another/path?token=TOKEN&refresh_token=RTOKEN"
            "&expires_in=EXPIRES_IN"
        )
        qs = "return_to=/another/path"
    else:
        exp_path = "/?token=TOKEN&refresh_token=RTOKEN&expires_in=EXPIRES_IN"
        qs = ""

    request = fastapi.Request(
        scope={
            "type": "http",
            "query_string": qs,
            "session": session,
        }
    )

    aat = oidc.authorize_access_token = mock.AsyncMock()

    if w_error == "aat":
        aat.side_effect = starlette_client.OAuthError("testing")
    else:
        aat.return_value = {
            "access_token": "TOKEN",
            "refresh_token": "RTOKEN",
            "expires_in": "EXPIRES_IN",
        }

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_auth_system(
                request=request,
                system=system,
                the_installation=the_installation,
                the_unauth_logger=the_unauth_logger,
            )
        bound_logger.error.assert_called_once_with(
            loggers.AUTHN_NO_AUTH_MODE,
        )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.AUTHN_NO_AUTH_MODE

        aat.assert_not_awaited()
        auth_fn.assert_not_called()
        cc.assert_not_called()

    else:
        if w_error is not None:
            with pytest.raises(fastapi.HTTPException) as exc:
                await authn_views.get_auth_system(
                    request=request,
                    system=system,
                    the_installation=the_installation,
                    the_unauth_logger=the_unauth_logger,
                )

            bound_logger.exception.assert_called_once_with(
                loggers.AUTHN_JWT_INVALID,
            )

            assert exc.value.status_code == 401
        else:
            response = await authn_views.get_auth_system(
                request=request,
                system=system,
                the_installation=the_installation,
                the_unauth_logger=the_unauth_logger,
            )

            assert isinstance(response, responses.RedirectResponse)
            assert response.status_code == 307
            assert response.headers["location"] == exp_path

            bound_logger.debug.assert_called_once_with(
                loggers.AUTHN_JWT_VALID,
            )

        aat.assert_awaited_once_with(request)

        if w_error != "aat":
            auth_fn.assert_called_once_with(the_installation, "TOKEN")
        else:
            auth_fn.assert_not_called()

        cc.assert_called_once_with(system)

    the_unauth_logger.bind.assert_called_once_with(
        oidc_system=system,
    )


@pytest.mark.anyio
async def test_get_auth_system_with_hash_routing():
    """Test that authn callback handles hash-based routing correctly."""

    # Mock request with hash-based return_to URL
    request = mock.Mock()
    request.query_params = {"return_to": "/#/authn/callback"}
    request.url_for = mock.Mock(
        return_value=mock.Mock(
            replace_query_params=mock.Mock(
                return_value="http://test/authn/system"
            )
        )
    )

    # Mock installation with empty oidc_auth_system_configs
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = False
    the_installation.oidc_auth_system_configs = []
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    # Mock OAuth components
    oauth = mock.Mock()
    oauth_app = mock.Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
    }

    oauth_app.authorize_access_token = mock.AsyncMock(return_value=tokendict)
    oauth.create_client = mock.Mock(return_value=oauth_app)

    # Patch auth functions
    with (
        mock.patch("soliplex.authn.get_oauth", return_value=oauth),
        mock.patch("soliplex.authn.authenticate"),
    ):
        # Call the function
        result = await authn_views.get_auth_system(
            request=request,
            system="pydio",
            the_installation=the_installation,
            the_unauth_logger=the_unauth_logger,
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
    request = mock.Mock()
    request.query_params = {"return_to": "/dashboard"}
    request.url_for = mock.Mock(
        return_value=mock.Mock(
            replace_query_params=mock.Mock(
                return_value="http://test/authn/system"
            )
        )
    )

    # Mock installation with empty oidc_auth_system_configs
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = False
    the_installation.oidc_auth_system_configs = []
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    # Mock OAuth components
    oauth = mock.Mock()
    oauth_app = mock.Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
    }

    oauth_app.authorize_access_token = mock.AsyncMock(return_value=tokendict)
    oauth.create_client = mock.Mock(return_value=oauth_app)

    # Patch auth functions
    with (
        mock.patch("soliplex.authn.get_oauth", return_value=oauth),
        mock.patch("soliplex.authn.authenticate"),
    ):
        # Call the function
        result = await authn_views.get_auth_system(
            request=request,
            system="pydio",
            the_installation=the_installation,
            the_unauth_logger=the_unauth_logger,
        )

    # Check that the redirect URL has standard query params
    assert isinstance(result, responses.RedirectResponse)
    redirect_url = result.headers.get("location")

    # Should be /dashboard?token=xxx&refresh_token=xxx
    assert redirect_url.startswith("/dashboard")
    assert "?token=test_access_token" in redirect_url
    assert "&refresh_token=test_refresh_token" in redirect_url
    assert "#" not in redirect_url  # No hash fragment


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
async def test_get_user_info(w_auth_disabled):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_user_info(
                the_installation=the_installation,
                the_user_claims=AUTH_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.AUTHN_NO_AUTH_MODE

        the_logger.error.assert_called_once_with(loggers.AUTHN_NO_AUTH_MODE)

    else:
        found = await authn_views.get_user_info(
            the_installation=the_installation,
            the_user_claims=AUTH_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found == models.UserProfile(**AUTH_USER_CLAIMS)

        the_logger.debug.assert_called_once_with(loggers.AUTHN_GET_USER_INFO)
