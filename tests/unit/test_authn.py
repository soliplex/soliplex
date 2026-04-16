from unittest import mock

import fastapi
import jwt
import pytest

from soliplex import authn
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

WO_OIDC_PEM_OIDC_CONFIG_YAML = f"""
auth_systems:
  - id: "{AUTHSYSTEM_ID}"
    title: "{AUTHSYSTEM_TITLE}"
    server_url: "{AUTHSYSTEM_SERVER_URL}"
    client_id: "{AUTHSYSTEM_CLIENT_ID}"
    scope: "{AUTHSYSTEM_SCOPE}"
    token_validation_pem: |
{AUTHSYSTEM_TOKEN_VALIDATION_PEM}
"""

W_OIDC_PEM_OIDC_CONFIG_YAML = f"""
oidc_client_pem_path: "{OIDC_CLIENT_PEM_PATH}"

{WO_OIDC_PEM_OIDC_CONFIG_YAML}
"""

EXISTING = object()


@mock.patch("starlette.config.Config")
@mock.patch("authlib.integrations.starlette_client.OAuth")
def test_get_oauth_wo_initialized(
    oauth_klass,
    config_klass,
    temp_dir,
    with_auth_systems,
):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems

    with (
        mock.patch("soliplex.authn._oauth", None),
    ):
        found = authn.get_oauth(the_installation)

    assert found is oauth_klass.return_value

    oauth_klass.assert_called_once_with(config_klass.return_value)

    expected_config = {}

    config_klass.assert_called_once_with(environ=expected_config)

    for registered, auth_system in zip(
        found.register.call_args_list,
        with_auth_systems,
        strict=True,
    ):
        assert (
            registered.kwargs["name"]
            == auth_system.oauth_client_kwargs["name"]
        )


def test_get_oauth_w_initialized():
    the_installation = mock.create_autospec(installation.Installation)
    expected = object()

    with mock.patch("soliplex.authn._oauth", expected):
        found = authn.get_oauth(the_installation)

    assert found is expected


@pytest.mark.parametrize("w_auth_disabled", [False, True])
def test_authenticate_w_token_none(w_auth_disabled):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled

    if w_auth_disabled:
        found = authn.authenticate(the_installation, None)
        assert found == installation.NO_AUTH_MODE_USER_TOKEN

    else:
        with pytest.raises(fastapi.HTTPException) as exc:
            authn.authenticate(the_installation, None)

        assert exc.value.status_code == 401
        assert exc.value.detail == authn.JWT_VALIDATION_NO_TOKEN


@pytest.mark.parametrize("w_hit", [None, "first", "second"])
@mock.patch("soliplex.authn.validate_access_token")
def test_authenticate(vat, with_auth_systems, w_hit):
    FIRST_USER = {"test": "pydio"}
    SECOND_USER = {"test": "acme"}
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = len(with_auth_systems) == 0
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_installation.lti_platform_configs = []
    token = object()

    no_auth = len(with_auth_systems) == 0

    if w_hit is None:
        vat.return_value = None
    elif w_hit == "first":
        vat.return_value = FIRST_USER
    else:
        vat.side_effect = [None, SECOND_USER]

    if no_auth:
        found = authn.authenticate(the_installation, token)
        assert found == installation.NO_AUTH_MODE_USER_TOKEN

    else:
        if w_hit is None or w_hit == "second" and len(with_auth_systems) < 2:
            with pytest.raises(fastapi.HTTPException) as exc:
                authn.authenticate(the_installation, token)

            assert exc.value.status_code == 401
            assert exc.value.detail == authn.JWT_VALIDATION_INVALID_TOKEN

        else:
            found = authn.authenticate(the_installation, token)

            if w_hit == "first":
                assert found is FIRST_USER
                vat.assert_called_once_with(
                    token,
                    with_auth_systems[0].token_validation_pem,
                )
            else:
                assert found is SECOND_USER
                first_call, second_call = vat.call_args_list
                assert first_call == mock.call(
                    token,
                    with_auth_systems[0].token_validation_pem,
                )
                assert second_call == mock.call(
                    token,
                    with_auth_systems[1].token_validation_pem,
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

    found = authn.validate_access_token(TOKEN, PEM)

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


# -- LTI session token fallback tests --

LTI_SECRET = "test-lti-secret"
LTI_CLAIMS = {"sub": "lti-user", "email": "lti@example.com"}


def _make_lti_platform(session_ttl=3600):
    from soliplex.config import lti as config_lti

    return config_lti.LTIPlatformConfig(
        id="moodle",
        issuer="https://moodle.example.com",
        client_id="tool-1",
        auth_login_url="https://moodle.example.com/auth",
        auth_token_url="https://moodle.example.com/token",
        key_set_url="https://moodle.example.com/certs",
        default_room_id="room-1",
        session_ttl=session_ttl,
    )


@mock.patch("soliplex.authn.validate_access_token")
@mock.patch("soliplex.lti.session.validate_session_token")
def test_authenticate_lti_fallback_hit(vst, vat, with_auth_systems):
    """LTI session token accepted after OIDC miss"""
    vat.return_value = None
    vst.return_value = LTI_CLAIMS

    platform = _make_lti_platform()
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = False
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_installation.lti_platform_configs = [platform]
    the_installation.get_secret.return_value = LTI_SECRET

    found = authn.authenticate(the_installation, "tok")

    assert found is LTI_CLAIMS
    vst.assert_called_once_with(LTI_SECRET, "tok", max_age=3600)


@mock.patch("soliplex.authn.validate_access_token")
@mock.patch("soliplex.lti.session.validate_session_token")
def test_authenticate_lti_fallback_miss(vst, vat, with_auth_systems):
    """LTI session token miss still raises 401"""
    vat.return_value = None
    vst.return_value = None

    platform = _make_lti_platform()
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = False
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_installation.lti_platform_configs = [platform]
    the_installation.get_secret.return_value = LTI_SECRET

    with pytest.raises(fastapi.HTTPException) as exc:
        authn.authenticate(the_installation, "tok")

    assert exc.value.status_code == 401


@mock.patch("soliplex.authn.validate_access_token")
def test_authenticate_lti_secret_missing(vat, with_auth_systems):
    """Missing LTI secret skips LTI check gracefully"""
    vat.return_value = None

    platform = _make_lti_platform()
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = False
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_installation.lti_platform_configs = [platform]
    the_installation.get_secret.side_effect = KeyError("LTI_SESSION_SECRET")

    with pytest.raises(fastapi.HTTPException) as exc:
        authn.authenticate(the_installation, "tok")

    assert exc.value.status_code == 401
