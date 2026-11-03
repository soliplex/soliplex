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
