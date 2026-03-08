import dataclasses

import pytest
import yaml

from soliplex.config import exceptions as config_exc
from soliplex.config import logfire as config_logfire

EMPTY_LFIPYDAI_CONFIG_YAML = ""  # raises
DEFAULT_LFIPYDAI_EXP_KWARGS = {
    "include_binary_content": True,
    "include_content": True,
}

W_VALUES_LFIPYDAI_CONFIG_KW = {
    "include_binary_content": False,
    "include_content": False,
}
W_VALUES_LFIPYDAI_CONFIG_YAML = """\
include_binary_content: false
include_content: false
"""
W_VALUES_LFIPYDAI_CONFIG_EXP_KW = W_VALUES_LFIPYDAI_CONFIG_KW

EMPTY_LFIFAPI_CONFIG_YAML = ""  # raises
DEFAULT_LFIFAPI_EXP_KWARGS = {
    "capture_headers": False,
    "excluded_urls": None,
    "record_send_receive": False,
    "extra_spans": False,
}

LFIFAPI_EXCLUDE_URL = "https://exclude-ifapi.example.com"
W_VALUES_LFIFAPI_CONFIG_KW = {
    "capture_headers": True,
    "excluded_urls": [LFIFAPI_EXCLUDE_URL],
    "record_send_receive": True,
    "extra_spans": True,
}
W_VALUES_LFIFAPI_CONFIG_YAML = f"""\
capture_headers: true
excluded_urls:
    - "{LFIFAPI_EXCLUDE_URL}"
record_send_receive: true
extra_spans: true
"""
W_VALUES_LFIFAPI_CONFIG_EXP_KW = W_VALUES_LFIFAPI_CONFIG_KW


EMPTY_LOGFIRE_CONFIG_YAML = ""  # raises

#
#   Secret / environment for default 'logfire_config' (token-only)
#
TEST_LOGFIRE_TOKEN = "DEADBEEF"
TEST_LOGFIRE_SERVICE_NAME = "test-service-name"
TEST_LOGFIRE_SERVICE_VERSION = "test-service-version"
TEST_LOGFIRE_ENVIRONMENT = "test-environment"
TEST_LOGFIRE_CONFIG_DIR = "/path/to/logfire/config"
TEST_LOGFIRE_DATA_DIR = "/path/to/logfire/data"
TEST_LOGFIRE_MIN_LEVEL = "debug"
TEST_LOGFIRE_BASE_URL = "https://logfire.example.com"

TEST_LOGFIRE_IC_DEFAULT_SECRETS = {
    "secret:LOGFIRE_TOKEN": TEST_LOGFIRE_TOKEN,
}

TEST_LOGFIRE_IC_DEFAULT_ENV = {
    "LOGFIRE_SERVICE_NAME": TEST_LOGFIRE_SERVICE_NAME,
    "LOGFIRE_SERVICE_VERSION": TEST_LOGFIRE_SERVICE_VERSION,
    "LOGFIRE_ENVIRONMENT": TEST_LOGFIRE_ENVIRONMENT,
    "LOGFIRE_CONFIG_DIR": TEST_LOGFIRE_CONFIG_DIR,
    "LOGFIRE_DATA_DIR": TEST_LOGFIRE_DATA_DIR,
    "LOGFIRE_MIN_LEVEL": TEST_LOGFIRE_MIN_LEVEL,
}

W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW = {
    "send_to_logfire": False,
    "token": "secret:LOGFIRE_TOKEN",
}
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_YAML = """\
send_to_logfire: false
token: "secret:LOGFIRE_TOKEN"
"""
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "send_to_logfire": False,
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_AS_YAML = {
    "send_to_logfire": False,
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
}
W_TOKEN_ONLY_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
"""
W_TOKEN_ONLY_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

#
#   Secret / environment for full 'logfire_config' (all scalars)
#
TEST_LOGFIRE_OTHER_TOKEN = "FACEDACE"
TEST_LOGFIRE_OTHER_SERVICE_NAME = "other-service-name"
TEST_LOGFIRE_OTHER_SERVICE_VERSION = "other-service-version"
TEST_LOGFIRE_OTHER_ENVIRONMENT = "other-environment"
TEST_LOGFIRE_OTHER_CONFIG_DIR = "/other/path/to/logfire/config"
TEST_LOGFIRE_OTHER_DATA_DIR = "/other/path/to/logfire/data"
TEST_LOGFIRE_OTHER_MIN_LEVEL = "other"
TEST_LOGFIRE_OTHER_BASE_URL = "https://logfire-other.example.com"

TEST_LOGFIRE_IC_OTHER_SECRETS = {
    "secret:LOGFIRE_TOKEN": TEST_LOGFIRE_OTHER_TOKEN,
}

TEST_LOGFIRE_IC_OTHER_ENV = {
    "LOGFIRE_SERVICE_NAME": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "LOGFIRE_SERVICE_VERSION": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "LOGFIRE_ENVIRONMENT": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "LOGFIRE_CONFIG_DIR": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "LOGFIRE_DATA_DIR": TEST_LOGFIRE_OTHER_DATA_DIR,
    "LOGFIRE_MIN_LEVEL": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "LOGFIRE_BASE_URL": TEST_LOGFIRE_OTHER_BASE_URL,
}

W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
}
W_SOME_SCALARS_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
service_name: "NOT_ENVVAR_LOGFIRE_SERVICE_NAME"
service_version: "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION"
environment: "NOT_ENVVAR_LOGFIRE_ENVIRONMENT"
"""
W_SOME_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "add_baggage_to_attributes": True,
}
W_SOME_SCALARS_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "NOT_ENVVAR_LOGFIRE_SERVICE_NAME",
    "service_version": "NOT_ENVVAR_LOGFIRE_SERVICE_VERSION",
    "environment": "NOT_ENVVAR_LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
}

W_SCALARS_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}
W_SCALARS_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
service_name: "env:LOGFIRE_SERVICE_NAME"
service_version: "env:LOGFIRE_SERVICE_VERSION"
environment: "env:LOGFIRE_ENVIRONMENT"
config_dir: "env:LOGFIRE_CONFIG_DIR"
data_dir: "env:LOGFIRE_DATA_DIR"
min_level: "env:LOGFIRE_MIN_LEVEL"
inspect_arguments: False
add_baggage_to_attributes: False
distributed_tracing: True
"""
W_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}
W_SCALARS_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "inspect_arguments": False,
    "add_baggage_to_attributes": False,
    "distributed_tracing": True,
}

W_BASE_URL_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "base_url": "env:LOGFIRE_BASE_URL",
}
W_BASE_URL_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
base_url: "env:LOGFIRE_BASE_URL"
"""
W_BASE_URL_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_OTHER_TOKEN,
    "service_name": TEST_LOGFIRE_OTHER_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_OTHER_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_OTHER_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_OTHER_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_OTHER_DATA_DIR,
    "min_level": TEST_LOGFIRE_OTHER_MIN_LEVEL,
    "add_baggage_to_attributes": True,
    "advanced": {
        "base_url": TEST_LOGFIRE_OTHER_BASE_URL,
    },
}
W_BASE_URL_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "base_url": "env:LOGFIRE_BASE_URL",
}

W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "scrubbing_patterns": [".*"],
}
W_SCRUBBING_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
scrubbing_patterns:
    - ".*"
"""
W_SCRUBBING_LOGFIRE_CONFIG_EXP_LC_KWARGS = {
    "token": TEST_LOGFIRE_TOKEN,
    "service_name": TEST_LOGFIRE_SERVICE_NAME,
    "service_version": TEST_LOGFIRE_SERVICE_VERSION,
    "environment": TEST_LOGFIRE_ENVIRONMENT,
    "config_dir": TEST_LOGFIRE_CONFIG_DIR,
    "data_dir": TEST_LOGFIRE_DATA_DIR,
    "min_level": TEST_LOGFIRE_MIN_LEVEL,
    "add_baggage_to_attributes": True,
    "scrubbing": {
        "extra_patterns": [
            ".*",
        ],
    },
}
W_SCRUBBING_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "scrubbing_patterns": [".*"],
}

W_IPYDAI_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "instrument_pydantic_ai": config_logfire.LogfireInstrumentPydanticAI(
        include_binary_content=False,
        include_content=False,
    ),
}
W_IPYDAI_LOGFIRE_CONFIG_YAML = """\
token: "secret:LOGFIRE_TOKEN"
instrument_pydantic_ai:
    include_binary_content: false
    include_content: false
"""
W_IPYDAI_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "instrument_pydantic_ai": {
        "include_binary_content": False,
        "include_content": False,
    },
}

W_IFAPI_LOGFIRE_CONFIG_INIT_KW = {
    "token": "secret:LOGFIRE_TOKEN",
    "instrument_fast_api": config_logfire.LogfireInstrumentFastAPI(
        capture_headers=True,
        excluded_urls=[LFIFAPI_EXCLUDE_URL],
        record_send_receive=True,
        extra_spans=True,
    ),
}
W_IFAPI_LOGFIRE_CONFIG_YAML = f"""\
token: "secret:LOGFIRE_TOKEN"
instrument_fast_api:
    capture_headers: true
    excluded_urls:
        - "{LFIFAPI_EXCLUDE_URL}"
    record_send_receive: true
    extra_spans: true
"""
W_IFAPI_LOGFIRE_CONFIG_AS_YAML = {
    "token": "secret:LOGFIRE_TOKEN",
    "service_name": "env:LOGFIRE_SERVICE_NAME",
    "service_version": "env:LOGFIRE_SERVICE_VERSION",
    "environment": "env:LOGFIRE_ENVIRONMENT",
    "config_dir": "env:LOGFIRE_CONFIG_DIR",
    "data_dir": "env:LOGFIRE_DATA_DIR",
    "min_level": "env:LOGFIRE_MIN_LEVEL",
    "add_baggage_to_attributes": True,
    "instrument_fast_api": {
        "capture_headers": True,
        "excluded_urls": [LFIFAPI_EXCLUDE_URL],
        "record_send_receive": True,
        "extra_spans": True,
    },
}


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIPYDAI_EXP_KWARGS),
        (W_VALUES_LFIPYDAI_CONFIG_KW, W_VALUES_LFIPYDAI_CONFIG_EXP_KW),
    ],
)
def test_lfipydai_instrument_pydantic_ai_kwargs(init_kw, expected):
    ipydai_config = config_logfire.LogfireInstrumentPydanticAI(**init_kw)

    found = ipydai_config.instrument_pydantic_ai_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIPYDAI_EXP_KWARGS),
        (W_VALUES_LFIPYDAI_CONFIG_KW, W_VALUES_LFIPYDAI_CONFIG_EXP_KW),
    ],
)
def test_lfipydai_as_yaml(init_kw, expected):
    ipydai_config = config_logfire.LogfireInstrumentPydanticAI(**init_kw)

    found = ipydai_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LFIPYDAI_CONFIG_YAML, None),
        (W_VALUES_LFIPYDAI_CONFIG_YAML, W_VALUES_LFIPYDAI_CONFIG_KW),
    ],
)
def test_lfipydai_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    pass
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_logfire.LogfireInstrumentPydanticAI.from_yaml(
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        expected = config_logfire.LogfireInstrumentPydanticAI(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _config_path=yaml_file,
        )

        found = config_logfire.LogfireInstrumentPydanticAI.from_yaml(
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIFAPI_EXP_KWARGS),
        (W_VALUES_LFIFAPI_CONFIG_KW, W_VALUES_LFIFAPI_CONFIG_EXP_KW),
    ],
)
def test_lfifapi_instrument_fast_api_kwargs(init_kw, expected):
    ipydai_config = config_logfire.LogfireInstrumentFastAPI(**init_kw)

    found = ipydai_config.instrument_fast_api_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        ({}, DEFAULT_LFIFAPI_EXP_KWARGS),
        (W_VALUES_LFIFAPI_CONFIG_KW, W_VALUES_LFIFAPI_CONFIG_EXP_KW),
    ],
)
def test_lfifapi_as_yaml(init_kw, expected):
    ipydai_config = config_logfire.LogfireInstrumentFastAPI(**init_kw)

    found = ipydai_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LFIFAPI_CONFIG_YAML, None),
        (W_VALUES_LFIFAPI_CONFIG_YAML, W_VALUES_LFIFAPI_CONFIG_KW),
    ],
)
def test_lfifapi_from_yaml(
    temp_dir,
    config_yaml,
    expected_kw,
):
    pass
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_logfire.LogfireInstrumentFastAPI.from_yaml(
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        expected = config_logfire.LogfireInstrumentFastAPI(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _config_path=yaml_file,
        )

        found = config_logfire.LogfireInstrumentFastAPI.from_yaml(
            yaml_file,
            config_dict,
        )

        assert found == expected


@pytest.mark.parametrize(
    "init_kw, ic_secrets, ic_env, expected",
    [
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_SOME_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_SCALARS_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_OTHER_SECRETS,
            TEST_LOGFIRE_IC_OTHER_ENV,
            W_BASE_URL_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
            TEST_LOGFIRE_IC_DEFAULT_SECRETS,
            TEST_LOGFIRE_IC_DEFAULT_ENV,
            W_SCRUBBING_LOGFIRE_CONFIG_EXP_LC_KWARGS,
        ),
    ],
)
def test_logfireconfig_logfire_config_kwargs(
    installation_config,
    init_kw,
    ic_secrets,
    ic_env,
    expected,
):
    get_secret = installation_config.get_secret
    get_secret.side_effect = ic_secrets.get

    installation_config.get_environment.side_effect = ic_env.get

    lf_config = config_logfire.LogfireConfig(
        _installation_config=installation_config,
        **init_kw,
    )

    found = lf_config.logfire_config_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "init_kw, expected",
    [
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            W_SOME_SCALARS_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
            W_SCALARS_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
            W_BASE_URL_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
            W_SCRUBBING_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_IPYDAI_LOGFIRE_CONFIG_INIT_KW,
            W_IPYDAI_LOGFIRE_CONFIG_AS_YAML,
        ),
        (
            W_IFAPI_LOGFIRE_CONFIG_INIT_KW,
            W_IFAPI_LOGFIRE_CONFIG_AS_YAML,
        ),
    ],
)
def test_logfireconfig_logfire_as_yaml(
    installation_config,
    init_kw,
    expected,
):
    lf_config = config_logfire.LogfireConfig(
        _installation_config=installation_config,
        **init_kw,
    )

    found = lf_config.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (EMPTY_LOGFIRE_CONFIG_YAML, None),
        (
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_YAML,
            W_SEND_TO_LOGFIRE_FALSE_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_TOKEN_ONLY_LOGFIRE_CONFIG_YAML,
            W_TOKEN_ONLY_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SOME_SCALARS_LOGFIRE_CONFIG_YAML,
            W_SOME_SCALARS_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SCALARS_LOGFIRE_CONFIG_YAML,
            W_SCALARS_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_BASE_URL_LOGFIRE_CONFIG_YAML,
            W_BASE_URL_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_SCRUBBING_LOGFIRE_CONFIG_YAML,
            W_SCRUBBING_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_IPYDAI_LOGFIRE_CONFIG_YAML,
            W_IPYDAI_LOGFIRE_CONFIG_INIT_KW,
        ),
        (
            W_IFAPI_LOGFIRE_CONFIG_YAML,
            W_IFAPI_LOGFIRE_CONFIG_INIT_KW,
        ),
    ],
)
def test_logfireconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_logfire.LogfireConfig.from_yaml(
                installation_config,
                yaml_file,
                config_dict,
            )

        assert exc.value._config_path == yaml_file

    else:
        ipydai = expected_kw.pop("instrument_pydantic_ai", None)

        if ipydai is not None:
            ipydai = dataclasses.replace(ipydai, _config_path=yaml_file)
            expected_kw["instrument_pydantic_ai"] = ipydai

        ifapi = expected_kw.pop("instrument_fast_api", None)

        if ifapi is not None:
            ifapi = dataclasses.replace(ifapi, _config_path=yaml_file)
            expected_kw["instrument_fast_api"] = ifapi

        expected = config_logfire.LogfireConfig(**expected_kw)
        expected = dataclasses.replace(
            expected,
            _installation_config=installation_config,
            _config_path=yaml_file,
        )

        found = config_logfire.LogfireConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected
