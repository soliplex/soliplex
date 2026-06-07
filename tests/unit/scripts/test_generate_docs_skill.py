"""Unit tests for ``scripts/generate_docs_skill.py``.

The generator is not part of the importable ``soliplex`` package, so it is
loaded here by file path. It delegates to ``build.build_skill``, passing a
generator hook that fills ``references/`` from the live ``docs/`` and appends
a nav-derived map to ``SKILL.md``. Tests exercise the nav helpers and that
hook directly, and stub ``build.build_skill`` for ``main``'s delegation -- no
real repo, network, or dev dependency.

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
def docs_tree(tmp_path, monkeypatch):
    """Fake ``docs/`` + ``zensical.toml`` pinned onto the module constants."""
    docs = tmp_path / "docs"
    docs.mkdir()
    _doc(docs, "index.md", "# Home\n\nWelcome home.\n")
    _doc(docs, "guide.md", "# Guide\n\nA guide.\n")
    zensical = tmp_path / "zensical.toml"
    zensical.write_text(
        "[project]\n"
        'nav = [{ Home = "index.md" }, { Docs = [{ Guide = "guide.md" }] }]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(gd, "DOCS", docs)
    monkeypatch.setattr(gd, "ZENSICAL", zensical)
    return docs


def _built_skill(tmp_path: pathlib.Path) -> pathlib.Path:
    """A freshly-copied skill dir, as build_skill hands to the generator."""
    out = tmp_path / "dist" / "soliplex-docs"
    (out / "references").mkdir(parents=True)
    (out / "references" / ".gitkeep").write_text("", encoding="utf-8")
    (out / "SKILL.md").write_text(
        "---\nname: soliplex-docs\nmetadata:\n"
        '  source_commit: "abc1234"\n'
        "---\n# Soliplex documentation\n\nStatic body.\n",
        encoding="utf-8",
    )
    return out


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
# _add_references_and_map (the build_skill generator hook)
# --------------------------------------------------------------------------
def test_generator_fills_references_and_appends_map(docs_tree, tmp_path):
    out = _built_skill(tmp_path)

    gd._add_references_and_map(out)

    assert (out / "references" / "index.md").is_file()  # filled from docs/
    assert not (out / "references" / ".gitkeep").exists()  # placeholder gone
    text = (out / "SKILL.md").read_text(encoding="utf-8")
    assert "# Soliplex documentation" in text  # static body kept
    assert 'source_commit: "abc1234"' in text  # stamp preserved
    assert "## Documentation map" in text  # map appended


def test_generator_missing_docs(tmp_path, monkeypatch):
    out = _built_skill(tmp_path)
    monkeypatch.setattr(gd, "DOCS", tmp_path / "nonexistent")

    with pytest.raises(gd.DocsDirNotFound):
        gd._add_references_and_map(out)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def test_main_delegates_to_build_skill(monkeypatch, capsys, tmp_path):
    dist = tmp_path / "dist"
    build_skill = mock.Mock(return_value=dist / "soliplex-docs")
    monkeypatch.setattr(gd.build, "build_skill", build_skill)
    monkeypatch.setattr(gd.build, "git_head_commit", lambda repo: "feedface")

    rc = gd.main(["--out", str(dist)])

    assert rc == 0
    build_skill.assert_called_once_with(
        "soliplex-docs",
        src=gd.SKILLS_DIR,
        dist=dist.resolve(),
        commit="feedface",
        validate=True,
        generator=gd._add_references_and_map,
    )
    assert "Generated skill:" in capsys.readouterr().out


def test_main_no_validate_and_explicit_commit(monkeypatch, tmp_path):
    dist = tmp_path / "dist"
    build_skill = mock.Mock(return_value=dist / "soliplex-docs")
    monkeypatch.setattr(gd.build, "build_skill", build_skill)

    rc = gd.main(["--out", str(dist), "--commit", "abc1234", "--no-validate"])

    assert rc == 0
    build_skill.assert_called_once_with(
        "soliplex-docs",
        src=gd.SKILLS_DIR,
        dist=dist.resolve(),
        commit="abc1234",
        validate=False,
        generator=gd._add_references_and_map,
    )


def test_main_reports_build_error(monkeypatch, capsys, tmp_path):
    def boom(*args, **kwargs):
        raise gd.build.ValidationFailed("soliplex-docs", ["bad frontmatter"])

    monkeypatch.setattr(gd.build, "build_skill", boom)
    monkeypatch.setattr(gd.build, "git_head_commit", lambda repo: "abc1234")

    rc = gd.main(["--out", str(tmp_path / "dist")])

    assert rc == 1
    assert "bad frontmatter" in capsys.readouterr().err
