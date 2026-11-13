import contextlib
from unittest import mock

import pydantic_ai
import pytest

from soliplex import agents
from soliplex import installation
from soliplex.tools import file_uploads as file_uploads_tools

TEST_ROOM_ID = "test-room-id"
TEST_THREAD_ID = "test-thread-id"
TEST_FILENAME = "test.txt"
BOGUS_FILENAME = "bogus.txt"
FILE_CONTENT_BYTES = "\u00001234\u0345".encode("utf-16")
FILE_CONTENT_TEXT = "test thread file content"

no_error = contextlib.nullcontext


@pytest.fixture
def the_installation():
    return mock.create_autospec(installation.Installation)


@pytest.fixture
def ctx_w_deps(the_installation):
    ctx = mock.create_autospec(pydantic_ai.RunContext)
    ctx.deps = mock.create_autospec(agents.AgentDependencies)
    ctx.deps.the_installation = the_installation
    ctx.deps.room_id = TEST_ROOM_ID
    ctx.deps.thread_id = TEST_THREAD_ID

    return ctx


@pytest.fixture
def uploads_path(temp_dir):
    result = temp_dir / "uploads"
    return result


@pytest.fixture
def rooms_upload_path(uploads_path):
    result = uploads_path / "rooms"
    return result


@pytest.fixture
def threads_upload_path(uploads_path):
    result = uploads_path / "threads"
    return result


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_env, w_room_files, expectation",
    [
        (True, (), no_error(set())),
        (True, ["foo.txt", "bar.txt"], no_error({"foo.txt", "bar.txt"})),
        (
            True,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotADirectory),
        ),
        (
            False,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotConfigured),
        ),
    ],
)
async def test_list_room_file_uploads(
    the_installation,
    ctx_w_deps,
    rooms_upload_path,
    w_upload_env,
    w_room_files,
    expectation,
):
    """List filenames of files uploaded to this room

    Args:
      room_id (str, required): UUID of the current AGUI room
    """
    if w_upload_env:
        the_installation.rooms_upload_path = rooms_upload_path

        if w_room_files is not None:
            room_dir = rooms_upload_path / TEST_ROOM_ID
            room_dir.mkdir(parents=True)

            for filename in w_room_files:
                room_file = room_dir / filename
                room_file.write_text("")
    else:
        the_installation.rooms_upload_path = None

    with expectation as expected:
        found = await file_uploads_tools.list_room_file_uploads(ctx_w_deps)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert set(found) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_env, w_room_file, w_contents, expectation",
    [
        (
            True,
            TEST_FILENAME,
            FILE_CONTENT_BYTES,
            no_error(FILE_CONTENT_BYTES),
        ),
        (
            True,
            TEST_FILENAME,
            FILE_CONTENT_TEXT,
            no_error(FILE_CONTENT_TEXT),
        ),
        (
            True,
            BOGUS_FILENAME,
            None,
            pytest.raises(file_uploads_tools.UploadNotFound),
        ),
        (
            True,
            None,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotADirectory),
        ),
        (
            False,
            None,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotConfigured),
        ),
    ],
)
async def test_get_room_file_upload(
    the_installation,
    ctx_w_deps,
    rooms_upload_path,
    w_upload_env,
    w_room_file,
    w_contents,
    expectation,
):
    """List filenames of files uploaded to this room

    Args:
      room_id (str, required): UUID of the current AGUI room
    """
    if w_upload_env:
        the_installation.rooms_upload_path = rooms_upload_path

        if w_room_file is not None:
            room_dir = rooms_upload_path / TEST_ROOM_ID
            room_dir.mkdir(parents=True)

            room_file = room_dir / TEST_FILENAME
            if w_contents is not None:
                if isinstance(w_contents, bytes):
                    room_file.write_bytes(w_contents)
                else:
                    room_file.write_text(w_contents)
    else:
        the_installation.rooms_upload_path = None

    with expectation as expected:
        found = await file_uploads_tools.get_room_file_upload(
            ctx_w_deps,
            filename=w_room_file,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_env, w_thread_files, expectation",
    [
        (True, (), no_error(set())),
        (True, ["foo.txt", "bar.txt"], no_error({"foo.txt", "bar.txt"})),
        (
            True,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotADirectory),
        ),
        (
            False,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotConfigured),
        ),
    ],
)
async def test_list_thread_file_uploads(
    the_installation,
    ctx_w_deps,
    threads_upload_path,
    w_upload_env,
    w_thread_files,
    expectation,
):
    """List filenames of files uploaded to this thread

    Args:
      thread_id (str, required): UUID of the current AGUI thread
    """
    if w_upload_env:
        the_installation.threads_upload_path = threads_upload_path

        if w_thread_files is not None:
            thread_dir = threads_upload_path / TEST_THREAD_ID
            thread_dir.mkdir(parents=True)

            for filename in w_thread_files:
                thread_file = thread_dir / filename
                thread_file.write_text("")
    else:
        the_installation.threads_upload_path = None

    with expectation as expected:
        found = await file_uploads_tools.list_thread_file_uploads(ctx_w_deps)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert set(found) == expected


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_upload_env, w_thread_file, w_contents, expectation",
    [
        (
            True,
            TEST_FILENAME,
            FILE_CONTENT_BYTES,
            no_error(FILE_CONTENT_BYTES),
        ),
        (
            True,
            TEST_FILENAME,
            FILE_CONTENT_TEXT,
            no_error(FILE_CONTENT_TEXT),
        ),
        (
            True,
            BOGUS_FILENAME,
            None,
            pytest.raises(file_uploads_tools.UploadNotFound),
        ),
        (
            True,
            None,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotADirectory),
        ),
        (
            False,
            None,
            None,
            pytest.raises(file_uploads_tools.UploadsPathNotConfigured),
        ),
    ],
)
async def test_get_thread_file_upload(
    the_installation,
    ctx_w_deps,
    threads_upload_path,
    w_upload_env,
    w_thread_file,
    w_contents,
    expectation,
):
    """List filenames of files uploaded to this thread

    Args:
      thread_id (str, required): UUID of the current AGUI thread
    """
    if w_upload_env:
        the_installation.threads_upload_path = threads_upload_path

        if w_thread_file is not None:
            thread_dir = threads_upload_path / TEST_THREAD_ID
            thread_dir.mkdir(parents=True)

            thread_file = thread_dir / TEST_FILENAME
            if w_contents is not None:
                if isinstance(w_contents, bytes):
                    thread_file.write_bytes(w_contents)
                else:
                    thread_file.write_text(w_contents)
    else:
        the_installation.threads_upload_path = None

    with expectation as expected:
        found = await file_uploads_tools.get_thread_file_upload(
            ctx_w_deps,
            filename=w_thread_file,
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected


INTERNAL_NAMES = [".soliplex-upload-abc", ".nfs0001"]


@pytest.mark.anyio
@pytest.mark.parametrize("which", ["room", "thread"])
async def test_list_file_uploads_skips_internal_names(
    the_installation,
    ctx_w_deps,
    rooms_upload_path,
    threads_upload_path,
    which,
):
    the_installation.rooms_upload_path = rooms_upload_path
    the_installation.threads_upload_path = threads_upload_path
    upload_dir = (
        rooms_upload_path / TEST_ROOM_ID
        if which == "room"
        else threads_upload_path / TEST_THREAD_ID
    )
    upload_dir.mkdir(parents=True)

    for filename in [TEST_FILENAME, *INTERNAL_NAMES]:
        (upload_dir / filename).write_text("")

    list_tool = getattr(file_uploads_tools, f"list_{which}_file_uploads")
    found = await list_tool(ctx_w_deps)

    assert found == [TEST_FILENAME]


@pytest.mark.anyio
@pytest.mark.parametrize("which", ["room", "thread"])
@pytest.mark.parametrize("filename", INTERNAL_NAMES)
async def test_get_file_upload_refuses_internal_names(
    the_installation,
    ctx_w_deps,
    rooms_upload_path,
    threads_upload_path,
    which,
    filename,
):
    the_installation.rooms_upload_path = rooms_upload_path
    the_installation.threads_upload_path = threads_upload_path
    upload_dir = (
        rooms_upload_path / TEST_ROOM_ID
        if which == "room"
        else threads_upload_path / TEST_THREAD_ID
    )
    upload_dir.mkdir(parents=True)
    (upload_dir / filename).write_text("internal")

    get_tool = getattr(file_uploads_tools, f"get_{which}_file_upload")

    with pytest.raises(file_uploads_tools.UploadNotFound):
        await get_tool(ctx_w_deps, filename)
