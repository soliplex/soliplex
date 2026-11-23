"""Room uploads and operator-placed symlinks

Links let an operator share a large dataset between rooms.  They use no
upload storage, so the quota does not count them;  and an upload under a
link's name replaces the link itself, never writing through it.
"""

import io
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex.views import room_file_uploads as room_views
from tests import _platform
from tests.unit.views import test_room_file_uploads as test_uploads

pytestmark = _platform.requires_posix_symlinks

TEST_ROOM_ID = test_uploads.TEST_ROOM_ID
TEST_FILENAME = test_uploads.TEST_FILENAME
TEST_CONTENT = test_uploads.TEST_CONTENT
SHARED_CONTENT = b"a large shared dataset"

fresh_upload_sync = test_uploads.fresh_upload_sync
uploads_path = test_uploads.uploads_path


@pytest.mark.anyio
@pytest.mark.parametrize("w_dangling", [False, True])
@mock.patch("soliplex.views.room_file_uploads.has_write_access_to_room")
async def test_post_uploads_room_replaces_link_not_target(
    hwatr,
    temp_dir,
    uploads_path,
    w_dangling,
):
    hwatr.return_value = True
    shared = temp_dir / "shared.dat"

    if not w_dangling:
        shared.write_bytes(SHARED_CONTENT)

    room_dir = uploads_path / "rooms" / TEST_ROOM_ID
    room_dir.mkdir(parents=True)
    link = room_dir / TEST_FILENAME
    link.symlink_to(shared)
    upload_file = fastapi.UploadFile(
        file=io.BytesIO(TEST_CONTENT),
        filename=TEST_FILENAME,
        headers={"Content-Type": "text/plain"},
    )
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.get_room_config.return_value = (
        test_uploads._room_config_w_quota(None)
    )
    the_installation.rooms_upload_path = str(uploads_path / "rooms")

    response = await room_views.post_uploads_room(
        room_id=TEST_ROOM_ID,
        upload_file=upload_file,
        the_installation=the_installation,
        the_admin_users=mock.create_autospec(authz.AdminUserPolicy),
        the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
        the_user_claims=test_uploads.THE_USER_CLAIMS,
        the_logger=mock.create_autospec(loggers.LogWrapper),
        the_authz_logger=mock.create_autospec(loggers.LogWrapper),
        the_audit=mock.create_autospec(loggers.RoomUploadAuditLog),
    )

    assert response.status_code == 204
    assert not link.is_symlink()
    assert link.read_bytes() == TEST_CONTENT

    if w_dangling:
        assert not shared.exists()
    else:
        assert shared.read_bytes() == SHARED_CONTENT


@pytest.fixture
def shared_dataset(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_bytes(SHARED_CONTENT * 100)
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

    found = await room_views.get_uploads_room(
        request=request,
        room_id=TEST_ROOM_ID,
        the_installation=the_installation,
        the_room_authz=mock.create_autospec(authz.RoomAuthorizationPolicy),
        the_user_claims=test_uploads.THE_USER_CLAIMS,
        the_logger=mock.create_autospec(loggers.LogWrapper),
    )

    sizes = {f_up.filename: f_up.size_bytes for f_up in found.uploads}
    assert sizes == {
        "real.txt": 3,
        "linked.dat": len(SHARED_CONTENT * 100),
    }
    assert found.total_size_bytes == 3
    assert found.available_bytes == 97


@pytest.mark.anyio
async def test_post_uploads_room_link_uses_no_quota(
    uploads_path,
    shared_dataset,
):
    # Replacing a link credits nothing (it stored nothing), and other
    # links count for nothing.
    poster = test_uploads._Poster(uploads_path, len(TEST_CONTENT))
    poster.room_dir.mkdir(parents=True)
    (poster.room_dir / "linked.dat").symlink_to(shared_dataset)
    link = poster.room_dir / TEST_FILENAME
    link.symlink_to(shared_dataset)

    response = await poster.post(test_uploads._upload_file())

    assert response.status_code == 204
    assert not link.is_symlink()
    assert link.read_bytes() == TEST_CONTENT
