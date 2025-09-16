from unittest import mock

import logfire
import pytest
from starlette import datastructures

from soliplex import util


@pytest.mark.parametrize("to_scrub, expected", [
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
    (
        {"foo": "bar", "spam": []}, {"foo": "bar", "spam": []}
    ),
    (
        {"foo": "bar", "spam": [{"baz": "bam"}]},
        {"foo": "bar", "spam": [{"baz": "bam"}]}
    ),
    (
        {"foo": "bar", "spam": [{"baz": "bam", "_bif": "spaz"}]},
        {"foo": "bar", "spam": [{"baz": "bam"}]}
    ),
])
def test_scrub_private_keys(to_scrub, expected):
    found = util.scrub_private_keys(to_scrub)

    assert found == expected


@pytest.mark.parametrize("source, env_patch, expected", [
    ("no_env_prefix", {}, "no_env_prefix"),
    ("no_env_prefix", {"foo": "bar"}, "no_env_prefix"),
    ("env:{foo}", {"foo": "bar"}, "bar"),
    ("env:Testing {foo}", {"foo": "bar"}, "Testing bar"),
    ("env:{foo}", {"foo": "bar", "baz": "qux"}, "bar"),
    ("env:{baz}-{foo}", {"foo": "bar", "baz": "qux"}, "qux-bar"),
    ("env:Pfx {baz}-{foo}", {"foo": "bar", "baz": "qux"}, "Pfx qux-bar"),
])
def test_interpolate_env_vars(source, env_patch, expected):

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        found = util.interpolate_env_vars(source)

    assert found == expected


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
    sp.check_output.side_effect =  ValueError("testing")

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


@pytest.mark.parametrize("start_url, expected", [
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
])
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
