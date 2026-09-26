import copy
import dataclasses
import pathlib
import ssl

import pytest
import yaml

from soliplex.config import authsystem as config_authsystem
from soliplex.config import exceptions as config_exc

here = pathlib.Path(__file__).resolve().parent

AUTHSYSTEM_ID = "testing"
AUTHSYSTEM_TITLE = "Testing OIDC"
AUTHSYSTEM_SERVER_URL = "https://example.com/auth/realms/sso"
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
AUTHSYSTEM_CLIENT_ID = "testing-oidc"

ABSOLUTE_OIDC_CLIENT_PEM_PATH = "/path/to/cacert.pem"
RELATIVE_OIDC_CLIENT_PEM_PATH = "./cacert.pem"
BARE_AUTHSYSTEM_CONFIG_KW = {
    "id": AUTHSYSTEM_ID,
    "title": AUTHSYSTEM_TITLE,
    "server_url": AUTHSYSTEM_SERVER_URL,
    "token_validation_pem": AUTHSYSTEM_TOKEN_VALIDATION_PEM,
    "client_id": AUTHSYSTEM_CLIENT_ID,
}
BARE_AUTHSYSTEM_CONFIG_YAML = f"""
    id: "{AUTHSYSTEM_ID}"
    title: "{AUTHSYSTEM_TITLE}"
    server_url: "{AUTHSYSTEM_SERVER_URL}"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAlXYDp/ux5839pPyhRAjq
        RZTeyv6fKZqgvJS2cvrNzjfttYni7/++nU2uywAiKRnxfVIf6TWKaC4/oy0VkLpW
        mkC4oyj0ArST9OYWI9mqxqdweEHrzXf8CjU7Q88LVY/9JUmHAiKjOH17m5hLY+q9
        cmIs33SMq9g7GMgPfABNsgh57Xei1sVPSzzSzTd80AguMF7B9hrNg6eTr69CN+3s
        3535wDD7tBgPzhz1qJ+lhaBSWrht9mjYpX5S0/7IQOV9M7YVBsFYztpD4Ht9TQc0
        jbVPyMXk2bi6vmfpfjCtio7RjDqi38wTf38RuD7mhPYyDOzGFcfSr4yNnORRKyYH
        9QIDAQAB
        -----END PUBLIC KEY-----
    client_id: "{AUTHSYSTEM_CLIENT_ID}"
"""

AUTHSYSTEM_SCOPE = "test one two three"
W_SCOPE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "scope": AUTHSYSTEM_SCOPE,
}
W_SCOPE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    scope: "{AUTHSYSTEM_SCOPE}"
"""

W_PEM_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "oidc_client_pem_path": ABSOLUTE_OIDC_CLIENT_PEM_PATH,
}
W_PEM_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{ABSOLUTE_OIDC_CLIENT_PEM_PATH}"
"""

AUTHSYSTEM_CLIENT_SECRET_LIT = "REALLY BIG SECRET"
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "client_secret": AUTHSYSTEM_CLIENT_SECRET_LIT,
}
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_LIT}"
"""

CLIENT_SECRET_NAME = "TEST_OIDC_CLIENT_SECRET"
AUTHSYSTEM_CLIENT_SECRET_SECRET = f"secret:{CLIENT_SECRET_NAME}"
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "client_secret": AUTHSYSTEM_CLIENT_SECRET_SECRET,
}
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_SECRET}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME = "cacert.pem"
AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL = "./cacert.pem"
W_OIDC_CPP_REL_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "oidc_client_pem_path": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL,
}
W_OIDC_CPP_REL_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS = str(
    pathlib.Path(here, "fixtures/cacert.pem")
)
W_OIDC_CPP_ABS_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "oidc_client_pem_path": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS,
}
W_OIDC_CPP_ABS_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS}"
"""

W_AFO_EMPTY_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "allowed_frontend_origins": [],
}
W_AFO_EMPTY_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    allowed_frontend_origins: []
"""

ALLOWED_FRONTEND_ORIGIN = "https://frontend.example.com"
W_AFO_NONEMPTY_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "allowed_frontend_origins": [ALLOWED_FRONTEND_ORIGIN],
}
W_AFO_NONEMPTY_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    allowed_frontend_origins:
      - "{ALLOWED_FRONTEND_ORIGIN}"
"""

UFOP = config_authsystem.UnlistedFrontendOriginPolicy
W_UFOP_CONSENT_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "unlisted_frontend_origin": UFOP.CONSENT_REQUIRED,
}
W_UFOP_CONSENT_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    unlisted_frontend_origin: "{UFOP.CONSENT_REQUIRED}"
"""

W_UFOP_DENY_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "unlisted_frontend_origin": UFOP.DENY_ALL,
}
W_UFOP_DENY_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    unlisted_frontend_origin: "{UFOP.DENY_ALL}"
"""

ABSOLUTE_CONSENT_TEMPLATE_PATH = "/path/to/consent.html.mako"
W_ABS_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "consent_template_path": ABSOLUTE_CONSENT_TEMPLATE_PATH,
}
W_ABS_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    consent_template_path: "{ABSOLUTE_CONSENT_TEMPLATE_PATH}"
"""

RELATIVE_CONSENT_TEMPLATE_PATH = "./consent.html.mako"
W_REL_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW | {
    "consent_template_path": RELATIVE_CONSENT_TEMPLATE_PATH,
}
W_REL_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    consent_template_path: "{RELATIVE_CONSENT_TEMPLATE_PATH}"
"""

W_ERROR_AUTHSYSTM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    unknown: "BOGUS"
"""


def test_authsystem_from_yaml_w_error(
    installation_config,
    temp_dir,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(W_ERROR_AUTHSYSTM_CONFIG_YAML)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    with pytest.raises(config_exc.FromYamlException) as exc_info:
        config_authsystem.OIDCAuthSystemConfig.from_yaml(
            installation_config,
            config_path,
            config_dict,
        )

    assert exc_info.value._config_path == config_path


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BARE_AUTHSYSTEM_CONFIG_YAML, BARE_AUTHSYSTEM_CONFIG_KW.copy()),
        (W_SCOPE_AUTHSYSTEM_CONFIG_YAML, W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy()),
        (W_PEM_AUTHSYSTEM_CONFIG_YAML, W_PEM_AUTHSYSTEM_CONFIG_KW.copy()),
    ],
)
def test_authsystem_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **exp_config,
    )

    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    oidc_client_pem_path = exp_config.get("oidc_client_pem_path")

    if oidc_client_pem_path is not None:
        expected = dataclasses.replace(
            expected,
            oidc_client_pem_path=config_path.parent / oidc_client_pem_path,
        )

    expected._config_path = config_path

    found = config_authsystem.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, exp_config, exp_secret",
    [
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML,
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            AUTHSYSTEM_CLIENT_SECRET_LIT,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML,
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
        ),
    ],
)
def test_authsystem_from_yaml_w_client_secret(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
    exp_secret,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        **exp_config,
    )
    expected.client_secret = exp_secret

    found = config_authsystem.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, exp_config, exp_path",
    [
        (
            W_OIDC_CPP_REL_CONFIG_YAML,
            W_OIDC_CPP_REL_CONFIG_KW,
            "{temp_dir}/{rel_name}",
        ),
        (
            W_OIDC_CPP_ABS_CONFIG_YAML,
            W_OIDC_CPP_ABS_CONFIG_KW,
            AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS,
        ),
    ],
)
def test_authsystem_from_yaml_w_oid_cpp(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
    exp_path,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        **exp_config,
    )

    if exp_path.startswith("{"):
        kwargs = {
            "temp_dir": temp_dir,
            "rel_name": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME,
        }
        exp_path = exp_path.format(**kwargs)

    expected.oidc_client_pem_path = pathlib.Path(exp_path)

    found = config_authsystem.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, exp_config, exp_ufo",
    [
        (
            W_AFO_EMPTY_AUTHSYSTEM_CONFIG_YAML,
            W_AFO_EMPTY_AUTHSYSTEM_CONFIG_KW,
            UFOP.CONSENT_REQUIRED,
        ),
        (
            W_AFO_NONEMPTY_AUTHSYSTEM_CONFIG_YAML,
            W_AFO_NONEMPTY_AUTHSYSTEM_CONFIG_KW,
            UFOP.CONSENT_REQUIRED,
        ),
        (
            W_UFOP_CONSENT_AUTHSYSTEM_CONFIG_YAML,
            W_UFOP_CONSENT_AUTHSYSTEM_CONFIG_KW,
            UFOP.CONSENT_REQUIRED,
        ),
        (
            W_UFOP_DENY_AUTHSYSTEM_CONFIG_YAML,
            W_UFOP_DENY_AUTHSYSTEM_CONFIG_KW,
            UFOP.DENY_ALL,
        ),
    ],
)
def test_authsystem_from_yaml_w_afo_ufop(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
    exp_ufo,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        **exp_config,
    )

    found = config_authsystem.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected
    assert found.unlisted_frontend_origin is exp_ufo


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (
            W_ABS_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML,
            W_ABS_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_KW.copy(),
        ),
        (
            W_REL_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML,
            W_REL_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_KW.copy(),
        ),
    ],
)
def test_authsystem_from_yaml_w_consent_template(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    config_path = temp_dir / "config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    exp_config |= {
        "consent_template_path": config_path.parent
        / exp_config["consent_template_path"],
    }

    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        **exp_config,
    )

    found = config_authsystem.OIDCAuthSystemConfig.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )

    assert found == expected


@pytest.mark.parametrize(
    "w_kw",
    [
        BARE_AUTHSYSTEM_CONFIG_KW.copy(),
        W_SCOPE_AUTHSYSTEM_CONFIG_KW.copy(),
        W_PEM_AUTHSYSTEM_CONFIG_KW.copy(),
        W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW.copy(),
        W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW.copy(),
        W_OIDC_CPP_REL_CONFIG_KW.copy(),
        W_OIDC_CPP_ABS_CONFIG_KW.copy(),
    ],
)
def test_authsystem_as_yaml(installation_config, temp_dir, w_kw):
    config_path = temp_dir / "config.yaml"

    inst = config_authsystem.OIDCAuthSystemConfig(
        **w_kw,
        _config_path=config_path,
        _installation_config=installation_config,
    )

    expected = {
        "id": w_kw["id"],
        "title": w_kw["title"],
        "server_url": w_kw["server_url"],
        "token_validation_pem": w_kw["token_validation_pem"],
        "client_id": w_kw["client_id"],
    }

    if "scope" in w_kw:
        expected["scope"] = w_kw["scope"]

    if "client_secret" in w_kw:
        expected["client_secret"] = w_kw["client_secret"]

    if "oidc_client_pem_path" in w_kw:
        expected["oidc_client_pem_path"] = str(w_kw["oidc_client_pem_path"])

    found = inst.as_yaml

    assert found == expected


def test_authsystem_as_yaml_emits_client_secret_marker_unresolved(
    installation_config,
    temp_dir,
):
    """A 'secret:' marker is dumped as configured, not resolved.

    'env:' markers are not supported: the field is declared as
    '_secret_whole_or_literal_field(default="")'
    """
    client_secret = AUTHSYSTEM_CLIENT_SECRET_SECRET

    w_kw = BARE_AUTHSYSTEM_CONFIG_KW.copy()
    w_kw["client_secret"] = client_secret
    inst = config_authsystem.OIDCAuthSystemConfig(
        **w_kw,
        _config_path=temp_dir / "config.yaml",
        _installation_config=installation_config,
    )

    found = inst.as_yaml

    assert found["client_secret"] == client_secret
    installation_config.get_secret.assert_not_called()
    installation_config.get_environment.assert_not_called()


def _round_trip_authsystem_config(
    installation_config,
    config_path,
    config_dict,
):
    """Reload an 'OIDCAuthSystemConfig' from its own dump.

    'from_yaml' drains 'oidc_client_pem_path' out of the mapping it is
    handed, hence the copies.
    """
    klass = config_authsystem.OIDCAuthSystemConfig
    original = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(config_dict),
    )
    reloaded = klass.from_yaml(
        installation_config,
        config_path,
        copy.deepcopy(original.as_yaml),
    )

    return original, reloaded


@pytest.mark.parametrize(
    "config_yaml",
    [
        BARE_AUTHSYSTEM_CONFIG_YAML,
        W_SCOPE_AUTHSYSTEM_CONFIG_YAML,
        # 'oidc_client_pem_path' is absolutized against the config dir on
        # load; re-joining an absolute path is idempotent, so a dump of
        # the resolved path should still round-trip.
        W_PEM_AUTHSYSTEM_CONFIG_YAML,
        W_OIDC_CPP_REL_CONFIG_YAML,
        W_OIDC_CPP_ABS_CONFIG_YAML,
        # 'client_secret' holds a marker, not a resolved value, so the
        # dump must emit the marker rather than 'oauth_client_kwargs''
        # resolved secret.
        W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML,
        W_AFO_EMPTY_AUTHSYSTEM_CONFIG_YAML,
        W_AFO_NONEMPTY_AUTHSYSTEM_CONFIG_YAML,
        W_UFOP_CONSENT_AUTHSYSTEM_CONFIG_YAML,
        W_UFOP_DENY_AUTHSYSTEM_CONFIG_YAML,
        W_ABS_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML,
        W_REL_CONSENT_TEMPLATE_AUTHSYSTEM_CONFIG_YAML,
    ],
)
def test_authsystem_as_yaml_round_trips(
    installation_config,
    temp_dir,
    config_yaml,
):
    original, reloaded = _round_trip_authsystem_config(
        installation_config,
        temp_dir / "config.yaml",
        yaml.safe_load(config_yaml),
    )

    assert reloaded == original


def test_authsystem_server_metadata_url():
    inst = config_authsystem.OIDCAuthSystemConfig(**BARE_AUTHSYSTEM_CONFIG_KW)

    assert inst.server_metadata_url == (
        f"{AUTHSYSTEM_SERVER_URL}/"
        f"{config_authsystem.WELL_KNOWN_OPENID_CONFIGURATION}"
    )


@pytest.mark.parametrize(
    "w_config, exp_client_kwargs, exp_secret, w_marker",
    [
        (BARE_AUTHSYSTEM_CONFIG_KW.copy(), {}, "", False),
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_LIT,
            False,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
            True,
        ),
        (W_SCOPE_AUTHSYSTEM_CONFIG_KW, {"scope": AUTHSYSTEM_SCOPE}, "", False),
        (
            W_OIDC_CPP_ABS_CONFIG_KW,
            {"verify": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS},
            "",
            False,
        ),
    ],
)
def test_authsystem_oauth_client_args(
    installation_config,
    temp_dir,
    w_config,
    exp_client_kwargs,
    exp_secret,
    w_marker,
):
    inst = config_authsystem.OIDCAuthSystemConfig(
        **w_config,
    )
    inst._installation_config = installation_config
    exp_url = (
        f"{AUTHSYSTEM_SERVER_URL}/"
        f"{config_authsystem.WELL_KNOWN_OPENID_CONFIGURATION}"
    )

    icgs = installation_config.get_secret

    found = inst.oauth_client_kwargs

    assert found["name"] == AUTHSYSTEM_ID
    assert found["server_metadata_url"] == exp_url
    assert found["client_id"] == AUTHSYSTEM_CLIENT_ID
    if "verify" in found["client_kwargs"]:
        exp_client_kwargs.pop("verify")
        actual_verify = found["client_kwargs"].pop("verify")
        assert actual_verify.__class__ is ssl.SSLContext
    assert found["client_kwargs"] == exp_client_kwargs

    if w_marker:
        assert found["client_secret"] is icgs.return_value
        icgs.assert_called_once_with(exp_secret)
    else:
        # not a 'secret:' reference, so it never reaches 'get_secret'
        assert found["client_secret"] == exp_secret
        icgs.assert_not_called()


def test_authsystem_oauth_client_args_w_unresolvable_secret(
    installation_config,
):
    """An unresolvable 'secret:' name propagates.

    It was formerly swallowed, handing the raw marker text to the IdP as
    the client secret.
    """
    inst = config_authsystem.OIDCAuthSystemConfig(
        **W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
    )
    inst._installation_config = installation_config
    installation_config.get_secret.side_effect = ValueError("testing")

    with pytest.raises(ValueError, match="testing"):
        _ = inst.oauth_client_kwargs
