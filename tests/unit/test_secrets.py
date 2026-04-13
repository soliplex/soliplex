import contextlib
import pathlib
import sys
from unittest import mock

import pytest

from soliplex import secrets
from soliplex.config import installation as config_installation
from soliplex.config import secrets as config_secrets

SECRET_NAME = "TEST_SECRET"
ENV_VAR_NAME = "TEST_ENV_VAR"
SECRET_VALUE = "DEADBEEF"
OTHER_SECRET_VALUE = "FACEDACE"
ERROR_MISS = object()

SECRET_NAME_1 = "TEST_SECRET"
SECRET_NAME_2 = "OTHER_SECRET"
SECRET_CONFIG_1 = config_secrets.SecretConfig(secret_name=SECRET_NAME_1)
SECRET_CONFIG_2 = config_secrets.SecretConfig(secret_name=SECRET_NAME_2)

NoRaise = contextlib.nullcontext()
EnvVarNotFound = pytest.raises(secrets.SecretEnvVarNotFound)
FilePathNotFound = pytest.raises(secrets.SecretFilePathNotFound)
SubprocessError = pytest.raises(secrets.SecretSubprocessError)
ExcGroup = pytest.raises(ExceptionGroup)


@pytest.mark.parametrize(
    "secret_name, ev_name, env_patch, expectation, expected",
    [
        (
            SECRET_NAME,
            None,
            {},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            None,
            {SECRET_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {SECRET_NAME: SECRET_VALUE},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {ENV_VAR_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
    ],
)
def test_get_env_var_secret_wo_installation_config(
    secret_name,
    ev_name,
    env_patch,
    expectation,
    expected,
):
    if ev_name is None:
        source = config_secrets.EnvVarSecretSource(
            secret_name=SECRET_NAME,
        )
    else:
        source = config_secrets.EnvVarSecretSource(
            secret_name=SECRET_NAME,
            env_var_name=ev_name,
        )

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = secrets.get_env_var_secret(source)

        if expected is not ERROR_MISS:
            assert found == expected


@pytest.mark.parametrize(
    "secret_name, ev_name, env_patch, from_dotenv, expectation, expected",
    [
        (
            SECRET_NAME,
            None,
            {},
            {},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {},
            {},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            None,
            {SECRET_NAME: SECRET_VALUE},
            {},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            None,
            {},
            {SECRET_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {SECRET_NAME: SECRET_VALUE},
            {},
            EnvVarNotFound,
            ERROR_MISS,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {ENV_VAR_NAME: SECRET_VALUE},
            {},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {},
            {ENV_VAR_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
        (
            SECRET_NAME,
            ENV_VAR_NAME,
            {ENV_VAR_NAME: OTHER_SECRET_VALUE},
            {ENV_VAR_NAME: SECRET_VALUE},
            NoRaise,
            SECRET_VALUE,
        ),
    ],
)
def test_get_env_var_secret_w_installation_config(
    secret_name,
    ev_name,
    env_patch,
    from_dotenv,
    expectation,
    expected,
):
    installation_config = mock.create_autospec(
        config_installation.InstallationConfig,
        from_dotenv=from_dotenv,
    )
    if ev_name is None:
        source = config_secrets.EnvVarSecretSource(
            secret_name=SECRET_NAME,
            _installation_config=installation_config,
        )
    else:
        source = config_secrets.EnvVarSecretSource(
            secret_name=SECRET_NAME,
            env_var_name=ev_name,
            _installation_config=installation_config,
        )

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = secrets.get_env_var_secret(source)

        if expected is not ERROR_MISS:
            assert found == expected


@pytest.mark.parametrize(
    "file_path, expectation, expected",
    [
        (
            str(pathlib.Path("/path/to/nowhere").resolve()),
            FilePathNotFound,
            ERROR_MISS,
        ),
        ("./nonesuch", FilePathNotFound, ERROR_MISS),
        ("./secret_file", NoRaise, SECRET_VALUE),
    ],
)
def test_get_file_path_secret(temp_dir, file_path, expectation, expected):
    if file_path.startswith("."):
        write_file_path = temp_dir / file_path
        if expected is not ERROR_MISS:
            write_file_path.write_text(expected)

    source = config_secrets.FilePathSecretSource(
        secret_name=SECRET_NAME,
        file_path=file_path,
        _config_path=temp_dir / "installation.yaml",
    )

    with expectation:
        found = secrets.get_file_path_secret(source)

    if expected is not ERROR_MISS:
        assert found == expected


@pytest.mark.parametrize(
    "command, args, expectation, expected",
    [
        ("/nowhere/not_executable", (), SubprocessError, ERROR_MISS),
        (sys.executable, ["-c", ""], SubprocessError, ERROR_MISS),
        (
            sys.executable,
            ["-c", f"print('{SECRET_VALUE}')"],
            NoRaise,
            SECRET_VALUE,
        ),
    ],
)
def test_get_subprocess_secret(command, args, expectation, expected):
    source = config_secrets.SubprocessSecretSource(
        secret_name=SECRET_NAME,
        command=command,
        args=args,
    )

    with expectation:
        found = secrets.get_subprocess_secret(source)

    if expected is not ERROR_MISS:
        assert found == expected


@mock.patch("subprocess.check_output")
def test_get_subprocess_secret_empty_output(sco):
    sco.return_value = ""

    source = config_secrets.SubprocessSecretSource(
        secret_name=SECRET_NAME,
        command="some_cmd",
        args=(),
    )

    with SubprocessError:
        secrets.get_subprocess_secret(source)


@mock.patch("os.urandom")
def test_random_chars_secret_source(o_ur):
    source = config_secrets.RandomCharsSecretSource(
        secret_name=SECRET_NAME,
        n_chars=32,
    )

    found = secrets.get_random_chars_secret(source)

    assert found is o_ur.return_value.hex.return_value

    o_ur.assert_called_once_with(32)


ENV_VAR_MISS = config_secrets.EnvVarSecretSource(
    secret_name=SECRET_NAME,
    env_var_name="NONESUCH",
)
ENV_VAR_HIT = config_secrets.EnvVarSecretSource(
    secret_name=SECRET_NAME,
    env_var_name=ENV_VAR_NAME,
)
RANDOM_CHARS = config_secrets.RandomCharsSecretSource(secret_name=SECRET_NAME)


@pytest.mark.parametrize(
    "sources, expectation, expected",
    [
        ([ENV_VAR_MISS], ExcGroup, ERROR_MISS),
        ([ENV_VAR_MISS, ENV_VAR_HIT], NoRaise, SECRET_VALUE),
    ],
)
@mock.patch("os.urandom")
def test_secret_ctor_w_sources(
    o_ur,
    sources,
    expectation,
    expected,
):
    secret_config = config_secrets.SecretConfig(
        secret_name=SECRET_NAME,
        sources=sources,
    )

    env_patch = {ENV_VAR_NAME: SECRET_VALUE}

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        with expectation:
            found = secrets.get_secret(secret_config)

    if expected is not ERROR_MISS:
        assert found == expected


@pytest.mark.parametrize(
    "secret_configs, expectation",
    [
        ((), NoRaise),
        ([SECRET_CONFIG_1], ExcGroup),
        ([SECRET_CONFIG_1, SECRET_CONFIG_2], ExcGroup),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_resolve_secrets(gs, secret_configs, expectation):
    gs.side_effect = secrets.SecretError("testing")

    with mock.patch("os.environ", clear=True):
        with expectation as expected:
            secrets.resolve_secrets(secret_configs)

    if expected is not None:
        assert len(expected.value.exceptions) == len(secret_configs)

        for secret_config, gs_call in zip(
            secret_configs,
            gs.call_args_list,
            strict=True,
        ):
            assert gs_call == mock.call(secret_config)
