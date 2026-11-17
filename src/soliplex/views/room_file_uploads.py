"""Room uploads:  list, download, upload, and delete a room's shared files

An upload is written through a hidden *reservation* file in the room's
directory ('util.UPLOAD_RESERVATION_PREFIX'):

1. Reserve, under the room's lock (milliseconds):  check the room's
   quota against its stored bytes (reservations included), then create
   the reservation and extend it to the upload's full size.  From then
   on, the upload counts against the quota for every process sharing the
   uploads tree.
2. Store, outside the lock:  copy the spooled upload into the
   reservation, then 'os.replace' it onto the upload's name.  Readers
   never see a partly written file under that name.

All filesystem work runs in worker threads (the uploads tree may be on a
network filesystem), through 'anyio.to_thread.run_sync', which does not
abandon the thread on cancellation:  so the lock covers the whole
reservation step, and a reservation is always renamed or removed.
"""

import asyncio
import contextlib
import dataclasses
import os
import pathlib
import uuid
import weakref

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

# The longest an upload waits for its room's lock before answering 503.
# The lock covers only the reservation step, so a long wait means the
# storage is stalled.  Kept below the usual 60-second proxy timeout, so
# that the client sees the 503, not a proxy's 504.
ROOM_UPLOAD_LOCK_TIMEOUT_SECONDS = 30

# 'Retry-After' for every 503 this module answers.
ROOM_UPLOAD_RETRY_AFTER_SECONDS = 5

# Worker threads upload I/O may use at once.  A limiter of its own keeps
# uploads stuck on slow storage from starving anyio's default pool, which
# Starlette uses for other blocking work.
UPLOAD_IO_THREADS = 8

_COPY_CHUNK_BYTES = 1024 * 1024


def get_the_room_upload_audit_log(
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> RoomUploadAuditLog:
    return RoomUploadAuditLog(claims=the_user_claims)


depend_the_room_upload_audit_log = fastapi.Depends(
    get_the_room_upload_audit_log,
)

# One lock per room with an upload reserving, making "scan, check, and
# create the reservation" atomic within this process.  Weak values drop a
# room's lock as soon as no upload holds or awaits it, so the table never
# outgrows the uploads in flight.  Module level, not on 'Installation':
# a config reload replaces the installation, and an upload under the old
# lock would then race one under a fresh lock.
#
# The locks are per-process:  with more than one server process (e.g.
# 'serve --workers N', or several replicas sharing the uploads tree) the
# quota is soft.  Reservations keep the overshoot small;  'soliplex-cli
# audit rooms' reports it.
_ROOM_UPLOAD_LOCKS: weakref.WeakValueDictionary[str, asyncio.Lock] = (
    weakref.WeakValueDictionary()
)

# Created on first use:  a limiter attaches to the event loop which first
# waits on it.
_UPLOAD_IO_LIMITER: anyio.CapacityLimiter | None = None


def _room_upload_lock(room_id: str) -> asyncio.Lock:
    lock = _ROOM_UPLOAD_LOCKS.get(room_id)

    if lock is None:
        lock = _ROOM_UPLOAD_LOCKS[room_id] = asyncio.Lock()

    return lock


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


@contextlib.asynccontextmanager
async def _acquire_room_upload_lock(
    room_id: str,
    the_logger: loggers.LogWrapper,
):
    """Hold the room's upload lock;  raise 503 if it cannot be had in time"""
    lock = _room_upload_lock(room_id)

    try:
        with anyio.fail_after(ROOM_UPLOAD_LOCK_TIMEOUT_SECONDS):
            await lock.acquire()
    except TimeoutError:
        the_logger.exception(loggers.UPLOADS_ROOM_BUSY, room_id=room_id)
        busy = _service_unavailable(f"{loggers.UPLOADS_ROOM_BUSY}: {room_id}")
        raise busy from None

    try:
        yield
    finally:
        lock.release()


def _upload_size(upload_file: fastapi.UploadFile) -> int:
    """Return the size of the (already spooled) uploaded file"""
    if upload_file.size is not None:
        return upload_file.size

    stream = upload_file.file
    size = stream.seek(0, os.SEEK_END)
    stream.seek(0)

    return size


@dataclasses.dataclass(frozen=True, kw_only=True)
class _OverQuota:
    used_bytes: int
    available_bytes: int


class UploadLargerThanReserved(ValueError):
    """The spooled upload held more bytes than its reported size"""

    def __init__(self, reserved_bytes: int):
        self.reserved_bytes = reserved_bytes
        super().__init__(
            f"Upload is larger than its reserved {reserved_bytes} bytes",
        )


def _reservation_path(room_dir: pathlib.Path) -> pathlib.Path:
    return room_dir / (
        f"{views_util.UPLOAD_RESERVATION_PREFIX}{uuid.uuid4().hex}"
    )


def _reserve_room_upload(
    room_dir: pathlib.Path,
    upload_target: pathlib.Path,
    reservation: pathlib.Path,
    upload_bytes: int,
    quota_bytes: int | None,
) -> _OverQuota | None:
    """Check the quota, then create 'reservation' for 'upload_bytes'

    Runs in a worker thread, under the room's lock.  Replacing an existing
    file counts only the difference in size;  other uploads' reservations
    count at their full size.  Return an '_OverQuota' (having created
    nothing), or 'None' once reserved.  Raise 'OSError' when the storage
    fails, leaving no reservation behind.

    The caller names the reservation, so that it can remove it even when
    cancelled before this call's result reaches it.
    """
    room_dir.mkdir(parents=True, exist_ok=True)

    if quota_bytes is not None:
        used_bytes = views_util.scan_uploads(room_dir).stored_bytes
        replaced_bytes = views_util.stored_size(upload_target)
        available_bytes = max(quota_bytes - used_bytes + replaced_bytes, 0)

        if upload_bytes > available_bytes:
            return _OverQuota(
                used_bytes=used_bytes,
                available_bytes=available_bytes,
            )

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    fd = os.open(reservation, flags, 0o666)

    try:
        # The full size at once, so that every scan counts it from now.
        os.ftruncate(fd, upload_bytes)
    except BaseException:
        os.close(fd)  # before the unlink:  see '_discard_reservation'
        _discard_reservation(reservation)
        raise

    os.close(fd)

    return None


def _copy_reserved(source, out, reserved_bytes: int) -> int:
    """Copy 'source' into 'out', refusing more than 'reserved_bytes'"""
    written = 0

    while chunk := source.read(_COPY_CHUNK_BYTES):
        written += len(chunk)

        if written > reserved_bytes:
            raise UploadLargerThanReserved(reserved_bytes)

        out.write(chunk)

    return written


def _store_room_upload(
    reservation: pathlib.Path,
    source,
    upload_target: pathlib.Path,
    upload_bytes: int,
):
    """Fill the reservation from 'source', then rename it into place

    Runs in a worker thread, outside the room's lock.  On any failure the
    reservation is closed, then removed, and the target is left as it was.
    """
    try:
        with reservation.open("r+b") as out:
            source.seek(0)
            written = _copy_reserved(source, out, upload_bytes)

            if written < upload_bytes:
                out.truncate(written)

            out.flush()
            os.fsync(out.fileno())

        os.replace(reservation, upload_target)
    except BaseException:
        _discard_reservation(reservation)
        raise


def _discard_reservation(reservation: pathlib.Path):
    """Remove a reservation, if it is still there

    Always called with the file closed:  on NFS (EFS included), removing
    a file still open leaves a '.nfs*' file behind until it is closed.
    A failure here is not raised:  the orphan stays, counted against the
    quota, and 'soliplex-cli audit rooms' reports it.
    """
    with contextlib.suppress(OSError):
        reservation.unlink(missing_ok=True)


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

    if views_util.is_internal_upload_name(filename) or not file_path.is_file():
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
    """Upload a file to the given room

    Body of request must be a file matching the `Content-Type' header
    of the request.  An upload with an existing file's name replaces it.

    If the room configures 'quotas.room_uploads_bytes', an upload which
    would take the room's stored bytes past it answers 507, and nothing
    is written.  Replacing a file counts only the difference in size, and
    uploads in progress count at their full size.  With more than one
    server process sharing the uploads tree, the quota is soft:  uploads
    starting at the same moment in different processes may overshoot it.

    Answers 503, with 'Retry-After', when the room's upload lock cannot
    be had in time, or the storage fails;  nothing is written either way.

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
        room_config = await the_installation.get_room_config(
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

    if views_util.is_internal_upload_name(stripped_filename):
        # It would be hidden from the listing, yet count against the quota.
        raise fastapi.HTTPException(
            status_code=400,
            detail=f"Reserved upload filename: {stripped_filename}",
        )

    room_dir = pathlib.Path(uploads_path) / room_id
    upload_target = room_dir / stripped_filename
    quota_bytes = room_config.quotas.room_uploads_bytes
    upload_bytes = _upload_size(upload_file)

    reservation = _reservation_path(room_dir)

    try:
        # 1. Reserve.  Locked only after the lookup above has found the
        #    room configured, so no unknown 'room_id' ever gets a lock.
        async with _acquire_room_upload_lock(room_id, the_logger):
            over_quota = await _run_upload_io(
                _reserve_room_upload,
                room_dir,
                upload_target,
                reservation,
                upload_bytes,
                quota_bytes,
            )

        # 2. Store, outside the lock.
        if over_quota is None:
            await _run_upload_io(
                _store_room_upload,
                reservation,
                upload_file.file,
                upload_target,
                upload_bytes,
            )
    except fastapi.HTTPException:
        # Busy:  nothing reserved.  No cleanup either, which on stalled
        # storage would itself stall.
        raise
    except OSError:
        # Either step has already removed whatever it reserved.
        raise _storage_unavailable(the_logger, room_id) from None
    except BaseException:
        # Cancelled, or failed otherwise, at any point:  the reservation
        # must not be left behind (once stored, it is gone already).
        with anyio.CancelScope(shield=True):
            await _run_upload_io(_discard_reservation, reservation)
        raise

    if over_quota is not None:
        the_logger.error(
            loggers.UPLOADS_ROOM_QUOTA_EXCEEDED,
            room_id=room_id,
            quota_bytes=quota_bytes,
            used_bytes=over_quota.used_bytes,
            upload_bytes=upload_bytes,
        )
        the_audit.room_upload_quota_exceeded(
            room_id=room_id,
            filename=stripped_filename,
            quota_bytes=quota_bytes,
            used_bytes=over_quota.used_bytes,
            upload_bytes=upload_bytes,
        )
        raise fastapi.HTTPException(
            status_code=507,
            detail=(
                f"{loggers.UPLOADS_ROOM_QUOTA_EXCEEDED}: "
                f"{upload_bytes} bytes requested, "
                f"{over_quota.available_bytes} available"
            ),
        )

    the_audit.room_upload_added(room_id=room_id, filename=stripped_filename)

    return fastapi.Response(status_code=204)


def _delete_room_upload(room_dir: pathlib.Path, filename: str) -> str | None:
    """Remove the named upload;  return a 404 detail if there is none"""
    if not room_dir.is_dir():
        return f"No uploads in room: {room_dir.name}"

    file_path = room_dir / filename

    if views_util.is_internal_upload_name(filename) or not file_path.is_file():
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
    anything else, internal files included, answers 404, leaving the rest
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
