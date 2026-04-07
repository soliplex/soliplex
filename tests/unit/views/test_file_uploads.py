import contextlib
import io
from unittest import mock

import fastapi
import pytest

from soliplex import agui as agui_package
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex.config import rooms as config_rooms
from soliplex.views import file_uploads as file_uploads_views

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

TEST_ROOM_ID = "test-room-id"
TEST_THREAD_ID = "test-thread-id"
TEST_FILENAME = "test_file.txt"
TEST_CONTENT = b"DEADBEEF"


no_error = contextlib.nullcontext


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.fixture
def the_threads():
    return mock.create_autospec(agui_package.ThreadStorage)


@pytest.fixture
def uploads_path(temp_dir):
    result = temp_dir / "uploads"
    result.mkdir()
    return result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename, exp_filename",
    [
        (TEST_FILENAME, TEST_FILENAME),
        ("../../../../etc/passwd", "passwd"),
    ],
)
@pytest.mark.parametrize(
    "w_upload_path, expectation",
    [
        (True, no_error(204)),
        (False, raises_httpexc(code=404, match="Room uploads not configured")),
    ],
)
@pytest.mark.parametrize("w_admin_access", [False, True])
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_uploads_room(
    cuir,
    w_admin_access,
    uploads_path,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=w_filename,
        headers={"Content-Type": "text/plain"},
    )

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.rooms_upload_path = str(uploads_path / "rooms")
    else:
        the_installation.rooms_upload_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_authz_policy.check_admin_access.return_value = w_admin_access
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_authz_logger = mock.create_autospec(loggers.LogWrapper)

    if not w_admin_access:
        with pytest.raises(fastapi.HTTPException) as exc:
            await file_uploads_views.post_uploads_room(
                room_id=TEST_ROOM_ID,
                upload_file=upload_file,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
                the_authz_logger=the_authz_logger,
            )

        assert exc.value.status_code == 403
        assert exc.value.detail == loggers.AUTHZ_ADMIN_ACCESS_REQUIRED

        the_authz_logger.error.assert_called_once_with(
            loggers.AUTHZ_ADMIN_ACCESS_REQUIRED
        )

    else:
        with expectation as expected:
            response = await file_uploads_views.post_uploads_room(
                room_id=TEST_ROOM_ID,
                upload_file=upload_file,
                the_installation=the_installation,
                the_authz_policy=the_authz_policy,
                the_user_claims=THE_USER_CLAIMS,
                the_logger=the_logger,
                the_authz_logger=the_authz_logger,
            )

        if not isinstance(expected, pytest.ExceptionInfo):
            assert response.status_code == expected
            exp_file = uploads_path / "rooms" / TEST_ROOM_ID / exp_filename
            assert exp_file.read_bytes() == TEST_CONTENT

    the_authz_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filename, exp_filename",
    [
        (TEST_FILENAME, TEST_FILENAME),
        ("../../../../etc/passwd", "passwd"),
    ],
)
@pytest.mark.parametrize(
    "tsgt_side_effect, w_upload_path, expectation",
    [
        (None, True, no_error(204)),
        (
            agui_package.UnknownThread(USER_NAME, TEST_THREAD_ID),
            True,
            raises_httpexc(code=404, match="Unknown thread"),
        ),
        (
            None,
            False,
            raises_httpexc(code=404, match="Thread uploads not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_post_uploads_room_thread(
    cuir,
    uploads_path,
    the_threads,
    tsgt_side_effect,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=w_filename,
        headers={"Content-Type": "text/plain"},
    )

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.threads_upload_path = str(uploads_path / "threads")
    else:
        the_installation.threads_upload_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)
    the_threads.get_thread.side_effect = tsgt_side_effect

    with expectation as expected:
        response = await file_uploads_views.post_uploads_room_thread(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            upload_file=upload_file,
            the_installation=the_installation,
            the_threads=the_threads,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert response.status_code == expected
        exp_file = uploads_path / "threads" / TEST_THREAD_ID / exp_filename
        assert exp_file.read_bytes() == TEST_CONTENT

    the_threads.get_thread.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM_THREAD,
    )
