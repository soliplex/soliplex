import ag_ui.core as agui_core

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

    def access(self, db_path, tool, selector, result_refs):
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
