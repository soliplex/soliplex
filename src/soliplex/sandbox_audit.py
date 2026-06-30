import contextlib
import pathlib
import typing

from soliplex import loggers


@contextlib.contextmanager
def audit_sandbox_exec(
    state: typing.Any,
    *,
    action: str,
    environment: str | None,
    workdir: pathlib.Path | None,
):
    """Bracket a sandbox ``run`` / ``run_python`` tool body, emitting one
    ``sandbox-exec`` data-change record.

    ``state`` is the skill's ``SandboxState``: actor identity
    (``preferred_username``) and run correlation (``room_id`` /
    ``thread_id`` / ``run_id``) are taken from it. ``action`` is the audit
    action ('run' / 'run-python'); ``workdir`` is the per-run working
    directory whose data the execution may have changed (logged as a string).

    A body exception is recorded as a failure (reason = the exception type,
    never its message) and re-raised; otherwise a success is recorded. The
    command / script body is never logged.
    """
    audit = loggers.SandboxExecAuditLog(
        claims={"preferred_username": state.preferred_username},
        room_id=state.room_id,
        thread_id=state.thread_id,
        run_id=state.run_id,
    )
    logged_workdir = str(workdir) if workdir is not None else None
    try:
        yield
    except Exception as exc:
        audit.execute_failed(
            action, logged_workdir, environment, type(exc).__name__
        )
        raise
    audit.executed(action, logged_workdir, environment)
