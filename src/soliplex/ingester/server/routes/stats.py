import logging

from fastapi import APIRouter
from fastapi import Response
from fastapi import status

from soliplex.ingester.lib.wf import operations as wf_ops

logger = logging.getLogger(__name__)

stats_router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@stats_router.get(
    "/durations",
    status_code=status.HTTP_200_OK,
    summary="get workflow durations by run_group_id",
)
async def get_run_group_durations(run_group_id: int, response: Response):
    try:
        return await wf_ops.get_run_group_durations(status)
    except Exception as e:
        logger.exception("error getting run group durations", exc_info=e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}


@stats_router.get(
    "/step-stats",
    status_code=status.HTTP_200_OK,
    summary="get workflow step stats by run_group_id",
)
async def get_run_group_step_stats(run_group_id: int, response: Response):
    try:
        return await wf_ops.get_step_stats(run_group_id)
    except Exception as e:
        logger.exception("error getting run group step stats", exc_info=e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}
