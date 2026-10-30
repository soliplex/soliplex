import os

from soliplex import util
from tests import _platform

pytestmark = _platform.requires_posix_symlinks


def test_upload_files_follows_symlinks(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_text("shared")
    os.utime(shared, (1_761_725_730, 1_761_725_730))
    uploads = temp_dir / "uploads"
    uploads.mkdir()
    (uploads / "linked.dat").symlink_to(shared)
    (uploads / "broken.dat").symlink_to(temp_dir / "missing")

    found = util.upload_files(uploads)

    assert {
        name: (stat_result.st_mtime, stat_result.st_size)
        for name, stat_result in found.items()
    } == {"linked.dat": (1_761_725_730, len("shared"))}
