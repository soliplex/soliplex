import pydantic
import pytest

from soliplex import loggers
from soliplex import rag_audit

USER_EMAIL = "x@a.test"
ROOM_ID = "room-1"
THREAD_ID = "thread-1"
RUN_ID = "run-1"
DB_PATH = "/db"


class SimpleClaims(pydantic.BaseModel):
    email: str


class ToolDeps(pydantic.BaseModel):
    user: SimpleClaims | None
    room_id: str
    thread_id: str
    run_id: str


def _tool_deps(user=None):
    return ToolDeps(
        user=user,
        room_id=ROOM_ID,
        thread_id=THREAD_ID,
        run_id=RUN_ID,
    )


def test_audit_tool_access_records_search(audit_records):
    deps = _tool_deps(SimpleClaims(email=USER_EMAIL))

    with rag_audit.audit_tool_access(
        deps,
        audit_method="search",
        db_path=DB_PATH,
        selector="q",
    ) as access:
        access.record_refs(["c1", "c2"])

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_SEARCH
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.db_path == DB_PATH
    assert record.selector == "q"
    assert record.result_refs == ["c1", "c2"]
    assert record.claims == {"email": USER_EMAIL}


def test_audit_tool_access_without_user_uses_empty_claims(audit_records):
    with rag_audit.audit_tool_access(
        _tool_deps(),
        audit_method="search",
        db_path=DB_PATH,
        selector="q",
    ):
        pass

    assert audit_records[-1].claims == {}


def test_audit_tool_access_records_failure(audit_records):
    with pytest.raises(RuntimeError):
        with rag_audit.audit_tool_access(
            _tool_deps(),
            audit_method="search",
            db_path=DB_PATH,
            selector="q",
        ):
            raise RuntimeError("boom")

    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_SEARCH
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.reason == "RuntimeError"
