import contextlib
import io
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
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


@pytest.fixture
def uploads_path(temp_dir):
    result = temp_dir / "uploads"
    result.mkdir()
    return result


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

    if w_room_path:
        room_path.mkdir(parents=True)
        (room_path / "ignore_me").mkdir()
        for filename in w_filenames:
            file_path = room_path / filename
            file_path.write_text(f"filename: {filename}")
            exp_filename_urls[filename] = download_url(
                ROUTE_NAME, TEST_ROOM_ID, filename
            )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
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
        else:
            assert found.uploads == []

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM,
    )


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
    "w_admin_access, w_allow_write, w_upload_path, expectation",
    [
        pytest.param(
            False,
            False,
            True,
            raises_httpexc(
                code=403,
                match=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
            ),
            id="noperm",
        ),
        pytest.param(True, False, True, no_error(204), id="admin_ok"),
        pytest.param(False, True, True, no_error(204), id="write_ok"),
        pytest.param(
            False,
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
async def test_post_uploads_room(
    uploads_path,
    w_admin_access,
    w_allow_write,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
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
    the_admin_users.check_admin_access.return_value = w_admin_access
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = w_allow_write
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

        if not w_admin_access and not w_allow_write:
            # Denied by the permission gate, which precedes the lookup.
            the_installation.get_room_config.assert_not_called()

    if w_admin_access:
        # The gate is not even consulted for admins.
        the_room_authz.check_room_access.assert_not_called()
    else:
        the_room_authz.check_room_access.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            user_token=THE_USER_CLAIMS,
            permission=authz.Permission.WRITE,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )


@pytest.mark.anyio
async def test_post_uploads_room_unknown_room(
    uploads_path,
):
    # Admins bypass the room 'WRITE' gate entirely;  an admin attempting
    # to upload into a room which is not (or no longer) configured gets
    # a 404 from the room config lookup.
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
    # The gate is not even consulted for admins;  the denied 'WRITE'
    # check would not have covered a missing room config, either way.
    the_room_authz.check_room_access.assert_not_called()
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
    "w_admin_access, w_allow_write, w_upload_path, expectation",
    [
        pytest.param(
            False,
            False,
            True,
            raises_httpexc(
                code=403,
                match=loggers.AUTHZ_ROOM_ALLOW_WRITE_REQUIRED,
            ),
            id="noperm",
        ),
        pytest.param(True, False, True, no_error(204), id="admin_ok"),
        pytest.param(False, True, True, no_error(204), id="write_ok"),
        pytest.param(
            False,
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
async def test_delete_uploads_room(
    uploads_path,
    w_admin_access,
    w_allow_write,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    room_config = mock.create_autospec(config_rooms.RoomConfig)

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
    the_admin_users.check_admin_access.return_value = w_admin_access
    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_room_authz.check_room_access.return_value = w_allow_write
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

        if not w_admin_access and not w_allow_write:
            # Denied by the permission gate, which precedes the lookup.
            the_installation.get_room_config.assert_not_called()

    if w_admin_access:
        # The gate is not even consulted for admins.
        the_room_authz.check_room_access.assert_not_called()
    else:
        the_room_authz.check_room_access.assert_called_once_with(
            room_id=TEST_ROOM_ID,
            user_token=THE_USER_CLAIMS,
            permission=authz.Permission.WRITE,
        )

    the_authz_logger.debug.assert_called_once_with(
        loggers.UPLOADS_DELETE_ROOM_FILE,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_DELETE_ROOM_FILE,
    )


@pytest.mark.anyio
async def test_delete_uploads_room_unknown_room(
    uploads_path,
):
    # Admins bypass the room 'WRITE' gate entirely;  an admin attempting
    # to upload into a room which is not (or no longer) configured gets
    # a 404 from the room config lookup.
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
    # The gate is not even consulted for admins;  the denied 'WRITE'
    # check would not have covered a missing room config, either way.
    the_room_authz.check_room_access.assert_not_called()
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
