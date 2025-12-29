import asyncio
import collections

from fastapi import APIRouter
from fastapi import Form
from fastapi import Response
from fastapi import status

from soliplex.ingester.lib import operations
from soliplex.ingester.lib import workflow as workflow
from soliplex.ingester.lib.wf import operations as wf_ops

batch_router = APIRouter(prefix="/api/v1/batch", tags=["batch"])


@batch_router.get(
    "/", status_code=status.HTTP_200_OK, summary="Get all batches"
)
async def get_batches():
    return await operations.list_batches()


@batch_router.post(
    "/", status_code=status.HTTP_201_CREATED, summary="Create a new batch"
)
async def create_batch(
    source: str = Form(...),
    name: str = Form(...),
):
    batch_id = await operations.new_batch(source, name)
    return {"batch_id": batch_id}


@batch_router.post(
    "/start-workflows",
    status_code=status.HTTP_201_CREATED,
    summary="Start workflows for all docs in a batch",
)
async def start_workflows(
    response: Response,
    batch_id: int = Form(...),
    workflow_definition_id: str | None = Form(None),
    priority: int = Form(0),
    param_id: str = Form(None),
):
    try:
        run_group, runs = await wf_ops.create_workflow_runs_for_batch(
            batch_id,
            workflow_definition_id=workflow_definition_id,
            priority=priority,
            param_id=param_id,
        )
        return {
            "message": "Workflows started",
            "workflows": len(runs),
            "run_group": run_group,
        }
    except wf_ops.NotFoundError:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Batch {batch_id} not found"}
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}


@batch_router.get(
    "/status",
    status_code=status.HTTP_200_OK,
    summary="Get batch status document count and parsed count",
)
async def batch_status(batch_id: int, response: Response):
    batch = await operations.get_batch(batch_id)
    if batch:
        grp = asyncio.gather(
            operations.get_documents_in_batch(batch_id),
            wf_ops.get_workflows(batch_id),
        )
        docs, workflows = await grp
        parsed = [x for x in docs if x.rag_id is not None]
        stat_counts = collections.Counter([x.status.value for x in workflows])
        batchres = {
            "batch": batch,
            "document_count": len(docs),
            "workflow_count": stat_counts,
            "workflows": workflows,
            "parsed": len(parsed),
            "remaining": len(docs) - len(parsed),
        }
        return batchres
    else:
        response.status_code = status.HTTP_404_NOT_FOUND
        return {"error": f"Batch {batch_id} not found"}
