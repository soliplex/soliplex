"""Room uploads and operator-placed symlinks"""

import io
from unittest import mock

import fastapi
import pytest

from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex.config import rooms as config_rooms
from soliplex.views import room_file_uploads as room_views
from tests import _platform
from tests.unit.views import test_room_file_uploads as test_uploads

pytestmark = _platform.requires_posix_symlinks

TEST_ROOM_ID = test_uploads.TEST_ROOM_ID
TEST_FILENAME = test_uploads.TEST_FILENAME
TEST_CONTENT = test_uploads.TEST_CONTENT
SHARED_CONTENT = b"a large shared dataset"

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
    the_installation.get_room_config.return_value = mock.create_autospec(
        config_rooms.RoomConfig,
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
