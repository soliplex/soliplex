from __future__ import annotations

import contextlib
from unittest import mock

import pytest
import typer

from soliplex import installation
from soliplex.cli import cli_util
from soliplex.config import installation as config_installation

no_error_none = contextlib.nullcontext()

TESTCASE_ID = "testcase-id"

BARE_INSTALLATION_CONFIG = f"""
id: {TESTCASE_ID}
oidc_paths:
  -
"""

BAD_ENV_VAR = """
environment:
  - "NONESUCH_VAR"
"""


@pytest.fixture
def haiku_rag_yaml(tmp_path):
    yaml_file = tmp_path / "haiku.rag.yaml"
    yaml_file.write_text(f"id: {TESTCASE_ID}")

    return yaml_file


@pytest.fixture
def installation_yaml(tmp_path, haiku_rag_yaml):  # , oidc_config_yaml):
    yaml_file = tmp_path / "installation.yaml"
    yaml_file.write_text(BARE_INSTALLATION_CONFIG)

    return yaml_file


@pytest.mark.parametrize(
    "w_append_text, would_raise",
    [
        ("", False),
        (BAD_ENV_VAR, True),
    ],
)
@pytest.mark.parametrize("w_auditing", [None, False, True])
@pytest.mark.parametrize("w_dir", [False, True])
def test_get_installation(
    installation_yaml,
    w_dir,
    w_auditing,
    w_append_text,
    would_raise,
):
    installation_yaml.write_text(
        "\n".join([BARE_INSTALLATION_CONFIG, w_append_text])
    )
    w_auditing_kw = {}

    if w_auditing is not None:
        w_auditing_kw["auditing"] = w_auditing

    if not would_raise or w_auditing:
        expectation = no_error_none
    else:
        expectation = pytest.raises(config_installation.MissingEnvVars)

    if w_dir:
        installation_path = installation_yaml.parent
    else:
        installation_path = installation_yaml

    with expectation as expected:
        found = cli_util.get_installation(installation_path, **w_auditing_kw)

    if expected is None:
        assert isinstance(found, installation.Installation)


@pytest.mark.parametrize(
    "dburi, expectation",
    [
        ("pgsql:db.example.com@/dbname", no_error_none),
        (
            config_installation.SYNC_MEMORY_ENGINE_URL,
            pytest.raises(typer.Exit),
        ),
    ],
)
@mock.patch("soliplex.cli.cli_util.the_console")
def test__check_ram_dburi(the_console, dburi, expectation):

    with expectation as expected:
        cli_util._check_ram_dburi(dburi, "test-command")

    if expected is not None:
        (return_code,) = expected.value.args
        assert return_code == 1
        the_console.rule.assert_called_once_with(
            "Authorization DB is RAM-based",
        )
        the_console.print.assert_called_once_with(
            "'test-command' is a no-op with a RAM-based database",
        )
