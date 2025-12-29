import logging

import aiofiles
import pytest

import soliplex.ingester.lib.operations as doc_ops
import soliplex.ingester.lib.wf.operations as wf_ops
import soliplex.ingester.lib.wf.runner as runner
from soliplex.ingester.lib import workflow
from soliplex.ingester.lib.models import ArtifactType
from soliplex.ingester.lib.models import RunStep
from soliplex.ingester.lib.models import WorkflowStepType
from tests.unit import data
from tests.unit.common import do_monkeypatch

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def xtest_create_workflow_run(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)
    batch_id = await doc_ops.new_batch("pytest-source", "pytest-batch")
    test_uri = "/tmp/test.pdf"
    mime_type = "application/pdf"
    test_bytes = b"test bytes"
    test_source = "pytest"
    test_doc_meta = {"test": "test"}

    uri1, doc1 = await doc_ops.create_document_from_uri(
        test_uri,
        test_source,
        mime_type,
        test_bytes,
        doc_meta=test_doc_meta,
        batch_id=batch_id,
    )

    wf_run = await wf_ops.create_workflow_run(
        workflow_definitinon_id="batch",
        batch_id=batch_id,
        doc_id=doc1.hash,
        param_id="test1",
    )
    assert wf_run is not None


@pytest.mark.asyncio
async def xtest_split_ingestion(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    batch_id = await doc_ops.new_batch("pytest", "pytest")

    test_uri = "/tmp/test.pdf"
    test_bytes = bytes(data.MIN_PDF, "utf-8")
    async with aiofiles.open("tests/files/amt_handbook_sample.pdf", "rb") as f:
        test_bytes = await f.read()
    test_source = "test source"
    test_doc_meta = {"test": "test"}

    docuri1, doc1 = await doc_ops.create_document_from_uri(
        test_uri,
        test_source,
        file_bytes=test_bytes,
        doc_meta=test_doc_meta,
        batch_id=batch_id,
    )
    rg = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="default")
    wf_run, steps = await wf_ops.create_workflow_run(rg, doc_id=doc1.hash)
    ids = await wf_ops.get_step_config_ids("default")
    sc_map = {}
    for id in ids.values():
        sc = await wf_ops.get_step_config_by_id(id)

        sc_map[sc.step_type] = sc
    assert doc1 is not None
    assert docuri1 is not None
    op = await wf_ops.find_operator_for_workflow_run(wf_run.id, WorkflowStepType.PARSE, ArtifactType.PARSED_JSON)
    assert op

    await workflow.split_parse_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.PARSE],
        force=True,
        workflow_run=wf_run,
    )
    await workflow.chunk_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.CHUNK],
        force=True,
        workflow_run=wf_run,
    )
    await workflow.embed_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.EMBED],
        force=True,
        workflow_run=wf_run,
    )
    await workflow.save_to_rag(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.STORE],
        force=True,
        workflow_run=wf_run,
    )

    doc_history = await doc_ops.get_document_uri_history(docuri1.id)
    for h in doc_history:
        logger.info(h)
    assert doc_history is not None
    assert len(doc_history) == 4  # created, parsed, chunked,  saved


@pytest.mark.asyncio
async def xtest_workflow(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    batch_id = await doc_ops.new_batch("pytest", "pytest")

    test_uri = "/tmp/test.pdf"
    test_bytes = bytes(data.MIN_PDF, "utf-8")
    async with aiofiles.open("tests/files/amt_handbook_sample.pdf", "rb") as f:
        test_bytes = await f.read()
    test_source = "test source"
    test_doc_meta = {"test": "test"}

    docuri1, doc1 = await doc_ops.create_document_from_uri(
        test_uri,
        test_source,
        file_bytes=test_bytes,
        doc_meta=test_doc_meta,
        batch_id=batch_id,
    )

    rg = await wf_ops.create_run_group(workflow_definition_id="test_wf", batch_id=batch_id, param_id="default")

    wf_run, steps = await wf_ops.create_workflow_run(rg, doc_id=doc1.hash)
    ids = await wf_ops.get_step_config_ids("default")
    sc_map = {}
    for id in ids.values():
        sc = await wf_ops.get_step_config_by_id(id)

        sc_map[sc.step_type] = sc
    assert doc1 is not None
    assert docuri1 is not None
    op = await wf_ops.find_operator_for_workflow_run(wf_run.id, WorkflowStepType.PARSE, ArtifactType.PARSED_JSON)
    assert op

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert runnable
    assert len(runnable) == 1
    assert isinstance(runnable[0], RunStep)
    assert runnable[0].step_type == WorkflowStepType.VALIDATE

    await runner.run_wf_step(runnable[0], coro_id=1)

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert runnable
    assert len(runnable) == 1
    assert isinstance(runnable[0], RunStep)
    assert runnable[0].step_type == WorkflowStepType.PARSE

    await runner.run_wf_step(runnable[0], coro_id=1)

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert runnable
    assert len(runnable) == 1
    assert isinstance(runnable[0], RunStep)
    assert runnable[0].step_type == WorkflowStepType.CHUNK

    await runner.run_wf_step(runnable[0], coro_id=1)

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert runnable
    assert isinstance(runnable[0], RunStep)
    assert runnable[0].step_type == WorkflowStepType.EMBED

    await runner.run_wf_step(runnable[0], coro_id=1)

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert runnable
    assert isinstance(runnable[0], RunStep)
    assert runnable[0].step_type == WorkflowStepType.STORE

    await runner.run_wf_step(runnable[0], coro_id=1)

    runnable = await runner.get_runnable_steps(1, batch_id=batch_id)
    assert not runnable


@pytest.mark.asyncio
async def test_ingestion(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    batch_id = await doc_ops.new_batch("pytest", "pytest")

    rg = await wf_ops.create_run_group(workflow_definition_id="test_wf", batch_id=batch_id, param_id="s3_default")

    test_uri = "/tmp/test.pdf"
    test_bytes = bytes(data.MIN_PDF, "utf-8")
    async with aiofiles.open("tests/files/amt_handbook_sample.pdf", "rb") as f:
        test_bytes = await f.read()
    test_source = "test source"
    test_doc_meta = {"test": "test"}

    docuri1, doc1 = await doc_ops.create_document_from_uri(
        test_uri,
        test_source,
        file_bytes=test_bytes,
        doc_meta=test_doc_meta,
        batch_id=batch_id,
    )
    wf_run, steps = await wf_ops.create_workflow_run(rg, doc_id=doc1.hash)
    ids = await wf_ops.get_step_config_ids(rg.param_definition_id)

    sc_map = {}
    for id in ids.values():
        sc = await wf_ops.get_step_config_by_id(id)

        sc_map[sc.step_type] = sc
    assert doc1 is not None
    assert docuri1 is not None

    await workflow.validate_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.VALIDATE],
    )
    docf = await doc_ops.get_document(doc1.hash)
    assert "is_valid" in docf.doc_meta

    await workflow.parse_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.PARSE],
        force=True,
        workflow_run=wf_run,
    )
    await workflow.chunk_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.CHUNK],
        force=True,
        workflow_run=wf_run,
    )

    await workflow.embed_document(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.EMBED],
        force=True,
        workflow_run=wf_run,
    )
    await workflow.save_to_rag(
        batch_id,
        doc1.hash,
        test_source,
        step_config=sc_map[WorkflowStepType.STORE],
        force=True,
        workflow_run=wf_run,
    )

    doc_history = await doc_ops.get_document_uri_history(docuri1.id)
    for h in doc_history:
        logger.info(h)
    assert doc_history is not None
    # assert len(doc_history) == 5  # created, parsed, chunked, embed, saved


@pytest.mark.asyncio
async def xtest_status(monkeypatch, mock_engine):  # noqa F811
    do_monkeypatch(monkeypatch, mock_engine)

    batch_id = await doc_ops.new_batch("pytest", "pytest")

    test_uri = "/tmp/test.pdf"
    test_bytes = bytes(data.MIN_PDF, "utf-8")
    async with aiofiles.open("tests/files/amt_handbook_sample.pdf", "rb") as f:
        test_bytes = await f.read()
    test_source = "test source"
    test_doc_meta = {"test": "test"}

    docuri1, doc1 = await doc_ops.create_document_from_uri(
        test_uri,
        test_source,
        file_bytes=test_bytes,
        doc_meta=test_doc_meta,
        batch_id=batch_id,
    )
    rg = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="default")
    wf_run, steps = await wf_ops.create_workflow_run(rg, doc_id=doc1.hash)
