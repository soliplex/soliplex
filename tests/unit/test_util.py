from unittest import mock

import pytest

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
