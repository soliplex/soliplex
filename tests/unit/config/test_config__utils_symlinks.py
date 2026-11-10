import pytest

from soliplex.config import _utils as config__utils
from soliplex.config import exceptions as config_exc
from tests import _platform

pytestmark = _platform.requires_posix_symlinks


def test__local_path_w_symlink_inside(temp_dir):
    room_dir = temp_dir / "room"
    room_dir.mkdir()
    (room_dir / "real.png").write_bytes(b"")
    (room_dir / "logo.png").symlink_to(room_dir / "real.png")

    found = config__utils._local_path(room_dir, "./logo.png")

    assert found == room_dir / "real.png"


def test__local_path_w_symlink_outside(temp_dir):
    room_dir = temp_dir / "room"
    room_dir.mkdir()
    (temp_dir / "outside.png").write_bytes(b"")
    (room_dir / "logo.png").symlink_to(temp_dir / "outside.png")

    with pytest.raises(config_exc.PathNotLocal) as exc_info:
        config__utils._local_path(room_dir, "./logo.png")

    assert exc_info.value.config_dir == room_dir
    assert exc_info.value.path == "./logo.png"


def test__local_path_w_symlinked_dir_outside(temp_dir):
    room_dir = temp_dir / "room"
    room_dir.mkdir()
    (temp_dir / "elsewhere").mkdir()
    (room_dir / "sub").symlink_to(temp_dir / "elsewhere")

    with pytest.raises(config_exc.PathNotLocal) as exc_info:
        config__utils._local_path(room_dir, "./sub/logo.png")

    assert exc_info.value.config_dir == room_dir
    assert exc_info.value.path == "./sub/logo.png"


def test__local_path_w_symlinked_config_dir(temp_dir):
    real_dir = temp_dir / "real_room"
    real_dir.mkdir()
    room_dir = temp_dir / "room"
    room_dir.symlink_to(real_dir)

    found = config__utils._local_path(room_dir, "./logo.png")

    assert found == real_dir / "logo.png"
