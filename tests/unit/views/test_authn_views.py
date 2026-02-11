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

AUTH_USER = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}


@pytest.mark.anyio
async def test_get_login(with_auth_systems):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems

    found = await authn_views.get_login(the_installation)

    with_auth_systems_map = {asys.id: asys for asys in with_auth_systems}

    for (f_key, f_val), (e_key, e_val) in zip(
        sorted(found.items()),
        sorted(with_auth_systems_map.items()),
        strict=True,
    ):
        assert isinstance(f_val, models.OIDCAuthSystem)
        assert f_key == e_key
        assert f_val.title == e_val.title


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@mock.patch("soliplex.authn.get_oauth")
async def test_get_login_system(get_oauth, w_return_to, w_auth_disabled):
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled

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
                request,
                system,
                the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        oidc.authorize_redirect.assert_not_called()
        ar.assert_not_awaited()
        rqp.assert_not_called()
        ruf.assert_not_called()
        cc.assert_not_called()

    else:
        found = await authn_views.get_login_system(
            request,
            system,
            the_installation,
        )

        assert found is oidc.authorize_redirect.return_value

        ar.assert_awaited_once_with(request, rqp.return_value)
        rqp.assert_called_once_with(return_to=exp_path)
        ruf.assert_called_once_with("get_auth_system", system=system)
        cc.assert_called_once_with(system)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@pytest.mark.parametrize("w_error", [None, "aat", "authenticate"])
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.loggers.LogWrapper")
async def test_get_auth_system(
    lw_klass,
    auth_fn,
    get_oauth,
    w_error,
    w_return_to,
    w_auth_disabled,
):
    lw = lw_klass.return_value
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled

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
            "refresh_expires_in": "REFRESH_EXPIRES_IN",
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
            "&expires_in=EXPIRES_IN&refresh_expires_in=REFRESH_EXPIRES_IN"
        )
        qs = "return_to=/another/path"
    else:
        exp_path = (
            "/?token=TOKEN&refresh_token=RTOKEN"
            "&expires_in=EXPIRES_IN&refresh_expires_in=REFRESH_EXPIRES_IN"
        )
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
            "refresh_expires_in": "REFRESH_EXPIRES_IN",
        }

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_auth_system(
                request,
                system,
                the_installation,
            )
        lw.debug.assert_called_once_with(loggers.AUTHN_NO_AUTH_MODE)

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.AUTHN_NO_AUTH_MODE

        aat.assert_not_awaited()
        auth_fn.assert_not_called()
        cc.assert_not_called()

    else:
        if w_error is not None:
            with pytest.raises(fastapi.HTTPException) as exc:
                await authn_views.get_auth_system(
                    request,
                    system,
                    the_installation,
                )

            lw.exception.assert_called_once_with(
                loggers.AUTHN_JWT_INVALID,
            )

            assert exc.value.status_code == 401
        else:
            response = await authn_views.get_auth_system(
                request,
                system,
                the_installation,
            )

            assert isinstance(response, responses.RedirectResponse)
            assert response.status_code == 307
            assert response.headers["location"] == exp_path

            lw.debug.assert_called_once_with(loggers.AUTHN_JWT_VALID)

        aat.assert_awaited_once_with(request)

        if w_error != "aat":
            auth_fn.assert_called_once_with(the_installation, "TOKEN")
        else:
            auth_fn.assert_not_called()

        cc.assert_called_once_with(system)


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
    installation = mock.Mock()
    installation.auth_disabled = False
    installation.oidc_auth_system_configs = []

    # Mock OAuth components
    oauth = mock.Mock()
    oauth_app = mock.Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
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
    installation = mock.Mock()
    installation.auth_disabled = False
    installation.oidc_auth_system_configs = []

    # Mock OAuth components
    oauth = mock.Mock()
    oauth_app = mock.Mock()
    tokendict = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_in": 3600,
        "refresh_expires_in": 86400,
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


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@mock.patch("soliplex.authn.authenticate")
async def test_get_user_info(authenticate, w_auth_disabled):
    authenticate.return_value = AUTH_USER

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    token = object()

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_user_info(the_installation, token)

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        authenticate.assert_not_called()

    else:
        found = await authn_views.get_user_info(the_installation, token)

        assert found == AUTH_USER

        authenticate.assert_called_once_with(the_installation, token)
