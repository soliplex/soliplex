import json
import logging
from unittest.mock import AsyncMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

logger = logging.getLogger(__name__)


@pytest.fixture
def test_client():
    """Create a test client with mocked lifespan"""
    with patch("soliplex.ingester.lib.wf.runner.start_worker", new_callable=AsyncMock):
        from soliplex.ingester.server import app

        client = TestClient(app)
        return client


def test_source_status(test_client):
    """Test source_status endpoint"""
    with patch("soliplex.ingester.server.operations.get_doc_status") as mock_status:
        mock_status.return_value = ({"hash1": "status1"}, [])
        response = test_client.post(
            "/api/v1/source-status",
            data={
                "source": "test_source",
                "hashes": json.dumps({"hash1": "v1"}),
            },
        )
        assert response.status_code == 200
        mock_status.assert_called_once()


def test_source_status_invalid_hashes(test_client):
    """Test source_status endpoint with invalid hashes"""
    with patch("soliplex.ingester.server.operations.get_doc_status") as mock_status:
        response = test_client.post(
            "/api/v1/source-status",
            data={"source": "test_source", "hashes": json.dumps("not a dict")},
        )
        assert mock_status
        assert response.status_code == 500


def test_get_batches(test_client):
    """Test get all batches endpoint"""
    with patch("soliplex.ingester.server.routes.batch.operations.list_batches") as mock_list:
        mock_list.return_value = []
        response = test_client.get("/api/v1/batch/")
        assert response.status_code == 200
        mock_list.assert_called_once()


def test_create_batch(test_client):
    """Test create batch endpoint"""
    with patch("soliplex.ingester.server.routes.batch.operations.new_batch") as mock_new:
        mock_new.return_value = 123
        response = test_client.post(
            "/api/v1/batch/",
            data={"source": "test_source", "name": "test_batch"},
        )
        assert response.status_code == 201
        assert response.json() == {"batch_id": 123}
        mock_new.assert_called_once_with("test_source", "test_batch")


def test_start_workflows_success(test_client):
    """Test start workflows endpoint"""
    with patch("soliplex.ingester.server.routes.batch.wf_ops.create_workflow_runs_for_batch") as mock_create:
        mock_run_group = Mock()
        mock_runs = [Mock(), Mock()]
        mock_create.return_value = (mock_run_group, mock_runs)
        response = test_client.post("/api/v1/batch/start-workflows", data={"batch_id": 1})
        assert response.status_code == 201
        assert response.json()["workflows"] == 2


def test_start_workflows_not_found(test_client):
    """Test start workflows endpoint with batch not found"""
    with patch("soliplex.ingester.server.routes.batch.wf_ops.create_workflow_runs_for_batch") as mock_create:
        from soliplex.ingester.lib.wf.operations import NotFoundError

        mock_create.side_effect = NotFoundError("Batch not found")
        response = test_client.post("/api/v1/batch/start-workflows", data={"batch_id": 999})
        assert response.status_code == 404


def test_start_workflows_error(test_client):
    """Test start workflows endpoint with error"""
    with patch("soliplex.ingester.server.routes.batch.wf_ops.create_workflow_runs_for_batch") as mock_create:
        mock_create.side_effect = Exception("Test error")
        response = test_client.post("/api/v1/batch/start-workflows", data={"batch_id": 1})
        assert response.status_code == 500


def test_batch_status_success(test_client):
    """Test batch status endpoint"""
    with patch("soliplex.ingester.server.routes.batch.operations.get_batch") as mock_get_batch:
        with patch("soliplex.ingester.server.routes.batch.operations.get_documents_in_batch") as mock_get_docs:
            with patch("soliplex.ingester.server.routes.batch.wf_ops.get_workflows") as mock_get_wf:
                mock_batch = Mock()
                mock_get_batch.return_value = mock_batch

                mock_doc1 = Mock()
                mock_doc1.rag_id = "rag1"
                mock_doc2 = Mock()
                mock_doc2.rag_id = None
                mock_get_docs.return_value = [mock_doc1, mock_doc2]

                mock_wf = Mock()
                mock_wf.status.value = "completed"
                mock_get_wf.return_value = [mock_wf]

                response = test_client.get("/api/v1/batch/status?batch_id=1")
                assert response.status_code == 200
                data = response.json()
                assert data["document_count"] == 2
                assert data["parsed"] == 1
                assert data["remaining"] == 1


def test_batch_status_not_found(test_client):
    """Test batch status endpoint with batch not found"""
    with patch("soliplex.ingester.server.routes.batch.operations.get_batch") as mock_get_batch:
        mock_get_batch.return_value = None
        response = test_client.get("/api/v1/batch/status?batch_id=999")
        assert response.status_code == 404


def test_get_docs_by_source(test_client):
    """Test get documents by source"""
    with patch("soliplex.ingester.server.routes.document.operations.get_uris_for_source") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/document/?source=test_source")
        assert response.status_code == 200
        mock_get.assert_called_once_with("test_source")


def test_get_docs_by_batch(test_client):
    """Test get documents by batch_id"""
    with patch("soliplex.ingester.server.routes.document.operations.get_uris_for_batch") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/document/?batch_id=1")
        assert response.status_code == 200
        mock_get.assert_called_once_with(1)


def test_get_docs_no_params(test_client):
    """Test get documents with no parameters"""
    response = test_client.get("/api/v1/document/")
    assert response.status_code == 400


def test_ingest_document_success(test_client):
    """Test ingest document endpoint"""
    with patch("soliplex.ingester.server.routes.document.workflow.initial_load") as mock_load:
        mock_uri = Mock()
        mock_uri.id = 1
        mock_doc = Mock()
        mock_doc.hash = "hash123"
        mock_load.return_value = (mock_uri, mock_doc)

        response = test_client.post(
            "/api/v1/document/ingest-document",
            data={
                "source_uri": "/test.pdf",
                "source": "test",
                "batch_id": 1,
                "doc_meta": '{"key": "value"}',
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["document_hash"] == "hash123"


def test_ingest_document_invalid_json(test_client):
    """Test ingest document with invalid JSON metadata"""
    response = test_client.post(
        "/api/v1/document/ingest-document",
        data={
            "source_uri": "/test.pdf",
            "source": "test",
            "batch_id": 1,
            "doc_meta": "invalid json",
        },
    )
    assert response.status_code == 400


def test_ingest_document_invalid_metadata_type(test_client):
    """Test ingest document with non-dict metadata"""
    response = test_client.post(
        "/api/v1/document/ingest-document",
        data={
            "source_uri": "/test.pdf",
            "source": "test",
            "batch_id": 1,
            "doc_meta": '["not", "a", "dict"]',
        },
    )
    assert response.status_code == 500


def test_ingest_document_key_error(test_client):
    """Test ingest document with KeyError"""
    with patch("soliplex.ingester.server.routes.document.workflow.initial_load") as mock_load:
        mock_load.side_effect = KeyError("test_key")
        response = test_client.post(
            "/api/v1/document/ingest-document",
            data={
                "source_uri": "/test.pdf",
                "source": "test",
                "batch_id": 1,
                "doc_meta": "{}",
            },
        )
        assert response.status_code == 400


def test_ingest_document_exception(test_client):
    """Test ingest document with exception"""
    with patch("soliplex.ingester.server.routes.document.workflow.initial_load") as mock_load:
        mock_load.side_effect = Exception("test error")
        response = test_client.post(
            "/api/v1/document/ingest-document",
            data={
                "source_uri": "/test.pdf",
                "source": "test",
                "batch_id": 1,
                "doc_meta": "{}",
            },
        )
        assert response.status_code == 500


def test_get_run_group_durations(test_client):
    """Test get run group durations endpoint"""
    with patch("soliplex.ingester.server.routes.stats.wf_ops.get_run_group_durations") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/stats/durations?run_group_id=1")
        assert response.status_code == 200


def test_get_run_group_durations_error(test_client):
    """Test get run group durations with error"""
    with patch("soliplex.ingester.server.routes.stats.wf_ops.get_run_group_durations") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/stats/durations?run_group_id=1")
        assert response.status_code == 500


def test_get_run_group_step_stats(test_client):
    """Test get run group step stats endpoint"""
    with patch("soliplex.ingester.server.routes.stats.wf_ops.get_step_stats") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/stats/step-stats?run_group_id=1")
        assert response.status_code == 200


def test_get_run_group_step_stats_error(test_client):
    """Test get run group step stats with error"""
    with patch("soliplex.ingester.server.routes.stats.wf_ops.get_step_stats") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/stats/step-stats?run_group_id=1")
        assert response.status_code == 500


def test_get_workflows(test_client):
    """Test get workflows endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflows") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/workflow/")
        assert response.status_code == 200


def test_get_workflows_for_status(test_client):
    """Test get workflows by status endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflows_for_status") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/workflow/by-status?status=completed")
        assert response.status_code == 200


def test_list_workflows_definitions(test_client):
    """Test list workflow definitions endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_registry") as mock_load:
        mock_wf1 = Mock()
        mock_wf1.id = "wf1"
        mock_wf1.name = "Workflow 1"
        mock_load.return_value = {"wf1": mock_wf1}
        response = test_client.get("/api/v1/workflow/definitions")
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_get_workflow_def_success(test_client):
    """Test get workflow definition by id"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_workflow_registry") as mock_load:
        mock_wf = Mock()
        mock_load.return_value = {"wf1": mock_wf}
        response = test_client.get("/api/v1/workflow/definitions/wf1")
        assert response.status_code == 200


def test_get_workflow_def_not_found(test_client):
    """Test get workflow definition not found"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_workflow_registry") as mock_load:
        mock_load.return_value = {}
        response = test_client.get("/api/v1/workflow/definitions/nonexistent")
        assert response.status_code == 404


def test_list_params(test_client):
    """Test list param sets endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_param_registry") as mock_load:
        mock_param = Mock()
        mock_param.id = "p1"
        mock_param.name = "Params 1"
        mock_load.return_value = {"p1": mock_param}
        response = test_client.get("/api/v1/workflow/param-sets")
        assert response.status_code == 200
        assert len(response.json()) == 1


def test_get_param_set_success(test_client):
    """Test get param set by id"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_param_registry") as mock_load:
        mock_param = Mock()
        mock_load.return_value = {"p1": mock_param}
        response = test_client.get("/api/v1/workflow/param-sets/p1")
        assert response.status_code == 200


def test_get_param_set_not_found(test_client):
    """Test get param set not found"""
    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_param_registry") as mock_load:
        mock_load.return_value = {}
        response = test_client.get("/api/v1/workflow/param-sets/nonexistent")
        assert response.status_code == 404


def test_get_param_set_by_target(test_client):
    """Test get param set by target"""
    from soliplex.ingester.lib.models import WorkflowStepType

    with patch("soliplex.ingester.server.routes.workflow.wf_registry.load_param_registry") as mock_load:
        mock_param = Mock()
        mock_param.config = {WorkflowStepType.STORE: {"data_dir": "/test/dir"}}
        mock_load.return_value = {"p1": mock_param}
        response = test_client.get("/api/v1/workflow/param_sets/target//test/dir")
        assert response.status_code == 200


def test_get_workflow_status(test_client):
    """Test get workflow status endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_steps") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/workflow/steps?status=completed")
        assert response.status_code == 200


def test_get_workflow_status_error(test_client):
    """Test get workflow status with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_steps") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/steps?status=completed")
        assert response.status_code == 200
        assert "error" in response.json()


def test_get_workflow_run_groups(test_client):
    """Test get workflow run groups endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_groups_for_batch") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/workflow/run-groups")
        assert response.status_code == 200


def test_get_workflow_run_groups_error(test_client):
    """Test get workflow run groups with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_groups_for_batch") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/run-groups")
        assert response.status_code == 500


def test_get_workflow_run_group(test_client):
    """Test get workflow run group by id"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_group") as mock_get:
        mock_get.return_value = {}
        response = test_client.get("/api/v1/workflow/run_groups/1")
        assert response.status_code == 200


def test_get_workflow_run_group_error(test_client):
    """Test get workflow run group with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_group") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/run_groups/1")
        assert response.status_code == 500


def test_get_run_group_stats(test_client):
    """Test get run group stats endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_group_stats") as mock_get:
        mock_get.return_value = {}
        response = test_client.get("/api/v1/workflow/run_groups/1/stats")
        assert response.status_code == 200


def test_get_run_group_stats_error(test_client):
    """Test get run group stats with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_run_group_stats") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/run_groups/1/stats")
        assert response.status_code == 500


def test_get_workflow_runs(test_client):
    """Test get workflow runs endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflow_runs") as mock_get:
        mock_get.return_value = []
        response = test_client.get("/api/v1/workflow/runs?batch_id=1")
        assert response.status_code == 200


def test_get_workflow_runs_error(test_client):
    """Test get workflow runs with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflow_runs") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/runs?batch_id=1")
        assert response.status_code == 200
        assert "error" in response.json()


def test_get_workflow_by_id(test_client):
    """Test get workflow by id endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflow_run") as mock_get:
        mock_get.return_value = {}
        response = test_client.get("/api/v1/workflow/runs/1")
        assert response.status_code == 200


def test_get_workflow_by_id_error(test_client):
    """Test get workflow by id with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.get_workflow_run") as mock_get:
        mock_get.side_effect = Exception("test error")
        response = test_client.get("/api/v1/workflow/runs/1")
        assert response.status_code == 200
        assert "error" in response.json()


def test_start_workflow(test_client):
    """Test start workflow endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.create_single_workflow_run") as mock_create:
        mock_create.return_value = {}
        response = test_client.post("/api/v1/workflow/", data={"doc_id": "hash123"})
        assert response.status_code == 201


def test_start_workflow_error(test_client):
    """Test start workflow with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.create_single_workflow_run") as mock_create:
        mock_create.side_effect = Exception("test error")
        response = test_client.post("/api/v1/workflow/", data={"doc_id": "hash123"})
        assert response.status_code == 500


def test_retry_workflow(test_client):
    """Test retry workflow endpoint"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.reset_failed_steps") as mock_reset:
        mock_reset.return_value = {}
        response = test_client.post("/api/v1/workflow/retry?run_group_id=1")
        assert response.status_code == 201


def test_retry_workflow_error(test_client):
    """Test retry workflow with error"""
    with patch("soliplex.ingester.server.routes.workflow.wf_ops.reset_failed_steps") as mock_reset:
        mock_reset.side_effect = Exception("test error")
        response = test_client.post("/api/v1/workflow/retry?run_group_id=1")
        assert response.status_code == 500
