from __future__ import annotations

import json
from unittest import mock

import pytest

from soliplex import secrets
from soliplex.cli import main as cli_main
from soliplex.config import installation as config_installation


@pytest.fixture
def cli_runner():
    from typer.testing import CliRunner

    return CliRunner()


class _FakeConfig:
    as_yaml = {"installation": "fake"}
    agui_features = ()


class _RaisingInstallation:
    """A stand-in whose secret/env resolution both raise.

    Drives the two 'except: pass' branches of the 'config' command with a
    single invocation, since a real scratch installation resolves cleanly.
    """

    _config = _FakeConfig()

    def resolve_secrets(self):
        raise secrets.SecretsNotFound("missing", [ValueError("nope")])

    def resolve_environment(self):
        raise config_installation.MissingEnvVars(
            "MISSING", [ValueError("nope")]
        )


def test_version(cli_runner):
    result = cli_runner.invoke(cli_main.the_cli, ["--version"])

    assert result.exit_code == 0
    assert "Installed soliplex version" in result.stdout


def test_config(cli_runner, scratch_installation):
    result = cli_runner.invoke(
        cli_main.the_cli,
        ["config", str(scratch_installation.path)],
    )

    assert result.exit_code == 0
    assert "# Source:" in result.stdout


def test_config_tolerates_unresolved_secrets_and_env(cli_runner):
    with mock.patch.object(
        cli_main.cli_util,
        "get_installation",
        return_value=_RaisingInstallation(),
    ):
        result = cli_runner.invoke(
            cli_main.the_cli,
            ["config", "ignored.yaml"],
        )

    assert result.exit_code == 0
    assert "installation: fake" in result.stdout


def test_agui_feature_schemas(cli_runner, scratch_installation):
    result = cli_runner.invoke(
        cli_main.the_cli,
        ["agui-feature-schemas", str(scratch_installation.path)],
    )

    assert result.exit_code == 0
    assert isinstance(json.loads(result.stdout), dict)


def test_shell(cli_runner, scratch_installation):
    with mock.patch.object(cli_main.code, "interact") as interact:
        result = cli_runner.invoke(
            cli_main.the_cli,
            ["shell", str(scratch_installation.path)],
        )

    assert result.exit_code == 0
    interact.assert_called_once()
