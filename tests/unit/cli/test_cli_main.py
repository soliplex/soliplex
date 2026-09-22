from __future__ import annotations

import json
from unittest import mock

import pytest

from soliplex import alembic_migrations
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


# --------------------------------------------------------------------------
# main: the console-script seam (see '#1371')
# --------------------------------------------------------------------------
def test_main_invokes_the_cli():
    with mock.patch.object(cli_main, "the_cli") as the_cli:
        cli_main.main()

    the_cli.assert_called_once_with()


def test_main_reports_a_migration_error_without_a_traceback(capsys):
    # Every 'admin-users' / 'room-authz' command reaches the shell through
    # here, and none of them converts the family itself.
    boom = alembic_migrations.UnstampedDatabase(["agui"])

    with mock.patch.object(cli_main, "the_cli", side_effect=boom):
        with pytest.raises(SystemExit) as exc_info:
            cli_main.main()

    assert exc_info.value.code == 1
    written = capsys.readouterr().err
    assert written.startswith("Error: agui: ")
    assert "Traceback" not in written


def test_main_leaves_other_exceptions_alone():
    # A traceback is the right answer for a bug, so only the documented
    # family is flattened.
    boom = RuntimeError("a bug")

    with mock.patch.object(cli_main, "the_cli", side_effect=boom):
        with pytest.raises(RuntimeError, match="a bug"):
            cli_main.main()
