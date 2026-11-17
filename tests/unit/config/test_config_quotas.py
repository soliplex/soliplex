import pathlib
from unittest import mock

import pytest

from soliplex.config import installation as config_installation
from soliplex.config import interpolation as config_interp
from soliplex.config import quotas as config_quotas

CONFIG_PATH = pathlib.Path("/path/to/room_config.yaml")
ENV_NAME = "ROOM_UPLOAD_QUOTA"
ENV_MARKER = f"env:{ENV_NAME}"


@pytest.fixture
def installation_config():
    return mock.create_autospec(config_installation.InstallationConfig)


def _quotas(installation_config, value):
    return config_quotas.QuotasConfig(
        _room_uploads_bytes=value,
        _installation_config=installation_config,
        _config_path=CONFIG_PATH,
    )


@pytest.mark.parametrize(
    "config_yaml, exp_stored",
    [
        ({}, None),
        ({"room_uploads_bytes": 0}, 0),
        ({"room_uploads_bytes": 500_000_000}, 500_000_000),
        ({"room_uploads_bytes": ENV_MARKER}, ENV_MARKER),
    ],
)
def test_quotas_config_from_yaml(installation_config, config_yaml, exp_stored):
    found = config_quotas.QuotasConfig.from_yaml(
        installation_config,
        CONFIG_PATH,
        config_yaml,
    )

    assert found._room_uploads_bytes == exp_stored
    assert found._installation_config is installation_config
    assert found._config_path == CONFIG_PATH


@pytest.mark.parametrize(
    "config_yaml, expected_exc, match",
    [
        ("500MB", config_quotas.QuotasNotAMapping, "must be a mapping"),
        ([1], config_quotas.QuotasNotAMapping, "must be a mapping"),
        (
            {"room_uploads_byte": 1, "tokens": 2},
            config_quotas.QuotasUnknownKeys,
            r"unknown key\(s\): \['room_uploads_byte', 'tokens'\]",
        ),
        (
            {"room_uploads_bytes": -1},
            config_quotas.QuotasInvalidBytes,
            "'room_uploads_bytes' must be a non-negative integer",
        ),
        ({"room_uploads_bytes": True}, config_quotas.QuotasInvalidBytes, None),
        ({"room_uploads_bytes": 1.5}, config_quotas.QuotasInvalidBytes, None),
        (
            {"room_uploads_bytes": "500MB"},
            config_quotas.QuotasInvalidBytes,
            None,
        ),
        ({"room_uploads_bytes": None}, config_quotas.QuotasInvalidBytes, None),
        (
            {"room_uploads_bytes": "secret:QUOTA"},
            config_quotas.QuotasInvalidBytes,
            None,
        ),
        (
            {"room_uploads_bytes": f"x {ENV_MARKER}"},
            config_quotas.QuotasInvalidBytes,
            None,
        ),
        (
            {"room_uploads_bytes": "env:"},
            config_quotas.QuotasInvalidBytes,
            None,
        ),
    ],
)
def test_quotas_config_from_yaml_invalid(
    installation_config,
    config_yaml,
    expected_exc,
    match,
):
    with pytest.raises(expected_exc, match=match) as exc_info:
        config_quotas.QuotasConfig.from_yaml(
            installation_config,
            CONFIG_PATH,
            config_yaml,
        )

    assert exc_info.value._config_path == CONFIG_PATH
    assert isinstance(exc_info.value, config_quotas.InvalidQuotasConfig)
    assert str(CONFIG_PATH) in str(exc_info.value)


@pytest.mark.parametrize("value", [None, 0, 42])
def test_quotas_config_room_uploads_bytes_w_literal(
    installation_config,
    value,
):
    quotas = _quotas(installation_config, value)

    assert quotas.room_uploads_bytes == value
    installation_config.get_environment.assert_not_called()


@pytest.mark.parametrize(
    "env_value, expected",
    [("500", 500), ("0", 0), (500, 500), (0, 0)],
)
def test_quotas_config_room_uploads_bytes_w_env(
    installation_config,
    env_value,
    expected,
):
    installation_config.get_environment.return_value = env_value
    quotas = _quotas(installation_config, ENV_MARKER)

    assert quotas.room_uploads_bytes == expected
    installation_config.get_environment.assert_called_once_with(ENV_NAME)


def test_quotas_config_room_uploads_bytes_w_env_unresolved(
    installation_config,
):
    installation_config.get_environment.return_value = None
    quotas = _quotas(installation_config, ENV_MARKER)

    with pytest.raises(
        config_quotas.QuotasUnresolvedEnvironment,
        match=f"'{ENV_NAME}', which has no value",
    ) as exc_info:
        _ = quotas.room_uploads_bytes

    assert exc_info.value.env_name == ENV_NAME
    assert exc_info.value._config_path == CONFIG_PATH


@pytest.mark.parametrize(
    "env_value",
    ["500MB", "-1", "1_000", " 5", "", "1e9", -1, 1.5, True],
)
def test_quotas_config_room_uploads_bytes_w_env_invalid(
    installation_config,
    env_value,
):
    installation_config.get_environment.return_value = env_value
    quotas = _quotas(installation_config, ENV_MARKER)

    with pytest.raises(
        config_quotas.QuotasInvalidEnvironmentValue,
        match="is not a non-negative integer",
    ) as exc_info:
        _ = quotas.room_uploads_bytes

    assert exc_info.value.env_name == ENV_NAME
    assert exc_info.value.value == env_value


def test_quotas_config_room_uploads_bytes_wo_installation_config():
    # A WHOLE_OPTIONAL marker with nothing to resolve it passes through
    # 'resolve_field' as written, which is not a byte count.
    quotas = _quotas(None, ENV_MARKER)

    with pytest.raises(config_quotas.QuotasInvalidEnvironmentValue):
        _ = quotas.room_uploads_bytes


@pytest.mark.parametrize(
    "value, expected",
    [
        (None, {}),
        (0, {"room_uploads_bytes": 0}),
        (42, {"room_uploads_bytes": 42}),
        (ENV_MARKER, {"room_uploads_bytes": ENV_MARKER}),
    ],
)
def test_quotas_config_as_yaml(installation_config, value, expected):
    quotas = _quotas(installation_config, value)

    assert quotas.as_yaml == expected


@pytest.mark.parametrize("value", [None, 0, 42, ENV_MARKER])
def test_quotas_config_as_yaml_round_trips(installation_config, value):
    quotas = _quotas(installation_config, value)

    found = config_quotas.QuotasConfig.from_yaml(
        installation_config,
        CONFIG_PATH,
        quotas.as_yaml,
    )

    assert found == quotas


def test_quotas_config_compares_wo_context(installation_config):
    # The context 'from_yaml' sets does not take part in comparison, so a
    # room with an empty 'quotas:' stanza equals one with none at all.
    assert _quotas(installation_config, None) == config_quotas.QuotasConfig()


def test_quotas_config_interpolation_spec():
    spec = config_interp.spec_for(
        config_quotas.QuotasConfig,
        "_room_uploads_bytes",
    )

    assert spec.kinds is config_interp.MarkerKind.ENVIRONMENT
    assert spec.arity is config_interp.MarkerArity.WHOLE_OPTIONAL
    assert spec.shape is config_interp.ValueShape.SCALAR
    assert spec.public_name == "quotas.room_uploads_bytes"
    assert spec.accessor == "room_uploads_bytes"


@pytest.mark.parametrize(
    "value, expected",
    [(None, None), (42, None), (ENV_MARKER, ENV_NAME)],
)
def test_quotas_config_room_uploads_bytes_env_name(
    installation_config,
    value,
    expected,
):
    quotas = _quotas(installation_config, value)

    assert quotas.room_uploads_bytes_env_name == expected
