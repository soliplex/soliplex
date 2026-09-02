import pathlib

import fastapi
from fastapi import responses

from soliplex import agui
from soliplex import authn as authn_package
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import views
from soliplex.views import agui as soliplex_views_agui
from soliplex.views import authz as soliplex_views_authz
from soliplex.views import util as soliplex_views_util

router = fastapi.APIRouter(tags=["uploads"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui.depend_the_threads
depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger
depend_the_authz_logger = soliplex_views_authz.depend_the_authz_logger

RoomUploadAuditLog = loggers.RoomUploadAuditLog


def get_the_room_upload_audit_log(
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
) -> RoomUploadAuditLog:
    return RoomUploadAuditLog(claims=the_user_claims)


depend_the_room_upload_audit_log = fastapi.Depends(
    get_the_room_upload_audit_log,
)


@soliplex_views_util.logfire_span(
    "GET /v1/uploads/{room_id}",
)
@router.get("/v1/uploads/{room_id}")
async def get_uploads_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomUploads:
    """Return a list of files uploaded to the room"""
    the_logger.debug(loggers.UPLOADS_GET_ROOM)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
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
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Download a file from the room uploads directory"""
    the_logger.debug(loggers.UPLOADS_GET_ROOM_FILE)

    _room_config = await soliplex_views_agui._check_user_in_room(
        room_id=room_id,
        the_installation=the_installation,
        the_room_authz=the_room_authz,
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
            detail=f"No uploads in room: {room_id}",
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
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn_package.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
    the_audit: RoomUploadAuditLog = depend_the_room_upload_audit_log,
) -> fastapi.Response:
    """Upload a file for a thread within the given room

    Body of request must be a file matching the `Content-Type' header
    of the request.
    """
    the_logger.debug(loggers.UPLOADS_POST_ROOM)
    the_authz_logger.debug(loggers.UPLOADS_POST_ROOM)

    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_ROOM_UPLOAD,
        action=loggers.AUDIT_ACTION_CREATE,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

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

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=405,
            detail="Room uploads not configured",
            headers={"Allow": "GET"},
        )

    room_dir = pathlib.Path(uploads_path) / room_id
    room_dir.mkdir(parents=True, exist_ok=True)
    stripped_filename = pathlib.Path(upload_file.filename).name
    upload_target = room_dir / stripped_filename
    upload_target.write_bytes(await upload_file.read())

    the_audit.room_upload_added(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)
