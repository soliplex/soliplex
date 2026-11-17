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


def test_stored_size_w_symlink_counts_zero(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_bytes(b"shared")
    link = temp_dir / "linked.dat"
    link.symlink_to(shared)

    assert util.stored_size(link) == 0


def test_scan_uploads_lists_but_does_not_count_symlinks(temp_dir):
    shared = temp_dir / "shared.dat"
    shared.write_bytes(b"shared data, not an upload")
    uploads = temp_dir / "uploads"
    uploads.mkdir()
    (uploads / "real.dat").write_bytes(b"abc")
    (uploads / "linked.dat").symlink_to(shared)
    (uploads / "dangling.dat").symlink_to(temp_dir / "nonesuch")

    found = util.scan_uploads(uploads)

    assert sorted(found.files) == ["linked.dat", "real.dat"]
    assert found.files["linked.dat"] == shared.stat()
    assert found.stored_bytes == 3
    assert found.hidden == []


def test_scan_uploads_skips_internal_symlink(temp_dir):
    # A link with an internal name is neither listed, counted, nor hidden.
    shared = temp_dir / "shared.dat"
    shared.write_bytes(b"shared")
    uploads = temp_dir / "uploads"
    uploads.mkdir()
    (uploads / f"{util.UPLOAD_RESERVATION_PREFIX}x").symlink_to(shared)

    found = util.scan_uploads(uploads)

    assert found == util.UploadsScan(files={}, stored_bytes=0, hidden=[])
