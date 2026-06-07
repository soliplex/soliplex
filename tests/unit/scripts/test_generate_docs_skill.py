"""Unit tests for ``scripts/generate_docs_skill.py``.

The generator is not part of the importable ``soliplex`` package, so it is
loaded here by file path. It assembles the published ``soliplex-docs`` skill
from the committed ``skills/soliplex-docs/`` tree plus the live ``docs/`` and
``zensical.toml`` nav; tests build throwaway trees in ``tmp_path`` and stub the
``skills_ref`` / git seams -- no real repo, network, or dev dependency.

Each test is laid out in three blank-line-separated phases -- setup, then the
single call under test (the "act"), then the assertions -- and performs that
act exactly once (cases that would repeat it are parametrized).
"""

from __future__ import annotations

import importlib.util
import pathlib
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
# Helpers / fixtures
# --------------------------------------------------------------------------
def _doc(directory: pathlib.Path, name: str, text: str) -> pathlib.Path:
    path = directory / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """Pin SRC/DOCS/ZENSICAL/DIST into a fake repo under ``tmp_path``."""
    docs = tmp_path / "docs"
    docs.mkdir()
    _doc(docs, "index.md", "# Home\n\nWelcome home.\n")
    _doc(docs, "guide.md", "# Guide\n\nA guide.\n")
    _doc(docs, "extra.md", "# Extra\n\nExtra info.\n")

    zensical = tmp_path / "zensical.toml"
    zensical.write_text(
        "[project]\n"
        'nav = [{ Home = "index.md" }, { Docs = [{ Guide = "guide.md" }] }]\n',
        encoding="utf-8",
    )

    src = tmp_path / "skills" / "soliplex-docs"
    (src / "references").mkdir(parents=True)
    (src / "references" / ".gitkeep").write_text("", encoding="utf-8")
    (src / "scripts").mkdir()
    (src / "scripts" / "skill_versions.py").write_text(
        "# shim\n", encoding="utf-8"
    )
    (src / "SKILL.md").write_text(
        "---\nname: soliplex-docs\nmetadata:\n  source: https://x/repo\n"
        "---\n# Soliplex documentation\n\nStatic body.\n",
        encoding="utf-8",
    )

    dist = tmp_path / "dist"
    monkeypatch.setattr(gd, "SRC", src)
    monkeypatch.setattr(gd, "DOCS", docs)
    monkeypatch.setattr(gd, "ZENSICAL", zensical)
    monkeypatch.setattr(gd, "DIST", dist)
    return tmp_path, docs, src, dist


# --------------------------------------------------------------------------
# _load_nav / flatten_nav
# --------------------------------------------------------------------------
def test_load_nav(tmp_path):
    zensical = tmp_path / "zensical.toml"
    zensical.write_text(
        '[project]\nnav = [{ Home = "index.md" }]\n', encoding="utf-8"
    )

    assert gd._load_nav(zensical) == [{"Home": "index.md"}]


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
        tmp_path, "b.md", "# T\n- a list item\nreal paragraph\n## sub\n"
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
# _doc_map
# --------------------------------------------------------------------------
def test_doc_map_renders_sections_extras_and_summaries(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    _doc(docs, "index.md", "# Home\n\nHome summary.\n")
    guide = docs / "guide"
    guide.mkdir()
    _doc(guide, "intro.md", "# Intro\n")  # H1 only -> no summary
    _doc(guide, "setup.md", "# Setup\n\nSetup summary.\n")
    _doc(docs, "extra1.md", "# Extra One\n\nExtra summary.\n")  # not in nav
    _doc(docs, "extra2.md", "plain text, no heading\n")  # extra, no summary
    # Two leaves under "Guide" exercise the section-dedup skip path; the two
    # extras (with/without a summary) cover both branches of the extras loop.
    nav = [
        {"Home": "index.md"},
        {"Guide": [{"Intro": "guide/intro.md"}, {"Setup": "guide/setup.md"}]},
    ]

    out = gd._doc_map(docs, nav)

    assert out.startswith("## Documentation map")
    assert "### General" in out
    assert "### Guide" in out
    assert "### Other" in out
    assert "  Home summary." in out
    assert "  Setup summary." in out
    assert "**Extra One** — `references/extra1.md`" in out  # via _h1_title
    assert "**extra2** — `references/extra2.md`" in out  # extra, no summary


def test_doc_map_without_extras(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    _doc(docs, "index.md", "# Home\n\nHi.\n")

    out = gd._doc_map(docs, [{"Home": "index.md"}])

    assert "### Other" not in out


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------
def test_generate_assembles_skill(layout):
    _tmp, _docs, _src, dist = layout

    out = gd.generate(out_dir=dist, commit="deadbee")

    assert out == dist / "soliplex-docs"
    assert (out / "references" / "index.md").is_file()  # filled from docs/
    assert not (out / "references" / ".gitkeep").exists()  # placeholder gone
    assert (out / "scripts" / "skill_versions.py").is_file()  # carried over
    text = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "# Soliplex documentation" in text  # static body kept
    assert "## Documentation map" in text  # map appended
    assert 'source_commit: "deadbee"' in text  # stamped


def test_generate_replaces_existing_out(layout):
    _tmp, _docs, _src, dist = layout
    stale = dist / "soliplex-docs"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("old", encoding="utf-8")

    gd.generate(out_dir=dist, commit="deadbee")

    assert not (dist / "soliplex-docs" / "stale.txt").exists()


def test_generate_without_commit_skips_stamp(layout):
    _tmp, _docs, _src, dist = layout

    out = gd.generate(out_dir=dist, commit=None)

    assert "source_commit" not in (out / "SKILL.md").read_text(
        encoding="utf-8"
    )


def test_generate_missing_docs(layout, monkeypatch):
    _tmp, _docs, _src, dist = layout
    monkeypatch.setattr(gd, "DOCS", dist / "nonexistent")

    with pytest.raises(gd.DocsDirNotFound):
        gd.generate(out_dir=dist, commit="x")


# --------------------------------------------------------------------------
# _validate
# --------------------------------------------------------------------------
def test_validate_ok(monkeypatch, capsys, tmp_path):
    validate = mock.Mock(return_value=[])
    monkeypatch.setattr(gd.skills_ref, "validate", validate)

    gd._validate(tmp_path)

    assert "Validated skill:" in capsys.readouterr().out
    validate.assert_called_once_with(tmp_path)


def test_validate_reports_errors(monkeypatch, tmp_path):
    validate = mock.Mock(return_value=["boom"])
    monkeypatch.setattr(gd.skills_ref, "validate", validate)

    with pytest.raises(gd.SkillValidationFailed) as excinfo:
        gd._validate(tmp_path)

    assert excinfo.value.errors == ["boom"]
    validate.assert_called_once_with(tmp_path)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def test_main_assembles_and_validates(layout, monkeypatch, capsys):
    _tmp, _docs, _src, dist = layout
    monkeypatch.setattr(gd.build, "git_head_commit", lambda repo: "feedface")
    validate = mock.Mock(return_value=[])
    monkeypatch.setattr(gd.skills_ref, "validate", validate)

    rc = gd.main(["--out", str(dist)])

    out = dist / "soliplex-docs"
    assert rc == 0
    assert 'source_commit: "feedface"' in (out / "SKILL.md").read_text()
    validate.assert_called_once_with(out)
    assert "Validated skill:" in capsys.readouterr().out


def test_main_explicit_commit_skips_validation(layout, capsys):
    _tmp, _docs, _src, dist = layout

    rc = gd.main(["--out", str(dist), "--commit", "abc1234", "--no-validate"])

    out = dist / "soliplex-docs"
    assert rc == 0
    assert 'source_commit: "abc1234"' in (out / "SKILL.md").read_text()
    assert "Generated skill:" in capsys.readouterr().out
