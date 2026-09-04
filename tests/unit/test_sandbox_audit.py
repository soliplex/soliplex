import pathlib
from types import SimpleNamespace

import pytest

from soliplex import loggers
from soliplex import sandbox_audit

USERNAME = "phreddy"
ROOM_ID = "room-1"
THREAD_ID = "thread-1"
RUN_ID = "run-1"
WORKDIR = pathlib.Path("/work/room-1/thread-1/run-1")
TRANSCRIPT = "/transcripts/room-1/thread-1/run-1/abc123.py"
VOLUME = "thread"


class _Refused(Exception):
    """Stand-in for the skill's environment-name rejections"""


def _state():
    user = SimpleNamespace(model_dump=lambda: {"preferred_username": USERNAME})
    return SimpleNamespace(
        user=user,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


def _record_ref_then_raise(access):
    """Keeps the 'pytest.raises' body a single statement (ruff PT012)"""
    access.record_workdir(WORKDIR)
    access.record_ref(TRANSCRIPT)
    raise RuntimeError("boom")


def _raise_refused(access):
    raise _Refused


def _raise_runtime_error(access):
    raise RuntimeError("boom")


def test_audit_sandbox_exec_records_success(audit_records):
    with sandbox_audit.audit_sandbox_exec(
        _state(),
        action=loggers.AUDIT_SANDBOX_ACTION_RUN,
        environment="bare",
    ) as access:
        access.record_workdir(WORKDIR)
        access.record_ref(TRANSCRIPT)
        access.record_exit_code(0)

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir == str(WORKDIR)
    assert record.environment == "bare"
    assert record.refs == [TRANSCRIPT]
    assert record.exit_code == 0
    assert record.claims == {"preferred_username": USERNAME}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID
    assert record.run_id == RUN_ID


def test_audit_sandbox_exec_without_workdir_logs_none(audit_records):
    with sandbox_audit.audit_sandbox_exec(
        _state(),
        action=loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
        environment=None,
    ):
        pass

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir is None
    assert record.environment is None
    # Nothing recorded -> empty refs, and no status to report.
    assert record.refs == []
    assert record.exit_code is None


@pytest.mark.parametrize(
    "w_exit_code, exp_outcome, exp_reason",
    [
        (0, loggers.AUDIT_OUTCOME_SUCCESS, None),
        (None, loggers.AUDIT_OUTCOME_SUCCESS, None),
        (42, loggers.AUDIT_OUTCOME_ERROR, "exit-code"),
        (
            sandbox_audit.TIMEOUT_EXIT_CODE,
            loggers.AUDIT_OUTCOME_ERROR,
            "timeout",
        ),
    ],
)
def test_audit_sandbox_exec_records_exit_code(
    audit_records,
    w_exit_code,
    exp_outcome,
    exp_reason,
):
    """A bad exit fails the record even though the body returned cleanly"""
    with sandbox_audit.audit_sandbox_exec(
        _state(),
        action=loggers.AUDIT_SANDBOX_ACTION_RUN,
        environment="bare",
    ) as access:
        access.record_exit_code(w_exit_code)

    record = audit_records[-1]
    assert record.outcome == exp_outcome
    assert record.exit_code == w_exit_code
    assert getattr(record, "reason", None) == exp_reason


def test_audit_sandbox_exec_records_failure(audit_records):
    with pytest.raises(RuntimeError):
        with sandbox_audit.audit_sandbox_exec(
            _state(),
            action=loggers.AUDIT_SANDBOX_ACTION_RUN,
            environment="bare",
            denied_exceptions=(_Refused,),
        ) as access:
            _record_ref_then_raise(access)

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.workdir == str(WORKDIR)
    assert record.environment == "bare"
    # Refs recorded before the failure still land on the failure record.
    assert record.refs == [TRANSCRIPT]
    assert record.reason == "RuntimeError"
    assert record.exit_code is None


def test_audit_sandbox_exec_records_denial(audit_records):
    """A refusal names no workdir, because none was created"""
    with pytest.raises(_Refused):
        with sandbox_audit.audit_sandbox_exec(
            _state(),
            action=loggers.AUDIT_SANDBOX_ACTION_RUN,
            environment="nonesuch",
            denied_exceptions=(_Refused,),
        ) as access:
            _raise_refused(access)

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_DENIED
    assert record.workdir is None
    assert record.environment == "nonesuch"
    assert record.refs == []
    assert record.reason == "_Refused"


def test_audit_sandbox_list_records_success(audit_records):
    with sandbox_audit.audit_sandbox_list(_state(), volume=VOLUME) as access:
        access.record_count(3)

    record = audit_records[-1]
    assert record.getMessage() == loggers.AUDIT_SANDBOX_VOLUME_LIST
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.volume == VOLUME
    assert record.count == 3
    assert record.claims == {"preferred_username": USERNAME}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID
    assert record.run_id == RUN_ID


def test_audit_sandbox_list_records_failure(audit_records):
    with pytest.raises(RuntimeError):
        with sandbox_audit.audit_sandbox_list(
            _state(), volume=VOLUME
        ) as access:
            _raise_runtime_error(access)

    record = audit_records[-1]
    assert record.getMessage() == loggers.AUDIT_SANDBOX_VOLUME_LIST
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.volume == VOLUME
    assert record.reason == "RuntimeError"
