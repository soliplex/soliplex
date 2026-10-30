from __future__ import annotations

import io
import json
import pathlib
from unittest import mock

import pytest
import typer
from rich import console

from soliplex import loggers
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


def _invoke_validate(cli_runner, scratch_installation, *args, stdin=None):
    return cli_runner.invoke(
        cli_main.the_cli,
        ["service-token", "validate", str(scratch_installation.path), *args],
        env={"SOLIPLEX_URL_SAFE_TOKEN_SECRET": SECRET},
        input=stdin,
    )


@pytest.fixture
def recording_console(monkeypatch):
    recording = console.Console(file=io.StringIO(), width=1000)
    monkeypatch.setattr(cli_service_token, "the_console", recording)
    return recording


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


# -- _get_stable_secret ----------------------------------------------------


def test__get_stable_secret(scratch_installation, monkeypatch):
    monkeypatch.setenv("SOLIPLEX_URL_SAFE_TOKEN_SECRET", SECRET)

    found = cli_service_token._get_stable_secret(scratch_installation.path)

    assert found == SECRET


def test__get_stable_secret_wo_stable_secret(
    scratch_installation,
    monkeypatch,
    tmp_path,
):
    # Keep a developer's '.env' in the cwd from supplying the secret.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SOLIPLEX_URL_SAFE_TOKEN_SECRET", raising=False)

    with pytest.raises(typer.Exit) as exc_info:
        cli_service_token._get_stable_secret(scratch_installation.path)

    assert exc_info.value.exit_code == 1


# -- _write_output ----------------------------------------------------------


@pytest.mark.parametrize("w_force", [False, True])
def test__write_output_new_file(tmp_path, w_force):
    output = tmp_path / "token"

    cli_service_token._write_output(output, TOKEN, force=w_force)

    assert output.read_text(encoding="utf-8") == TOKEN


def test__write_output_existing_wo_force(tmp_path):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        cli_service_token._write_output(output, TOKEN, force=False)

    assert output.read_text(encoding="utf-8") == "before\n"


def test__write_output_existing_w_force(tmp_path):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    cli_service_token._write_output(output, TOKEN, force=True)

    assert output.read_text(encoding="utf-8") == TOKEN


# -- _emit ------------------------------------------------------------------


def test__emit_to_stdout(capsys):

    cli_service_token._emit(
        cli_service_token.STDOUT_OUTPUT,
        f"{TOKEN}\n",
        force=False,
    )

    assert capsys.readouterr().out == f"{TOKEN}\n"


@pytest.mark.parametrize("w_existing", [False, True])
def test__emit_to_file(tmp_path, w_existing):
    output = tmp_path / "token"
    if w_existing:
        output.write_text("before\n", encoding="utf-8")

    cli_service_token._emit(output, f"{TOKEN}\n", force=True)

    assert output.read_text(encoding="utf-8") == f"{TOKEN}\n"


def test__emit_to_existing_file_wo_force(tmp_path, recording_console):
    output = tmp_path / "token"
    output.write_text("before\n", encoding="utf-8")

    with pytest.raises(typer.Exit) as exc_info:
        cli_service_token._emit(output, f"{TOKEN}\n", force=False)

    assert exc_info.value.exit_code == 1
    assert output.read_text(encoding="utf-8") == "before\n"


# -- _read_token ------------------------------------------------------------


@pytest.mark.parametrize("text", [TOKEN, f"{TOKEN}\n", f"  {TOKEN}\n\n"])
def test__read_token_from_file(tmp_path, text):
    input_path = tmp_path / "token"
    input_path.write_text(text, encoding="utf-8")

    found = cli_service_token._read_token(input_path)

    assert found == TOKEN


@pytest.mark.parametrize("text", [TOKEN, f"{TOKEN}\n", f"  {TOKEN}\n\n"])
def test__read_token_from_stdin(monkeypatch, text):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))

    found = cli_service_token._read_token(cli_service_token.STDIN_INPUT)

    assert found == TOKEN


# -- _format_claims ---------------------------------------------------------


CLAIMS = {"sub": "ops", "preferred_username": "ops", "exp": NOW + 600}


@pytest.mark.parametrize(
    "output", ["-", "claims", "claims.json", "x.yaml.txt"]
)
def test__format_claims_as_json(output):

    found = cli_service_token._format_claims(CLAIMS, pathlib.Path(output))

    assert found == (
        "{\n"
        '  "sub": "ops",\n'
        '  "preferred_username": "ops",\n'
        '  "exp": 1700000600\n'
        "}\n"
    )


@pytest.mark.parametrize(
    "output", ["claims.yaml", "claims.yml", "CLAIMS.YAML"]
)
def test__format_claims_as_yaml(output):

    found = cli_service_token._format_claims(CLAIMS, pathlib.Path(output))

    assert found == "sub: ops\npreferred_username: ops\nexp: 1700000600\n"


# -- _print_summary ---------------------------------------------------------


@pytest.mark.parametrize("w_file", [False, True])
def test__print_summary(tmp_path, recording_console, w_file):
    output = tmp_path / "claims" if w_file else cli_service_token.STDOUT_OUTPUT

    cli_service_token._print_summary("Testing", CLAIMS, output)

    lines = recording_console.file.getvalue().splitlines()
    assert "Testing" in lines[0]
    assert ("Written to: " + str(output) in lines) == w_file
    assert "Subject:    ops" in lines
    assert "Expires:    2023-11-14T22:23:20+00:00" in lines


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


# -- validate ---------------------------------------------------------------


def _mint(claims=None, *, expires_in=600, secret=SECRET):
    if claims is None:
        claims = {"sub": "ops", "preferred_username": "ops"}
    return token_mint.mint_service_token(
        secret,
        claims,
        expires_in=expires_in,
    )


@mock.patch("time.time", return_value=NOW)
def test_validate_from_stdin(time_time, scratch_installation, cli_runner):
    claims = {"sub": "ops", "preferred_username": "ops"}

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        stdin=f"{_mint(claims)}\n",
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        **claims,
        "iat": NOW,
        "exp": NOW + 600,
    }


@mock.patch("time.time", return_value=NOW)
def test_validate_from_file(
    time_time,
    scratch_installation,
    cli_runner,
    tmp_path,
):
    claims = {"sub": "ops", "preferred_username": "ops"}
    input_path = tmp_path / "token"
    input_path.write_text(f"{_mint(claims)}\n", encoding="utf-8")

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--input",
        str(input_path),
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        **claims,
        "iat": NOW,
        "exp": NOW + 600,
    }


@mock.patch("time.time", return_value=NOW)
def test_validate_to_json_file(
    time_time,
    scratch_installation,
    cli_runner,
    tmp_path,
):
    claims = {"sub": "ops", "preferred_username": "ops"}
    output = tmp_path / "claims.json"

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "-o",
        str(output),
        stdin=_mint(claims),
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert json.loads(output.read_text(encoding="utf-8")) == {
        **claims,
        "iat": NOW,
        "exp": NOW + 600,
    }


@mock.patch("time.time", return_value=NOW)
def test_validate_to_yaml_file(
    time_time,
    scratch_installation,
    cli_runner,
    tmp_path,
):
    claims = {"sub": "ops", "preferred_username": "ops"}
    output = tmp_path / "claims.yaml"

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "-o",
        str(output),
        stdin=_mint(claims),
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert output.read_text(encoding="utf-8") == (
        "sub: ops\npreferred_username: ops\niat: 1700000000\nexp: 1700000600\n"
    )


def test_validate_w_existing_output(
    scratch_installation, cli_runner, tmp_path
):
    output = tmp_path / "claims"
    output.write_text("before\n", encoding="utf-8")

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--output",
        str(output),
        stdin=_mint(),
    )

    assert result.exit_code == 1
    assert output.read_text(encoding="utf-8") == "before\n"


def test_validate_w_force(scratch_installation, cli_runner, tmp_path):
    output = tmp_path / "claims"
    output.write_text("before\n", encoding="utf-8")

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--output",
        str(output),
        "--force",
        stdin=_mint(),
    )

    assert result.exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["sub"] == "ops"


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-token",
        _mint(secret="some-other-secret"),
        token_mint.generate_url_safe_token(
            SECRET,
            token_mint.SERVICE_TOKEN_SALT,
            sub="ops",
        ),
    ],
)
def test_validate_w_invalid_token(
    scratch_installation,
    cli_runner,
    tmp_path,
    token,
):
    output = tmp_path / "claims"

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--output",
        str(output),
        stdin=token,
    )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert not output.exists()


def test_validate_w_expired_token(scratch_installation, cli_runner):
    token = _mint(expires_in=600)

    with mock.patch("time.time", return_value=2 * NOW):
        result = _invoke_validate(
            cli_runner,
            scratch_installation,
            stdin=token,
        )

    assert result.exit_code == 1
    assert result.stdout == ""
    assert loggers.AUTHN_SERVICE_TOKEN_EXPIRED in result.stderr


def test_validate_w_missing_input(scratch_installation, cli_runner, tmp_path):

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--input",
        str(tmp_path / "nonesuch"),
    )

    assert result.exit_code == 2


@pytest.mark.parametrize("w_file", [False, True])
def test_validate_summary(scratch_installation, cli_runner, tmp_path, w_file):
    output_args = ["--output", str(tmp_path / "claims")] if w_file else []

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        *output_args,
        stdin=_mint(),
    )

    assert result.exit_code == 0
    assert result.stderr != ""


@pytest.mark.parametrize("w_file", [False, True])
def test_validate_quiet(scratch_installation, cli_runner, tmp_path, w_file):
    output_args = ["--output", str(tmp_path / "claims")] if w_file else []

    result = _invoke_validate(
        cli_runner,
        scratch_installation,
        "--quiet",
        *output_args,
        stdin=_mint(),
    )

    assert result.exit_code == 0
    assert result.stderr == ""


def test_validate_wo_stable_secret(
    scratch_installation,
    cli_runner,
    tmp_path,
    monkeypatch,
):
    # Keep a developer's '.env' in the cwd from supplying the secret.
    monkeypatch.chdir(tmp_path)

    result = cli_runner.invoke(
        cli_main.the_cli,
        ["service-token", "validate", str(scratch_installation.path)],
        env={"SOLIPLEX_URL_SAFE_TOKEN_SECRET": None},
        input=_mint(),
    )

    assert result.exit_code == 1
    assert result.stdout == ""
