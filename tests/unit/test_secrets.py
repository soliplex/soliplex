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

NoRaise = contextlib.nullcontext()
EnvVarNotFound = pytest.raises(secrets.SecretEnvVarNotFound)
FilePathNotFound = pytest.raises(secrets.SecretFilePathNotFound)
SubprocessError = pytest.raises(secrets.SecretSubprocessError)


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
    "file_path, expectation, content, expected",
    [
        (
            str(pathlib.Path("/path/to/nowhere").resolve()),
            FilePathNotFound,
            ERROR_MISS,
            None,
        ),
        ("./nonesuch", FilePathNotFound, ERROR_MISS, None),
        ("./secret_file", NoRaise, SECRET_VALUE, SECRET_VALUE),
        ("./secret_file", NoRaise, f"{SECRET_VALUE} ", SECRET_VALUE),
        ("./secret_file", NoRaise, f"{SECRET_VALUE}\n", SECRET_VALUE),
        ("./secret_file", NoRaise, f"\n {SECRET_VALUE}\n", SECRET_VALUE),
    ],
)
def test_get_file_path_secret(
    temp_dir,
    file_path,
    expectation,
    content,
    expected,
):
    if expected is None:
        expected = content

    if file_path.startswith("."):
        write_file_path = temp_dir / file_path
        if expected is not ERROR_MISS:
            write_file_path.write_text(content)

    source = config_secrets.FilePathSecretSource(
        secret_name=SECRET_NAME,
        file_path=file_path,
        _config_path=temp_dir / "installation.yaml",
    )

    with expectation:
        found = secrets.get_file_path_secret(source)

    if expected is not ERROR_MISS:
        assert found == expected


# Mixes both cp1252 failure modes: '’' / '—' mojibake silently, while
# 'Ł' (U+0141 -> b"\xc5\x81") lands in one of cp1252's undefined slots
# and raises outright.
NON_ASCII_SECRET = "pa’sswörd—Łódź"


def test_get_file_path_secret_w_non_ascii(temp_dir):
    """A UTF-8 secret file decodes the same whatever the host locale.

    A mojibaked secret authenticates against nothing and gives no clue
    why, so this path must not depend on the host's locale encoding.
    """
    secret_path = temp_dir / "secret_file"
    secret_text = f"{NON_ASCII_SECRET}\n"
    secret_path.write_bytes(secret_text.encode("utf-8"))

    source = config_secrets.FilePathSecretSource(
        secret_name=SECRET_NAME,
        file_path="./secret_file",
        _config_path=temp_dir / "installation.yaml",
    )

    assert secrets.get_file_path_secret(source) == NON_ASCII_SECRET


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
