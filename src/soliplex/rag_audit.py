import contextlib
import typing

from soliplex import loggers


class _ToolAccessRecorder:
    """Carry references returned by a room-level RAG tool to its auditor."""

    def __init__(self):
        self.result_refs: list[typing.Any] = []

    def record_refs(self, refs: list[typing.Any]):
        self.result_refs.extend(refs)


@contextlib.contextmanager
def audit_tool_access(
    deps: typing.Any,
    *,
    audit_method: str,
    db_path: str,
    selector: typing.Any,
):
    """Audit a room-level RAG tool body and the references it disclosed."""
    audit = loggers.RAGAccessAuditLog(
        claims=(deps.user.model_dump() if deps.user else {}),
        room_id=deps.room_id,
        thread_id=deps.thread_id,
        run_id=deps.run_id,
    )
    recorder = _ToolAccessRecorder()
    try:
        yield recorder
    except Exception as exc:
        getattr(audit, f"{audit_method}_failed")(
            db_path,
            selector,
            type(exc).__name__,
        )
        raise
    getattr(audit, audit_method)(db_path, selector, recorder.result_refs)
