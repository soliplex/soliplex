"""Room uploads and operator-placed symlinks

Links let an operator share a large dataset between rooms.  They use no
upload storage, so the quota does not count them;  and an upload under a
link's name replaces the link itself, never writing through it.
"""

from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from tests import _platform
from tests.unit.views import test_room_file_uploads as test_uploads

pytestmark = _platform.requires_posix_symlinks

TEST_ROOM_ID = test_uploads.TEST_ROOM_ID
TEST_CONTENT = test_uploads.TEST_CONTENT
SHARED_CONTENT = b"a large shared dataset" * 100

fresh_upload_sync = test_uploads.fresh_upload_sync
uploads_path = test_uploads.uploads_path


@pytest.fixture
def shared_dataset(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_bytes(SHARED_CONTENT)
    return shared


@pytest.mark.anyio
@mock.patch("soliplex.views.agui._check_user_in_room")
async def test_get_uploads_room_lists_but_does_not_count_link(
    cuir,
    uploads_path,
    shared_dataset,
):
    room_dir = uploads_path / "rooms" / TEST_ROOM_ID
    room_dir.mkdir(parents=True)
    (room_dir / "real.txt").write_bytes(b"abc")
    (room_dir / "linked.dat").symlink_to(shared_dataset)
    cuir.return_value = test_uploads._room_config_w_quota(100)
    request = mock.create_autospec(fastapi.Request)
    request.url_for.return_value = f"{test_uploads.URL_PREFIX}/file"
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.rooms_upload_path = str(uploads_path / "rooms")

    found = await test_uploads.room_views.get_uploads_room(
        request=request,
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
        the_user_claims=test_uploads.THE_USER_CLAIMS,
        the_logger=mock.create_autospec(loggers.LogWrapper),
    )

    sizes = {f_up.filename: f_up.size_bytes for f_up in found.uploads}
    assert sizes == {"real.txt": 3, "linked.dat": len(SHARED_CONTENT)}
    assert found.total_size_bytes == 3
    assert found.available_bytes == 97


@pytest.mark.anyio
async def test_post_uploads_room_link_uses_no_quota(
    uploads_path,
    shared_dataset,
):
    poster = test_uploads._Poster(uploads_path, len(TEST_CONTENT))
    poster.room_dir.mkdir(parents=True)
    (poster.room_dir / "linked.dat").symlink_to(shared_dataset)

    response = await poster.post(test_uploads._upload_file())

    assert response.status_code == 204


@pytest.mark.anyio
async def test_post_uploads_room_replaces_link_not_target(
    uploads_path,
    shared_dataset,
):
    # Replacing a link credits nothing (it stored nothing), and swaps the
    # link itself:  the shared target is untouched.
    poster = test_uploads._Poster(uploads_path, len(TEST_CONTENT))
    poster.room_dir.mkdir(parents=True)
    link = poster.room_dir / test_uploads.TEST_FILENAME
    link.symlink_to(shared_dataset)

    response = await poster.post(test_uploads._upload_file())

    assert response.status_code == 204
    assert not link.is_symlink()
    assert link.read_bytes() == TEST_CONTENT
    assert shared_dataset.read_bytes() == SHARED_CONTENT
