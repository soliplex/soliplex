import pathlib

import fastapi
import pydantic
from fastapi import responses

from soliplex import agui
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
depend_the_threads = agui.depend_the_threads
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}/thread/{thread_id}",
)
@router.get("/v1/uploads/{room_id}/thread/{thread_id}")
async def get_uploads_room_thread(
    request: fastapi.Request,
    room_id: str,
    thread_id: pydantic.UUID4,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomUploads:
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)

    the_logger.debug(loggers.UPLOADS_GET_ROOM_THREAD)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
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
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Download a file from the room uploads directory"""
    thread_id = str(thread_id)

    the_logger.debug(loggers.UPLOADS_GET_ROOM_THREAD_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
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
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
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
        the_room_authz=the_room_authz,
        the_user_claims=the_user_claims,
        the_logger=the_logger,
    )

    if not _room_config.has_sandbox:
        raise fastapi.HTTPException(
            status_code=405,
            detail="Sandbox not configured",
            headers={"Allow": "GET"},
        )

    uploads_path = the_installation.threads_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=405,
            detail="Thread uploads not configured",
            headers={"Allow": "GET"},
        )

    try:
        await the_threads.get_thread(
            user_name=user_name,
            room_id=room_id,
            thread_id=thread_id,
        )
    except agui.AGUI_Exception as exc:
        raise fastapi.HTTPException(
            status_code=exc.status_code,
            detail=exc.args,
        ) from None

    thread_dir = pathlib.Path(uploads_path) / thread_id
    thread_dir.mkdir(parents=True, exist_ok=True)
    stripped_filename = pathlib.Path(upload_file.filename).name
    upload_target = thread_dir / stripped_filename
    upload_target.write_bytes(await upload_file.read())

    return fastapi.Response(status_code=204)
