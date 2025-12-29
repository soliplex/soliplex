import datetime
import logging

import pytest
from common import do_monkeypatch
from common import mock_engine  # noqa

import soliplex.ingester.lib.models as models
import soliplex.ingester.lib.operations as doc_ops
import soliplex.ingester.lib.wf.operations as wf_ops
from soliplex.ingester.lib.models import LifeCycleEvent
from soliplex.ingester.lib.models import RunStatus
from soliplex.ingester.lib.models import WorkflowStepType

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_not_found_error():
    """Test NotFoundError exception"""
    error = wf_ops.NotFoundError("test message")
    assert "test message" in str(error)


@pytest.mark.asyncio
async def test_create_run_group(monkeypatch, mock_engine):  # noqa F811
    """Test create_run_group function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create a batch first
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")

    # Create run group
    run_group = await wf_ops.create_run_group(
        workflow_definition_id="batch", batch_id=batch_id, param_id="test1", name="Test Run Group"
    )

    assert run_group is not None
    assert run_group.id is not None
    assert run_group.workflow_definition_id == "batch"
    assert run_group.batch_id == batch_id
    assert run_group.param_definition_id == "test1"
    assert run_group.name == "Test Run Group"
    assert run_group.start_date is not None
    assert run_group.created_date is not None


@pytest.mark.asyncio
async def test_create_run_group_with_invalid_batch(monkeypatch, mock_engine):  # noqa F811
    """Test create_run_group with non-existent batch"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="Batch .* not found"):
        await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=99999, param_id="test1")


@pytest.mark.asyncio
async def test_get_run_group(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_group function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create a batch and run group
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    run_group = await wf_ops.create_run_group(
        workflow_definition_id="batch", batch_id=batch_id, param_id="test1", name="Test Run Group"
    )

    # Get the run group
    retrieved_group = await wf_ops.get_run_group(run_group.id)
    assert retrieved_group is not None
    assert retrieved_group.id == run_group.id
    assert retrieved_group.workflow_definition_id == run_group.workflow_definition_id


@pytest.mark.asyncio
async def test_get_run_group_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_group with non-existent id"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="run group .* not found"):
        await wf_ops.get_run_group(99999)


@pytest.mark.asyncio
async def test_get_run_groups_for_batch(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_groups_for_batch function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create a batch and run groups
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    run_group1 = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    run_group2 = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test2")

    # Get run groups for batch
    groups = await wf_ops.get_run_groups_for_batch(batch_id)
    assert len(groups) >= 2
    group_ids = [g.id for g in groups]
    assert run_group1.id in group_ids
    assert run_group2.id in group_ids


@pytest.mark.asyncio
async def test_get_run_groups_for_batch_no_filter(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_groups_for_batch with no batch_id filter"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create a batch and run group
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")

    # Get all run groups (no filter)
    groups = await wf_ops.get_run_groups_for_batch(None)
    assert len(groups) >= 1


@pytest.mark.asyncio
async def test_create_workflow_run(monkeypatch, mock_engine):  # noqa F811
    """Test create_workflow_run function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/workflow_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    # Create run group
    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")

    # Create workflow run
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash, priority=5)

    assert workflow_run is not None
    assert workflow_run.id is not None
    assert workflow_run.run_group_id == run_group.id
    assert workflow_run.workflow_definition_id == "batch"
    assert workflow_run.batch_id == batch_id
    assert workflow_run.doc_id == doc.hash
    assert workflow_run.priority == 5
    assert workflow_run.status == RunStatus.PENDING

    # Check steps
    assert steps is not None
    assert len(steps) > 0
    for step in steps:
        assert step.workflow_run_id == workflow_run.id
        assert step.status == RunStatus.PENDING


@pytest.mark.asyncio
async def test_create_single_workflow_run(monkeypatch, mock_engine):  # noqa F811
    """Test create_single_workflow_run function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/single_workflow_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    # Create single workflow run
    workflow_run, steps = await wf_ops.create_single_workflow_run(
        workflow_definiton_id="batch", doc_id=doc.hash, priority=3, param_id="test1"
    )

    assert workflow_run is not None
    assert workflow_run.doc_id == doc.hash
    assert workflow_run.priority == 3
    assert steps is not None
    assert len(steps) > 0


@pytest.mark.asyncio
async def test_create_workflow_runs_for_batch(monkeypatch, mock_engine):  # noqa F811
    """Test create_workflow_runs_for_batch function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri1 = "/tmp/batch_workflow_test1.pdf"
    test_uri2 = "/tmp/batch_workflow_test2.pdf"
    test_bytes1 = b"test bytes 1"  # Different bytes for different hash
    test_bytes2 = b"test bytes 2"  # Different bytes for different hash

    await doc_ops.create_document_from_uri(test_uri1, "test_source", "application/pdf", test_bytes1, batch_id=batch_id)
    await doc_ops.create_document_from_uri(test_uri2, "test_source", "application/pdf", test_bytes2, batch_id=batch_id)

    # Create workflow runs for batch
    run_group, runs = await wf_ops.create_workflow_runs_for_batch(
        batch_id=batch_id, workflow_definition_id="batch", priority=2, param_id="test1"
    )

    assert run_group is not None
    assert run_group.batch_id == batch_id
    assert runs is not None
    assert len(runs) == 2
    for run in runs:
        assert run.batch_id == batch_id
        assert run.priority == 2


@pytest.mark.asyncio
async def test_get_workflow_run(monkeypatch, mock_engine):  # noqa F811
    """Test get_workflow_run function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/get_workflow_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get workflow run without steps
    retrieved_run = await wf_ops.get_workflow_run(workflow_run.id, get_steps=False)
    assert retrieved_run is not None
    assert retrieved_run.id == workflow_run.id
    assert retrieved_run.doc_id == doc.hash

    # Get workflow run with steps
    retrieved_run2, retrieved_steps = await wf_ops.get_workflow_run(workflow_run.id, get_steps=True)
    assert retrieved_run2 is not None
    assert retrieved_run2.id == workflow_run.id
    assert retrieved_steps is not None
    assert len(retrieved_steps) > 0


@pytest.mark.asyncio
async def test_get_workflow_run_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test get_workflow_run with non-existent id"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="workflow run .* not found"):
        await wf_ops.get_workflow_run(99999)


@pytest.mark.asyncio
async def test_get_workflows(monkeypatch, mock_engine):  # noqa F811
    """Test get_workflows function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/workflows_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get workflows for batch
    workflows, total = await wf_ops.get_workflows(batch_id)
    assert len(workflows) >= 1
    assert total >= 1

    # Get all workflows (no filter)
    all_workflows, all_total = await wf_ops.get_workflows(None)
    assert len(all_workflows) >= 1
    assert all_total >= 1


@pytest.mark.asyncio
async def test_get_workflows_with_steps(monkeypatch, mock_engine):  # noqa F811
    """Test get_workflows function with include_steps=True"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/workflows_with_steps_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get workflows with steps
    workflows_with_steps, total = await wf_ops.get_workflows(batch_id, include_steps=True)
    assert len(workflows_with_steps) >= 1
    assert total >= 1

    # Verify the result is a list of WorkflowRunWithSteps
    from soliplex.ingester.lib.models import WorkflowRun
    from soliplex.ingester.lib.models import WorkflowRunWithSteps

    # Find our specific workflow run in the results
    our_workflow = None
    for wf in workflows_with_steps:
        assert isinstance(wf, WorkflowRunWithSteps)
        if wf.workflow_run.id == workflow_run.id:
            our_workflow = wf
            break

    assert our_workflow is not None, f"Could not find workflow_run.id={workflow_run.id} in results"
    assert our_workflow.steps is not None
    assert len(our_workflow.steps) == len(steps)

    # Verify without include_steps returns plain WorkflowRun
    workflows_without_steps, total_without = await wf_ops.get_workflows(batch_id, include_steps=False)
    assert isinstance(workflows_without_steps[0], WorkflowRun)
    assert total_without >= 1


@pytest.mark.asyncio
async def test_get_workflows_for_status(monkeypatch, mock_engine):  # noqa F811
    """Test get_workflows_for_status function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/status_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get workflows with PENDING status
    pending_workflows = await wf_ops.get_workflows_for_status(RunStatus.PENDING, batch_id)
    assert len(pending_workflows) >= 1

    # Get workflows with PENDING status (no batch filter)
    all_pending = await wf_ops.get_workflows_for_status(RunStatus.PENDING, None)
    assert len(all_pending) >= 1


@pytest.mark.asyncio
async def test_get_run_step(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_step function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/run_step_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get the first step
    step = await wf_ops.get_run_step(steps[0].id)
    assert step is not None
    assert step.id == steps[0].id
    assert step.workflow_run_id == workflow_run.id


@pytest.mark.asyncio
async def test_get_run_step_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_step with non-existent id"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="run step .* not found"):
        await wf_ops.get_run_step(99999)


@pytest.mark.asyncio
async def test_get_run_steps(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_steps function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/run_steps_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get all PENDING steps
    pending_steps = await wf_ops.get_run_steps(RunStatus.PENDING)
    assert len(pending_steps) >= 1


@pytest.mark.asyncio
async def test_get_steps_for_batch(monkeypatch, mock_engine):  # noqa F811
    """Test get_steps_for_batch function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/steps_for_batch_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get steps for batch
    batch_steps = await wf_ops.get_steps_for_batch(batch_id)
    assert len(batch_steps) >= len(steps)


@pytest.mark.asyncio
async def test_get_step_config_by_id(monkeypatch, mock_engine):  # noqa F811
    """Test get_step_config_by_id function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Get step config ids for a param set
    step_config_ids = await wf_ops.get_step_config_ids("test1")
    assert step_config_ids is not None

    # Get a step config by id
    parse_config_id = step_config_ids[WorkflowStepType.PARSE]
    step_config = await wf_ops.get_step_config_by_id(parse_config_id)

    assert step_config is not None
    assert step_config.id == parse_config_id
    assert step_config.step_type == WorkflowStepType.PARSE


@pytest.mark.asyncio
async def test_get_step_config_by_id_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test get_step_config_by_id with non-existent id"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="step config .* not found"):
        await wf_ops.get_step_config_by_id(99999)


@pytest.mark.asyncio
async def test_get_step_config_for_workflow_run(monkeypatch, mock_engine):  # noqa F811
    """Test get_step_config_for_workflow_run function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/step_config_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get step config for PARSE step
    parse_config = await wf_ops.get_step_config_for_workflow_run(workflow_run.id, WorkflowStepType.PARSE)
    assert parse_config is not None
    assert parse_config.step_type == WorkflowStepType.PARSE


@pytest.mark.asyncio
async def test_get_step_config_for_workflow_run_not_found(monkeypatch, mock_engine):  # noqa F811
    """Test get_step_config_for_workflow_run with non-existent workflow"""
    do_monkeypatch(monkeypatch, mock_engine)

    with pytest.raises(wf_ops.NotFoundError, match="step config .* not found"):
        await wf_ops.get_step_config_for_workflow_run(99999, WorkflowStepType.PARSE)


@pytest.mark.asyncio
async def test_find_operator_for_workflow_run(monkeypatch, mock_engine):  # noqa F811
    """Test find_operator_for_workflow_run function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/operator_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Find operator for workflow run
    operator = await wf_ops.find_operator_for_workflow_run(
        workflow_run.id, WorkflowStepType.PARSE, models.ArtifactType.PARSED_JSON
    )
    assert operator is not None


@pytest.mark.asyncio
async def test_create_lifecycle_history(monkeypatch, mock_engine):  # noqa F811
    """Test create_lifecycle_history function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/lifecycle_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    workflow_run, steps = await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Create lifecycle history
    history = await wf_ops.create_lifecycle_history(
        run_group_id=run_group.id,
        workflow_run_id=workflow_run.id,
        event=LifeCycleEvent.ITEM_START,
        status=RunStatus.RUNNING,
        step_id=steps[0].id,
        status_message="Test message",
        status_meta={"key": "value"},
    )

    assert history is not None
    assert history.run_group_id == run_group.id
    assert history.workflow_run_id == workflow_run.id
    assert history.event == LifeCycleEvent.ITEM_START
    assert history.status == RunStatus.RUNNING
    assert history.step_id == steps[0].id
    assert history.status_message == "Test message"


@pytest.mark.asyncio
async def test_update_run_status(monkeypatch, mock_engine):  # noqa F811
    """Test update_run_status function - tests status update logic"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/update_status_test.pdf"
    test_bytes = b"test bytes for update"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")

    # Create and update in the same session
    async with models.get_session() as session:
        workflow_run = models.WorkflowRun(
            run_group_id=run_group.id,
            workflow_definition_id="batch",
            batch_id=batch_id,
            doc_id=doc.hash,
            start_date=datetime.datetime.now(),
            priority=0,
            created_date=datetime.datetime.now(),
            run_params={},
        )
        session.add(workflow_run)
        await session.flush()
        await session.refresh(workflow_run)
        workflow_run_id = workflow_run.id

        # Update run status to COMPLETED (last step completed)
        result = await wf_ops.update_run_status(
            workflow_run_id, is_last_step=True, status=RunStatus.COMPLETED, session=session
        )
        assert result == RunStatus.COMPLETED
        await session.commit()


@pytest.mark.asyncio
async def test_update_run_status_failed(monkeypatch, mock_engine):  # noqa F811
    """Test update_run_status with FAILED status"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/update_status_failed_test.pdf"
    test_bytes = b"test bytes for failed"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")

    # Create and update in the same session
    async with models.get_session() as session:
        workflow_run = models.WorkflowRun(
            run_group_id=run_group.id,
            workflow_definition_id="batch",
            batch_id=batch_id,
            doc_id=doc.hash,
            start_date=datetime.datetime.now(),
            priority=0,
            created_date=datetime.datetime.now(),
            run_params={},
        )
        session.add(workflow_run)
        await session.flush()
        await session.refresh(workflow_run)
        workflow_run_id = workflow_run.id

        # Update run status to FAILED
        result = await wf_ops.update_run_status(workflow_run_id, is_last_step=False, status=RunStatus.FAILED, session=session)
        assert result == RunStatus.FAILED
        await session.commit()


@pytest.mark.asyncio
async def test_update_run_status_running(monkeypatch, mock_engine):  # noqa F811
    """Test update_run_status with RUNNING status"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/update_status_running_test.pdf"
    test_bytes = b"test bytes for running"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")

    # Create and update in the same session
    async with models.get_session() as session:
        workflow_run = models.WorkflowRun(
            run_group_id=run_group.id,
            workflow_definition_id="batch",
            batch_id=batch_id,
            doc_id=doc.hash,
            start_date=datetime.datetime.now(),
            priority=0,
            created_date=datetime.datetime.now(),
            run_params={},
        )
        session.add(workflow_run)
        await session.flush()
        await session.refresh(workflow_run)
        workflow_run_id = workflow_run.id

        # Update run status to RUNNING (not last step)
        result = await wf_ops.update_run_status(
            workflow_run_id, is_last_step=False, status=RunStatus.COMPLETED, session=session
        )
        assert result == RunStatus.RUNNING
        await session.commit()


@pytest.mark.asyncio
async def test_get_run_group_stats(monkeypatch, mock_engine):  # noqa F811
    """Test get_run_group_stats function"""
    do_monkeypatch(monkeypatch, mock_engine)

    # Create test data
    batch_id = await doc_ops.new_batch("test_source", "Test Batch")
    test_uri = "/tmp/stats_test.pdf"
    test_bytes = b"test bytes"
    uri, doc = await doc_ops.create_document_from_uri(
        test_uri, "test_source", "application/pdf", test_bytes, batch_id=batch_id
    )

    run_group = await wf_ops.create_run_group(workflow_definition_id="batch", batch_id=batch_id, param_id="test1")
    await wf_ops.create_workflow_run(run_group=run_group, doc_id=doc.hash)

    # Get stats
    stats = await wf_ops.get_run_group_stats(run_group.id)
    assert stats is not None
    assert isinstance(stats, dict)
    # Should have status counts
    assert "PENDING" in stats
