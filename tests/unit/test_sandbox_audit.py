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


def _state():
    user = SimpleNamespace(model_dump=lambda: {"preferred_username": USERNAME})
    return SimpleNamespace(
        user=user,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


def _record_ref_then_raise(access):
    access.record_ref(TRANSCRIPT)
    raise RuntimeError("boom")


def test_audit_sandbox_exec_records_success(audit_records):
    with sandbox_audit.audit_sandbox_exec(
        _state(),
        action=loggers.AUDIT_SANDBOX_ACTION_RUN,
        environment="default",
        workdir=WORKDIR,
    ) as access:
        access.record_ref(TRANSCRIPT)

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir == str(WORKDIR)
    assert record.environment == "default"
    assert record.refs == [TRANSCRIPT]
    assert record.claims == {"preferred_username": USERNAME}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID
    assert record.run_id == RUN_ID


def test_audit_sandbox_exec_without_workdir_logs_none(audit_records):
    with sandbox_audit.audit_sandbox_exec(
        _state(),
        action=loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON,
        environment=None,
        workdir=None,
    ):
        pass

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN_PYTHON
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.workdir is None
    assert record.environment is None
    # No 'record_ref' call -> empty refs.
    assert record.refs == []


def test_audit_sandbox_exec_records_failure(audit_records):
    with pytest.raises(RuntimeError):
        with sandbox_audit.audit_sandbox_exec(
            _state(),
            action=loggers.AUDIT_SANDBOX_ACTION_RUN,
            environment="default",
            workdir=WORKDIR,
        ) as access:
            _record_ref_then_raise(access)

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_SANDBOX_ACTION_RUN
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.workdir == str(WORKDIR)
    assert record.environment == "default"
    # Refs recorded before the failure still land on the failure record.
    assert record.refs == [TRANSCRIPT]
    assert record.reason == "RuntimeError"
