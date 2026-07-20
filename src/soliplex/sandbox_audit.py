import contextlib
import pathlib
import typing

from soliplex import loggers


class _SandboxExecRecorder:
    """Carries the saved-transcript paths back to the surrounding audit.

    The wrapped tool calls ``record_ref`` with each transcript path it
    writes; ``audit_sandbox_exec`` records them as the record's ``refs`` on
    both the success and failure paths.
    """

    def __init__(self):
        self.refs: list[str] = []

    def record_ref(self, ref: str):
        self.refs.append(ref)


@contextlib.contextmanager
def audit_sandbox_exec(
    deps: typing.Any,
    *,
    action: str,
    environment: str | None,
    workdir: pathlib.Path | None,
):
    """Bracket a sandbox ``run`` / ``run_python`` tool body, emitting one
    ``sandbox-exec`` data-change record.

    Actor identity and run correlation are taken directly from the room
    agent dependencies. ``action`` is the audit
    action ('run' / 'run-python'); ``workdir`` is the per-run working
    directory whose data the execution may have changed (logged as a string).

    Yields a recorder whose ``record_ref`` the tool calls with each saved
    command / script transcript path; those land in the record's ``refs`` on
    success *and* failure. A body exception is recorded as a failure (reason =
    the exception type, never its message) and re-raised; otherwise a success
    is recorded. The command / script body itself is never logged.
    """
    user = getattr(deps, "user", None)
    audit = loggers.SandboxExecAuditLog(
        claims=user.model_dump() if user is not None else {},
        room_id=deps.room_id,
        thread_id=deps.thread_id,
        run_id=deps.run_id,
    )
    logged_workdir = str(workdir) if workdir is not None else None
    recorder = _SandboxExecRecorder()
    try:
        yield recorder
    except Exception as exc:
        audit.execute_failed(
            action,
            logged_workdir,
            environment,
            recorder.refs,
            type(exc).__name__,
        )
        raise
    audit.executed(action, logged_workdir, environment, recorder.refs)
