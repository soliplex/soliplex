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
def uploads_dir(temp_dir):
    result = temp_dir / "uploads"
    result.mkdir()
    return result


@pytest.mark.anyio
@mock.patch("soliplex.views.agui._check_user_in_room")
@pytest.mark.parametrize(
    "tsgt_side_effect, w_upload_env, expectation",
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
            raises_httpexc(code=404, match="Uploads not configured"),
        ),
    ],
)
async def test_post_room_agui_thread_id_upload(
    cuir,
    uploads_dir,
    the_threads,
    tsgt_side_effect,
    w_upload_env,
    expectation,
):
    room_config = mock.create_autospec(config_rooms.RoomConfig)
    cuir.return_value = room_config
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=TEST_FILENAME,
        headers={"Content-Type": "text/plain"},
    )

    the_installation = mock.create_autospec(
        installation.Installation,
    )

    installation_env = {}
    the_installation.get_environment.side_effect = installation_env.get

    if w_upload_env:
        installation_env["SOLIPLEX_UPLOADS_PATH"] = str(uploads_dir)

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
        exp_file = uploads_dir / TEST_THREAD_ID / TEST_FILENAME
        assert exp_file.read_bytes() == TEST_CONTENT

    the_threads.get_thread.assert_called_once_with(
        user_name=USER_NAME,
        room_id=TEST_ROOM_ID,
        thread_id=TEST_THREAD_ID,
    )

    the_logger.debug.assert_called_once_with(
        loggers.UPLOADS_POST_ROOM_THREAD,
    )
