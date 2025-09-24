from unittest import mock

import fastapi
import pytest
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import installation
from soliplex.views import auth as auth_views

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

    found = await auth_views.get_login(the_installation)

    for f_as, e_as in zip(found["systems"], with_auth_systems, strict=True):
        assert f_as["id"] == e_as.id
        assert f_as["title"] == e_as.title


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@mock.patch("soliplex.auth.get_oauth")
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

    request = fastapi.Request(scope={
        "type": "http",
        "query_string": qs,
    })
    ruf = request.url_for = mock.Mock(spec_set=())
    rqp = ruf.return_value.replace_query_params

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await auth_views.get_login_system(
                request, system, the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        oidc.authorize_redirect.assert_not_called()
        ar.assert_not_awaited()
        rqp.assert_not_called()
        ruf.assert_not_called()
        cc.assert_not_called()

    else:
        found = await auth_views.get_login_system(
            request, system, the_installation,
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
@mock.patch("soliplex.auth.get_oauth")
@mock.patch("soliplex.auth.authenticate")
async def test_get_auth_system(
    auth_fn, get_oauth, w_error, w_return_to, w_auth_disabled,
):
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
            "access_token":"TOKEN",
            "refresh_token":"RTOKEN",
            "expires_in":"EXPIRES_IN",
            "refresh_expires_in":"REFRESH_EXPIRES_IN",
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

    request = fastapi.Request(scope={
        "type": "http",
        "query_string": qs,
        "session": session,
    })

    aat = oidc.authorize_access_token = mock.AsyncMock()

    if w_error == "aat":
        aat.side_effect = starlette_client.OAuthError("testing")
    else:
        aat.return_value = {
            "access_token":"TOKEN",
            "refresh_token":"RTOKEN",
            "expires_in":"EXPIRES_IN",
            "refresh_expires_in":"REFRESH_EXPIRES_IN",
            }

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await auth_views.get_auth_system(
                request, system, the_installation,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        aat.assert_not_awaited()
        auth_fn.assert_not_called()
        cc.assert_not_called()

    else:
        if w_error is not None:
            with pytest.raises(fastapi.HTTPException) as exc:
                await auth_views.get_auth_system(
                    request, system, the_installation,
                )

            assert exc.value.status_code == 401
        else:
            response = await auth_views.get_auth_system(
                request, system, the_installation,
            )

            assert isinstance(response, responses.RedirectResponse)
            assert response.status_code == 307
            assert response.headers["location"] == exp_path

        aat.assert_awaited_once_with(request)

        if w_error != "aat":
            auth_fn.assert_called_once_with(the_installation, "TOKEN")
        else:
            auth_fn.assert_not_called()

        cc.assert_called_once_with(system)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@mock.patch("soliplex.auth.authenticate")
async def test_get_user_info(authenticate, w_auth_disabled):
    authenticate.return_value = AUTH_USER

    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    token = object()

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await auth_views.get_user_info(the_installation, token)

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        authenticate.assert_not_called()

    else:
        found = await auth_views.get_user_info(the_installation, token)

        assert found == AUTH_USER

        authenticate.assert_called_once_with(the_installation, token)
