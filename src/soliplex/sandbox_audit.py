import contextlib
import pathlib
import typing

from soliplex import loggers


class _SandboxExecRecorder:
    """Carries what an execution reports back to the surrounding audit."""

    def __init__(self):
        self.workdir: pathlib.Path | None = None
        self.refs: list[str] = []
        self.exit_code: int | None = None
        self.timed_out: bool = False
        self.timeout_seconds: float | None = None
        self.truncated: bool = False

    @property
    def logged_workdir(self) -> str | None:
        return str(self.workdir) if self.workdir is not None else None

    def record_workdir(self, workdir: pathlib.Path | None):
        self.workdir = workdir

    def record_ref(self, ref: str):
        self.refs.append(ref)

    def record_result(self, result):
        self.exit_code = result.exit_code
        self.timed_out = result.timed_out
        self.timeout_seconds = result.timeout_seconds
        self.truncated = result.truncated


class _SandboxImageReadRecorder:
    """Carries what a read disclosed: which mount, how much, what type."""

    def __init__(self):
        self.volume: str = ""
        self.byte_count: int = 0
        self.media_type: str = ""

    def record_image(self, volume: str, data: bytes, media_type: str):
        self.volume = volume
        self.byte_count = len(data)
        self.media_type = media_type


def _audit_log(deps: typing.Any) -> loggers.SandboxExecAuditLog:
    """Bind actor identity and run correlation from the agent deps."""
    user = getattr(deps, "user", None)

    return loggers.SandboxExecAuditLog(
        claims=user.model_dump() if user is not None else {},
        room_id=deps.room_id,
        thread_id=deps.thread_id,
        run_id=deps.run_id,
    )


@contextlib.contextmanager
def audit_sandbox_exec(
    deps: typing.Any,
    *,
    action: str,
    environment: str | None,
):
    """Bracket a ``run`` / ``run_python`` tool body, emitting one
    ``sandbox-exec`` record.

    Yields a recorder the tool feeds with the working directory, each
    transcript path, and the result.  The command and script bodies are
    never logged.
    """
    audit = _audit_log(deps)
    recorder = _SandboxExecRecorder()

    try:
        yield recorder
    except Exception as exc:
        audit.execute_failed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            type(exc).__name__,
            exit_code=recorder.exit_code,
            truncated=recorder.truncated,
            timeout_seconds=recorder.timeout_seconds,
        )
        raise

    bounds = {
        "exit_code": recorder.exit_code,
        "truncated": recorder.truncated,
        "timeout_seconds": recorder.timeout_seconds,
    }

    if recorder.timed_out:
        audit.execute_failed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            loggers.AUDIT_SANDBOX_REASON_TIMEOUT,
            **bounds,
        )
    elif recorder.exit_code:  # neither a clean zero nor an absent status
        audit.execute_failed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            loggers.AUDIT_SANDBOX_REASON_EXIT_CODE,
            **bounds,
        )
    else:
        audit.executed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            **bounds,
        )


@contextlib.contextmanager
def audit_sandbox_read_image(deps: typing.Any, *, path: str):
    """Bracket the ``read_image`` tool body, emitting one record."""
    audit = _audit_log(deps)
    recorder = _SandboxImageReadRecorder()

    try:
        yield recorder
    except Exception as exc:
        audit.image_read_failed(path, type(exc).__name__)
        raise

    audit.image_read(
        path,
        recorder.volume,
        byte_count=recorder.byte_count,
        media_type=recorder.media_type,
    )
