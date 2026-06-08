"""Unit tests for the bundled ``scripts/skill_versions.py`` shim.

The script ships inside the generated ``soliplex-docs`` skill and is not
part of the importable ``soliplex`` package, so it is loaded here by file
path. Since the adoption of ``soliplex-skills`` it is a thin shim over that
library, so these tests pin the skill's identity (its ``SkillSpec``) and that
each subcommand delegates to the right ``SkillVersions`` call. The library's
own behavior -- the GitHub/network seams, tarball handling, diffing -- is
covered by its own test suite and is never exercised here.

Each test is laid out in three blank-line-separated phases -- setup, then the
single call under test (the "act"), then the assertions -- and performs that
act exactly once.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest
from soliplex_skills import versions

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "skills"
    / "soliplex-docs"
    / "scripts"
    / "skill_versions.py"
)
_spec = importlib.util.spec_from_file_location("skill_versions", _MODULE_PATH)
sv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sv)


class _RecordingVersions:
    """Stand-in for ``SkillVersions`` that records construction and calls."""

    spec = None
    calls: dict = {}

    def __init__(self, spec):
        type(self).spec = spec

    def list(self, **kwargs):
        type(self).calls["list"] = kwargs
        return [{"tag": "docs-2026.05.29-bbbbbbb"}]

    def diff(self, *args, **kwargs):
        type(self).calls["diff"] = (args, kwargs)
        return 1

    def diff_published(self, *args, **kwargs):
        type(self).calls["diff_published"] = (args, kwargs)
        return 1

    def upgrade(self, *args, **kwargs):
        type(self).calls["upgrade"] = (args, kwargs)
        return 0


@pytest.fixture
def recorder(monkeypatch):
    """Replace ``versions.SkillVersions`` with a call recorder."""
    _RecordingVersions.spec = None
    _RecordingVersions.calls = {}
    monkeypatch.setattr(versions, "SkillVersions", _RecordingVersions)
    return _RecordingVersions


# -- identity --------------------------------------------------------------
def test_spec_identifies_the_docs_skill():
    spec = sv.SPEC

    assert spec.skill_name == "soliplex-docs"
    assert spec.owner == "soliplex"
    assert spec.repo == "soliplex"
    assert spec.asset_tarball == "soliplex-docs-skill.tar.gz"
    assert spec.pointer_tag == "docs-latest"
    assert spec.rolling_re.match("docs-2026.05.29-abc1234")


# -- list ------------------------------------------------------------------
def test_list_delegates_with_install_context(recorder, monkeypatch, capsys):
    monkeypatch.setattr(versions, "format_list_table", lambda rows: "TABLE")

    rc = sv.main(["list", "--kind", "rolling"])

    assert rc == 0
    assert recorder.spec is sv.SPEC
    assert recorder.calls["list"] == {
        "kind": "rolling",
        "installed_path": sv.SKILL_ROOT,
        "mark_latest": True,
    }
    assert capsys.readouterr().out.strip() == "TABLE"


def test_list_json_emits_rows(recorder, capsys):
    rc = sv.main(["list", "--json"])

    assert rc == 0
    assert json.loads(capsys.readouterr().out) == [
        {"tag": "docs-2026.05.29-bbbbbbb"}
    ]


# -- diff ------------------------------------------------------------------
def test_diff_one_target_compares_against_installed(recorder):
    rc = sv.main(["diff", "v0.68"])

    assert rc == 1
    assert recorder.calls["diff"] == (
        (sv.SKILL_ROOT, "v0.68"),
        {"name_only": False},
    )
    assert "diff_published" not in recorder.calls


def test_diff_two_tags_compares_published_versions(recorder):
    rc = sv.main(["diff", "v0.67", "v0.68", "--name-only"])

    assert rc == 1
    assert recorder.calls["diff_published"] == (
        ("v0.67", "v0.68"),
        {"name_only": True},
    )
    assert "diff" not in recorder.calls


# -- upgrade ---------------------------------------------------------------
def test_upgrade_delegates_with_flags(recorder):
    rc = sv.main(
        ["upgrade", "docs-2026.05.29-bbbbbbb", "--force", "--dry-run"]
    )

    assert rc == 0
    assert recorder.calls["upgrade"] == (
        (sv.SKILL_ROOT, "docs-2026.05.29-bbbbbbb"),
        {"force": True, "dry_run": True},
    )


# -- error handling --------------------------------------------------------
def test_pointer_unavailable_exits_2(monkeypatch, capsys):
    def boom(self, *args, **kwargs):
        raise versions.PointerUnavailable("docs-latest")

    monkeypatch.setattr(versions.SkillVersions, "diff", boom)

    rc = sv.main(["diff"])

    assert rc == 2
    assert "docs-latest" in capsys.readouterr().err
