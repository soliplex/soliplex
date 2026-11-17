import contextlib
import datetime
import errno
import os
import pathlib
import re
from unittest import mock

import logfire
import pytest
from starlette import datastructures

from soliplex import util

GIT_HASH = "test-git-hash"
GIT_BRANCH = "test-git-branch"
GIT_TAG = "test-git-tag"


@pytest.mark.parametrize(
    "to_scrub, expected",
    [
        ({}, {}),
        ({"foo": "bar"}, {"foo": "bar"}),
        ({"foo": "bar", "_qux": "spam"}, {"foo": "bar"}),
        (
            {"foo": "bar", "baz": {"spam": "qux"}},
            {"foo": "bar", "baz": {"spam": "qux"}},
        ),
        (
            {"foo": "bar", "baz": {"_spam": "qux"}},
            {"foo": "bar", "baz": {}},
        ),
        ({"foo": "bar", "spam": []}, {"foo": "bar", "spam": []}),
        (
            {"foo": "bar", "spam": [{"baz": "bam"}]},
            {"foo": "bar", "spam": [{"baz": "bam"}]},
        ),
        (
            {"foo": "bar", "spam": [{"baz": "bam", "_bif": "spaz"}]},
            {"foo": "bar", "spam": [{"baz": "bam"}]},
        ),
    ],
)
def test_scrub_private_keys(to_scrub, expected):
    found = util.scrub_private_keys(to_scrub)

    assert found == expected


@pytest.mark.parametrize("w_override_files", [False, True])
@pytest.mark.parametrize("w_file_path_file", [False, True])
def test_gitmetadata_ctor(temp_dir, w_file_path_file, w_override_files):
    if w_file_path_file:
        file_path = temp_dir / "filename.txt"
        file_path.touch()
    else:
        file_path = temp_dir

    if w_override_files:
        hash_file = temp_dir / "git-hash.txt"
        hash_file.write_text(GIT_HASH)
        branch_file = temp_dir / "git-branch.txt"
        branch_file.write_text(GIT_BRANCH)
        tag_file = temp_dir / "git-tag.txt"
        tag_file.write_text(GIT_TAG)

    found = util.GitMetadata(file_path)

    if w_override_files:
        assert found._git_hash == GIT_HASH
        assert found._git_branch == GIT_BRANCH
        assert found._git_tag == GIT_TAG
    else:
        assert found._git_hash is None
        assert found._git_branch is None
        assert found._git_tag is None


# Git refnames may hold any UTF-8, so the override files are read as
# UTF-8 rather than the host locale encoding. Under 'cp1252' (the Windows
# default) '’' / '—' would mojibake silently and 'Ł' (U+0141 ->
# b"\xc5\x81") would raise, since 0x81 is one of cp1252's undefined
# slots. Written as bytes so the fixture is UTF-8 on any host.
NON_ASCII_HASH = "hash-Łódź"
NON_ASCII_BRANCH = "feature/Ada-Lovelace’s-notes"
NON_ASCII_TAG = "v1.0—Łódź"


def test_gitmetadata_ctor_w_non_ascii_override_files(temp_dir):
    """UTF-8 override files decode the same whatever the host locale."""
    (temp_dir / "git-hash.txt").write_bytes(NON_ASCII_HASH.encode("utf-8"))
    (temp_dir / "git-branch.txt").write_bytes(NON_ASCII_BRANCH.encode("utf-8"))
    (temp_dir / "git-tag.txt").write_bytes(NON_ASCII_TAG.encode("utf-8"))

    found = util.GitMetadata(temp_dir)

    assert found._git_hash == NON_ASCII_HASH
    assert found._git_branch == NON_ASCII_BRANCH
    assert found._git_tag == NON_ASCII_TAG


@pytest.mark.parametrize("w_already", [None, "already"])
@mock.patch("soliplex.util.subprocess")
def test_gitmetadata_git_hash(subp, temp_dir, w_already):
    gitmeta = util.GitMetadata(temp_dir)

    if w_already:
        expected = gitmeta._git_hash = "already"
    else:
        subp.check_output.return_value = f"{GIT_HASH}\n".encode("ascii")
        expected = GIT_HASH

    found = gitmeta.git_hash

    assert found == expected

    if w_already:
        subp.check_output.assert_not_called()
    else:
        subp.check_output.assert_called_once_with(
            ["git", "-C", str(temp_dir), "rev-parse", "HEAD"],
            stderr=subp.DEVNULL,
        )


@pytest.mark.parametrize(
    "w_lines, expected",
    [
        ([], None),
        (
            ["  other-branch"],
            None,
        ),
        (
            [
                f"* {GIT_BRANCH}",
            ],
            GIT_BRANCH,
        ),
        (
            [
                "  other-branch",
                f"* {GIT_BRANCH}",
            ],
            GIT_BRANCH,
        ),
        (
            [
                "  other-branch",
                f"* {GIT_BRANCH}",
                "  waaa-branch",
            ],
            GIT_BRANCH,
        ),
    ],
)
@pytest.mark.parametrize("w_already", [None, "already"])
@mock.patch("soliplex.util.subprocess")
def test_gitmetadata_git_branch(subp, temp_dir, w_already, w_lines, expected):
    gitmeta = util.GitMetadata(temp_dir)

    if w_already:
        expected = gitmeta._git_branch = "already"
    else:
        subp.check_output.return_value = "\n".join(w_lines).encode("ascii")

    found = gitmeta.git_branch

    assert found == expected

    if w_already:
        subp.check_output.assert_not_called()
    else:
        subp.check_output.assert_called_once_with(
            ["git", "-C", str(temp_dir), "branch", "--list"],
            stderr=subp.DEVNULL,
        )


@pytest.mark.parametrize(
    "w_lines, expected",
    [
        ([], None),
        (
            ["DEADBEEF other-tag"],
            None,
        ),
        (
            [
                f"{GIT_HASH} {GIT_TAG}",
            ],
            GIT_TAG,
        ),
        (
            [
                "DEADBEEF other-tag",
                f"{GIT_HASH} {GIT_TAG}",
            ],
            GIT_TAG,
        ),
        (
            [
                "DEADBEEF other-tag",
                "",
                f"{GIT_HASH} {GIT_TAG}",
                "FACEDACE waaa-tag",
            ],
            GIT_TAG,
        ),
    ],
)
@pytest.mark.parametrize("w_already", [None, "already"])
@mock.patch("soliplex.util.subprocess")
def test_gitmetadata_git_tag(subp, temp_dir, w_already, w_lines, expected):
    gitmeta = util.GitMetadata(temp_dir)
    gitmeta._git_hash = GIT_HASH

    if w_already:
        expected = gitmeta._git_tag = "already"
    else:
        subp.check_output.return_value = "\n".join(w_lines).encode("ascii")

    found = gitmeta.git_tag

    assert found == expected

    if w_already:
        subp.check_output.assert_not_called()
    else:
        subp.check_output.assert_called_once_with(
            [
                "git",
                "-C",
                str(temp_dir),
                "tag",
                "--list",
                "--sort=creatordate",
                "--format=%(objectname) %(refname:strip=2)",
            ],
            stderr=subp.DEVNULL,
        )


@mock.patch("soliplex.util.subprocess.check_output")
def test_gitmetadata_git_hash_w_calledprocesserror(check_output, temp_dir):
    """Test git_hash returns 'unknown' when git command fails."""
    import subprocess

    gitmeta = util.GitMetadata(temp_dir)
    check_output.side_effect = subprocess.CalledProcessError(128, "git")

    found = gitmeta.git_hash

    assert found == "unknown"


@mock.patch("soliplex.util.subprocess.check_output")
def test_gitmetadata_git_branch_w_calledprocesserror(check_output, temp_dir):
    """Test git_branch returns 'unknown' when git command fails."""
    import subprocess

    gitmeta = util.GitMetadata(temp_dir)
    check_output.side_effect = subprocess.CalledProcessError(128, "git")

    found = gitmeta.git_branch

    assert found == "unknown"


@mock.patch("soliplex.util.subprocess.check_output")
def test_gitmetadata_git_tag_w_calledprocesserror(check_output, temp_dir):
    """Test git_tag returns 'unknown' when git command fails."""
    import subprocess

    gitmeta = util.GitMetadata(temp_dir)
    gitmeta._git_hash = GIT_HASH  # Set hash so tag lookup proceeds
    check_output.side_effect = subprocess.CalledProcessError(128, "git")

    found = gitmeta.git_tag

    assert found == "unknown"


@pytest.mark.parametrize(
    "start_url, expected",
    [
        # HTTP default port
        (
            "http://localhost:80/foo/bar",
            "http://localhost/foo/bar",
        ),
        # HTTPS default port
        (
            "https://localhost:443/foo/bar",
            "https://localhost/foo/bar",
        ),
        # HTTP non-default port
        (
            "http://localhost:8080/foo/bar",
            "http://localhost:8080/foo/bar",
        ),
        # HTTPS non-default port
        (
            "https://localhost:4443/foo/bar",
            "https://localhost:4443/foo/bar",
        ),
        # no port
        (
            "http://localhost/foo/bar",
            "http://localhost/foo/bar",
        ),
        # username / password
        (
            "http://user:pass@localhost:80/foo/bar",
            "http://user:pass@localhost/foo/bar",
        ),
        (
            "https://user:pass@localhost:443/foo/bar",
            "https://user:pass@localhost/foo/bar",
        ),
        (
            "http://user:pass@localhost:8080/foo/bar",
            "http://user:pass@localhost:8080/foo/bar",
        ),
        (
            "https://user:pass@localhost:4443/foo/bar",
            "https://user:pass@localhost:4443/foo/bar",
        ),
        # Only username
        (
            "http://user@localhost:80/foo/bar",
            "http://user@localhost/foo/bar",
        ),
        (
            "https://user@localhost:443/foo/bar",
            "https://user@localhost/foo/bar",
        ),
        (
            "http://user@localhost:8080/foo/bar",
            "http://user@localhost:8080/foo/bar",
        ),
        (
            "https://user@localhost:4443/foo/bar",
            "https://user@localhost:4443/foo/bar",
        ),
        # Query string
        (
            "http://localhost:80/foo/bar?baz=1&qux=2",
            "http://localhost/foo/bar?baz=1&qux=2",
        ),
        (
            "https://localhost:443/foo/bar?baz=1",
            "https://localhost/foo/bar?baz=1",
        ),
        (
            "http://localhost:8080/foo/bar?baz=1",
            "http://localhost:8080/foo/bar?baz=1",
        ),
        # Anchor fragment
        (
            "http://localhost:80/foo/bar#frag",
            "http://localhost/foo/bar#frag",
        ),
        (
            "https://localhost:443/foo/bar#frag",
            "https://localhost/foo/bar#frag",
        ),
        (
            "http://localhost:8080/foo/bar#frag",
            "http://localhost:8080/foo/bar#frag",
        ),
        # Query string + anchor fragment
        (
            "http://localhost:80/foo/bar?baz=1#frag",
            "http://localhost/foo/bar?baz=1#frag",
        ),
        (
            "https://localhost:443/foo/bar?baz=1#frag",
            "https://localhost/foo/bar?baz=1#frag",
        ),
        (
            "http://localhost:8080/foo/bar?baz=1#frag",
            "http://localhost:8080/foo/bar?baz=1#frag",
        ),
    ],
)
def test_strip_default_port(start_url, expected):
    found = util.strip_default_port(datastructures.URL(start_url))

    assert found == expected


def test_modified_at_is_utc():
    stat_result = os.stat_result((0,) * 8 + (1_761_725_730, 0))

    found = util.modified_at(stat_result)

    # On a UTC host a local time compares and prints the same as UTC.
    assert found.tzinfo is datetime.UTC


@pytest.mark.parametrize(
    "w_mtime, expected",
    [
        pytest.param(
            1_761_725_730.5,
            datetime.datetime(
                2025, 10, 29, 8, 15, 30, 500_000, tzinfo=datetime.UTC
            ),
            id="sub_second",
        ),
        pytest.param(-62_135_596_801, None, id="before_year_1"),
        pytest.param(
            -62_135_596_800,
            datetime.datetime(1, 1, 1, tzinfo=datetime.UTC),
            id="first_second_of_year_1",
        ),
        pytest.param(
            253_402_300_799,
            datetime.datetime(9999, 12, 31, 23, 59, 59, tzinfo=datetime.UTC),
            id="last_second_of_year_9999",
        ),
        pytest.param(253_402_300_800, None, id="year_10000"),
    ],
)
def test_modified_at_w_mtime(w_mtime, expected):
    stat_result = os.stat_result((0,) * 8 + (w_mtime, 0))

    found = util.modified_at(stat_result)

    assert found == expected


def test_upload_files_maps_file_to_its_stat(temp_dir):
    file_path = temp_dir / "a.txt"
    file_path.write_text("a")
    expected = file_path.stat()

    found = util.upload_files(temp_dir)

    assert found == {"a.txt": expected}


def test_upload_files_skips_subdirectory(temp_dir):
    (temp_dir / "sub").mkdir()

    found = util.upload_files(temp_dir)

    assert found == {}


def test_upload_files_wo_directory(temp_dir):

    found = util.upload_files(temp_dir / "nonesuch")

    assert found == {}


def test_upload_files_skips_file_removed_before_stat(temp_dir):
    (temp_dir / "kept.txt").write_text("kept")
    (temp_dir / "vanishing.txt").write_text("vanishing")
    real_glob = pathlib.Path.glob

    def glob_then_remove(path, pattern):
        found = list(real_glob(path, pattern))
        (path / "vanishing.txt").unlink()
        return found

    with mock.patch.object(
        pathlib.Path,
        "glob",
        autospec=True,
        side_effect=glob_then_remove,
    ):
        found = util.upload_files(temp_dir)

    assert list(found) == ["kept.txt"]


def test_upload_files_hides_internal_names(temp_dir):
    (temp_dir / "kept.txt").write_text("kept")
    (temp_dir / f"{util.UPLOAD_RESERVATION_PREFIX}abc").write_text("x")
    (temp_dir / ".nfs0001").write_text("x")

    found = util.upload_files(temp_dir)

    assert list(found) == ["kept.txt"]


@pytest.mark.parametrize(
    "name, expected",
    [
        (f"{util.UPLOAD_RESERVATION_PREFIX}0123abcd", True),
        (".nfs000000000001", True),
        ("report.pdf", False),
        (".env", False),
        ("a.nfs1", False),
        ("x.soliplex-upload-1", False),
    ],
)
def test_is_internal_upload_name(name, expected):
    assert util.is_internal_upload_name(name) is expected


def test_stored_size_w_regular_file(temp_dir):
    file_path = temp_dir / "a.txt"
    file_path.write_bytes(b"abc")

    assert util.stored_size(file_path) == 3


def test_stored_size_w_directory(temp_dir):
    (temp_dir / "sub").mkdir()

    assert util.stored_size(temp_dir / "sub") == 0


def test_stored_size_wo_file(temp_dir):
    assert util.stored_size(temp_dir / "nonesuch") == 0


def _lstat_raising(*errnos):
    """Patch 'Path.lstat' to raise 'OSError(e)' for each of 'errnos' in turn

    Once they are used up, the real 'lstat' answers.
    """
    real_lstat = pathlib.Path.lstat
    pending = list(errnos)

    def lstat(path):
        if pending:
            err = pending.pop(0)
            raise OSError(err, os.strerror(err))
        return real_lstat(path)

    return mock.patch.object(
        pathlib.Path, "lstat", autospec=True, side_effect=lstat
    )


def test_stored_size_retries_estale_once(temp_dir):
    file_path = temp_dir / "a.txt"
    file_path.write_bytes(b"abc")

    with _lstat_raising(errno.ESTALE):
        found = util.stored_size(file_path)

    assert found == 3


def test_stored_size_retried_estale_removed(temp_dir):
    # Stale, and then gone on the retry:  it no longer occupies storage.
    with _lstat_raising(errno.ESTALE):
        found = util.stored_size(temp_dir / "nonesuch")

    assert found == 0


def test_stored_size_raises_estale_twice(temp_dir):
    file_path = temp_dir / "a.txt"
    file_path.write_bytes(b"abc")

    with (
        _lstat_raising(errno.ESTALE, errno.ESTALE),
        pytest.raises(OSError, match=re.escape(os.strerror(errno.ESTALE))),
    ):
        util.stored_size(file_path)


def test_stored_size_raises_other_oserror(temp_dir):
    file_path = temp_dir / "a.txt"
    file_path.write_bytes(b"abc")

    with (
        _lstat_raising(errno.EIO),
        pytest.raises(OSError, match=re.escape(os.strerror(errno.EIO))),
    ):
        util.stored_size(file_path)


def test_scan_uploads(temp_dir):
    (temp_dir / "a.txt").write_bytes(b"abc")
    (temp_dir / "b.txt").write_bytes(b"defgh")
    (temp_dir / "sub").mkdir()
    (temp_dir / "sub" / "nested.txt").write_bytes(b"not counted")
    reservation = temp_dir / f"{util.UPLOAD_RESERVATION_PREFIX}abc"
    reservation.write_bytes(b"0123456789")
    os.utime(reservation, (1_700_000_000, 1_700_000_000))
    (temp_dir / ".nfs0001").write_bytes(b"xy")
    (temp_dir / ".nfs-dir").mkdir()  # internal, but not a regular file

    found = util.scan_uploads(temp_dir)

    assert sorted(found.files) == ["a.txt", "b.txt"]
    assert found.files["a.txt"].st_size == 3
    assert found.stored_bytes == 3 + 5 + 10 + 2
    assert sorted(found.hidden, key=lambda h: h.name) == [
        util.HiddenUpload(name=".nfs0001", size_bytes=2, mtime=mock.ANY),
        util.HiddenUpload(
            name=f"{util.UPLOAD_RESERVATION_PREFIX}abc",
            size_bytes=10,
            mtime=1_700_000_000,
        ),
    ]


def test_scan_uploads_wo_directory(temp_dir):
    found = util.scan_uploads(temp_dir / "nonesuch")

    assert found == util.UploadsScan(files={}, stored_bytes=0, hidden=[])


def test_scan_uploads_skips_file_removed_before_lstat(temp_dir):
    (temp_dir / "kept.txt").write_bytes(b"kept")
    (temp_dir / "vanishing.txt").write_bytes(b"vanishing")
    real_scandir = os.scandir

    def scandir_then_remove(path):
        found = list(real_scandir(path))
        (temp_dir / "vanishing.txt").unlink()
        return iter(found)

    with mock.patch("os.scandir", side_effect=scandir_then_remove):
        found = util.scan_uploads(temp_dir)

    assert list(found.files) == ["kept.txt"]
    assert found.stored_bytes == 4


def test_scan_uploads_skips_unstatable_non_regular(temp_dir):
    # A non-regular entry is listed only when it stats as a regular file
    # (a link to one);  one which cannot be stat'd is left out, as
    # 'upload_files' leaves it out.
    (temp_dir / "sub").mkdir()

    def lstat(path):
        # 'Path.lstat' delegates to 'Path.stat' on some platforms (Windows)
        # but not others:  pin it, so that only the followed 'stat' fails,
        # by the same path everywhere.
        return os.lstat(path)

    with (
        mock.patch.object(pathlib.Path, "lstat", lstat),
        mock.patch.object(
            pathlib.Path,
            "stat",
            side_effect=PermissionError(errno.EACCES, "denied"),
        ),
    ):
        found = util.scan_uploads(temp_dir)

    assert found.files == {}


def test_scan_uploads_fails_closed(temp_dir):
    (temp_dir / "a.txt").write_bytes(b"abc")

    with (
        _lstat_raising(errno.EIO),
        pytest.raises(OSError, match=re.escape(os.strerror(errno.EIO))),
    ):
        util.scan_uploads(temp_dir)


@pytest.fixture
def mock_span():
    with mock.patch.object(
        logfire, "start_span", mock.MagicMock(), create=True
    ) as patched:
        yield patched


@pytest.mark.anyio
def test_logfile_span_w_sync_function(mock_span):
    @util.logfire_span("test_span")
    def foo(x):
        return x + 1

    result = foo(3)
    assert result == 4
    mock_span.assert_called_once_with("test_span")
    # Check that the context manager was entered and exited
    assert mock_span.return_value.__enter__.called
    assert mock_span.return_value.__exit__.called


@pytest.mark.anyio
async def test_logfile_span_w_async_function(mock_span):
    @util.logfire_span("test_async_span")
    async def bar(x):
        return x * 2

    result = await bar(4)
    assert result == 8
    mock_span.assert_called_once_with("test_async_span")
    # Check that the context manager was entered and exited
    assert mock_span.return_value.__enter__.called
    assert mock_span.return_value.__exit__.called


def test_logfile_span_preserves_function_metadata(mock_span):
    @util.logfire_span("meta_span")
    def baz():
        """A test docstring."""

    assert baz.__name__ == "baz"
    assert baz.__doc__ == "A test docstring."


@pytest.mark.parametrize(
    "text, expected",
    [
        # Test 4+ dots get replaced with ...
        ("foo....bar", "foo...bar"),
        ("foo.....bar", "foo...bar"),
        ("foo..........bar", "foo...bar"),
        # Test 2+ ellipses get replaced with …
        ("foo……bar", "foo…bar"),
        ("foo………bar", "foo…bar"),
        ("foo…………bar", "foo…bar"),
        # Test 3 or fewer dots are not modified
        ("foo...bar", "foo...bar"),
        ("foo..bar", "foo..bar"),
        ("foo.bar", "foo.bar"),
        ("foobar", "foobar"),
        # Test 1 ellipse is not modified
        ("foo…bar", "foo…bar"),
        # Test multiple replacements in same string
        ("foo....bar....baz", "foo...bar...baz"),
        ("foo……bar……baz", "foo…bar…baz"),
        ("start......middle.....end", "start...middle...end"),
        # Test edge cases
        ("", ""),
        ("....", "..."),
        ("...", "..."),
        ("..........", "..."),
        ("…", "…"),
        ("……", "…"),
        # Test dots at beginning/end of string
        ("....text", "...text"),
        ("text....", "text..."),
        # Test ellipses at beginning/end of string
        ("text……", "text…"),
        ("……text", "…text"),
        # Test dots with newlines and other characters
        ("line1....\nline2", "line1...\nline2"),
        ("test....\t....test", "test...\t...test"),
        # Test ellipses with newlines and other characters
        ("line1……\nline2", "line1…\nline2"),
        ("test……\t……test", "test…\t…test"),
    ],
)
def test_preprocess_markdown(text, expected):
    assert util.preprocess_markdown(text) == expected


@pytest.mark.parametrize(
    "w_object, expectation",
    [
        (
            datetime.date(2026, 1, 27),
            contextlib.nullcontext("2026-01-27"),
        ),
        (
            datetime.time(9, 49, 27),
            contextlib.nullcontext("09:49:27"),
        ),
        (
            datetime.datetime(2026, 1, 27, 9, 49, 27, tzinfo=datetime.UTC),
            contextlib.nullcontext("2026-01-27T09:49:27+00:00"),
        ),
        (
            object(),
            pytest.raises(util.SQLA_JSONSerializationError),
        ),
    ],
)
def test_sqla_json_defaults(w_object, expectation):
    with expectation as expected:
        found = util.sqla_json_defaults(w_object)

    if not isinstance(expected, pytest.ExceptionInfo):
        assert found == expected


@mock.patch("json.dumps")
def test_serialize_sqla_json(jd):
    data = {
        "timestamp": datetime.datetime.now(datetime.UTC),
    }

    found = util.serialize_sqla_json(data)

    assert found is jd.return_value

    jd.assert_called_once_with(data, default=util.sqla_json_defaults)
