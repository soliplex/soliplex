from __future__ import annotations

import json
import os
import stat
from unittest import mock

import pytest

from soliplex import token_mint
from soliplex.cli import main as cli_main
from soliplex.cli import service_token as cli_service_token
from soliplex.config import secrets as config_secrets

SECRET = "service-token-testing-secret"
NOW = 1_700_000_000
TOKEN = "DEADBEEF"
STABLE_SECRET_NAME = "TESTING_SECRET"
STABLE_ENV_VAR_NAME = "SOLIPLEX_TESTING_SERVICE_TOKEN_SECRET"


def _invoke(cli_runner, scratch_installation, *args):
    return cli_runner.invoke(
        cli_main.the_cli,
        ["service-token", "mint", str(scratch_installation.path), *args],
        env={"SOLIPLEX_URL_SAFE_TOKEN_SECRET": SECRET},
    )


# -- parse_duration ---------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("15s", 15),
        ("15m", 15 * 60),
        ("2h", 2 * 60 * 60),
        ("90d", 90 * 24 * 60 * 60),
        ("4w", 4 * 7 * 24 * 60 * 60),
        ("0m", 0),
    ],
)
def test_parse_duration(value, expected):

    found = cli_service_token.parse_duration(value)

    assert found == expected


@pytest.mark.parametrize(
    "value",
    ["", "10", "m", "10x", "1.5h", "-1h", " 10m", "10m "],
)
def test_parse_duration_invalid(value):

    with pytest.raises(cli_service_token.InvalidDuration) as exc_info:
        cli_service_token.parse_duration(value)

    assert exc_info.value.value == value


# -- parse_claims -----------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("{}", {}),
        ('{"preferred_username": "ops"}', {"preferred_username": "ops"}),
    ],
)
def test_parse_claims(value, expected):

    found = cli_service_token.parse_claims(value)

    assert found == expected


@pytest.mark.parametrize("value", ["", "{", "not json"])
def test_parse_claims_invalid_json(value):

    with pytest.raises(cli_service_token.InvalidClaimsJSON) as exc_info:
        cli_service_token.parse_claims(value)

    assert exc_info.value.value == value


@pytest.mark.parametrize("value", ["[]", '"ops"', "123", "null"])
def test_parse_claims_not_an_object(value):

    with pytest.raises(cli_service_token.ClaimsNotAnObject) as exc_info:
        cli_service_token.parse_claims(value)

    assert exc_info.value.value == value


# -- _resolve_stable_secret ------------------------------------------------


def _secret_source(kind):
    if kind == "env_var":
        return config_secrets.EnvVarSecretSource(
            secret_name=STABLE_SECRET_NAME,
            env_var_name=STABLE_ENV_VAR_NAME,
        )
    return config_secrets.RandomCharsSecretSource(
        secret_name=STABLE_SECRET_NAME,
    )


@pytest.mark.parametrize(
    "kinds, w_env_var, expected",
    [
        (["env_var", "random_chars"], True, SECRET),
        (["env_var"], True, SECRET),
        (["env_var", "random_chars"], False, None),
        (["random_chars", "env_var"], True, None),
        (["random_chars"], False, None),
        ([], False, None),
    ],
)
def test__resolve_stable_secret(monkeypatch, kinds, w_env_var, expected):
    if w_env_var:
        monkeypatch.setenv(STABLE_ENV_VAR_NAME, SECRET)
    else:
        monkeypatch.delenv(STABLE_ENV_VAR_NAME, raising=False)
    secret_config = config_secrets.SecretConfig(
        secret_name=STABLE_SECRET_NAME,
        sources=[_secret_source(kind) for kind in kinds],
    )

    found = cli_service_token._resolve_stable_secret(secret_config)

    assert found == expected


# -- _write_token -----------------------------------------------------------


@pytest.mark.parametrize("w_force", [False, True])
def test__write_token_new_file(tmp_path, w_force):
    output = tmp_path / "token"

    cli_service_token._write_token(output, TOKEN, force=w_force)

    assert output.read_text(encoding="utf-8") == f"{TOKEN}\n"


@pytest.mark.skipif(os.name != "posix", reason="POSIX file modes")
def test__write_token_owner_only(tmp_path):
    output = tmp_path / "token"

    cli_service_token._write_token(output, TOKEN, force=False)

    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test__write_token_existing_wo_force(tmp_path):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        cli_service_token._write_token(output, TOKEN, force=False)

    assert output.read_text(encoding="utf-8") == "before\n"


def test__write_token_existing_w_force(tmp_path):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    cli_service_token._write_token(output, TOKEN, force=True)

    assert output.read_text(encoding="utf-8") == f"{TOKEN}\n"


# -- mint -------------------------------------------------------------------


@mock.patch("time.time", return_value=NOW)
def test_mint(time_time, scratch_installation, cli_runner, tmp_path):
    output = tmp_path / "token"
    claims = {"sub": "ops", "preferred_username": "ops"}

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        json.dumps(claims),
        "--expires-in",
        "10m",
        "--output",
        str(output),
    )

    assert result.exit_code == 0
    token = output.read_text(encoding="utf-8").strip()
    assert token_mint.load_service_token(SECRET, token) == (
        {**claims, "iat": NOW, "exp": NOW + 600},
        None,
    )


@pytest.mark.parametrize("w_existing", [False, True])
def test_mint_w_force(scratch_installation, cli_runner, tmp_path, w_existing):
    output = tmp_path / "token"
    if w_existing:
        output.write_text("before\n", encoding="utf-8")

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        '{"sub": "ops"}',
        "--expires-in",
        "10m",
        "--output",
        str(output),
        "--force",
    )

    assert result.exit_code == 0
    token = output.read_text(encoding="utf-8").strip()
    claims, _ = token_mint.load_service_token(SECRET, token)
    assert claims["sub"] == "ops"


def test_mint_w_existing_output(scratch_installation, cli_runner, tmp_path):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        '{"sub": "ops"}',
        "--expires-in",
        "10m",
        "--output",
        str(output),
    )

    assert result.exit_code == 1
    assert output.read_text(encoding="utf-8") == "before\n"


@pytest.mark.parametrize(
    "claims, expires_in",
    [
        ('{"sub": "ops", "exp": 123}', "10m"),
        ('{"sub": "ops", "iat": 123}', "10m"),
        ('{"sub": "ops"}', "0m"),
    ],
)
def test_mint_w_invalid_token(
    scratch_installation,
    cli_runner,
    tmp_path,
    claims,
    expires_in,
):
    output = tmp_path / "token"

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        claims,
        "--expires-in",
        expires_in,
        "--output",
        str(output),
    )

    assert result.exit_code == 1
    assert not output.exists()


@pytest.mark.parametrize(
    "claims, expires_in",
    [
        ("[]", "10m"),
        ('{"sub": "ops"}', "10x"),
    ],
)
def test_mint_w_bad_parameter(
    scratch_installation,
    cli_runner,
    tmp_path,
    claims,
    expires_in,
):
    output = tmp_path / "token"

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        claims,
        "--expires-in",
        expires_in,
        "--output",
        str(output),
    )

    assert result.exit_code == 2
    assert not output.exists()


@pytest.mark.parametrize("output_args", [[], ["--output", "-"]])
@mock.patch("time.time", return_value=NOW)
def test_mint_to_stdout(
    time_time,
    scratch_installation,
    cli_runner,
    tmp_path,
    output_args,
):
    claims = {"sub": "ops", "preferred_username": "ops"}

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        json.dumps(claims),
        "--expires-in",
        "10m",
        *output_args,
    )

    assert result.exit_code == 0
    assert token_mint.load_service_token(SECRET, result.stdout.strip()) == (
        {**claims, "iat": NOW, "exp": NOW + 600},
        None,
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("w_file", [False, True])
def test_mint_summary(scratch_installation, cli_runner, tmp_path, w_file):
    output_args = ["--output", str(tmp_path / "token")] if w_file else []

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        '{"sub": "ops"}',
        "--expires-in",
        "10m",
        *output_args,
    )

    assert result.exit_code == 0
    assert result.stderr != ""


@pytest.mark.parametrize("w_file", [False, True])
def test_mint_quiet(scratch_installation, cli_runner, tmp_path, w_file):
    output_args = ["--output", str(tmp_path / "token")] if w_file else []

    result = _invoke(
        cli_runner,
        scratch_installation,
        "--claims",
        '{"sub": "ops"}',
        "--expires-in",
        "10m",
        "--quiet",
        *output_args,
    )

    assert result.exit_code == 0
    assert result.stderr == ""


def test_mint_wo_stable_secret(
    scratch_installation,
    cli_runner,
    tmp_path,
    monkeypatch,
):
    # Keep a developer's '.env' in the cwd from supplying the secret.
    monkeypatch.chdir(tmp_path)

    result = cli_runner.invoke(
        cli_main.the_cli,
        [
            "service-token",
            "mint",
            str(scratch_installation.path),
            "--claims",
            '{"sub": "ops"}',
            "--expires-in",
            "10m",
        ],
        env={"SOLIPLEX_URL_SAFE_TOKEN_SECRET": None},
    )

    assert result.exit_code == 1
    assert result.stdout == ""
