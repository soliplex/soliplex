import contextlib
import datetime
import io
import os
import threading
from unittest import mock

import anyio
import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex.config import quotas as config_quotas
from soliplex.config import rooms as config_rooms
from soliplex.views import room_file_uploads as room_views

USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

TEST_ROOM_ID = "test-room-id"
TEST_FILENAME = "test_file.txt"
TEST_CONTENT = b"DEADBEEF"

URL_PREFIX = "http://test.example.com/api"

no_error = contextlib.nullcontext


def raises_httpexc(*, match, code, headers=None) -> pytest.raises:
    def _check(exc):
        if headers is not None:
            return exc.status_code == code and exc.headers == headers
        else:
            return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.fixture(autouse=True)
def fresh_upload_sync():
    """Locks and limiters attach to an event loop:  one per test"""
    room_views._ROOM_UPLOAD_LOCKS.clear()
    room_views._UPLOAD_IO_LIMITER = None
    yield
    room_views._ROOM_UPLOAD_LOCKS.clear()
    room_views._UPLOAD_IO_LIMITER = None


@pytest.fixture
def uploads_path(temp_dir):
    result = temp_dir / "uploads"
    result.mkdir()
    return result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_admin_access, w_allow_write, expected",
    [
        pytest.param(False, False, False, id="noperm"),
        pytest.param(True, False, True, id="admin_ok"),
        pytest.param(False, True, True, id="write_ok"),
        pytest.param(True, True, True, id="both_ok"),
    ],
)
async def test_has_write_access_to_room(
    w_admin_access,
    w_allow_write,
    expected,
):
    ROOM_ID = "foo"
    ACTION = "test-action"

    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = w_admin_access
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = w_allow_write

    found = await room_views.has_write_access_to_room(
        room_id=ROOM_ID,
        the_user_claims=THE_USER_CLAIMS,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
        action=ACTION,
    )

    assert found is expected

    the_admin_users.check_admin_access.assert_awaited_once_with(
        THE_USER_CLAIMS,
        resource=loggers.AUDIT_RESOURCE_ROOM_UPLOAD,
        action=ACTION,
    )

    if w_admin_access:
        the_room_authz.check_room_access.assert_not_awaited()
    else:
        the_room_authz.check_room_access.assert_awaited_once_with(
            room_id=ROOM_ID,
            user_token=THE_USER_CLAIMS,
            permission=authz.Permission.WRITE,
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filenames",
    [
        [],
        ["foo.txt"],
        [f"file_{i_file:03}.txt" for i_file in range(10)],
    ],
)
@pytest.mark.parametrize(
    "w_upload_path, w_room_path, expectation",
    [
        (True, True, no_error(None)),
        (True, False, no_error(None)),
        (
            False,
            None,
            raises_httpexc(code=404, match="Room uploads not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_only(
    cuir,
    uploads_path,
    w_upload_path,
    w_room_path,
    expectation,
    w_filenames,
):
    room_uploads_path = uploads_path / "rooms"
    room_path = room_uploads_path / TEST_ROOM_ID
    # Note: this is the name of the view function, and not the path
    #       to which it is bound.
    ROUTE_NAME = "get_uploads_room_filename"

    def download_url(name, room_id, filename):
        assert name == ROUTE_NAME
        return f"{URL_PREFIX}/v1/uploads/{room_id}/{filename}"

    exp_filename_urls = {}
    exp_stats = {}

    if w_room_path:
        room_path.mkdir(parents=True)
        (room_path / "ignore_me").mkdir()
        for i_file, filename in enumerate(w_filenames):
            file_path = room_path / filename
            file_path.write_text(f"filename: {filename}")
            exp_filename_urls[filename] = download_url(
                ROUTE_NAME, TEST_ROOM_ID, filename
            )
            mtime = 1_761_725_730 + i_file
            os.utime(file_path, (mtime, mtime))
            exp_stats[filename] = (
                datetime.datetime.fromtimestamp(mtime, tz=datetime.UTC),
                len(f"filename: {filename}"),
            )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig()
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.rooms_upload_path = str(room_uploads_path)
    else:
        the_installation.rooms_upload_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await room_views.get_uploads_room(
            request=request,
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert isinstance(found, models.RoomUploads)
        assert found.room_id == TEST_ROOM_ID

        if w_room_path:
            found_files = {f_up.filename: f_up.url for f_up in found.uploads}
            assert set(found_files) == set(w_filenames)

            for filename in w_filenames:
                exp_url = exp_filename_urls[filename]
                assert str(found_files[filename]) == exp_url

            found_stats = {
                f_up.filename: (f_up.modified_at, f_up.size_bytes)
                for f_up in found.uploads
            }
            assert found_stats == exp_stats
        else:
            assert found.uploads == []

        exp_total = sum(size for _, size in exp_stats.values())
        assert found.total_size_bytes == exp_total
        assert found.quota_bytes is None
        assert found.available_bytes is None

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM,
    )


@pytest.mark.anyio
@mock.patch("soliplex.util.scan_uploads")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_w_unrepresentable_time(
    cuir,
    scan_uploads,
    uploads_path,
):
    # A file's time can be set beyond year 9999, but the filesystem under
    # the test may not store it as set, so the stat is built by hand.
    scan_uploads.return_value = util.UploadsScan(
        files={"far.txt": os.stat_result((0,) * 8 + (253_402_300_800, 0))},
        stored_bytes=0,
        hidden=[],
    )
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig()
    cuir.return_value = room_config
    request = mock.create_autospec(fastapi.Request)
    request.url_for.return_value = f"{URL_PREFIX}/file"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")

    found = await room_views.get_uploads_room(
        request=request,
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
        the_user_claims=THE_USER_CLAIMS,
        the_logger=mock.create_autospec(loggers.LogWrapper),
    )

    assert [(f_up.filename, f_up.modified_at) for f_up in found.uploads] == [
        ("far.txt", None)
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_path, w_room_path, w_filename, expectation",
    [
        (True, True, True, no_error(None)),
        (
            True,
            True,
            False,
            raises_httpexc(code=404, match=".*"),
        ),
        (
            True,
            False,
            None,
            raises_httpexc(code=404, match=".*"),
        ),
        (
            False,
            None,
            None,
            raises_httpexc(code=404, match="Room uploads not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_filename(
    cuir,
    uploads_path,
    w_upload_path,
    w_room_path,
    w_filename,
    expectation,
):
    room_uploads_path = uploads_path / "rooms"
    room_path = room_uploads_path / TEST_ROOM_ID

    if w_room_path:
        room_path.mkdir(parents=True)

        if w_filename:
            file_path = room_path / TEST_FILENAME
            file_path.write_text(f"filename: {TEST_FILENAME}")

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig()
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.rooms_upload_path = str(room_uploads_path)
    else:
        the_installation.rooms_upload_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await room_views.get_uploads_room_filename(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found == str(file_path)

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM_FILE,
    )


@mock.patch("soliplex.views.room_file_uploads.RoomUploadAuditLog")
def test_get_the_room_upload_audit_log(rual_klass):
    found = room_views.get_the_room_upload_audit_log(THE_USER_CLAIMS)

    assert found is rual_klass.return_value
    rual_klass.assert_called_once_with(claims=THE_USER_CLAIMS)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename, exp_filename",
    [
        (TEST_FILENAME, TEST_FILENAME),
        ("../../../../etc/passwd", "passwd"),
    ],
)
@pytest.mark.parametrize(
    "w_has_write, w_upload_path, expectation",
    [
        pytest.param(
            False,
            False,
            raises_httpexc(
                code=403,
                match=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
            ),
            id="noperm",
        ),
        pytest.param(True, True, no_error(204), id="write_ok"),
        pytest.param(
            True,
            False,
            raises_httpexc(
                code=405,
                match="Room uploads not configured",
                headers={"Allow": ""},
            ),
            id="no_uploads",
        ),
    ],
)
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_post_uploads_room(
    hwatr,
    uploads_path,
    w_has_write,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    hwatr.return_value = w_has_write
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig()
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=w_filename,
        headers={"Content-Type": "text/plain"},
    )

    the_installation = mock.create_autospec(
        installation.Installation,
    )
    the_installation.get_room_config.return_value = room_config

    if w_upload_path:
        the_installation.rooms_upload_path = str(uploads_path / "rooms")
    else:
        the_installation.rooms_upload_path = None

    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with expectation as expected:
        response = await room_views.post_uploads_room(
            room_id=TEST_ROOM_ID,
            upload_file=upload_file,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
            the_authz_logger=the_authz_logger,
            the_audit=the_audit,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert response.status_code == expected
        exp_file = uploads_path / "rooms" / TEST_ROOM_ID / exp_filename
        assert exp_file.read_bytes() == TEST_CONTENT
        the_audit.room_upload_added.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            filename=exp_filename,
        )
        # The config lookup consults no authz policy:  room 'WRITE'
        # (checked above) or admin alone suffices to upload.
        the_installation.get_room_config.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            user=THE_USER_CLAIMS,
        )
    else:
        # Denied by a gate, or uploads not configured:  no upload
        # occurred, and therefore there is no audit record of one.
        the_audit.room_upload_added.assert_not_called()

        if not w_has_write:
            # Denied by the permission gate, which precedes the lookup.
            the_installation.get_room_config.assert_not_called()

    hwatr.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        the_user_claims=THE_USER_CLAIMS,
        action=loggers.AUDIT_ACTION_CREATE,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
    )

    the_authz_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )


@pytest.mark.anyio
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_post_uploads_room_unknown_room(
    hwatr,
    uploads_path,
):
    hwatr.return_value = True
    # A user with write access attempting to upload into a room which is not
    # (or no longer) configured gets a 404 from the room config lookup.
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=TEST_FILENAME,
        headers={"Content-Type": "text/plain"},
    )

    the_installation = mock.create_autospec(
        installation.Installation,
    )
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_installation.get_room_config.side_effect = KeyError(TEST_ROOM_ID)

    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = True
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = False
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with pytest.raises(fastapi.HTTPException) as exc:
        await room_views.post_uploads_room(
            room_id=TEST_ROOM_ID,
            upload_file=upload_file,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
            the_authz_logger=the_authz_logger,
            the_audit=the_audit,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {TEST_ROOM_ID}"
    )

    hwatr.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        the_user_claims=THE_USER_CLAIMS,
        action=loggers.AUDIT_ACTION_CREATE,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
    )
    the_audit.room_upload_added.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename, exp_filename",
    [
        (TEST_FILENAME, TEST_FILENAME),
        ("../../../../etc/passwd", "passwd"),
    ],
)
@pytest.mark.parametrize(
    "w_has_write, w_upload_path, expectation",
    [
        pytest.param(
            False,
            True,
            raises_httpexc(
                code=403,
                match=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
            ),
            id="noperm",
        ),
        pytest.param(True, True, no_error(204), id="write_ok"),
        pytest.param(
            True,
            False,
            raises_httpexc(
                code=405,
                match="Room uploads not configured",
                headers={"Allow": ""},
            ),
            id="no_uploads",
        ),
    ],
)
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_delete_uploads_room(
    hwatr,
    uploads_path,
    w_has_write,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    hwatr.return_value = w_has_write
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig()

    the_installation = mock.create_autospec(
        installation.Installation,
    )
    the_installation.get_room_config.return_value = room_config

    exp_file = uploads_path / "rooms" / TEST_ROOM_ID / exp_filename

    if w_upload_path:
        the_installation.rooms_upload_path = str(uploads_path / "rooms")
        exp_file.parent.mkdir(parents=True)
        exp_file.touch()
    else:
        the_installation.rooms_upload_path = None

    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with expectation as expected:
        response = await room_views.delete_uploads_room(
            room_id=TEST_ROOM_ID,
            filename=w_filename,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
            the_authz_logger=the_authz_logger,
            the_audit=the_audit,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert response.status_code == expected
        assert not exp_file.exists()
        the_audit.room_upload_deleted.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            filename=exp_filename,
        )
        # The config lookup consults no authz policy:  room 'WRITE'
        # (checked above) or admin alone suffices to delete.
        the_installation.get_room_config.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            user=THE_USER_CLAIMS,
        )
    else:
        # Denied by a gate, or uploads not configured:  no delete
        # occurred, and therefore there is no audit record of one.
        the_audit.room_upload_deleted.assert_not_called()

        if not w_has_write:
            # Denied by the permission gate, which precedes the lookup.
            the_installation.get_room_config.assert_not_called()

    hwatr.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        the_user_claims=THE_USER_CLAIMS,
        action=loggers.AUDIT_ACTION_DELETE,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
    )

    the_authz_logger.debug.assert_called_once_with(
        loggers.UPLOADS_DELETE_ROOM_FILE,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_DELETE_ROOM_FILE,
    )


@pytest.mark.anyio
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_delete_uploads_room_unknown_room(
    hwatr,
    uploads_path,
):
    hwatr.return_value = True
    # Attempting to delete into a room which is not (or no longer)
    # configured gets a 404 from the room config lookup.
    the_installation = mock.create_autospec(
        installation.Installation,
    )
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_installation.get_room_config.side_effect = KeyError(TEST_ROOM_ID)

    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = True
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = False
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with pytest.raises(fastapi.HTTPException) as exc:
        await room_views.delete_uploads_room(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
            the_authz_logger=the_authz_logger,
            the_audit=the_audit,
        )

    assert exc.value.status_code == 404
    assert exc.value.detail == (
        f"{loggers.ROOM_UNKNOWN_ROOM_ID}: {TEST_ROOM_ID}"
    )
    hwatr.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        the_user_claims=THE_USER_CLAIMS,
        action=loggers.AUDIT_ACTION_DELETE,
        the_admin_users=the_admin_users,
        the_room_authz=the_room_authz,
    )
    the_audit.room_upload_deleted.assert_not_called()


@pytest.mark.anyio
async def test_delete_uploads_room_no_uploads_dir(
    uploads_path,
):
    """Deleting from a room with no uploads directory answers 404."""
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = False
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = True
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with raises_httpexc(
        code=404,
        match=f"No uploads in room: {TEST_ROOM_ID}",
    ):
        await room_views.delete_uploads_room(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=mock.create_autospec(loggers.LogWrapper),
            the_authz_logger=mock.create_autospec(loggers.LogWrapper),
            the_audit=the_audit,
        )

    the_audit.room_upload_deleted.assert_not_called()


@pytest.mark.anyio
async def test_delete_uploads_room_file_missing(
    uploads_path,
):
    """Deleting a filename the room never uploaded answers 404."""
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_admin_users = mock.create_autospec(authz.AdminUserPolicy)
    the_admin_users.check_admin_access.return_value = False
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = True
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    (uploads_path / "rooms" / TEST_ROOM_ID).mkdir(parents=True)
    # No file created:  the delete finds nothing to remove.

    with raises_httpexc(
        code=404,
        match=f"No room upload: {TEST_FILENAME}",
    ):
        await room_views.delete_uploads_room(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_admin_users=the_admin_users,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=mock.create_autospec(loggers.LogWrapper),
            the_authz_logger=mock.create_autospec(loggers.LogWrapper),
            the_audit=the_audit,
        )

    the_audit.room_upload_deleted.assert_not_called()


# ---------------------------------------------------------------------------
# Quotas, reservations, and storage behaviour
# ---------------------------------------------------------------------------

RESERVATION_GLOB = f"{util.UPLOAD_RESERVATION_PREFIX}*"


def _room_config_w_quota(quota_bytes):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    room_config.quotas = config_quotas.QuotasConfig(
        _room_uploads_bytes=quota_bytes,
    )
    return room_config


def _upload_file(content=TEST_CONTENT, filename=TEST_FILENAME, size=None):
    return fastapi.UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        size=size,
        headers={"Content-Type": "application/octet-stream"},
    )


class _Poster:
    """Call 'post_uploads_room' with mocked dependencies for one room"""

    def __init__(self, uploads_path, quota_bytes=None):
        self.rooms_path = uploads_path / "rooms"
        self.room_dir = self.rooms_path / TEST_ROOM_ID
        self.the_installation = mock.create_autospec(installation.Installation)
        self.the_installation.rooms_upload_path = str(self.rooms_path)
        self.the_installation.get_room_config.return_value = (
            _room_config_w_quota(quota_bytes)
        )
        self.the_logger = mock.create_autospec(loggers.LogWrapper)
        self.the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    async def post(self, upload_file):
        with mock.patch(
            "soliplex.views.room_file_uploads.has_write_access_to_room",
            return_value=True,
        ):
            return await room_views.post_uploads_room(
                room_id=TEST_ROOM_ID,
                upload_file=upload_file,
                the_installation=self.the_installation,
                the_admin_users=mock.create_autospec(authz.AdminUserPolicy),
                the_room_authz=mock.create_autospec(
                    authz.RoomAuthorizationPolicy
                ),
                the_user_claims=THE_USER_CLAIMS,
                the_logger=self.the_logger,
                the_authz_logger=mock.create_autospec(loggers.LogWrapper),
                the_audit=self.the_audit,
            )

    def reservations(self):
        return sorted(self.room_dir.glob(RESERVATION_GLOB))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_quota, w_existing, exp_status",
    [
        pytest.param(None, b"", 204, id="no-quota"),
        pytest.param(100, b"", 204, id="under"),
        pytest.param(len(TEST_CONTENT), b"", 204, id="exactly-at"),
        pytest.param(len(TEST_CONTENT) - 1, b"", 507, id="over"),
        pytest.param(0, b"", 507, id="zero"),
        # Replacing a file counts only the difference in size.
        pytest.param(len(TEST_CONTENT), b"12345678", 204, id="replace-same"),
        pytest.param(len(TEST_CONTENT) + 2, b"0123456789", 204, id="shrink"),
    ],
)
async def test_post_uploads_room_w_quota(
    uploads_path,
    w_quota,
    w_existing,
    exp_status,
):
    poster = _Poster(uploads_path, w_quota)
    target = poster.room_dir / TEST_FILENAME

    if w_existing:
        poster.room_dir.mkdir(parents=True)
        target.write_bytes(w_existing)

    if exp_status == 204:
        response = await poster.post(_upload_file())

        assert response.status_code == 204
        assert target.read_bytes() == TEST_CONTENT
        poster.the_audit.room_upload_added.assert_called_once()
    else:
        with raises_httpexc(
            code=507,
            match=loggers.UPLOADS_ROOM_QUOTA_EXCEEDED,
        ) as exc_info:
            await poster.post(_upload_file())

        assert exc_info.value.detail == (
            f"{loggers.UPLOADS_ROOM_QUOTA_EXCEEDED}: "
            f"{len(TEST_CONTENT)} bytes requested, {w_quota} available"
        )
        assert not target.exists()
        poster.the_audit.room_upload_added.assert_not_called()
        poster.the_audit.room_upload_quota_exceeded.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            quota_bytes=w_quota,
            used_bytes=0,
            upload_bytes=len(TEST_CONTENT),
        )
        poster.the_logger.error.assert_called_once_with(
            loggers.UPLOADS_ROOM_QUOTA_EXCEEDED,
            room_id=TEST_ROOM_ID,
            quota_bytes=w_quota,
            used_bytes=0,
            upload_bytes=len(TEST_CONTENT),
        )

    assert poster.reservations() == []


@pytest.mark.anyio
async def test_post_uploads_room_counts_other_reservations(uploads_path):
    # An upload in progress elsewhere holds its reservation at full size.
    poster = _Poster(uploads_path, 20)
    poster.room_dir.mkdir(parents=True)
    other = poster.room_dir / f"{util.UPLOAD_RESERVATION_PREFIX}other"
    other.write_bytes(b"x" * 15)

    with raises_httpexc(code=507, match="5 available"):
        await poster.post(_upload_file())

    assert poster.reservations() == [other]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename",
    [f"{util.UPLOAD_RESERVATION_PREFIX}abc", ".nfs0001"],
)
async def test_post_uploads_room_w_internal_name(uploads_path, w_filename):
    poster = _Poster(uploads_path)

    with raises_httpexc(code=400, match="Reserved upload filename"):
        await poster.post(_upload_file(filename=w_filename))

    assert not poster.room_dir.exists()


@pytest.mark.anyio
async def test_post_uploads_room_w_reported_size(uploads_path):
    # 'UploadFile.size' is used when Starlette reports it.
    poster = _Poster(uploads_path, len(TEST_CONTENT) - 1)

    with raises_httpexc(code=507, match=f"{len(TEST_CONTENT)} bytes"):
        await poster.post(_upload_file(size=len(TEST_CONTENT)))


@pytest.mark.anyio
async def test_post_uploads_room_w_spool_smaller_than_reported(uploads_path):
    poster = _Poster(uploads_path)

    await poster.post(_upload_file(size=100))

    assert (poster.room_dir / TEST_FILENAME).read_bytes() == TEST_CONTENT
    assert poster.reservations() == []


@pytest.mark.anyio
async def test_post_uploads_room_w_spool_larger_than_reported(uploads_path):
    poster = _Poster(uploads_path)

    with pytest.raises(room_views.UploadLargerThanReserved):
        await poster.post(_upload_file(size=2))

    assert not (poster.room_dir / TEST_FILENAME).exists()
    assert poster.reservations() == []


@pytest.mark.anyio
async def test_post_uploads_room_w_store_failure(uploads_path):
    poster = _Poster(uploads_path)
    poster.room_dir.mkdir(parents=True)
    target = poster.room_dir / TEST_FILENAME
    target.write_bytes(b"original")

    with (
        mock.patch("os.replace", side_effect=OSError("EFS gone")),
        raises_httpexc(
            code=503,
            match=loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
            headers={"Retry-After": "5"},
        ),
    ):
        await poster.post(_upload_file())

    assert target.read_bytes() == b"original"
    assert poster.reservations() == []
    poster.the_logger.exception.assert_called_once_with(
        loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        room_id=TEST_ROOM_ID,
    )


@pytest.mark.anyio
async def test_post_uploads_room_w_scan_failure(uploads_path):
    poster = _Poster(uploads_path, 100)

    with (
        mock.patch(
            "soliplex.util.scan_uploads",
            side_effect=OSError("EIO"),
        ),
        raises_httpexc(
            code=503,
            match=loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        ),
    ):
        await poster.post(_upload_file())

    assert poster.reservations() == []


@pytest.mark.anyio
async def test_post_uploads_room_w_ftruncate_failure(uploads_path):
    poster = _Poster(uploads_path)

    with (
        mock.patch("os.ftruncate", side_effect=OSError("ENOSPC")),
        raises_httpexc(
            code=503,
            match=loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        ),
    ):
        await poster.post(_upload_file())

    assert poster.reservations() == []


def test__discard_reservation_suppresses_oserror(temp_dir):
    reservation = temp_dir / "reservation"

    with mock.patch.object(
        type(reservation),
        "unlink",
        side_effect=OSError("EIO"),
    ):
        room_views._discard_reservation(reservation)  # does not raise


@pytest.mark.anyio
async def test_post_uploads_room_w_busy_room(uploads_path):
    poster = _Poster(uploads_path)
    lock = room_views._room_upload_lock(TEST_ROOM_ID)
    await lock.acquire()

    try:
        with (
            mock.patch.object(
                room_views,
                "ROOM_UPLOAD_LOCK_TIMEOUT_SECONDS",
                0.01,
            ),
            raises_httpexc(
                code=503,
                match=loggers.UPLOADS_ROOM_BUSY,
                headers={"Retry-After": "5"},
            ),
        ):
            await poster.post(_upload_file())
    finally:
        lock.release()

    assert not poster.room_dir.exists()  # nothing reserved
    poster.the_logger.exception.assert_called_once_with(
        loggers.UPLOADS_ROOM_BUSY,
        room_id=TEST_ROOM_ID,
    )


def _blocking(func, entered, release):
    """Wrap a worker-thread function to report entry, then wait"""

    def wrapper(*args):
        entered.set()
        assert release.wait(5)
        return func(*args)

    return wrapper


@pytest.mark.anyio
async def test_post_uploads_room_copies_outside_lock(uploads_path):
    # While A's copy is held, B's reservation step runs (the lock is free)
    # and sees A's reservation at full size:  B alone would fit, but the
    # two together do not.

    poster_a = _Poster(uploads_path, len(TEST_CONTENT) * 2 - 1)
    poster_b = _Poster(uploads_path, len(TEST_CONTENT) * 2 - 1)
    entered, release = threading.Event(), threading.Event()
    real_store = room_views._store_room_upload

    async with anyio.create_task_group() as tg:
        with mock.patch.object(
            room_views,
            "_store_room_upload",
            _blocking(real_store, entered, release),
        ):
            tg.start_soon(poster_a.post, _upload_file(filename="a.txt"))
            await anyio.to_thread.run_sync(entered.wait, 5)

        assert not room_views._room_upload_lock(TEST_ROOM_ID).locked()

        with raises_httpexc(
            code=507, match=loggers.UPLOADS_ROOM_QUOTA_EXCEEDED
        ):
            await poster_b.post(_upload_file(filename="b.txt"))

        release.set()

    assert (poster_a.room_dir / "a.txt").read_bytes() == TEST_CONTENT
    assert not (poster_a.room_dir / "b.txt").exists()
    assert poster_a.reservations() == []


@pytest.mark.anyio
async def test_post_uploads_room_copies_in_parallel(uploads_path):
    # Two uploads which both fit are both copying at once.

    poster = _Poster(uploads_path, 1000)
    barrier = threading.Barrier(2, timeout=5)
    real_store = room_views._store_room_upload

    def store_at_barrier(*args):
        barrier.wait()  # breaks, raising, unless both copies run at once
        return real_store(*args)

    with mock.patch.object(
        room_views,
        "_store_room_upload",
        store_at_barrier,
    ):
        async with anyio.create_task_group() as tg:
            tg.start_soon(poster.post, _upload_file(filename="a.txt"))
            tg.start_soon(poster.post, _upload_file(filename="b.txt"))

    assert sorted(p.name for p in poster.room_dir.iterdir()) == [
        "a.txt",
        "b.txt",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_step", ["_reserve_room_upload", "_store_room_upload"]
)
async def test_post_uploads_room_cancelled(uploads_path, w_step):
    # Cancelled while either step's thread is running:  the thread is not
    # abandoned, the lock is held until the reserve thread returns, and no
    # reservation is left behind either way.

    poster = _Poster(uploads_path)
    entered, release = threading.Event(), threading.Event()
    real_func = getattr(room_views, w_step)

    with mock.patch.object(
        room_views,
        w_step,
        _blocking(real_func, entered, release),
    ):
        async with anyio.create_task_group() as tg:
            tg.start_soon(poster.post, _upload_file())
            await anyio.to_thread.run_sync(entered.wait, 5)
            tg.cancel_scope.cancel()

            if w_step == "_reserve_room_upload":
                # Still held:  the reserve thread has not returned.
                assert room_views._room_upload_lock(TEST_ROOM_ID).locked()

            release.set()

    assert poster.reservations() == []
    assert not room_views._room_upload_lock(TEST_ROOM_ID).locked()
    target = poster.room_dir / TEST_FILENAME

    if w_step == "_store_room_upload":
        # The copy ran to completion:  the file landed, and is audited.
        assert target.read_bytes() == TEST_CONTENT
        poster.the_audit.room_upload_added.assert_called_once()
    else:
        # Cancelled before the store step:  nothing landed.
        assert not target.exists()
        poster.the_audit.room_upload_added.assert_not_called()


@pytest.mark.anyio
async def test_room_upload_lock_table_is_weak(uploads_path):
    poster = _Poster(uploads_path)

    await poster.post(_upload_file())

    assert TEST_ROOM_ID not in room_views._ROOM_UPLOAD_LOCKS


def test__upload_io_limiter_is_shared():
    first = room_views._upload_io_limiter()

    assert room_views._upload_io_limiter() is first
    assert first.total_tokens == room_views.UPLOAD_IO_THREADS


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_quota, w_files, exp_total, exp_available",
    [
        (None, {}, 0, None),
        (100, {"a.txt": b"abc"}, 3, 97),
        (100, {"a.txt": b"abc", ".nfs01": b"xy"}, 5, 95),
        (2, {"a.txt": b"abc"}, 3, 0),  # over quota
        (
            100,
            {f"{util.UPLOAD_RESERVATION_PREFIX}x": b"0123456789"},
            10,
            90,
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_w_quota(
    cuir,
    uploads_path,
    w_quota,
    w_files,
    exp_total,
    exp_available,
):
    room_dir = uploads_path / "rooms" / TEST_ROOM_ID
    room_dir.mkdir(parents=True)

    for name, content in w_files.items():
        (room_dir / name).write_bytes(content)

    cuir.return_value = _room_config_w_quota(w_quota)
    request = mock.create_autospec(fastapi.Request)
    request.url_for.return_value = f"{URL_PREFIX}/file"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")

    found = await room_views.get_uploads_room(
        request=request,
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
        the_user_claims=THE_USER_CLAIMS,
        the_logger=mock.create_autospec(loggers.LogWrapper),
    )

    assert found.total_size_bytes == exp_total
    assert found.quota_bytes == w_quota
    assert found.available_bytes == exp_available
    assert [f_up.filename for f_up in found.uploads] == [
        name for name in w_files if not util.is_internal_upload_name(name)
    ]


@pytest.mark.anyio
@mock.patch("soliplex.util.scan_uploads")
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_w_scan_failure(
    cuir, scan_uploads, uploads_path
):
    scan_uploads.side_effect = OSError("EIO")
    cuir.return_value = _room_config_w_quota(None)
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with raises_httpexc(
        code=503,
        match=loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        headers={"Retry-After": "5"},
    ):
        await room_views.get_uploads_room(
            request=mock.create_autospec(fastapi.Request),
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    the_logger.exception.assert_called_once_with(
        loggers.UPLOADS_ROOM_STORAGE_UNAVAILABLE,
        room_id=TEST_ROOM_ID,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename",
    [f"{util.UPLOAD_RESERVATION_PREFIX}abc", ".nfs0001"],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_filename_w_internal_name(
    cuir,
    uploads_path,
    w_filename,
):
    room_dir = uploads_path / "rooms" / TEST_ROOM_ID
    room_dir.mkdir(parents=True)
    (room_dir / w_filename).write_bytes(b"internal")
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")

    with raises_httpexc(code=404, match="No room upload"):
        await room_views.get_uploads_room_filename(
            room_id=TEST_ROOM_ID,
            filename=w_filename,
            the_installation=the_installation,
            the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
            the_user_claims=THE_USER_CLAIMS,
            the_logger=mock.create_autospec(loggers.LogWrapper),
        )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename",
    [f"{util.UPLOAD_RESERVATION_PREFIX}abc", ".nfs0001"],
)
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_delete_uploads_room_w_internal_name(
    hwatr,
    uploads_path,
    w_filename,
):
    hwatr.return_value = True
    room_dir = uploads_path / "rooms" / TEST_ROOM_ID
    room_dir.mkdir(parents=True)
    internal = room_dir / w_filename
    internal.write_bytes(b"internal")
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")
    the_audit = mock.create_autospec(loggers.RoomUploadAuditLog)

    with raises_httpexc(code=404, match="No room upload"):
        await room_views.delete_uploads_room(
            room_id=TEST_ROOM_ID,
            filename=w_filename,
            the_installation=the_installation,
            the_admin_users=mock.create_autospec(authz.AdminUserPolicy),
            the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
            the_user_claims=THE_USER_CLAIMS,
            the_logger=mock.create_autospec(loggers.LogWrapper),
            the_authz_logger=mock.create_autospec(loggers.LogWrapper),
            the_audit=the_audit,
        )

    assert internal.exists()
    the_audit.room_upload_deleted.assert_not_called()
