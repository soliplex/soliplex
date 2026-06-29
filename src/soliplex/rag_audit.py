import json
import re
import typing

import ag_ui.core as agui_core

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
            self._audit_log.access(
                db_path,
                tool,
                selector,
                _result_refs(content["result"]),
            )
