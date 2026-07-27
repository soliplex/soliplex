from unittest import mock

import pydantic
import pytest
from pydantic_ai import messages as ai_messages
from pydantic_ai import tools as ai_tools

from soliplex import loggers
from soliplex import rag_audit
from soliplex.capabilities import rag_audit as cap_audit

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


def _tool_definition(name="rag_search", capability_id="haiku-rag"):
    return ai_tools.ToolDefinition(
        name=name,
        description="Search",
        parameters_json_schema={"type": "object"},
        capability_id=capability_id,
    )


def _tool_call(name="rag_search"):
    return ai_messages.ToolCallPart(
        tool_name=name,
        args={"query": "what is x"},
        tool_call_id="call-1",
    )


@pytest.mark.anyio
@pytest.mark.parametrize("structured", [False, True])
async def test_capability_audits_native_search(audit_records, structured):
    capability = cap_audit.RAGAccessAuditCapability(
        id="rag-audit",
        db_paths={"haiku-rag": DB_PATH},
    )
    ctx = mock.Mock(deps=_tool_deps(SimpleClaims(email=USER_EMAIL)))
    rendered = "[c1] [rank 1 of 1]\nContent:\nalpha"
    result = (
        ai_messages.ToolReturn(return_value=rendered)
        if structured
        else rendered
    )

    found = await capability.after_tool_execute(
        ctx,
        call=_tool_call(),
        tool_def=_tool_definition(),
        args={"query": "what is x"},
        result=result,
    )

    assert found is result
    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_RETRIEVAL
    assert record.outcome == loggers.AUDIT_OUTCOME_SUCCESS
    assert record.db_path == DB_PATH
    assert record.tool == "rag_search"
    assert record.selector == {"query": "what is x"}
    assert record.result_refs == ["c1"]
    assert record.claims == {"email": USER_EMAIL}
    assert record.room_id == ROOM_ID
    assert record.thread_id == THREAD_ID
    assert record.run_id == RUN_ID


@pytest.mark.anyio
async def test_capability_audits_non_search_tool(audit_records):
    capability = cap_audit.RAGAccessAuditCapability(
        id="rag-audit",
        db_paths={"haiku-rag": DB_PATH},
    )
    tool_def = _tool_definition(name="rag_cite")

    await capability.after_tool_execute(
        mock.Mock(deps=_tool_deps()),
        call=_tool_call(tool_def.name),
        tool_def=tool_def,
        args={"chunk_ids": ["arbitrary-id"]},
        result="result",
    )

    record = audit_records[-1]
    assert record.tool == "rag_cite"
    assert record.selector == {"chunk_ids": ["arbitrary-id"]}
    assert record.result_refs == []


@pytest.mark.anyio
async def test_capability_ignores_unrelated_capability(audit_records):
    capability = cap_audit.RAGAccessAuditCapability(
        id="rag-audit",
        db_paths={"haiku-rag": DB_PATH},
    )

    await capability.after_tool_execute(
        mock.Mock(deps=_tool_deps()),
        call=_tool_call(),
        tool_def=_tool_definition(capability_id="other-capability"),
        args={},
        result="result",
    )

    assert audit_records == []


@pytest.mark.anyio
async def test_capability_audits_native_search_failure(audit_records):
    capability = cap_audit.RAGAccessAuditCapability(
        id="rag-audit",
        db_paths={"haiku-rag": DB_PATH},
    )
    error = RuntimeError("boom")

    with pytest.raises(RuntimeError) as raised:
        await capability.on_tool_execute_error(
            mock.Mock(deps=_tool_deps()),
            call=_tool_call(),
            tool_def=_tool_definition(),
            args={"query": "what is x"},
            error=error,
        )

    assert raised.value is error
    record = audit_records[-1]
    assert record.action == loggers.AUDIT_RAG_ACTION_RETRIEVAL
    assert record.outcome == loggers.AUDIT_OUTCOME_ERROR
    assert record.db_path == DB_PATH
    assert record.tool == "rag_search"
    assert record.selector == {"query": "what is x"}
    assert record.reason == "RuntimeError"


@pytest.mark.anyio
async def test_capability_reraises_unrelated_capability_error(audit_records):
    capability = cap_audit.RAGAccessAuditCapability(
        id="rag-audit",
        db_paths={"haiku-rag": DB_PATH},
    )
    error = RuntimeError("boom")

    with pytest.raises(RuntimeError) as raised:
        await capability.on_tool_execute_error(
            mock.Mock(deps=_tool_deps()),
            call=_tool_call(),
            tool_def=_tool_definition(capability_id="other-capability"),
            args={},
            error=error,
        )

    assert raised.value is error
    assert audit_records == []


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
