import pathlib

import fastapi
from fastapi import responses

from soliplex import agui
from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import views
from soliplex.views import agui as agui_views
from soliplex.views import authz as authz_views
from soliplex.views import util as views_util

router = fastapi.APIRouter(tags=["uploads"])

depend_the_installation = installation.depend_the_installation
depend_the_threads = agui.depend_the_threads
depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger
depend_the_authz_logger = authz_views.depend_the_authz_logger

RoomUploadAuditLog = loggers.RoomUploadAuditLog


def get_the_room_upload_audit_log(
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> RoomUploadAuditLog:
    return RoomUploadAuditLog(claims=the_user_claims)


depend_the_room_upload_audit_log = fastapi.Depends(
    get_the_room_upload_audit_log,
)


async def has_write_access_to_room(
    *,
    room_id: str,
    the_user_claims: authn.UserClaims,
    action: str,
    the_admin_users: authz.AdminUserPolicy,
    the_room_authz: authz.RoomAuthorizationPolicy,
) -> bool:
    """Does the user have write access to a given room?

    This is a permission question:  the full answer also depends on
    whether uploads are configured at all, which is checked separately.

    It is used at the point where the permission is being exercised,
    and so does the checks using the auditing versions.
    """

    if await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_ROOM_UPLOAD,
        action=action,
    ):  # admins have 'ALLOW WRITE' implicitly
        return True
    else:
        return await the_room_authz.check_room_access(
            room_id=room_id,
            user_token=the_user_claims,
            permission=authz.Permission.WRITE,
        )


@views_util.logfire_span(
    "GET /v1/uploads/{room_id}",
)
@router.get("/v1/uploads/{room_id}")
async def get_uploads_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomUploads:
    """Return a list of files uploaded to the room"""
    the_logger.debug(loggers.UPLOADS_GET_ROOM)

    _room_config = await agui_views._check_user_in_room(
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
    files = views_util.upload_files(room_dir)

    return models.RoomUploads(
        room_id=room_id,
        uploads=[
            models.FileUpload(
                filename=filename,
                url=str(  # The two URL types are not compatible
                    request.url_for(
                        # View function name, not the route path.
                        "get_uploads_room_filename",
                        room_id=room_id,
                        filename=filename,
                    )
                ),
                modified_at=views_util.modified_at(stat_result),
                size_bytes=stat_result.st_size,
            )
            for filename, stat_result in files.items()
        ],
    )


@views_util.logfire_span(
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
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> str:  # file path, converted to file response by FastAPI
    """Download a file from the room uploads directory

    Unlike sandbox workdir files, which are created by a possibly-
    hallucinating or mischievous agent, files in the room-uploads tree
    are under purview of the admin / operator:  symlinks to share e.g.
    large datasets between rooms may be intentional and appropriate.
    """
    the_logger.debug(loggers.UPLOADS_GET_ROOM_FILE)

    _room_config = await agui_views._check_user_in_room(
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


@views_util.logfire_span(
    "POST /v1/uploads/{room_id}/",
)
@router.post("/v1/uploads/{room_id}", status_code=204)
async def post_uploads_room(
    room_id: str,
    upload_file: fastapi.UploadFile,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
    the_audit: RoomUploadAuditLog = depend_the_room_upload_audit_log,
) -> fastapi.Response:
    """Upload a file for a thread within the given room

    Body of request must be a file matching the `Content-Type' header
    of the request.

    Requires room 'WRITE' permission (or admin access):  'READ' access
    is not required, allowing narrowly-scoped automation tokens to push
    files into the room without being able to read other resources in
    it.
    """
    the_logger.debug(loggers.UPLOADS_POST_ROOM)
    the_authz_logger.debug(loggers.UPLOADS_POST_ROOM)

    has_write = await has_write_access_to_room(
        room_id=room_id,
        the_user_claims=the_user_claims,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
        action=loggers.AUDIT_ACTION_CREATE,
    )

    if not has_write:
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
        ) from None

    # No authz check here:  the gate above has already established room
    # 'WRITE' (or admin) access, and uploading is a write-only operation,
    # so 'READ' access is not required.  A KeyError can only mean that
    # the room is not (or no longer) configured.
    try:
        _room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
        )
    except KeyError:
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=405,
            detail="Room uploads not configured",
            headers={"Allow": ""},
        )

    room_dir = pathlib.Path(uploads_path) / room_id
    room_dir.mkdir(parents=True, exist_ok=True)
    stripped_filename = pathlib.Path(upload_file.filename).name
    upload_target = room_dir / stripped_filename
    upload_target.write_bytes(await upload_file.read())

    the_audit.room_upload_added(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)


@views_util.logfire_span(
    "DELETE /v1/uploads/{room_id}/{filename}",
)
@router.delete("/v1/uploads/{room_id}/{filename}", status_code=204)
async def delete_uploads_room(
    room_id: str,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
    the_audit: RoomUploadAuditLog = depend_the_room_upload_audit_log,
) -> fastapi.Response:
    """Delete one uploaded file from the room.

    The room has to have an upload with the given name:  a delete of
    anything else answers 404, leaving the rest of the room's uploads
    alone.

    Requires the room's 'WRITE' permission (or admin access):  'READ'
    access is not required, allowing narrowly-scoped automation tokens
    to manage the room's contents without being able to read other
    resources in it.
    """
    the_logger.debug(loggers.UPLOADS_DELETE_ROOM_FILE)
    the_authz_logger.debug(loggers.UPLOADS_DELETE_ROOM_FILE)

    has_write = await has_write_access_to_room(
        room_id=room_id,
        the_user_claims=the_user_claims,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
        action=loggers.AUDIT_ACTION_DELETE,
    )

    if not has_write:
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
        ) from None

    # No authz check here:  the gate above has already established room
    # 'WRITE' (or admin) access, and deleting a room upload is a
    # write-level operation, so 'READ' access is not required.  A
    # KeyError can only mean that the room is not (or no longer)
    # configured.
    try:
        _room_config = await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
        )
    except KeyError:
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id=room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {room_id}",
        ) from None

    uploads_path = the_installation.rooms_upload_path

    if uploads_path is None:
        raise fastapi.HTTPException(
            status_code=405,
            detail="Room uploads not configured",
            headers={"Allow": ""},
        )

    room_dir = pathlib.Path(uploads_path) / room_id

    if not room_dir.is_dir():
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No uploads in room: {room_id}",
        )

    stripped_filename = pathlib.Path(filename).name
    file_path = room_dir / stripped_filename

    if not file_path.is_file():
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No room upload: {filename}",
        )

    file_path.unlink()

    the_audit.room_upload_deleted(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)
