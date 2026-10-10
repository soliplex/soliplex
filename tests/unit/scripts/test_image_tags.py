"""Unit tests for ``scripts/image_tags.py``.

The script is not part of the importable ``soliplex`` package, so it is
loaded here by file path.

Each test is laid out in three blank-line-separated phases -- setup, then the
single call under test (the "act"), then the assertions -- and performs that
act exactly once (cases that would repeat it are parametrized).
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3] / "scripts" / "image_tags.py"
)
_spec = importlib.util.spec_from_file_location("image_tags", _MODULE_PATH)
it = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(it)


# --------------------------------------------------------------------------
# released_versions
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tags, expected",
    [
        ([], []),
        (["v0.85"], ["0.85"]),
        (["v0.85.1", "v0.82.4"], ["0.85.1", "0.82.4"]),
        (["docs-2026.09.29-0fc1f71", "v0.85"], ["0.85"]),
        (["vnext", "v0.85"], ["0.85"]),
        (["0.85", "v0.84"], ["0.84"]),
    ],
)
def test_released_versions(tags, expected):
    result = list(it.released_versions(tags))

    assert result == [it.pkg_version.Version(v) for v in expected]


# --------------------------------------------------------------------------
# image_tags
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "project_version, tags, expected",
    [
        ("0.85", [], ["0.85.0", "0.85", "latest"]),
        ("0.85.1", [], ["0.85.1", "0.85", "latest"]),
        ("1", [], ["1.0.0", "1.0", "latest"]),
        ("0.85.1.2", [], ["0.85.1.2", "0.85", "latest"]),
        ("0.85.1", ["v0.85", "v0.85.1"], ["0.85.1", "0.85", "latest"]),
        ("0.85.2", ["v0.85.1", "v0.84"], ["0.85.2", "0.85", "latest"]),
        ("0.82.5", ["v0.82.4", "v0.85.1"], ["0.82.5", "0.82"]),
        ("0.85", ["docs-2026.09.29-0fc1f71"], ["0.85.0", "0.85", "latest"]),
        ("0.86dev0", ["v0.85.1"], ["0.86.dev0"]),
        ("0.86rc1", [], ["0.86rc1"]),
        ("0.85.post1", [], ["0.85.post1"]),
    ],
)
def test_image_tags(project_version, tags, expected):
    result = it.image_tags(project_version, tags)

    assert result == expected


def test_image_tags_w_invalid_version():
    with pytest.raises(it.pkg_version.InvalidVersion):
        it.image_tags("not-a-version")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def test_main_prints_tags(capsys):
    argv = ["--version", "0.82.5", "v0.82.4", "v0.85.1"]

    rc = it.main(argv)

    assert rc == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == ["0.82.5", "0.82"]
    assert err == ""


def test_main_w_invalid_version(capsys):
    argv = ["--version", "not-a-version"]

    rc = it.main(argv)

    assert rc == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err != ""
