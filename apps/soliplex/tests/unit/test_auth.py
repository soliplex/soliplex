from unittest import mock

import fastapi
import jwt
import pytest

from soliplex import auth
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


@mock.patch("soliplex.auth._get_session_secret_key")
@mock.patch("starlette.config.Config")
@mock.patch("authlib.integrations.starlette_client.OAuth")
def test_get_oauth_wo_initialized(
    oauth_klass,
    config_klass,
    gssk,
    temp_dir,
    with_auth_systems,
):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems

    with (
        mock.patch("soliplex.auth._oauth", None),
    ):
        found = auth.get_oauth(the_installation)

    assert found is oauth_klass.return_value

    oauth_klass.assert_called_once_with(config_klass.return_value)

    expected_config = {"SESSION_SECRET_KEY": gssk.return_value}

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

    with mock.patch("soliplex.auth._oauth", expected):
        found = auth.get_oauth(the_installation)

    assert found is expected


@pytest.mark.parametrize("w_auth_disabled", [False, True])
def test_authenticate_w_token_none(w_auth_disabled):
    DUMMY_USER = {
        "name": "Phreddy Phlyntstone",
        "email": "phreddy@example.com",
    }
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled

    if w_auth_disabled:
        found = auth.authenticate(the_installation, None)
        assert found == DUMMY_USER

    else:
        with pytest.raises(fastapi.HTTPException) as exc:
            auth.authenticate(the_installation, None)

        assert exc.value.status_code == 401
        assert exc.value.detail == "JWT validation failed (no token)"


@pytest.mark.parametrize("w_hit", [None, "first", "second"])
@mock.patch("soliplex.auth.validate_access_token")
def test_authenticate(vat, with_auth_systems, w_hit):
    FIRST_USER = {"test": "pydio"}
    SECOND_USER = {"test": "josce"}
    DUMMY_USER = {
        "name": "Phreddy Phlyntstone",
        "email": "phreddy@example.com",
    }
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = len(with_auth_systems) == 0
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
