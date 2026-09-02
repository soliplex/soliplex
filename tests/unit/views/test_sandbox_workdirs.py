import contextlib
import os
import pathlib
import uuid
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import rooms as config_rooms
from soliplex.views import sandbox_workdirs as workdir_views

USER_NAME = "phreddy"
EMAIL = "phreddy@example.com"

THE_USER_CLAIMS = {"preferred_username": USER_NAME, "email": EMAIL}

TEST_ROOM_ID = "test-room-id"
TEST_THREAD_ID = uuid.uuid4()
TEST_THREAD_ID_STR = str(TEST_THREAD_ID)
TEST_RUN_ID = uuid.uuid4()
TEST_RUN_ID_STR = str(TEST_RUN_ID)
TEST_FILENAME = "test_file.txt"

URL_PREFIX = "http://test.example.com/api"

no_error = contextlib.nullcontext


def raises_httpexc(*, match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.fixture
def sandbox_path(temp_dir):
    result = temp_dir / "sandbox"
    result.mkdir()
    return result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_filenames, w_link",
    [
        ([], None),
        (["foo.txt"], None),
        ([f"file_{i_file:03}.txt" for i_file in range(10)], None),
        (["sneaky.txt"], "symlink"),
        (["hard.txt"], "hardlink"),
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
@mock.patch("soliplex.views.agui._check_thread_ownership")
async def test_get_workdirs_room_thread_run_only(
    cto,
    the_threads,
    sandbox_path,
    w_sandbox_path,
    w_workdir_path,
    expectation,
    w_filenames,
    w_link,
):
    sandbox_workdirs_path = sandbox_path / "workdirs"
    run_path = (
        sandbox_workdirs_path
        / TEST_ROOM_ID
        / TEST_THREAD_ID_STR
        / TEST_RUN_ID_STR
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
        link_target = sandbox_path / "link-target"
        link_target.write_text("sneaky link points here")
        (run_path / "ignore_me").mkdir()
        for filename in w_filenames:
            file_path = run_path / filename
            if w_link == "symlink":
                file_path.symlink_to(link_target)
            elif w_link == "hardlink":
                file_path.hardlink_to(link_target)
                exp_filename_urls[filename] = download_url(
                    ROUTE_NAME,
                    TEST_ROOM_ID,
                    TEST_THREAD_ID_STR,
                    TEST_RUN_ID_STR,
                    filename,
                )
            else:
                file_path.write_text(f"filename: {filename}")
                exp_filename_urls[filename] = download_url(
                    ROUTE_NAME,
                    TEST_ROOM_ID,
                    TEST_THREAD_ID_STR,
                    TEST_RUN_ID_STR,
                    filename,
                )

    request = mock.create_autospec(fastapi.Request)
    request.url_for.side_effect = download_url

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cto.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_sandbox_path:
        the_installation.sandbox_workdirs_path = str(sandbox_workdirs_path)
    else:
        the_installation.sandbox_workdirs_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await workdir_views.get_workdirs_room_thread_run(
            request=request,
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID_STR,
            run_id=TEST_RUN_ID_STR,
            the_installation=the_installation,
            the_threads=the_threads,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert isinstance(found, models.RunWorkdirFiles)
        assert found.room_id == TEST_ROOM_ID
        assert found.thread_id == TEST_THREAD_ID_STR
        assert found.run_id == TEST_RUN_ID_STR

        if w_workdir_path:
            found_files = {f_up.filename: f_up.url for f_up in found.files}

            if w_link == "symlink":
                assert not found_files
            else:
                assert set(found_files) == set(w_filenames)
                for filename in w_filenames:
                    exp_url = exp_filename_urls[filename]
                    assert str(found_files[filename]) == exp_url
        else:
            assert found.files == []

    cto.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        run_id=TEST_RUN_ID_STR,
        the_installation=the_installation,
        the_threads=the_threads,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.WORKDIRS_GET_ROOM_THREAD_RUN,
    )


not_a_workdir_file = raises_httpexc(
    code=404,
    match=f"No workdir file: {TEST_FILENAME}",
)


@pytest.mark.parametrize(
    "w_workdir_path, w_filename, w_link, expectation",
    [
        # The open itself fails: 'O_NOFOLLOW' rejects the final component.
        (True, True, "symlink", not_a_workdir_file),
        # The open succeeds, but 'fstat' reports a non-regular file.
        (True, True, "dir", not_a_workdir_file),
        # 'O_NONBLOCK' keeps this from hanging until a writer appears.
        (True, True, "fifo", not_a_workdir_file),
        (True, False, None, not_a_workdir_file),
        (False, None, None, not_a_workdir_file),
        # A hard link is a regular file, and cannot escape the workdir:
        # each bwrap bind is its own mount, so 'link' fails 'EXDEV' across
        # them. It is therefore served like any other file.
        (True, True, "hardlink", no_error(None)),
        (True, True, None, no_error(None)),
    ],
)
def test__open_no_symlinks(
    sandbox_path,
    w_workdir_path,
    w_filename,
    w_link,
    expectation,
):
    workdir_path = sandbox_path / "workdir"
    file_path = workdir_path / TEST_FILENAME

    if w_workdir_path:
        workdir_path.mkdir()
        link_target = sandbox_path / "link-target"
        link_target.write_text("sneaky link points here")

        if w_filename:
            if w_link == "symlink":
                file_path.symlink_to(link_target)
            elif w_link == "hardlink":
                file_path.hardlink_to(link_target)
            elif w_link == "dir":
                file_path.mkdir()
            elif w_link == "fifo":
                os.mkfifo(file_path)
            else:
                file_path.write_text(f"filename: {TEST_FILENAME}")

    with expectation as expected:
        found = workdir_views._open_no_symlinks(file_path)

    if expected is None:
        streamer, size = found

        assert size == file_path.stat().st_size
        assert b"".join(streamer()) == file_path.read_bytes()


@pytest.mark.parametrize(
    "w_name, expected",
    [
        ("report.txt", "report.txt"),
        ('a"b.txt', "a%22b.txt"),
        ("a\r\nX-Injected: yes", "a%0D%0AX-Injected%3A%20yes"),
        ("r\u00e9sum\u00e9.pdf", "r%C3%A9sum%C3%A9.pdf"),
        ("/var/soliplex/workdirs/chat/uuid/uuid/report.txt", "report.txt"),
    ],
)
def test__disposition(w_name, expected):
    found = workdir_views._disposition(pathlib.Path(w_name))

    assert found == workdir_views.ATTACHMENT_PREFIX + expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_sandbox_path, expectation",
    [
        (True, no_error(None)),
        (
            False,
            raises_httpexc(code=404, match="Sandbox workdirs not configured"),
        ),
    ],
)
@mock.patch("soliplex.views.sandbox_workdirs._disposition")
@mock.patch("soliplex.views.sandbox_workdirs._open_no_symlinks")
@mock.patch("soliplex.views.agui._check_thread_ownership")
@mock.patch("fastapi.responses.StreamingResponse")
async def test_get_workdirs_room_thread_run_filename(
    frsr,
    cto,
    open_no_symlinks,
    disposition,
    the_threads,
    sandbox_path,
    w_sandbox_path,
    expectation,
):
    file_size = 2**17
    streamer = mock.MagicMock(name="streamer")
    open_no_symlinks.return_value = (streamer, file_size)

    sandbox_workdirs_path = sandbox_path / "workdirs"
    workdir_path = (
        sandbox_workdirs_path
        / TEST_ROOM_ID
        / TEST_THREAD_ID_STR
        / TEST_RUN_ID_STR
    )

    workdir_path.mkdir(parents=True)
    file_path = workdir_path / TEST_FILENAME
    file_path.write_text(f"filename: {TEST_FILENAME}")

    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cto.return_value = room_config

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    if w_sandbox_path:
        the_installation.sandbox_workdirs_path = str(sandbox_workdirs_path)
    else:
        the_installation.sandbox_workdirs_path = None

    the_room_authz = mock.create_autospec(authz.RoomAuthorizationPolicy)
    the_logger = mock.create_autospec(loggers.LogWrapper)

    with expectation as expected:
        found = await workdir_views.get_workdirs_room_thread_run_filename(
            room_id=TEST_ROOM_ID,
            thread_id=TEST_THREAD_ID,
            run_id=TEST_RUN_ID,
            filename=TEST_FILENAME,
            the_installation=the_installation,
            the_threads=the_threads,
            the_room_authz=the_room_authz,
            the_user_claims=THE_USER_CLAIMS,
            the_logger=the_logger,
        )

    if expected is None:
        assert found is frsr.return_value

        frsr.assert_called_once_with(
            streamer.return_value,
            media_type="application/octet-stream",
            headers={
                "content-length": str(file_size),
                "content-disposition": disposition.return_value,
                "x-content-type-options": "nosniff",
            },
        )
        disposition.assert_called_once_with(file_path)
        open_no_symlinks.assert_called_once_with(file_path)

    cto.assert_awaited_once_with(
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID_STR,
        run_id=TEST_RUN_ID_STR,
        the_installation=the_installation,
        the_threads=the_threads,
        the_room_authz=the_room_authz,
        the_user_claims=THE_USER_CLAIMS,
        the_logger=the_logger,
    )
    the_logger.debug.assert_called_once_with(
        loggers.WORKDIRS_GET_ROOM_THREAD_RUN_FILE,
    )
