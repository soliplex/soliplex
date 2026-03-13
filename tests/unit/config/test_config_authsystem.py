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
W_SCOPE_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_SCOPE_AUTHSYSTEM_CONFIG_KW["scope"] = AUTHSYSTEM_SCOPE
W_SCOPE_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    scope: "{AUTHSYSTEM_SCOPE}"
"""

W_PEM_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_PEM_AUTHSYSTEM_CONFIG_KW["oidc_client_pem_path"] = (
    ABSOLUTE_OIDC_CLIENT_PEM_PATH
)
W_PEM_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{ABSOLUTE_OIDC_CLIENT_PEM_PATH}"
"""

AUTHSYSTEM_CLIENT_SECRET_LIT = "REALLY BIG SECRET"
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_LIT
)
W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_LIT}"
"""

CLIENT_SECRET_NAME = "TEST_OIDC_CLIENT_SECRET"
AUTHSYSTEM_CLIENT_SECRET_SECRET = f"secret:{CLIENT_SECRET_NAME}"
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW["client_secret"] = (
    AUTHSYSTEM_CLIENT_SECRET_SECRET
)
W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    client_secret: "{AUTHSYSTEM_CLIENT_SECRET_SECRET}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL_NAME = "cacert.pem"
AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL = "./cacert.pem"
W_OIDC_CPP_REL_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_REL_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL
W_OIDC_CPP_REL_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_REL}"
"""

AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS = str(
    pathlib.Path(here, "fixtures/cacert.pem")
)
W_OIDC_CPP_ABS_KW = BARE_AUTHSYSTEM_CONFIG_KW.copy()
W_OIDC_CPP_ABS_KW["oidc_client_pem_path"] = AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS
W_OIDC_CPP_ABS_CONFIG_YAML = f"""
{BARE_AUTHSYSTEM_CONFIG_YAML}
    oidc_client_pem_path: "{AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS}"
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
    "exp_config, exp_path",
    [
        (W_OIDC_CPP_REL_KW, "{temp_dir}/{rel_name}"),
        (
            W_OIDC_CPP_ABS_KW,
            AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS,
        ),
    ],
)
def test_authsystem_from_yaml_w_oid_cpp(
    installation_config,
    temp_dir,
    exp_config,
    exp_path,
):
    expected = config_authsystem.OIDCAuthSystemConfig(
        _installation_config=installation_config,
        **exp_config,
    )
    config_path = expected._config_path = temp_dir / "config.yaml"

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
        exp_config,
    )

    assert found == expected


def test_authsystem_server_metadata_url():
    inst = config_authsystem.OIDCAuthSystemConfig(**BARE_AUTHSYSTEM_CONFIG_KW)

    assert inst.server_metadata_url == (
        f"{AUTHSYSTEM_SERVER_URL}/"
        f"{config_authsystem.WELL_KNOWN_OPENID_CONFIGURATION}"
    )


@pytest.mark.parametrize(
    "w_config, exp_client_kwargs, exp_secret, bare_secret",
    [
        (BARE_AUTHSYSTEM_CONFIG_KW.copy(), {}, "", True),
        (
            W_CLIENT_SECRET_LIT_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_LIT,
            True,
        ),
        (
            W_CLIENT_SECRET_SECRET_AUTHSYSTEM_CONFIG_KW,
            {},
            AUTHSYSTEM_CLIENT_SECRET_SECRET,
            False,
        ),
        (W_SCOPE_AUTHSYSTEM_CONFIG_KW, {"scope": AUTHSYSTEM_SCOPE}, "", True),
        (
            W_OIDC_CPP_ABS_KW,
            {"verify": AUTHSYSTEM_OIDC_CLIENT_PEM_PATH_ABS},
            "",
            True,
        ),
    ],
)
def test_authsystem_oauth_client_args(
    installation_config,
    temp_dir,
    w_config,
    exp_client_kwargs,
    exp_secret,
    bare_secret,
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

    if bare_secret:
        icgs.side_effect = ValueError("testing")

    found = inst.oauth_client_kwargs

    assert found["name"] == AUTHSYSTEM_ID
    assert found["server_metadata_url"] == exp_url
    assert found["client_id"] == AUTHSYSTEM_CLIENT_ID
    if "verify" in found["client_kwargs"]:
        exp_client_kwargs.pop("verify")
        actual_verify = found["client_kwargs"].pop("verify")
        assert actual_verify.__class__ is ssl.SSLContext
    assert found["client_kwargs"] == exp_client_kwargs

    if bare_secret:
        assert found["client_secret"] == exp_secret
    else:
        assert found["client_secret"] is icgs.return_value

    icgs.assert_called_once_with(exp_secret)
