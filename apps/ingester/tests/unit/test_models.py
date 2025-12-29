import datetime

from soliplex.ingester.lib.models import Document
from soliplex.ingester.lib.models import DocumentBatch
from soliplex.ingester.lib.models import DocumentURIHistory
from soliplex.ingester.lib.models import RunStep
from soliplex.ingester.lib.models import WorkflowRun
from soliplex.ingester.lib.models import doc_hash
from soliplex.ingester.lib.models import get_session


def test_get_session():
    session = get_session()
    assert session is not None


def test_document_init():
    doc = Document(uri="test.txt", hash="test-hash")

    assert doc.hash is not None


def test_document_bytes_init_with_file_bytes():
    """Test DocumentBytes init with file_bytes to cover line 175"""
    from soliplex.ingester.lib.models import ArtifactType
    from soliplex.ingester.lib.models import DocumentBytes

    doc_bytes = DocumentBytes(
        hash="test-hash",
        artifact_type=ArtifactType.DOC.value,
        storage_root="test",
        file_bytes=b"test data",
        file_size=None,
    )
    assert doc_bytes.file_size == 9


def test_document_history_init():
    doc_history = DocumentURIHistory(
        doc_uri_id=0,
        version=1,
        process_date=datetime.date.today(),
        hash="test-hash",
    )

    assert doc_history.doc_uri_id == 0
    assert doc_history.version == 1
    assert doc_history.hash is not None
    assert doc_history.process_date is not None


def test_doc_hash():
    """Test doc_hash function"""
    data = b"test data"
    hash_result = doc_hash(data)
    assert hash_result.startswith("sha256-")
    assert len(hash_result) == 71


def test_document_batch_duration_with_completed_date():
    """Test DocumentBatch duration property when completed_date is set"""
    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    completed = datetime.datetime(2024, 1, 1, 10, 5, 0)
    batch = DocumentBatch(name="test", source="test", start_date=start, completed_date=completed)
    assert batch.duration == 300.0


def test_document_batch_duration_without_completed_date():
    """Test DocumentBatch duration property when completed_date is None (lines 77-79)"""
    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    batch = DocumentBatch(name="test", source="test", start_date=start, completed_date=None)
    assert batch.duration is None


def test_workflow_run_duration_with_completed_date():
    """Test WorkflowRun duration property when completed_date is set"""
    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    completed = datetime.datetime(2024, 1, 1, 10, 5, 0)
    run = WorkflowRun(
        workflow_definition_id="test",
        batch_id=1,
        doc_id="doc1",
        run_group_id=1,
        start_date=start,
        completed_date=completed,
    )
    assert run.duration == 300.0


def test_workflow_run_duration_without_completed_date():
    """Test WorkflowRun duration property when completed_date is None"""
    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    run = WorkflowRun(
        workflow_definition_id="test",
        batch_id=1,
        doc_id="doc1",
        run_group_id=1,
        start_date=start,
        completed_date=None,
    )
    assert run.duration is None


def test_run_step_duration_with_completed_date():
    """Test RunStep duration property when completed_date is set"""
    from soliplex.ingester.lib.models import RunStatus
    from soliplex.ingester.lib.models import WorkflowStepType

    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    completed = datetime.datetime(2024, 1, 1, 10, 5, 0)
    step = RunStep(
        workflow_run_id=1,
        workflow_step_number=1,
        workflow_step_name="test",
        step_type=WorkflowStepType.INGEST,
        status=RunStatus.COMPLETED,
        step_config_id=1,
        start_date=start,
        completed_date=completed,
    )
    assert step.duration == 300.0


def test_run_step_duration_without_completed_date():
    """Test RunStep duration property when completed_date is None"""
    from soliplex.ingester.lib.models import RunStatus
    from soliplex.ingester.lib.models import WorkflowStepType

    start = datetime.datetime(2024, 1, 1, 10, 0, 0)
    step = RunStep(
        workflow_run_id=1,
        workflow_step_number=1,
        workflow_step_name="test",
        step_type=WorkflowStepType.INGEST,
        status=RunStatus.PENDING,
        step_config_id=1,
        start_date=start,
        completed_date=None,
    )
    assert step.duration is None
