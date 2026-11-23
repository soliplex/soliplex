import io

from soliplex import util
from tests import _platform

pytestmark = _platform.requires_posix_symlinks


def test_upload_files_follows_symlinks(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_text("shared")
    uploads = temp_dir / "uploads"
    uploads.mkdir()
    (uploads / "linked.dat").symlink_to(shared)
    expected = shared.stat()

    found = util.upload_files(uploads)

    assert found == {"linked.dat": expected}


def test_upload_files_skips_looping_symlink(temp_dir):
    (temp_dir / "loop.dat").symlink_to(temp_dir / "loop.dat")

    found = util.upload_files(temp_dir)

    assert found == {}


def test_store_upload_replaces_symlink_not_target(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_bytes(b"shared")
    uploads = temp_dir / "uploads"
    uploads.mkdir()
    target = uploads / "linked.dat"
    target.symlink_to(shared)
    source = io.BytesIO(b"uploaded")

    util.store_upload(source, target)

    assert not target.is_symlink()
    assert target.read_bytes() == b"uploaded"
    assert shared.read_bytes() == b"shared"
