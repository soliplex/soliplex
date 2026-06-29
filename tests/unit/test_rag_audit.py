import datetime as dt

import ag_ui.core as agui_core
import pydantic
import pytest
from haiku.rag.store.models import chunk as hr_chunk
from haiku.skills import agent as hs_agent
from pydantic_ai import messages as ai_messages

from soliplex import loggers
from soliplex import rag_audit

SEARCH_RESULT = (
    "[c1] [rank 1 of 2]\nSource: doc\nContent:\nalpha"
    "\n\n---\n\n"
    "[c2] [rank 2 of 2]\nContent:\nbeta"
)


class _RecordingLog:
    def __init__(self):
        self.calls = []

    def retrieval(self, db_path, tool, selector, result_refs):
        self.calls.append((db_path, tool, selector, result_refs))


def _activity(activity_type, content):
    return agui_core.ActivitySnapshotEvent(
        type=agui_core.EventType.ACTIVITY_SNAPSHOT,
        message_id="m1",
        activity_type=activity_type,
        content=content,
        replace=False,
    )


def _auditor(log):
    return rag_audit.RagAccessAuditor(
        log, db_path_for=lambda skill: f"/dbs/{skill}.lancedb"
    )


def test_ragaccessauditor__handle_search_call_then_result_records_access():
    log = _RecordingLog()
    auditor = _auditor(log)

    auditor.handle(
        _activity(
            "skill_tool_call",
            {
                "skill": "rag",
                "tool_name": "search",
                "tool_call_id": "t1",
                "args": '{"query": "what is x"}',
            },
        )
    )
    auditor.handle(
        _activity(
            "skill_tool_result",
            {
                "skill": "rag",
                "tool_name": "search",
                "tool_call_id": "t1",
                "result": SEARCH_RESULT,
            },
        )
    )

    assert log.calls == [
        (
            "/dbs/rag.lancedb",
            "search",
            {"query": "what is x"},
            ["c1", "c2"],
        )
    ]


def test_ragaccessauditor__handle_cite_records_chunk_ids_as_selector():
    log = _RecordingLog()
    auditor = _auditor(log)

    auditor.handle(
        _activity(
            "skill_tool_call",
            {
                "skill": "rag",
                "tool_name": "cite",
                "tool_call_id": "t2",
                "args": '{"chunk_ids": ["c1", "c2"]}',
            },
        )
    )
    auditor.handle(
        _activity(
            "skill_tool_result",
            {
                "skill": "rag",
                "tool_name": "cite",
                "tool_call_id": "t2",
                "result": "Registered 2 citation(s).",
            },
        )
    )

    assert log.calls == [
        ("/dbs/rag.lancedb", "cite", {"chunk_ids": ["c1", "c2"]}, [])
    ]


def test_ragaccessauditor__handle_non_activity_event_is_ignored():
    log = _RecordingLog()
    auditor = _auditor(log)

    auditor.handle(
        agui_core.RunStartedEvent(
            type=agui_core.EventType.RUN_STARTED,
            thread_id="t",
            run_id="r",
        )
    )

    assert log.calls == []


def test_ragaccessauditor__handle_unrelated_activity_type_is_ignored():
    log = _RecordingLog()
    auditor = _auditor(log)

    auditor.handle(_activity("some_other_activity", {"foo": "bar"}))

    assert log.calls == []


def test_ragaccessauditor__handle_unknown_skill_is_skipped():
    log = _RecordingLog()
    auditor = rag_audit.RagAccessAuditor(log, db_path_for=lambda skill: None)

    auditor.handle(
        _activity(
            "skill_tool_call",
            {
                "skill": "not-a-rag-skill",
                "tool_name": "search",
                "tool_call_id": "t3",
                "args": '{"query": "x"}',
            },
        )
    )
    auditor.handle(
        _activity(
            "skill_tool_result",
            {
                "skill": "not-a-rag-skill",
                "tool_name": "search",
                "tool_call_id": "t3",
                "result": SEARCH_RESULT,
            },
        )
    )

    assert log.calls == []


def test_ragaccessauditor__handle_orphan_result_is_ignored():
    log = _RecordingLog()
    auditor = _auditor(log)

    auditor.handle(
        _activity(
            "skill_tool_result",
            {
                "skill": "rag",
                "tool_name": "search",
                "tool_call_id": "missing",
                "result": SEARCH_RESULT,
            },
        )
    )

    assert log.calls == []


def test_ragaccessauditor__handle_missing_content_key_swallowed_warned(caplog):
    log = _RecordingLog()
    auditor = _auditor(log)

    with caplog.at_level("WARNING", logger=loggers.SOLIPLEX_LOGGER_NAME):
        auditor.handle(
            _activity(
                "skill_tool_call",
                {"skill": "rag", "tool_name": "search", "args": "{}"},
            )
        )

    assert log.calls == []
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"


def test_ragaccessauditor__handle_non_json_args_swallowed_warned(caplog):
    log = _RecordingLog()
    auditor = _auditor(log)

    with caplog.at_level("WARNING", logger=loggers.SOLIPLEX_LOGGER_NAME):
        auditor.handle(
            _activity(
                "skill_tool_call",
                {
                    "skill": "rag",
                    "tool_name": "search",
                    "tool_call_id": "t1",
                    "args": "not json",
                },
            )
        )

    assert log.calls == []
    assert len(caplog.records) == 1
    assert caplog.records[0].levelname == "ERROR"


# -- upstream-contract regression guards -------------------------------
#
# The auditor depends on surfaces owned by haiku.rag / haiku.skills that are
# not part of a stable public API: the agent-facing search render
# ('SearchResult.format_for_agent') and the skill activity events
# ('_events_to_activity', a private upstream helper). If either drifts, the
# auditor would silently record nothing rather than fail. These tests exercise
# the real upstream code so a future dependency bump breaks here -- loudly --
# instead of in production.


def test_contract_searchresult_render_yields_recoverable_chunk_ids():
    rendered = "\n\n".join(
        hr_chunk.SearchResult(
            content="x", score=1.0, chunk_id=chunk_id
        ).format_for_agent(rank=rank, total=2)
        for rank, chunk_id in enumerate(["c1", "c2"], start=1)
    )

    refs = rag_audit._result_refs(rendered)

    assert refs == ["c1", "c2"]


def test_contract_skill_activity_events_drive_the_auditor():
    call = ai_messages.FunctionToolCallEvent(
        part=ai_messages.ToolCallPart(
            tool_name="search", args={"query": "x"}, tool_call_id="t1"
        )
    )
    result = ai_messages.FunctionToolResultEvent(
        part=ai_messages.ToolReturnPart(
            tool_name="search",
            content=hr_chunk.SearchResult(
                content="x", score=1.0, chunk_id="c1"
            ).format_for_agent(rank=1, total=1),
            tool_call_id="t1",
            timestamp=dt.datetime(2024, 1, 1, tzinfo=dt.UTC),
        )
    )
    events = hs_agent._events_to_activity("rag", [call, result])
    log = _RecordingLog()
    auditor = _auditor(log)

    for event in events:
        auditor.handle(event)

    assert log.calls == [
        ("/dbs/rag.lancedb", "search", {"query": "x"}, ["c1"])
    ]


# -- audit_tool_access (room-agent RAG tool wrapper) -------------------

USER_EMAIL = "x@a.test"
ROOM_ID = "room-1"
THREAD_ID = "thread-1"
RUN_ID = "run-1"


class SimpleClaims(pydantic.BaseModel):
    email: str


class ToolDeps(pydantic.BaseModel):
    user: SimpleClaims | None
    room_id: str
    thread_id: str
    run_id: str


def _tool_deps(user):
    return ToolDeps(
        user=user,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


def test_audit_tool_access_records_search(audit_records):
    claims = SimpleClaims(email=USER_EMAIL)
    deps = _tool_deps(claims)

    with rag_audit.audit_tool_access(
        deps, audit_method="search", db_path="/db", selector="q"
    ) as access:
        access.record_refs(["c1", "c2"])

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_SEARCH
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.db_path == "/db"
    assert record.selector == "q"
    assert record.result_refs == ["c1", "c2"]
    assert record.claims == {"email": USER_EMAIL}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID
    assert record.run_id == RUN_ID


def test_audit_tool_access_without_user_uses_empty_claims(audit_records):
    deps = _tool_deps(None)

    with rag_audit.audit_tool_access(
        deps, audit_method="search", db_path="/db", selector="q"
    ):
        pass

    assert audit_records[-1].claims == {}


def test_audit_tool_access_records_failure(audit_records):
    deps = _tool_deps(None)

    with pytest.raises(RuntimeError):
        with rag_audit.audit_tool_access(
            deps, audit_method="search", db_path="/db", selector="q"
        ):
            raise RuntimeError("boom")

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_SEARCH
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.db_path == "/db"
    assert record.selector == "q"
    assert record.reason == "RuntimeError"
