import pathlib

import fastapi
import pydantic
from fastapi import responses

from soliplex import authn as authn_package
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import views
from soliplex.views import agui as soliplex_views_agui
from soliplex.views import util as soliplex_views_util

router = fastapi.APIRouter(tags=["uploads"])

depend_the_installation = installation.depend_the_installation
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@soliplex_views_util.logfire_span(
    "GET /v1/workdirs/{room_id}/thread/{thread_id}/{run_id}",
)
@router.get("/v1/workdirs/{room_id}/thread/{thread_id}/{run_id}")
async def get_workdirs_room_thread_run(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RunWorkdirFiles:
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)
    run_id = str(run_id)

    the_logger.debug(loggers.WORKDIRS_GET_ROOM_THREAD_RUN)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    workdirs_path = the_installation.sandbox_workdirs_path

    if workdirs_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Sandbox workdirs not configured",
        )

    run_dir = pathlib.Path(workdirs_path) / room_id / thread_id / run_id
    filename_urls = {}

    if run_dir.is_dir():
        for file_or_sub in run_dir.glob("*"):
            if file_or_sub.is_file():
                filename = file_or_sub.name
                filename_urls[filename] = request.url_for(
                    # View function name, not the route path.
                    "get_workdirs_room_thread_run_filename",
                    room_id=room_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    filename=filename,
                )

    return models.RunWorkdirFiles(
        room_id=room_id,
        thread_id=thread_id,
        run_id=run_id,
        files=[
            models.WorkdirFile(
                filename=key,
                url=str(value),  # The two URL types are not compatible
            )
            for key, value in filename_urls.items()
        ],
    )


@soliplex_views_util.logfire_span(
    "GET "
    "/v1/workdirs/{room_id}/thread/{thread_id}/run/{run_id}/file/{filename}"
)
@router.get(
    "/v1/workdirs/{room_id}/thread/{thread_id}/run/{run_id}/file/{filename}",
    response_class=responses.FileResponse,
)
async def get_workdirs_room_thread_run_filename(
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)
    run_id = str(run_id)

    the_logger.debug(loggers.WORKDIRS_GET_ROOM_THREAD_RUN_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    workdirs_path = the_installation.sandbox_workdirs_path

    if workdirs_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Sandbox workdirs not configured",
        )

    run_dir = pathlib.Path(workdirs_path) / room_id / thread_id / run_id

    file_path = run_dir / filename
    if not file_path.is_file():
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No workdir file: {filename}",
        )

    return str(file_path)
