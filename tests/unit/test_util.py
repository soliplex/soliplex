import contextlib
import datetime
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
        )


def test_get_git_hash_for_file_w_override_text_file(temp_dir):
    HASH = "abc9876543210"

    override_file = temp_dir / "git-hash.txt"
    override_file.write_text(HASH)

    fake_module = temp_dir / "module.py"

    found = util.get_git_hash_for_file(str(fake_module))

    assert found == HASH


@mock.patch("soliplex.util.traceback")
@mock.patch("soliplex.util.subprocess")
def test_get_git_hash_for_file_w_subprocess_miss(sp, tb):
    sp.check_output.side_effect = ValueError("testing")

    found = util.get_git_hash_for_file(__file__)

    assert found == "unknown"

    tb.print_exc.assert_called_once_with()


@mock.patch("soliplex.util.subprocess")
def test_get_git_hash_for_file_w_subprocess_hit(sp):
    HASH = "abc9876543210"
    get_rev_parse_head_output = f"{HASH}\n".encode("ascii")

    sp.check_output.side_effect = [get_rev_parse_head_output]

    found = util.get_git_hash_for_file(__file__)

    assert found == HASH


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
