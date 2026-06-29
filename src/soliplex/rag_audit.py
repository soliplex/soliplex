import contextlib
import json
import logging
import re
import typing

import ag_ui.core as agui_core

from soliplex import loggers

_logger = logging.getLogger(loggers.SOLIPLEX_LOGGER_NAME)

# Each search result is rendered as "[<chunk_id>] [rank N of M]\n...", so the
# chunk ids a query returned can be recovered from the result text.
_CHUNK_REF = re.compile(r"^\[([^\]]+)\] \[rank", re.MULTILINE)

_CALL = "skill_tool_call"
_RESULT = "skill_tool_result"


def _result_refs(result: str) -> list[str]:
    return _CHUNK_REF.findall(result)


class RagAccessAuditor:
    """Records knowledge-base accesses from a skill's AG-UI activity events.

    A skill sub-agent's tool calls surface as paired ``skill_tool_call`` /
    ``skill_tool_result`` activity snapshots sharing a ``tool_call_id``. Feed
    every run event to ``handle``; each completed access is recorded on the
    supplied ``RAGAccessAuditLog``. ``db_path_for`` maps a skill name to the
    LanceDB path the skill reads.
    """

    def __init__(
        self,
        audit_log: typing.Any,
        db_path_for: typing.Callable[[str], str | None],
    ):
        self._audit_log = audit_log
        self._db_path_for = db_path_for
        self._selectors: dict[str, tuple[str, typing.Any]] = {}

    def handle(self, event: typing.Any) -> None:
        # Auditing must never break the run it observes: a malformed activity
        # event (missing content key, non-JSON args, upstream schema drift) is
        # logged and swallowed rather than propagated into the event stream.
        try:
            self._handle(event)
        except Exception:
            _logger.exception(
                "rag-access audit skipped a malformed skill activity event",
            )

    def _handle(self, event: typing.Any) -> None:
        if getattr(event, "type", None) is not (
            agui_core.EventType.ACTIVITY_SNAPSHOT
        ):
            return

        content = event.content

        if event.activity_type == _CALL:
            self._selectors[content["tool_call_id"]] = (
                content["tool_name"],
                json.loads(content["args"]),
            )

        elif event.activity_type == _RESULT:
            captured = self._selectors.pop(content["tool_call_id"], None)
            if captured is None:
                return
            db_path = self._db_path_for(content["skill"])
            if db_path is None:
                return
            tool, selector = captured
            self._audit_log.retrieval(
                db_path,
                tool,
                selector,
                _result_refs(content["result"]),
            )


class _ToolAccessRecorder:
    """Carries the ids a wrapped RAG tool returned back to the auditor.

    The tool sets ``result_refs`` before its body returns; the surrounding
    ``audit_tool_access`` reads it to record what the access disclosed.
    """

    def __init__(self):
        self.result_refs: list[typing.Any] = []

    def record_refs(self, refs: list[typing.Any]):
        self.result_refs.extend(refs)


@contextlib.contextmanager
def audit_tool_access(
    deps: typing.Any, *, audit_method: str, db_path: str, selector: typing.Any
):
    """Bracket a room-agent RAG tool body, emitting one rag-access record.

    ``deps`` is the tool's ``RunContext.deps`` (an ``AgentDependencies``);
    identity and run correlation are taken from it. ``audit_method`` names the
    ``RAGAccessAuditLog`` success method ('search' today); its '<name>_failed'
    sibling records a body exception (reason = the exception type, never its
    message). Yields a recorder whose ``result_refs`` the tool sets.
    """
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
            db_path, selector, type(exc).__name__
        )
        raise
    getattr(audit, audit_method)(db_path, selector, recorder.result_refs)
