from __future__ import annotations

import json
import os
import stat
from unittest import mock

import pytest

from soliplex import token_mint
from soliplex.cli import main as cli_main
from soliplex.cli import service_token as cli_service_token

SECRET = "service-token-testing-secret"
NOW = 1_700_000_000
TOKEN = "DEADBEEF"


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
