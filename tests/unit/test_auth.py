from unittest import mock

import fastapi
import jwt
import pytest
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import auth
from soliplex import config
from soliplex import installation

OIDC_CLIENT_PEM_PATH = "/dev/null"
AUTHSYSTEM_ID = "testing"
AUTHSYSTEM_TITLE = "Testing OIDC"
AUTHSYSTEM_SERVER_URL = "https://example.com/auth/realms/sso"
AUTHSYSTEM_CLIENT_ID = "testing-oidc"
AUTHSYSTEM_SCOPE = "test one two three"
AUTHSYSTEM_TOKEN_VALIDATION_PEM = """\
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
        RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
        mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
        cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
        3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
        jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
        9QIDAQAB
        -----END PUBLIC KEY-----
"""

WO_OIDC_PEM_OIDC_CONFIG_YAML=f"""
auth_systems:
  - id: "{AUTHSYSTEM_ID}"
    title: "{AUTHSYSTEM_TITLE}"
    server_url: "{AUTHSYSTEM_SERVER_URL}"
    client_id: "{AUTHSYSTEM_CLIENT_ID}"
    scope: "{AUTHSYSTEM_SCOPE}"
    token_validation_pem: |
{AUTHSYSTEM_TOKEN_VALIDATION_PEM}
"""

W_OIDC_PEM_OIDC_CONFIG_YAML=f"""
oidc_client_pem_path: "{OIDC_CLIENT_PEM_PATH}"

{WO_OIDC_PEM_OIDC_CONFIG_YAML}
"""

EXISTING = object()


@pytest.mark.parametrize("w_before", [None, EXISTING])
@mock.patch("os.urandom")
def test__get_session_secret_key(urandom, w_before):

    with mock.patch.multiple(auth, _session_secret_key=w_before):
        found = auth._get_session_secret_key()

    if w_before is None:
        assert found is urandom.return_value.hex.return_value
        urandom.assert_called_once_with(16)
    else:
        assert found is EXISTING
        urandom.assert_not_called()


def _auth_systems(n_auth_systems):
    return [
        mock.create_autospec(
            config.OIDCAuthSystemConfig,
            id=f"auth-system-{i_auth_system}",
            title=f"Auth System #{i_auth_system}",
            token_validation_pem=f"PEM {i_auth_system:3d}",
            oauth_client_kwargs={"name": f"auth_system_{i_auth_system:03}"},
        ) for i_auth_system in range(n_auth_systems)
    ]

@pytest.mark.parametrize("n_auth_systems", [0, 1, 2])
@mock.patch("soliplex.auth._get_session_secret_key")
@mock.patch("starlette.config.Config")
@mock.patch("authlib.integrations.starlette_client.OAuth")
def test_get_oauth_wo_initialized(
    oauth_klass, config_klass, gssk, temp_dir, n_auth_systems,
):
    auth_systems = _auth_systems(n_auth_systems)
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = auth_systems

    with (
        mock.patch("soliplex.auth._oauth", None),
    ):
        found = auth.get_oauth(the_installation)

    assert found is oauth_klass.return_value

    oauth_klass.assert_called_once_with(config_klass.return_value)

    expected_config = {
        "SESSION_SECRET_KEY": gssk.return_value
    }

    config_klass.assert_called_once_with(environ=expected_config)

    for registered, auth_system in zip(
        found.register.call_args_list, auth_systems, strict=True,
    ):
        assert (
            registered.kwargs["name"] ==
            auth_system.oauth_client_kwargs["name"]
        )


def test_get_oauth_w_initialized():
    the_installation = mock.create_autospec(installation.Installation)
    expected = object()

    with mock.patch("soliplex.auth._oauth", expected):
        found = auth.get_oauth(the_installation)

    assert found is expected


@pytest.mark.parametrize("n_auth_systems", [0, 1, 2])
def test_auth_disabled(n_auth_systems):
    auth_systems = _auth_systems(n_auth_systems)
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = auth_systems

    found = auth.auth_disabled(the_installation)

    assert found == (n_auth_systems == 0)


@pytest.mark.parametrize("w_auth_disabled", [False, True])
@mock.patch("soliplex.auth.auth_disabled")
def test_authenticate_w_token_none(ad, w_auth_disabled):
    DUMMY_USER = {
        "name": "Phreddy Phlyntstone", "email": "phreddy@example.com",
    }
    the_installation = mock.create_autospec(installation.Installation)
    ad.return_value = w_auth_disabled

    if w_auth_disabled:
        found = auth.authenticate(the_installation, None)
        assert found == DUMMY_USER

    else:
        with pytest.raises(fastapi.HTTPException) as exc:
            auth.authenticate(the_installation, None)

        assert exc.value.status_code == 401
        assert exc.value.detail == "JWT validation failed (no token)"


@pytest.fixture(params=[0, 1, 2])
def with_auth_systems(request):
    return _auth_systems(request.param)


@pytest.mark.parametrize("w_hit", [None, "first", "second"])
@mock.patch("soliplex.auth.validate_access_token")
def test_authenticate(vat, with_auth_systems, w_hit):
    FIRST_USER = {"test": "pydio"}
    SECOND_USER = {"test": "josce"}
    DUMMY_USER = {
        "name": "Phreddy Phlyntstone", "email": "phreddy@example.com",
    }
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems
    token = object()

    no_auth = len(with_auth_systems) == 0

    if w_hit is None:
        vat.return_value = None
    elif w_hit == "first":
        vat.return_value = FIRST_USER
    else:
        vat.side_effect = [None, SECOND_USER]

    if no_auth:
        found = auth.authenticate(the_installation, token)
        assert found == DUMMY_USER

    else:
        if w_hit is None or w_hit == "second" and len(with_auth_systems) < 2:
            with pytest.raises(fastapi.HTTPException) as exc:
                auth.authenticate(the_installation, token)

            assert exc.value.status_code == 401
            assert exc.value.detail == "JWT validation failed (invalid token)"

        else:
            found = auth.authenticate(the_installation, token)

            if w_hit == "first":
                assert found is FIRST_USER
                vat.assert_called_once_with(
                    token, with_auth_systems[0].token_validation_pem,
                )
            else:
                assert found is SECOND_USER
                first_call, second_call = vat.call_args_list
                assert first_call == mock.call(
                    token, with_auth_systems[0].token_validation_pem,
                )
                assert second_call == mock.call(
                    token, with_auth_systems[1].token_validation_pem,
                )


@pytest.mark.parametrize("w_hit", [False, True])
@mock.patch("jwt.decode")
def test_validate_access_token(jwtd, w_hit):
    TOKEN = object()
    PEM = "abcdef0123456789"
    PAYLOAD = {"name": "Phreddy Phlyntstone", "email": "phreddy@example.com"}

    if w_hit:
        jwtd.return_value = PAYLOAD
    else:
        jwtd.side_effect = jwt.InvalidTokenError

    found = auth.validate_access_token(TOKEN, PEM)

    if w_hit:
        assert found == PAYLOAD

    else:
        assert found is None

    jwtd.assert_called_once_with(
        TOKEN,
        PEM,
        algorithms=["RS256"],
        options={"verify_aud": False},
    )


@pytest.mark.anyio
async def test_get_login(with_auth_systems):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems

    found = await auth.get_login(the_installation)

    for f_as, e_as in zip(found["systems"], with_auth_systems, strict=True):
        assert f_as["id"] == e_as.id
        assert f_as["title"] == e_as.title


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
@pytest.mark.parametrize("w_return_to", [False, True])
@mock.patch("soliplex.auth.auth_disabled")
@mock.patch("soliplex.auth.get_oauth")
async def test_get_login_system(get_oauth, ad, w_return_to, w_auth_disabled):
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)

    ad.return_value = w_auth_disabled

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
            await auth.get_login_system(request, system, the_installation)

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        oidc.authorize_redirect.assert_not_called()
        ar.assert_not_awaited()
        rqp.assert_not_called()
        ruf.assert_not_called()
        cc.assert_not_called()

    else:
        found = await auth.get_login_system(request, system, the_installation)

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
@mock.patch("soliplex.auth.auth_disabled")
async def test_get_auth_system(
    ad, get_oauth, w_error, w_return_to, w_auth_disabled,
):
    system = "test_oauth_appname"
    the_installation = mock.create_autospec(installation.Installation)

    ad.return_value = w_auth_disabled

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

    authenticate = auth.authenticate = mock.AsyncMock()

    if w_error == "authenticate":
        authenticate.side_effect = fastapi.HTTPException(status_code=401)
    else:
        authenticate.return_value = {
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
    authenticate = auth.authenticate = mock.Mock()

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
        authenticate.side_effect = fastapi.HTTPException(status_code=401)
    else:
        authenticate.return_value = {
            "name": "Phreddy Phlyntstone",
            "email": "phreddy@example.com",
        }

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await auth.get_auth_system(request, system, the_installation)

        assert exc.value.status_code == 404
        assert exc.value.detail == "system in no-auth mode"

        aat.assert_not_awaited()
        authenticate.assert_not_called()
        cc.assert_not_called()

    else:
        if w_error is not None:
            with pytest.raises(fastapi.HTTPException) as exc:
                await auth.get_auth_system(request, system, the_installation)

            assert exc.value.status_code == 401
        else:
            response = await auth.get_auth_system(
                request, system, the_installation,
            )

            assert isinstance(response, responses.RedirectResponse)
            assert response.status_code == 307
            assert response.headers["location"] == exp_path

        aat.assert_awaited_once_with(request)

        if w_error != "aat":
            authenticate.assert_called_once_with(the_installation, "TOKEN")
        else:
            authenticate.assert_not_called()

        cc.assert_called_once_with(system)
