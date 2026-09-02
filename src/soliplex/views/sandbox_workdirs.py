import os
import pathlib
import stat
import urllib.parse as url_parse

import fastapi
import pydantic
from fastapi import responses

from soliplex import agui
from soliplex import authn
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


CHUNKSIZE = 2**16  # 64k

# DO NOT SIMPLIFY HERE:
# This is the RFC 5987 extended-parameter syntax for a
# 'Content-Disposition' header value using 'attachment'.
ATTACHMENT_PREFIX = "attachment; filename*=UTF-8''"


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
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RunWorkdirFiles:
    """Return a list of files uploaded to the thread"""
    thread_id = str(thread_id)
    run_id = str(run_id)

    the_logger.debug(loggers.WORKDIRS_GET_ROOM_THREAD_RUN)

    await soliplex_views_agui._check_thread_ownership(
        room_id=room_id,
        thread_id=thread_id,
        run_id=run_id,
        the_installation=the_installation,
        the_threads=the_threads,
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
            if not file_or_sub.is_symlink() and file_or_sub.is_file():
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


def _open_no_symlinks(file_path: pathlib.Path):
    """Return a streaming generator for 'file_path'

    First ensure that it is a regular file (no symlinks, etc.)
    """
    not_found = f"No workdir file: {file_path.name}"

    try:
        fd = os.open(
            file_path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
        )
    except OSError:  # ELOOP for a symlink, ENOENT, EACCES
        raise fastapi.HTTPException(
            status_code=404,
            detail=not_found,
        ) from None

    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode):  # directory, FIFO, device, socket
        os.close(fd)
        raise fastapi.HTTPException(status_code=404, detail=not_found)

    def _stream():  # now owns the fd
        with os.fdopen(fd, "rb") as fh:
            while chunk := fh.read(CHUNKSIZE):
                yield chunk

    return _stream, st.st_size


def _disposition(file_path: pathlib.Path) -> str:
    attachment_name = url_parse.quote(file_path.name, safe="")
    return f"{ATTACHMENT_PREFIX}{attachment_name}"


@soliplex_views_util.logfire_span(
    "GET "
    "/v1/workdirs/{room_id}/thread/{thread_id}/run/{run_id}/file/{filename}"
)
@router.get(
    "/v1/workdirs/{room_id}/thread/{thread_id}/run/{run_id}/file/{filename}",
)
async def get_workdirs_room_thread_run_filename(
    room_id: str,
    thread_id: pydantic.UUID4,
    run_id: pydantic.UUID4,
    filename: str,
    the_installation: installation.Installation = depend_the_installation,
    the_threads: agui.ThreadStorage = depend_the_threads,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> responses.StreamingResponse:
    """Return a file uploaded to the thread.

    In order to prevent an agent-created symlink from exposing a file
    not in the workdir, this view returns a streaming response, rather
    than using `fastapi`s 'FileResponse-from-filename' affordance.
    """
    thread_id = str(thread_id)
    run_id = str(run_id)

    the_logger.debug(loggers.WORKDIRS_GET_ROOM_THREAD_RUN_FILE)

    await soliplex_views_agui._check_thread_ownership(
        room_id=room_id,
        thread_id=thread_id,
        run_id=run_id,
        the_installation=the_installation,
        the_threads=the_threads,
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

    streamer, size = _open_no_symlinks(file_path)

    stream = streamer()

    # Declare one fixed, inert type rather than guessing from the
    # filename as 'FileResponse' did: the name is chosen by
    # model-authored code, so a guess would hand the browser a
    # content type derived from untrusted input. Together with the
    # 'attachment' disposition and 'nosniff', this makes the browser
    # download the file and never interpret it.
    return responses.StreamingResponse(
        stream,
        media_type="application/octet-stream",
        headers={
            "content-length": str(size),
            "content-disposition": _disposition(file_path),
            "x-content-type-options": "nosniff",
        },
    )
