import pathlib

import fastapi
import pydantic
from fastapi import responses

from soliplex import agui as agui_package
from soliplex import authn as authn_package
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import views as views_package
from soliplex.views import agui as soliplex_views_agui
from soliplex.views import authz as soliplex_views_authz
from soliplex.views import util as soliplex_views_util

router = fastapi.APIRouter(tags=["uploads"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui_package.depend_the_threads
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_user_claims = views_package.depend_the_user_claims
depend_the_logger = views_package.depend_the_logger
depend_the_authz_logger = soliplex_views_authz.depend_the_authz_logger


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}",
)
@router.get("/v1/uploads/{room_id}")
async def get_uploads_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomUploads:
    """Return a list of files uploaded to the room"""
    the_logger.debug(loggers.UPLOADS_GET_ROOM)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Room uploads not configured",
        )

    room_dir = pathlib.Path(uploads_path) / room_id
    filename_urls = {}

    if room_dir.is_dir():
        for file_or_sub in room_dir.glob("*"):
            if file_or_sub.is_file():
                filename = file_or_sub.name
                filename_urls[filename] = request.url_for(
                    # View function name, not the route path.
                    "get_uploads_room_filename",
                    room_id=room_id,
                    filename=filename,
                )

    return models.RoomUploads(
        room_id=room_id,
        uploads=[
            models.FileUpload(
                filename=key,
                url=str(value),  # The two URL types are not compatible
            )
            for key, value in filename_urls.items()
        ],
    )


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}/file/{filename}",
)
@router.get(
    "/v1/uploads/{room_id}/file/{filename}",
    response_class=responses.FileResponse,
)
async def get_uploads_room_filename(
    room_id: str,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Download a file from the room uploads directory"""
    the_logger.debug(loggers.UPLOADS_GET_ROOM_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Room uploads not configured",
        )

    room_dir = pathlib.Path(uploads_path) / room_id

    if not room_dir.is_dir():
        raise fastapi.HTTPException(
            status_code=404,
            detail="No uploads in room: {room_id}",
        )

    file_path = room_dir / filename

    if not file_path.is_file():
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No room upload: {filename}",
        )

    return str(file_path)


@soliplex_views_util.logfire_span(
    "POST /v1/uploads/{room_id}/",
)
@router.post("/v1/uploads/{room_id}", status_code=204)
async def post_uploads_room(
    room_id: str,
    upload_file: fastapi.UploadFile,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> fastapi.Response:
    """Upload a file for a thread within the given room

    Body of request must be a file matching the `Content-Type' header
    of the request.
    """
    the_logger.debug(loggers.UPLOADS_POST_ROOM)
    the_authz_logger.debug(loggers.UPLOADS_POST_ROOM)

    if not await the_authz_policy.check_admin_access(the_user_claims):
        the_authz_logger.error(loggers.AUTHZ_ADMIN_ACCESS_REQUIRED)
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Room uploads not configured",
        )

    room_dir = pathlib.Path(uploads_path) / room_id
    room_dir.mkdir(parents=True, exist_ok=True)
    stripped_filename = pathlib.Path(upload_file.filename).name
    upload_target = room_dir / stripped_filename
    upload_target.write_bytes(await upload_file.read())

    return fastapi.Response(status_code=204)


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}/thread/{thread_id}",
)
@router.get("/v1/uploads/{room_id}/thread/{thread_id}")
async def get_uploads_room_thread(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomUploads:
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)

    the_logger.debug(loggers.UPLOADS_GET_ROOM_THREAD)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Thread uploads not configured",
        )

    thread_dir = pathlib.Path(uploads_path) / thread_id
    filename_urls = {}

    if thread_dir.is_dir():
        for file_or_sub in thread_dir.glob("*"):
            if file_or_sub.is_file():
                filename = file_or_sub.name
                filename_urls[filename] = request.url_for(
                    # View function name, not the route path.
                    "get_uploads_room_thread_filename",
                    room_id=room_id,
                    thread_id=thread_id,
                    filename=filename,
                )

    return models.ThreadUploads(
        room_id=room_id,
        thread_id=thread_id,
        uploads=[
            models.FileUpload(
                filename=key,
                url=str(value),  # The two URL types are not compatible
            )
            for key, value in filename_urls.items()
        ],
    )


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}/thread/{thread_id}/file/{filename}",
)
@router.get(
    "/v1/uploads/{room_id}/thread/{thread_id}/file/{filename}",
    response_class=responses.FileResponse,
)
async def get_uploads_room_thread_filename(
    room_id: str,
    thread_id: pydantic.UUID4,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Download a file from the room uploads directory"""
    thread_id = str(thread_id)

    the_logger.debug(loggers.UPLOADS_GET_ROOM_THREAD_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Thread uploads not configured",
        )

    thread_dir = pathlib.Path(uploads_path) / thread_id

    if not thread_dir.is_dir():
        raise fastapi.HTTPException(
            status_code=404,
            detail="No uploads in thread: {thread_id}",
        )

    file_path = thread_dir / filename

    if not file_path.is_file():
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No thread upload: {filename}",
        )

    return str(file_path)


@soliplex_views_util.logfire_span(
    "POST /v1/uploads/{room_id}/{thread_id}/",
)
@router.post("/v1/uploads/{room_id}/{thread_id}", status_code=204)
async def post_uploads_room_thread(
    room_id: str,
    thread_id: pydantic.UUID4,
    upload_file: fastapi.UploadFile,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> fastapi.Response:
    """Upload a file for a thread within the given room

    Body of request must be a file matching the `Content-Type' header
    of the request.
    """
    thread_id = str(thread_id)

    the_logger.debug(loggers.UPLOADS_POST_ROOM_THREAD)

    user_name = the_user_claims.get("preferred_username", "<unknown>")
    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    try:
        await the_threads.get_thread(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )
    except agui_package.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=404,
            detail="Thread uploads not configured",
        )

    thread_dir = pathlib.Path(uploads_path) / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)
    stripped_filename = pathlib.Path(upload_file.filename).name
    upload_target = thread_dir / stripped_filename
    upload_target.write_bytes(await upload_file.read())

    return fastapi.Response(status_code=204)


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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
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
        the_authz_policy=the_authz_policy,
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
    "/v1/workdirs/{room_id}/thread/{thread_id}/run/{run_id}/file/{filename}"
)
async def get_workdirs_room_thread_run_filename(
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RunWorkdirFiles:
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)
    run_id = str(run_id)

    the_logger.debug(loggers.WORKDIRS_GET_ROOM_THREAD_RUN_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_authz_policy=the_authz_policy,
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
