"""Unit tests for ``scripts/generate_docs_skill.py``.

The generator is not part of the importable ``soliplex`` package, so it is
loaded here by file path. Tests build throwaway ``docs/`` trees and config
files in ``tmp_path`` and stub out git / ``skills_ref`` -- no real repo,
network, or dev dependency is required.

Each test is laid out in three blank-line-separated phases -- setup, then the
single call under test (the "act"), then the assertions -- and performs that
act exactly once (cases that would repeat it are parametrized).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from unittest import mock

import pytest

_MODULE_PATH = (
    pathlib.Path(__file__).resolve().parents[3]
    / "scripts"
    / "generate_docs_skill.py"
)
_spec = importlib.util.spec_from_file_location(
    "generate_docs_skill", _MODULE_PATH
)
gd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gd)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _doc(directory: pathlib.Path, name: str, text: str) -> pathlib.Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


def _fake_repo(root: pathlib.Path, *, with_docs: bool) -> pathlib.Path:
    """Build a minimal repo root the generator can ingest."""
    root.mkdir(parents=True)
    if with_docs:
        docs = root / "docs"
        docs.mkdir()
        (docs / "index.md").write_text(
            "# Home\n\nWelcome home.\n", encoding="utf-8"
        )
    (root / "pyproject.toml").write_text(
        '[project]\nversion = "9.9.9"\n', encoding="utf-8"
    )
    (root / "zensical.toml").write_text(
        '[project]\nnav = [{ Home = "index.md" }]\n', encoding="utf-8"
    )
    return root


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
@pytest.fixture
def check_output(monkeypatch):
    """Install a Mock at ``subprocess.check_output`` and return it."""
    check_output = mock.Mock()
    monkeypatch.setattr(gd.subprocess, "check_output", check_output)
    return check_output


# --------------------------------------------------------------------------
# _yaml_dq / _validate_name
# --------------------------------------------------------------------------
def test_yaml_dq_escapes_quotes():
    assert gd._yaml_dq('x"y') == '"x\\"y"'


def test_yaml_dq_escapes_backslash():
    assert gd._yaml_dq("a\\b") == '"a\\\\b"'


def test_validate_name_ok():
    gd._validate_name("soliplex-docs")


def test_validate_name_bad_length():
    with pytest.raises(gd.InvalidSkillName):
        gd._validate_name("")


def test_validate_name_bad_chars():
    with pytest.raises(gd.InvalidSkillName) as excinfo:
        gd._validate_name("Bad_Name")

    assert excinfo.value.name == "Bad_Name"


# --------------------------------------------------------------------------
# git / config helpers
# --------------------------------------------------------------------------
def test_repo_root(check_output):
    check_output.return_value = "/some/root\n"

    root = gd._repo_root()

    assert root == pathlib.Path("/some/root")
    check_output.assert_called_once_with(
        ["git", "rev-parse", "--show-toplevel"], text=True
    )


def test_git_commit(check_output):
    check_output.return_value = "abc1234\n"

    commit = gd._git_commit(pathlib.Path("/r"))

    assert commit == "abc1234"
    check_output.assert_called_once_with(
        ["git", "-C", "/r", "rev-parse", "--short", "HEAD"], text=True
    )


def test_project_version(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nversion = "1.2.3"\n', encoding="utf-8"
    )

    assert gd._project_version(tmp_path) == "1.2.3"


def test_load_nav(tmp_path):
    (tmp_path / "zensical.toml").write_text(
        '[project]\nnav = [{ Home = "index.md" }]\n', encoding="utf-8"
    )

    assert gd._load_nav(tmp_path) == [{"Home": "index.md"}]


# --------------------------------------------------------------------------
# flatten_nav / _walk_group
# --------------------------------------------------------------------------
def test_flatten_nav_nested():
    nav = [
        {"Home": "index.md"},
        {
            "Guide": [
                {"Intro": "guide/intro.md"},
                {"Advanced": [{"Tuning": "guide/adv/tuning.md"}]},
            ]
        },
    ]

    out = gd.flatten_nav(nav)

    assert ("General", ["Home"], "index.md") in out
    assert ("Guide", ["Intro"], "guide/intro.md") in out
    assert ("Guide", ["Advanced", "Tuning"], "guide/adv/tuning.md") in out


# --------------------------------------------------------------------------
# _summarize / _h1_title
# --------------------------------------------------------------------------
def test_summarize_missing_file(tmp_path):
    assert gd._summarize(tmp_path / "nope.md") == ""


def test_summarize_full(tmp_path):
    doc = _doc(
        tmp_path,
        "a.md",
        "preamble line\n"
        "# Title\n"
        "\n"
        "This is *the* first [paragraph](http://x) with `code`.\n"
        "Second line.\n"
        "\n"
        "# Another heading\n",
    )

    assert (
        gd._summarize(doc)
        == "This is the first paragraph with code. Second line."
    )


def test_summarize_skips_special_lines(tmp_path):
    doc = _doc(
        tmp_path,
        "b.md",
        "# T\n- a list item\nreal paragraph\n## sub\n",
    )

    assert gd._summarize(doc) == "real paragraph"


def test_summarize_truncates(tmp_path):
    doc = _doc(tmp_path, "c.md", "# T\n" + "a" * 250 + "\n")

    out = gd._summarize(doc)

    assert out.endswith("…")
    assert len(out) == gd._SUMMARY_MAX


@pytest.mark.parametrize(
    "text, expected",
    [
        ("intro\n# Title Here\n", "Title Here"),
        ("no heading\n", "b"),
    ],
)
def test_h1_title(tmp_path, text, expected):
    doc = _doc(tmp_path, "b.md", text)

    assert gd._h1_title(doc) == expected


# --------------------------------------------------------------------------
# _render_skill_md
# --------------------------------------------------------------------------
def test_render_with_extras(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "# Home\n\nHome summary.\n", encoding="utf-8"
    )
    (docs / "guide").mkdir()
    (docs / "guide" / "intro.md").write_text("# Intro\n", encoding="utf-8")
    (docs / "guide" / "setup.md").write_text("# Setup\n", encoding="utf-8")
    (docs / "extra1.md").write_text(
        "# Extra One\n\nExtra summary.\n", encoding="utf-8"
    )
    (docs / "extra2.md").write_text(
        "plain text no heading\n", encoding="utf-8"
    )
    # Two leaves under "Guide" exercise the section-dedup skip path.
    nav = [
        {"Home": "index.md"},
        {
            "Guide": [
                {"Intro": "guide/intro.md"},
                {"Setup": "guide/setup.md"},
            ]
        },
    ]

    out = gd._render_skill_md(
        name="soliplex-docs",
        version="1.0",
        commit="c0ffee",
        generated="2026-01-01",
        docs_dir=docs,
        nav=nav,
    )

    assert "### General" in out
    assert "### Guide" in out
    assert "### Other" in out
    assert "Home summary." in out
    assert "**Extra One**" in out
    assert "**extra2**" in out
    assert 'source_commit: "c0ffee"' in out
    assert "skill_versions.py upgrade" in out


def test_render_without_extras(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\nHi.\n", encoding="utf-8")

    out = gd._render_skill_md(
        name="n",
        version="1",
        commit="c",
        generated="d",
        docs_dir=docs,
        nav=[{"Home": "index.md"}],
    )

    assert "### Other" not in out


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------
def test_generate_happy(tmp_path):
    repo = _fake_repo(tmp_path / "repo", with_docs=True)
    out = tmp_path / "out"

    skill = gd.generate(
        out_dir=out,
        name="soliplex-docs",
        repo_root=repo,
        commit="abc1234",
        generated="2026-01-01",
    )

    assert skill == out / "soliplex-docs"
    assert (skill / "SKILL.md").is_file()
    assert (skill / "references" / "index.md").is_file()
    assert (skill / "scripts" / "skill_versions.py").is_file()
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    assert 'version: "9.9.9"' in text
    assert 'source_commit: "abc1234"' in text


def test_generate_replaces_existing(tmp_path):
    repo = _fake_repo(tmp_path / "repo", with_docs=True)
    out = tmp_path / "out"
    stale = out / "soliplex-docs"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("old", encoding="utf-8")

    gd.generate(
        out_dir=out,
        name="soliplex-docs",
        repo_root=repo,
        commit="c",
        generated="d",
    )

    assert not (out / "soliplex-docs" / "stale.txt").exists()


def test_generate_without_template(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path / "repo", with_docs=True)
    out = tmp_path / "out"
    monkeypatch.setattr(gd, "_SKILL_TEMPLATE", tmp_path / "no-template")

    skill = gd.generate(
        out_dir=out,
        name="soliplex-docs",
        repo_root=repo,
        commit="c",
        generated="d",
    )

    assert not (skill / "scripts").exists()


def test_generate_missing_docs(tmp_path):
    repo = _fake_repo(tmp_path / "repo", with_docs=False)

    with pytest.raises(gd.DocsDirNotFound):
        gd.generate(
            out_dir=tmp_path / "out",
            name="soliplex-docs",
            repo_root=repo,
            commit="c",
            generated="d",
        )


# --------------------------------------------------------------------------
# _validate
# --------------------------------------------------------------------------
def test_validate_skipped_when_missing(monkeypatch, capsys, tmp_path):
    monkeypatch.setitem(sys.modules, "skills_ref", None)

    gd._validate(tmp_path)

    assert "skills-ref not installed" in capsys.readouterr().err


def test_validate_ok(monkeypatch, capsys, tmp_path):
    fake = types.ModuleType("skills_ref")
    fake.validate = mock.Mock(return_value=[])
    monkeypatch.setitem(sys.modules, "skills_ref", fake)

    gd._validate(tmp_path)

    assert "Validated skill:" in capsys.readouterr().out
    fake.validate.assert_called_once_with(tmp_path)


def test_validate_reports_errors(monkeypatch, tmp_path):
    fake = types.ModuleType("skills_ref")
    fake.validate = mock.Mock(return_value=["boom"])
    monkeypatch.setitem(sys.modules, "skills_ref", fake)

    with pytest.raises(gd.SkillValidationFailed) as excinfo:
        gd._validate(tmp_path)

    assert excinfo.value.errors == ["boom"]
    fake.validate.assert_called_once_with(tmp_path)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def test_main_with_explicit_args(tmp_path, capsys):
    repo = _fake_repo(tmp_path / "repo", with_docs=True)
    out = tmp_path / "out"

    rc = gd.main(
        [
            "--repo-root",
            str(repo),
            "--out",
            str(out),
            "--commit",
            "abc",
            "--generated",
            "2026-02-02",
            "--no-validate",
        ]
    )

    assert rc == 0
    assert (out / "soliplex-docs" / "SKILL.md").is_file()
    assert "Generated skill:" in capsys.readouterr().out


def test_main_defaults(tmp_path, monkeypatch):
    repo = _fake_repo(tmp_path / "repo", with_docs=True)
    out = tmp_path / "out"
    repo_root = mock.Mock(return_value=repo)
    git_commit = mock.Mock(return_value="deadbee")
    validate = mock.Mock()
    monkeypatch.setattr(gd, "_repo_root", repo_root)
    monkeypatch.setattr(gd, "_git_commit", git_commit)
    monkeypatch.setattr(gd, "_validate", validate)

    rc = gd.main(["--out", str(out)])

    assert rc == 0
    repo_root.assert_called_once_with()
    git_commit.assert_called_once_with(repo.resolve())
    validate.assert_called_once_with(out.resolve() / "soliplex-docs")
    text = (out / "soliplex-docs" / "SKILL.md").read_text(encoding="utf-8")
    assert 'source_commit: "deadbee"' in text
