import contextlib
import io
import uuid
from unittest import mock

import fastapi
import pytest

from soliplex import agui
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import rooms as config_rooms
from soliplex.views import thread_file_uploads as thread_views

USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

TEST_ROOM_ID = "test-room-id"
TEST_THREAD_ID = uuid.uuid4()
TEST_THREAD_ID_STR = str(TEST_THREAD_ID)
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
def the_threads():
    return mock.create_autospec(agui.ThreadStorage)


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
    "w_upload_path, w_thread_path, expectation",
    [
        (True, True, no_error(None)),
        (True, False, no_error(None)),
        (
            False,
            None,
            raises_httpexc(code=404, match="Thread uploads not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_thread_ownership")
async def test_get_uploads_room_id_thread_thread_id_only(
    cto,
    the_threads,
    uploads_path,
    w_upload_path,
    w_thread_path,
    expectation,
    w_filenames,
):
    thread_uploads_path = uploads_path / "threads"
    thread_path = thread_uploads_path / TEST_THREAD_ID_STR
    # Note: this is the name of the view function, and not the path
    #       to which it is bound.
    ROUTE_NAME = "get_uploads_room_id_thread_thread_id_filename"

    def download_url(name, room_id, thread_id, filename):
        assert name == ROUTE_NAME
        return f"{URL_PREFIX}/v1/uploads/{room_id}/{thread_id}/{filename}"

    exp_filename_urls = {}

    if w_thread_path:
        thread_path.mkdir(parents=True)
        (thread_path / "ignore_me").mkdir()
        for filename in w_filenames:
            file_path = thread_path / filename
            file_path.write_text(f"filename: {filename}")
            exp_filename_urls[filename] = download_url(
                ROUTE_NAME, TEST_ROOM_ID, TEST_THREAD_ID_STR, filename
            )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cto.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.threads_upload_path = str(thread_uploads_path)
    else:
        the_installation.threads_upload_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await thread_views.get_uploads_room_id_thread_thread_id(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            the_installation=the_installation,
            the_threads=the_threads,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert isinstance(found, models.ThreadUploads)
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == TEST_THREAD_ID_STR

        if w_thread_path:
            found_files = {f_up.filename: f_up.url for f_up in found.uploads}
            assert set(found_files) == set(w_filenames)

            for filename in w_filenames:
                exp_url = exp_filename_urls[filename]
                assert str(found_files[filename]) == exp_url
        else:
            assert found.uploads == []

    cto.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        the_installation=the_installation,
        the_threads=the_threads,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM_THREAD,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_path, w_thread_path, w_filename, expectation",
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
            raises_httpexc(code=404, match="Thread uploads not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_thread_ownership")
async def test_get_uploads_room_id_thread_thread_id_filename(
    cto,
    the_threads,
    uploads_path,
    w_upload_path,
    w_thread_path,
    w_filename,
    expectation,
):
    thread_uploads_path = uploads_path / "threads"
    thread_path = thread_uploads_path / TEST_THREAD_ID_STR

    if w_thread_path:
        thread_path.mkdir(parents=True)

        if w_filename:
            file_path = thread_path / TEST_FILENAME
            file_path.write_text(f"filename: {TEST_FILENAME}")

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cto.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.threads_upload_path = str(thread_uploads_path)
    else:
        the_installation.threads_upload_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    t_views = thread_views

    with expectation as expected:
        found = await t_views.get_uploads_room_id_thread_thread_id_filename(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_threads=the_threads,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found == str(file_path)

    cto.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        the_installation=the_installation,
        the_threads=the_threads,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM_THREAD_FILE,
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
    "w_sandbox, w_upload_path, expectation",
    [
        (
            False,
            True,
            raises_httpexc(
                code=405,
                match="Sandbox not configured",
                headers={"Allow": "GET"},
            ),
        ),
        (
            True,
            False,
            raises_httpexc(
                code=405,
                match="Thread uploads not configured",
                headers={"Allow": "GET"},
            ),
        ),
        (True, True, no_error(204)),
    ],
)
@mock.patch("soliplex.views.agui._check_thread_ownership")
async def test_post_uploads_room_id_thread_thread_id(
    cto,
    uploads_path,
    the_threads,
    w_sandbox,
    w_upload_path,
    expectation,
    w_filename,
    exp_filename,
):
    room_config = mock.create_autospec(
        config_rooms.RoomConfig,
        has_sandbox=w_sandbox,
    )
    cto.return_value = room_config

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

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        response = await thread_views.post_uploads_room_id_thread_thread_id(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            upload_file=upload_file,
            the_installation=the_installation,
            the_threads=the_threads,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert response.status_code == expected
        exp_file = uploads_path / "threads" / TEST_THREAD_ID_STR / exp_filename
        assert exp_file.read_bytes() == TEST_CONTENT

    cto.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        the_installation=the_installation,
        the_threads=the_threads,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM_THREAD,
    )
