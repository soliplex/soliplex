"""Room uploads:  list, download, upload, and delete a room's shared files

Listing and deleting run their filesystem work in worker threads (the
uploads tree may be on a network filesystem), on a limiter of their own.
"""

import pathlib

import anyio
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

# 'Retry-After' for every 503 this module answers.
ROOM_UPLOAD_RETRY_AFTER_SECONDS = 5

# Worker threads upload I/O may use at once.  A limiter of its own keeps
# uploads stuck on slow storage from starving anyio's default pool, which
# Starlette uses for other blocking work.
UPLOAD_IO_THREADS = 8


def get_the_room_upload_audit_log(
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> RoomUploadAuditLog:
    return RoomUploadAuditLog(claims=the_user_claims)


depend_the_room_upload_audit_log = fastapi.Depends(
    get_the_room_upload_audit_log,
)

# Created on first use:  a limiter attaches to the event loop which first
# waits on it.
_UPLOAD_IO_LIMITER: anyio.CapacityLimiter | None = None


def _upload_io_limiter() -> anyio.CapacityLimiter:
    global _UPLOAD_IO_LIMITER

    if _UPLOAD_IO_LIMITER is None:
        _UPLOAD_IO_LIMITER = anyio.CapacityLimiter(UPLOAD_IO_THREADS)

    return _UPLOAD_IO_LIMITER


async def _run_upload_io(func, *args):
    """Run 'func(*args)' in a worker thread, never abandoning it"""
    return await anyio.to_thread.run_sync(
        func,
        *args,
        limiter=_upload_io_limiter(),
    )


def _service_unavailable(detail: str) -> fastapi.HTTPException:
    return fastapi.HTTPException(
        status_code=503,
        detail=detail,
        headers={"Retry-After": str(ROOM_UPLOAD_RETRY_AFTER_SECONDS)},
    )


def _storage_unavailable(
    the_logger: loggers.LogWrapper,
    room_id: str,
) -> fastapi.HTTPException:
    """Log the 'OSError' being handled;  return the 503 to raise"""
    the_logger.exception(
        loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        room_id=room_id,
    )
    return _service_unavailable(
        f"{loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE}: {room_id}",
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
    """Return a list of files uploaded to the room, with its quota usage

    'total_size_bytes' counts what the room's quota counts:  stored files
    and uploads in progress, but not files an operator has linked in.  It
    can therefore differ from the sum of the listed sizes, either way.
    Answers 503 if the room's storage cannot be read.
    """
    the_logger.debug(loggers.UPLOADS_GET_ROOM)

    room_config = await agui_views._check_user_in_room(
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

    try:
        scan = await _run_upload_io(views_util.scan_uploads, room_dir)
    except OSError:
        raise _storage_unavailable(the_logger, room_id) from None

    quota_bytes = room_config.quotas.room_uploads_bytes

    if quota_bytes is not None:
        available_bytes = max(quota_bytes - scan.stored_bytes, 0)
    else:
        available_bytes = None

    return models.RoomUploads(
        room_id=room_id,
        total_size_bytes=scan.stored_bytes,
        quota_bytes=quota_bytes,
        available_bytes=available_bytes,
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
            for filename, stat_result in scan.files.items()
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

    Internal files (upload reservations, '.nfs*') are never served.
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

    if views_util.is_hidden_upload_name(filename) or not file_path.is_file():
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

    stripped_filename = pathlib.Path(upload_file.filename).name

    if views_util.is_hidden_upload_name(stripped_filename):
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Upload filename starts with '.': {stripped_filename}",
        )

    upload_target = pathlib.Path(uploads_path) / room_id / stripped_filename
    try:
        await anyio.to_thread.run_sync(
            views_util.store_upload,
            upload_file.file,
            upload_target,
        )
    except OSError:
        the_logger.exception(
            loggers.UPLOADS_POST_ROOM_STORE_FAILED,
            room_id=room_id,
            filename=stripped_filename,
        )
        raise fastapi.HTTPException(
            status_code=500,
            detail=(
                f"{loggers.UPLOADS_POST_ROOM_STORE_FAILED}: "
                f"{stripped_filename}"
            ),
        ) from None

    the_audit.room_upload_added(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)


def _delete_room_upload(room_dir: pathlib.Path, filename: str) -> str | None:
    """Remove the named upload;  return a 404 detail if there is none"""
    if not room_dir.is_dir():
        return f"No uploads in room: {room_dir.name}"

    file_path = room_dir / filename

    if views_util.is_hidden_upload_name(filename) or not file_path.is_file():
        return f"No room upload: {filename}"

    file_path.unlink()

    return None


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
    anything else, hidden files included, answers 404, leaving the rest
    of the room's uploads alone.

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
    stripped_filename = pathlib.Path(filename).name

    not_found = await _run_upload_io(
        _delete_room_upload,
        room_dir,
        stripped_filename,
    )

    if not_found is not None:
        raise fastapi.HTTPException(status_code=404, detail=not_found)

    the_audit.room_upload_deleted(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)
