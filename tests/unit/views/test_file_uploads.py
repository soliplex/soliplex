import contextlib
import io
import uuid
from unittest import mock

import fastapi
import pytest

from soliplex import agui as agui_package
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import rooms as config_rooms
from soliplex.views import file_uploads as file_uploads_views

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

TEST_ROOM_ID = "test-room-id"
TEST_THREAD_ID = uuid.uuid4()
TEST_RUN_ID = uuid.uuid4()
TEST_FILENAME = "test_file.txt"
TEST_CONTENT = b"DEADBEEF"

URL_PREFIX = "http://test.example.com/api"

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


@pytest.fixture
def sandbox_path(temp_dir):
    result = temp_dir / "sandbox"
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

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_uploads_room(
            request=request,
            room_id=TEST_ROOM_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
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

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_uploads_room_filename(
            room_id=TEST_ROOM_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found == str(file_path)

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_GET_ROOM_FILE,
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
    uploads_path,
    w_admin_access,
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
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_thread_only(
    cuir,
    uploads_path,
    w_upload_path,
    w_thread_path,
    expectation,
    w_filenames,
):
    thread_uploads_path = uploads_path / "threads"
    thread_path = thread_uploads_path / str(TEST_THREAD_ID)
    # Note: this is the name of the view function, and not the path
    #       to which it is bound.
    ROUTE_NAME = "get_uploads_room_thread_filename"

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
                ROUTE_NAME, TEST_ROOM_ID, str(TEST_THREAD_ID), filename
            )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.threads_upload_path = str(thread_uploads_path)
    else:
        the_installation.threads_upload_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_uploads_room_thread(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert isinstance(found, models.ThreadUploads)
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == str(TEST_THREAD_ID)

        if w_thread_path:
            found_files = {f_up.filename: f_up.url for f_up in found.uploads}
            assert set(found_files) == set(w_filenames)

            for filename in w_filenames:
                exp_url = exp_filename_urls[filename]
                assert str(found_files[filename]) == exp_url
        else:
            assert found.uploads == []

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
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_thread_filename(
    cuir,
    uploads_path,
    w_upload_path,
    w_thread_path,
    w_filename,
    expectation,
):
    thread_uploads_path = uploads_path / "threads"
    thread_path = thread_uploads_path / str(TEST_THREAD_ID)

    if w_thread_path:
        thread_path.mkdir(parents=True)

        if w_filename:
            file_path = thread_path / TEST_FILENAME
            file_path.write_text(f"filename: {TEST_FILENAME}")

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_upload_path:
        the_installation.threads_upload_path = str(thread_uploads_path)
    else:
        the_installation.threads_upload_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_uploads_room_thread_filename(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found == str(file_path)

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
    "tsgt_side_effect, w_upload_path, expectation",
    [
        (None, True, no_error(204)),
        (
            agui_package.UnknownThread(USER_NAME, str(TEST_THREAD_ID)),
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
        exp_file = (
            uploads_path / "threads" / str(TEST_THREAD_ID) / exp_filename
        )
        assert exp_file.read_bytes() == TEST_CONTENT

    the_threads.get_thread.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=str(TEST_THREAD_ID),
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM_THREAD,
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
    "w_sandbox_path, w_workdir_path, expectation",
    [
        (True, True, no_error(None)),
        (True, False, no_error(None)),
        (
            False,
            None,
            raises_httpexc(code=404, match="Sandbox workdirs not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_workdirs_room_thread_run_only(
    cuir,
    sandbox_path,
    w_sandbox_path,
    w_workdir_path,
    expectation,
    w_filenames,
):
    sandbox_workdirs_path = sandbox_path / "workdirs"
    run_path = (
        sandbox_workdirs_path
        / TEST_ROOM_ID
        / str(TEST_THREAD_ID)
        / str(TEST_RUN_ID)
    )

    # Note: this is the name of the view function, and not the path
    #       to which it is bound.
    ROUTE_NAME = "get_workdirs_room_thread_run_filename"

    def download_url(name, room_id, thread_id, run_id, filename):
        assert name == ROUTE_NAME
        return (
            f"{URL_PREFIX}/v1/workdir/{room_id}"
            f"/{thread_id}/{run_id}/{filename}"
        )

    exp_filename_urls = {}

    if w_workdir_path:
        run_path.mkdir(parents=True)
        (run_path / "ignore_me").mkdir()
        for filename in w_filenames:
            file_path = run_path / filename
            file_path.write_text(f"filename: {filename}")
            exp_filename_urls[filename] = download_url(
                ROUTE_NAME,
                TEST_ROOM_ID,
                str(TEST_THREAD_ID),
                str(TEST_RUN_ID),
                filename,
            )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_sandbox_path:
        the_installation.sandbox_workdirs_path = str(sandbox_workdirs_path)
    else:
        the_installation.sandbox_workdirs_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_workdirs_room_thread_run(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert isinstance(found, models.RunWorkdirFiles)
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == str(TEST_THREAD_ID)
        assert found.run_id == str(TEST_RUN_ID)

        if w_workdir_path:
            found_files = {f_up.filename: f_up.url for f_up in found.files}
            assert set(found_files) == set(w_filenames)

            for filename in w_filenames:
                exp_url = exp_filename_urls[filename]
                assert str(found_files[filename]) == exp_url
        else:
            assert found.files == []

    the_logger.debug.assert_called_once_with(
        loggers.WORKDIRS_GET_ROOM_THREAD_RUN,
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_sandbox_path, w_workdir_path, w_filename, expectation",
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
            raises_httpexc(code=404, match="Sandbox workdirs not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_workdirs_room_thread_run_filename(
    cuir,
    sandbox_path,
    w_sandbox_path,
    w_workdir_path,
    w_filename,
    expectation,
):
    sandbox_workdirs_path = sandbox_path / "workdirs"
    workdir_path = (
        sandbox_workdirs_path
        / TEST_ROOM_ID
        / str(TEST_THREAD_ID)
        / str(TEST_RUN_ID)
    )

    if w_workdir_path:
        workdir_path.mkdir(parents=True)

        if w_filename:
            file_path = workdir_path / TEST_FILENAME
            file_path.write_text(f"filename: {TEST_FILENAME}")

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_sandbox_path:
        the_installation.sandbox_workdirs_path = str(sandbox_workdirs_path)
    else:
        the_installation.sandbox_workdirs_path = None

    the_authz_policy = mock.create_autospec(
        authz_package.AuthorizationPolicy,
    )
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await file_uploads_views.get_workdirs_room_thread_run_filename(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_authz_policy=the_authz_policy,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found == str(file_path)

    the_logger.debug.assert_called_once_with(
        loggers.WORKDIRS_GET_ROOM_THREAD_RUN_FILE,
    )
