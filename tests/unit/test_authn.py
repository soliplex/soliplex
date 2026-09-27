import contextlib
from unittest import mock

import fastapi
import jwt
import pytest

from soliplex import authn
from soliplex import installation
from soliplex import loggers
from soliplex.config import authsystem as config_authsystem

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

AUTHSYSTEM_MISS = "authsystem-miss"
AUTHSYSTEM_CONFIG_MISS = mock.create_autospec(
    config_authsystem.OIDCAuthSystemConfig,
    id=AUTHSYSTEM_MISS,
)
AUTHSYSTEM_HIT = "authsystem-hit"
AUTHSYSTEM_CONFIG_HIT = mock.create_autospec(
    config_authsystem.OIDCAuthSystemConfig,
    id=AUTHSYSTEM_HIT,
)


def raises_httpexc(match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


ac_miss_noauth = raises_httpexc(loggers.AUTHN_NO_AUTH_MODE, 404)
ac_miss_nonesuch = raises_httpexc(loggers.AUTHN_UNKNOWN_AUTHSYSTEM, 404)
ac_hit = contextlib.nullcontext(AUTHSYSTEM_CONFIG_HIT)


@pytest.mark.parametrize(
    "w_auth_systems, expectation",
    [
        ([], ac_miss_noauth),
        ([AUTHSYSTEM_CONFIG_MISS], ac_miss_nonesuch),
        ([AUTHSYSTEM_CONFIG_MISS, AUTHSYSTEM_CONFIG_HIT], ac_hit),
        ([AUTHSYSTEM_CONFIG_HIT], ac_hit),
    ],
)
def test__get_authsystem_config(w_auth_systems, expectation):
    logger = mock.create_autospec(loggers.LogWrapper)
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = w_auth_systems

    with expectation as expected:
        found = authn._get_authsystem_config(
            the_installation=the_installation,
            logger=logger,
            system=AUTHSYSTEM_HIT,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found is expected


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
    logger = mock.create_autospec(loggers.LogWrapper)

    if w_auth_disabled:
        found = authn.authenticate(the_installation, logger, None)
        assert found == installation.NO_AUTH_MODE_USER_TOKEN

    else:
        with pytest.raises(fastapi.HTTPException) as exc:
            authn.authenticate(the_installation, logger, None)

        logger.info.assert_called_once_with(
            loggers.AUTHN_JWT_NOT_SET,
        )
        assert exc.value.status_code == 401
        assert exc.value.detail == authn.JWT_VALIDATION_NO_TOKEN


@pytest.mark.parametrize("w_hit", [None, "first", "second"])
@mock.patch("soliplex.authn.validate_access_token")
def test_authenticate(vat, with_auth_systems, w_hit):
    FIRST_USER = {"test": "pydio"}
    SECOND_USER = {"test": "josce"}
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = len(with_auth_systems) == 0
    the_installation.oidc_auth_system_configs = with_auth_systems
    logger = mock.create_autospec(loggers.LogWrapper)
    token = object()

    no_auth = len(with_auth_systems) == 0

    if w_hit is None:
        vat.return_value = None, "err"
    elif w_hit == "first":
        vat.return_value = FIRST_USER, None
    else:
        vat.side_effect = [
            (None, "err"),
            (SECOND_USER, None),
        ]

    if no_auth:
        found = authn.authenticate(the_installation, logger, token)
        assert found == installation.NO_AUTH_MODE_USER_TOKEN

    else:
        if w_hit is None or w_hit == "second" and len(with_auth_systems) < 2:
            with pytest.raises(fastapi.HTTPException) as exc:
                authn.authenticate(the_installation, logger, token)

            # Miss logs error for each system
            for system, err_call in zip(
                with_auth_systems,
                logger.error.call_args_list,
                strict=True,
            ):
                assert err_call == mock.call(
                    loggers.AUTHN_JWT_INVALID,
                    oidc_system_id=system.id,
                    reason="err",
                )

            assert exc.value.status_code == 401
            assert exc.value.detail == (
                f"{authn.JWT_VALIDATION_INVALID_TOKEN}"
            )

        else:
            found = authn.authenticate(the_installation, logger, token)

            if w_hit == "first":
                assert found is FIRST_USER
                vat.assert_called_once_with(
                    token,
                    with_auth_systems[0],
                )
            else:
                assert found is SECOND_USER
                first_call, second_call = vat.call_args_list
                assert first_call == mock.call(
                    token,
                    with_auth_systems[0],
                )
                assert second_call == mock.call(
                    token,
                    with_auth_systems[1],
                )

            logger.error.assert_not_called()


@pytest.mark.parametrize(
    "w_jwt_err, w_as_kw, exp_msg",
    [
        (
            None,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            None,
        ),
        (
            None,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {"typ": "Bearer", "foo": "QUX"},
            },
            None,
        ),
        (
            jwt.InvalidIssuerError,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            loggers.AUTHN_JWT_PARSE_INVALID_ISS,
        ),
        (
            jwt.InvalidSignatureError,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            loggers.AUTHN_JWT_PARSE_INVALID_SIG,
        ),
        (
            jwt.MissingRequiredClaimError("foo"),
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            f"{loggers.AUTHN_JWT_PARSE_REQUIRED_CLAIM}:foo",
        ),
        (
            jwt.ExpiredSignatureError,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            loggers.AUTHN_JWT_PARSE_EXPIRED_SIG,
        ),
        (
            jwt.InvalidTokenError,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {},
            },
            loggers.AUTHN_JWT_PARSE_OTHER,
        ),
        (
            None,
            {
                "accepted_azp_list": [],
                "required_claims": {},
            },
            loggers.AUTHN_JWT_BIND_AZP,
        ),
        (
            None,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {"typ": "OTHER"},
            },
            f"{loggers.AUTHN_JWT_BIND_CLAIM}:typ",
        ),
        (
            None,
            {
                "accepted_azp_list": [AUTHSYSTEM_CLIENT_ID],
                "required_claims": {"typ": "Bearer", "foo": "BAR"},
            },
            f"{loggers.AUTHN_JWT_BIND_CLAIM}:foo",
        ),
    ],
)
@mock.patch("jwt.decode")
def test_validate_access_token(jwtd, w_jwt_err, w_as_kw, exp_msg):
    TOKEN = object()
    PEM = "abcdef0123456789"
    ISSUER = "https://authn.example.com/"
    PAYLOAD = {
        "typ": "Bearer",
        "azp": AUTHSYSTEM_CLIENT_ID,
        "name": "Phreddy Phlyntstone",
        "email": "phreddy@example.com",
        "foo": "QUX",
    }

    auth_system = mock.create_autospec(
        config_authsystem.OIDCAuthSystemConfig,
        token_validation_pem=PEM,
        issuer=ISSUER,
        **w_as_kw,
    )

    if w_jwt_err is None:
        jwtd.return_value = PAYLOAD
    else:
        jwtd.side_effect = w_jwt_err

    found, msg = authn.validate_access_token(TOKEN, auth_system)

    if exp_msg is None:
        assert found == PAYLOAD
        assert msg is None

    else:
        assert found is None
        assert msg == exp_msg

    jwtd.assert_called_once_with(
        TOKEN,
        PEM,
        algorithms=["RS256"],
        issuer=ISSUER,
        options={
            "verify_aud": False,
            "require": ["exp", "iat", "iss", "sub"],
        },
    )
