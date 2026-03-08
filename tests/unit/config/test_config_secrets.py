import contextlib
from unittest import mock

import pytest

from soliplex.config import secrets as config_secrets

NoRaise = contextlib.nullcontext()
NotASecret = pytest.raises(config_secrets.NotASecret)


SECRET_NAME = "TEST_SECRET"
SECRET_VALUE = "DEADBEEF"
SECRET_FILE_PATH = "./very_seekrit"
ENV_VAR_NAME = "TEST_ENV_VAR"
COMMAND = "cat"


@pytest.mark.parametrize(
    "w_params, exp_env_var_name",
    [
        ({}, SECRET_NAME),
        ({"env_var_name": ENV_VAR_NAME}, ENV_VAR_NAME),
    ],
)
def test_envvarsecretsource_ctor(w_params, exp_env_var_name):
    source = config_secrets.EnvVarSecretSource(
        secret_name=SECRET_NAME, **w_params
    )

    assert source.env_var_name == exp_env_var_name
    assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize("yaml_config", [{}, {"env_var_name": ENV_VAR_NAME}])
def test_envvarsecretsource_from_yaml(temp_dir, yaml_config):
    config_path = temp_dir / "installation.yaml"
    yaml_config["secret_name"] = SECRET_NAME

    source = config_secrets.EnvVarSecretSource.from_yaml(
        config_path, yaml_config
    )

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME

    exp_env_var_name = (
        ENV_VAR_NAME if "env_var_name" in yaml_config else SECRET_NAME
    )

    assert source.env_var_name == exp_env_var_name
    assert source.extra_arguments == {"env_var_name": exp_env_var_name}


@pytest.mark.parametrize("has_ev", [False, True])
def test_envvarsecretsource_as_yaml(has_ev):
    config_kw = {"secret_name": SECRET_NAME}

    if has_ev:
        config_kw["env_var_name"] = ENV_VAR_NAME

    source = config_secrets.EnvVarSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.EnvVarSecretSource.kind,
        "secret_name": SECRET_NAME,
        "env_var_name": ENV_VAR_NAME if has_ev else SECRET_NAME,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize("file_path", ["/path/to/file", "./file"])
def test_filepathsecretsource_from_yaml(temp_dir, file_path):
    config_path = temp_dir / "installation.yaml"
    yaml_config = {"secret_name": SECRET_NAME, "file_path": file_path}

    source = config_secrets.FilePathSecretSource.from_yaml(
        config_path, yaml_config
    )

    assert source._config_path == config_path
    assert source.secret_name == SECRET_NAME
    assert source.file_path == file_path
    assert source.extra_arguments == {"file_path": file_path}


def test_filepathsecretsource_as_yaml():
    config_kw = {
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    source = config_secrets.FilePathSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.FilePathSecretSource.kind,
        "secret_name": SECRET_NAME,
        "file_path": SECRET_FILE_PATH,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_args, exp_command_line",
    [
        ((), COMMAND),
        (["-a", "foo"], f"{COMMAND} -a foo"),
    ],
)
def test_subprocess_secret_source_command_line(w_args, exp_command_line):
    source = config_secrets.SubprocessSecretSource(
        secret_name=SECRET_NAME,
        command=COMMAND,
        args=w_args,
    )
    assert source.command_line == exp_command_line
    assert source.extra_arguments == {"command_line": exp_command_line}


@pytest.mark.parametrize(
    "w_args",
    [
        (),
        ["-a", "foo"],
    ],
)
def test_subprocesssecretsource_as_yaml(w_args):
    config_kw = {
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": w_args,
    }

    source = config_secrets.SubprocessSecretSource(**config_kw)

    expected = {
        "kind": config_secrets.SubprocessSecretSource.kind,
        "secret_name": SECRET_NAME,
        "command": COMMAND,
        "args": list(w_args),
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomcharssecretsource_extra_args(kwargs, exp_nc):
    source = config_secrets.RandomCharsSecretSource(
        secret_name=SECRET_NAME, **kwargs
    )

    assert source.extra_arguments == {"n_chars": exp_nc}


@pytest.mark.parametrize(
    "kwargs, exp_nc",
    [
        ({}, 32),
        ({"n_chars": 17}, 17),
    ],
)
def test_randomcharssecretsource_as_yaml(kwargs, exp_nc):
    source = config_secrets.RandomCharsSecretSource(
        secret_name=SECRET_NAME, **kwargs
    )

    expected = {
        "kind": config_secrets.RandomCharsSecretSource.kind,
        "secret_name": SECRET_NAME,
        "n_chars": exp_nc,
    }

    found = source.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "w_sources, exp_sources",
    [
        (None, [config_secrets.EnvVarSecretSource(secret_name=SECRET_NAME)]),
        (
            [
                config_secrets.EnvVarSecretSource(
                    secret_name=SECRET_NAME,
                    env_var_name=ENV_VAR_NAME,
                ),
            ],
            None,
        ),
    ],
)
def test_secretconfig_ctor(w_sources, exp_sources):
    if exp_sources is None:
        exp_sources = w_sources

    secret = config_secrets.SecretConfig(
        secret_name=SECRET_NAME, sources=w_sources
    )

    assert secret.secret_name == SECRET_NAME
    assert secret.sources == exp_sources


def test_secretconfig_as_yaml():
    source_1 = mock.Mock(spec_set=["as_yaml"])
    source_2 = mock.Mock(spec_set=["as_yaml"])
    secret = config_secrets.SecretConfig(
        secret_name=SECRET_NAME,
        sources=[source_1, source_2],
    )

    expected = {
        "secret_name": SECRET_NAME,
        "sources": [
            source_1.as_yaml,
            source_2.as_yaml,
        ],
    }
    found = secret.as_yaml

    assert found == expected


def test_secretconfig_resolved():
    secret = config_secrets.SecretConfig(secret_name=SECRET_NAME)

    assert secret.resolved is None
    secret._resolved = SECRET_VALUE
    assert secret.resolved == SECRET_VALUE


@pytest.mark.parametrize(
    "config_str, expectation, expected",
    [
        ("secret:test", NoRaise, "test"),
        ("invalid", NotASecret, None),
    ],
)
def test_strip_secret_prefix(config_str, expectation, expected):
    with expectation:
        found = config_secrets.strip_secret_prefix(config_str)

    if expected is not None:
        assert found == expected
