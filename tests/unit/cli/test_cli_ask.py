from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import mock

import pytest

from soliplex import loggers
from soliplex.cli import ask as cli_ask


@pytest.fixture
def no_cli_logging():
    # 'ask' calls the process-global one-shot
    # 'cli_util._configure_cli_logging', which would replace the
    # 'soliplex-audit' handlers (dropping the 'audit_records' capture) and
    # silence the logger for the rest of the run. Neutralize it here so the
    # emitted audit records stay observable and the global state is left
    # untouched.
    with mock.patch("soliplex.cli.cli_util._configure_cli_logging") as patched:
        yield patched


def _invoke(cli_runner, scratch_installation, *args):
    # 'ask.app' has a single command, which Typer promotes to the top
    # level, so the command name is not part of the invocation. Testing
    # the module's own 'app' (rather than 'cli.main') mirrors the other
    # CLI suites, e.g. 'test_cli_audit.py' invoking 'audit.app'.
    return cli_runner.invoke(
        cli_ask.app,
        [str(scratch_installation.path), *args],
    )


def _records(audit_records, message):
    return [
        record for record in audit_records if record.getMessage() == message
    ]


def _access_records(audit_records):
    return _records(audit_records, loggers.AUDIT_ROOM_AGENT_ACCESS)


def _run_records(audit_records):
    return _records(audit_records, loggers.AUDIT_ROOM_AGENT_RUN)


def test_ask_plain_success(
    no_cli_logging,
    cli_runner,
    scratch_installation,
    audit_records,
):
    result = _invoke(cli_runner, scratch_installation, "faux", "what is up?")

    assert result.exit_code == 0
    assert "I don't know!" in result.output
    # The access is recorded before the run; its success after.
    access = _access_records(audit_records)
    assert access
    assert access[-1].outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert access[-1].room_id == "faux"
    run = _run_records(audit_records)
    assert run
    assert run[-1].outcome == loggers.AUDIT_OUTCOME_SUCCESS


def test_ask_json_success(no_cli_logging, cli_runner, scratch_installation):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "faux",
        "what is up?",
        "--json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["room_id"] == "faux"
    assert payload["prompt"] == "what is up?"
    assert payload["response"] == "I don't know!"
    assert payload["thread_id"]
    # The faux agent contacts no model, so no token usage is reported.
    assert payload["usage"] == {}


def test_ask_plain_failure_reports_on_stderr(
    no_cli_logging,
    cli_runner,
    scratch_installation,
    audit_records,
):
    result = _invoke(cli_runner, scratch_installation, "faux", "fail")

    assert result.exit_code == 1
    assert "failing on request" in result.stderr
    # Access recorded (success) before the run; the failure is the run event.
    assert _access_records(audit_records)[-1].outcome == (
        loggers.AUDIT_OUTCOME_SUCCESS
    )
    run = _run_records(audit_records)
    assert run
    assert run[-1].outcome == loggers.AUDIT_OUTCOME_ERROR


def test_ask_json_failure_reports_error_object(
    no_cli_logging,
    cli_runner,
    scratch_installation,
):
    result = _invoke(
        cli_runner,
        scratch_installation,
        "faux",
        "fail",
        "--json",
    )

    assert result.exit_code == 1
    assert json.loads(result.stderr) == {"error": "failing on request"}


def test_ask_unknown_room_fails(
    no_cli_logging,
    cli_runner,
    scratch_installation,
):
    result = _invoke(cli_runner, scratch_installation, "nope", "hi")

    assert result.exit_code == 1
    assert "No room configured with id 'nope'" in result.stderr


def test_ask_configures_cli_logging(
    no_cli_logging,
    cli_runner,
    scratch_installation,
):
    result = _invoke(cli_runner, scratch_installation, "faux", "hi")

    assert result.exit_code == 0
    no_cli_logging.assert_called_once()


def test_ask_reports_run_exception(
    no_cli_logging,
    cli_runner,
    scratch_installation,
    monkeypatch,
):
    def _boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli_ask, "_run_ask", _boom)

    result = _invoke(cli_runner, scratch_installation, "faux", "hi")

    assert result.exit_code == 1
    assert "kaboom" in result.stderr


def test_ask_reports_missing_result(
    no_cli_logging,
    cli_runner,
    scratch_installation,
    audit_records,
):
    async def _one_nonterminal(**kwargs):
        # A stream that ends without a RUN_FINISHED / RUN_ERROR event.
        yield SimpleNamespace(type="SOMETHING_ELSE")

    with mock.patch.object(
        cli_ask.agui_persistence,
        "drive_agui_turn",
        _one_nonterminal,
    ):
        result = _invoke(cli_runner, scratch_installation, "faux", "hi")

    assert result.exit_code == 1
    assert "no result" in result.stderr
    assert _access_records(audit_records)[-1].outcome == (
        loggers.AUDIT_OUTCOME_SUCCESS
    )
    run = _run_records(audit_records)
    assert run
    assert run[-1].outcome == loggers.AUDIT_OUTCOME_ERROR


def test_ask_audits_run_exception(
    no_cli_logging,
    cli_runner,
    scratch_installation,
    audit_records,
    monkeypatch,
):
    def _boom(**kwargs):
        raise RuntimeError("stream boom")  # noqa: TRY003

    monkeypatch.setattr(cli_ask.agui_persistence, "drive_agui_turn", _boom)

    result = _invoke(cli_runner, scratch_installation, "faux", "hi")

    assert result.exit_code == 1
    assert "stream boom" in result.stderr
    # Access recorded before the run; an exception mid-run is a run failure.
    assert _access_records(audit_records)[-1].outcome == (
        loggers.AUDIT_OUTCOME_SUCCESS
    )
    run = _run_records(audit_records)
    assert run
    assert run[-1].outcome == loggers.AUDIT_OUTCOME_ERROR


@pytest.mark.parametrize(
    "usage, expected",
    [
        (None, {}),
        (
            SimpleNamespace(input_tokens=3, output_tokens=5),
            {"input_tokens": 3, "output_tokens": 5},
        ),
    ],
)
def test_usage_as_dict(usage, expected):
    result = cli_ask._usage_as_dict(usage)

    assert result == expected
