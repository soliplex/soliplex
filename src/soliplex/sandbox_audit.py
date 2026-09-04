import contextlib
import pathlib
import typing

from soliplex import loggers

# 'bubble_sandbox' cuts a slow execution off and *returns* normally, with
# this sentinel in place of a real exit status, so a timeout reaches the
# auditor as an ordinary result rather than an exception.
TIMEOUT_EXIT_CODE = -1


class _SandboxExecRecorder:
    """Carries what an execution reports back to the surrounding audit.

    The wrapped tool calls ``record_workdir`` once it has created the
    per-run working directory, ``record_ref`` with each transcript path it
    writes, and ``record_exit_code`` with the status the execution ended
    with.  A call refused before any of that happens records none of them,
    which is why a denied record names no workdir: none was created.
    """

    def __init__(self):
        self.workdir: pathlib.Path | None = None
        self.refs: list[str] = []
        self.exit_code: int | None = None

    @property
    def logged_workdir(self) -> str | None:
        return str(self.workdir) if self.workdir is not None else None

    def record_workdir(self, workdir: pathlib.Path | None):
        self.workdir = workdir

    def record_ref(self, ref: str):
        self.refs.append(ref)

    def record_exit_code(self, exit_code: int | None):
        self.exit_code = exit_code


class _SandboxVolumeListRecorder:
    """Carries how many uploaded files a volume listing disclosed."""

    def __init__(self):
        self.count: int = 0

    def record_count(self, count: int):
        self.count = count


def _audit_log(deps: typing.Any) -> loggers.SandboxExecAuditLog:
    """Bind actor identity and run correlation from the agent deps."""
    user = getattr(deps, "user", None)

    return loggers.SandboxExecAuditLog(
        claims=user.model_dump() if user is not None else {},
        room_id=deps.room_id,
        thread_id=deps.thread_id,
        run_id=deps.run_id,
    )


def _exit_reason(exit_code: int) -> str:
    if exit_code == TIMEOUT_EXIT_CODE:
        return loggers.AUDIT_SANDBOX_REASON_TIMEOUT

    return loggers.AUDIT_SANDBOX_REASON_EXIT_CODE


@contextlib.contextmanager
def audit_sandbox_exec(
    deps: typing.Any,
    *,
    action: str,
    environment: str | None,
    denied_exceptions: tuple[type[BaseException], ...] = (),
):
    """Bracket a sandbox ``run`` / ``run_python`` tool body, emitting one
    ``sandbox-exec`` data-change record.

    Actor identity and run correlation are taken directly from the room
    agent dependencies.  ``action`` is the audit action ('run' /
    'run-python').  ``denied_exceptions`` are the types that mean the call
    was refused rather than attempted; the caller names them so this module
    need not import the skill which raises them.

    Yields a recorder the tool feeds as it goes: the working directory whose
    data the execution may change (logged as a string), each saved command /
    script transcript path, and the status the execution ended with.  The
    command / script body itself is never logged.

    The outcome follows what the body did.  One of ``denied_exceptions`` is
    recorded as 'denied', any other exception as 'error' -- reason being the
    exception type, never its message -- and both are re-raised.  Otherwise
    the exit status decides: a non-zero one is an 'error' naming either the
    timeout sentinel or an ordinary bad exit.  A status of None means the
    body never reported one, an execution that did not happen, and is no
    more an error than a clean zero.
    """
    audit = _audit_log(deps)
    recorder = _SandboxExecRecorder()

    try:
        yield recorder
    # Ahead of 'Exception': a refusal is raised as one of its subclasses.
    except denied_exceptions as exc:
        audit.execute_denied(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            type(exc).__name__,
        )
        raise
    except Exception as exc:
        audit.execute_failed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            type(exc).__name__,
            exit_code=recorder.exit_code,
        )
        raise

    if recorder.exit_code:  # neither a clean zero nor an absent status
        audit.execute_failed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            _exit_reason(recorder.exit_code),
            exit_code=recorder.exit_code,
        )
    else:
        audit.executed(
            action,
            recorder.logged_workdir,
            environment,
            recorder.refs,
            exit_code=recorder.exit_code,
        )


@contextlib.contextmanager
def audit_sandbox_list(deps: typing.Any, *, volume: str):
    """Bracket the sandbox ``list_volume_files`` tool body, emitting one
    ``sandbox volume list`` disclosure record.

    Yields a recorder whose ``record_count`` the tool calls with the number
    of uploaded files it disclosed.  The names themselves are never logged:
    the record answers which volume was read, and how much came back.
    """
    audit = _audit_log(deps)
    recorder = _SandboxVolumeListRecorder()

    try:
        yield recorder
    except Exception as exc:
        audit.volume_list_failed(volume, type(exc).__name__)
        raise

    audit.volume_listed(volume, recorder.count)
