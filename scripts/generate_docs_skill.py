#!/usr/bin/env python
"""Assemble the ``soliplex-docs`` Agent Skill into ``dist/``.

The skill's static body is committed under ``skills/soliplex-docs/`` (its
``SKILL.md``, an empty ``references/``, and ``scripts/skill_versions.py``).
This script assembles the *published* skill: it copies that tree into
``dist/soliplex-docs/``, fills ``references/`` with a verbatim copy of
``docs/``, appends a ``## Documentation map`` derived from the
``zensical.toml`` nav (mirroring the published site), stamps ``SKILL.md``
with the source commit, and validates the result with the agent-skills
reference library. No embeddings, vector database, or LLM are involved.

Usage::

    uv run --group dev python scripts/generate_docs_skill.py --out dist/
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import sys
import tomllib

import skills_ref
from soliplex_skills import build
from soliplex_skills import metadata

SKILL_NAME = "soliplex-docs"
REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
SRC = REPO_DIR / "skills" / SKILL_NAME
DOCS = REPO_DIR / "docs"
ZENSICAL = REPO_DIR / "zensical.toml"
DIST = REPO_DIR / "dist"

# Max length of the per-entry summary line in the doc map.
_SUMMARY_MAX = 200
# Collapse Markdown links ``[text](url)`` down to their visible ``text``.
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


class DocsDirNotFound(SystemExit):
    """The docs directory to ingest does not exist."""

    def __init__(self, docs_dir: pathlib.Path):
        self.docs_dir = docs_dir
        super().__init__(f"docs directory not found: {docs_dir}")


class SkillValidationFailed(SystemExit):
    """skills-ref rejected the assembled skill."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        joined = "\n  ".join(errors)
        super().__init__(f"Assembled skill failed validation:\n  {joined}")


def _load_nav(zensical: pathlib.Path) -> list:
    data = tomllib.loads(zensical.read_text(encoding="utf-8"))
    return data["project"]["nav"]


def flatten_nav(nav: list) -> list[tuple[str, list[str], str]]:
    """Flatten the nav tree to ``(section, breadcrumb, doc_path)`` tuples.

    ``section`` is the top-level nav title (or ``"General"`` for top-level
    leaves); ``breadcrumb`` is the path of titles below the section.
    """
    results: list[tuple[str, list[str], str]] = []
    for entry in nav:
        for title, value in entry.items():
            if isinstance(value, str):
                results.append(("General", [title], value))
            else:
                _walk_group(value, title, [], results)
    return results


def _walk_group(items, section, rel, results) -> None:
    for entry in items:
        for title, value in entry.items():
            if isinstance(value, str):
                results.append((section, rel + [title], value))
            else:
                _walk_group(value, section, rel + [title], results)


def _summarize(doc: pathlib.Path) -> str:
    """Best-effort one-line summary: first paragraph after the H1."""
    if not doc.exists():
        return ""
    lines = doc.read_text(encoding="utf-8").splitlines()
    seen_h1 = False
    buf: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not seen_h1:
            if stripped.startswith("# "):
                seen_h1 = True
            continue
        if not stripped:
            if buf:
                break
            continue
        if stripped.startswith(("#", "-", "*", ">", "|", "```")):
            if buf:
                break
            continue
        buf.append(stripped)
    text = _LINK_RE.sub(r"\1", " ".join(buf))
    text = re.sub(r"[*`_]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > _SUMMARY_MAX:
        text = text[: _SUMMARY_MAX - 1].rstrip() + "…"
    return text


def _h1_title(doc: pathlib.Path) -> str:
    for line in doc.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("# "):
            return line.strip()[2:].strip()
    return doc.stem


def _doc_map(docs_dir: pathlib.Path, nav: list) -> str:
    """Render the ``## Documentation map`` section from the nav + docs.

    Sections follow nav order; docs present on disk but absent from the nav
    (e.g. ``examples/``) are listed under a trailing ``Other`` section.
    """
    entries = flatten_nav(nav)
    in_nav = {path for _, _, path in entries}
    all_docs = sorted(
        str(p.relative_to(docs_dir)).replace("\\", "/")
        for p in docs_dir.rglob("*.md")
    )
    extras = [p for p in all_docs if p not in in_nav]

    lines: list[str] = ["## Documentation map", ""]

    sections: list[str] = []
    for section, _, _ in entries:
        if section not in sections:
            sections.append(section)

    for section in sections:
        lines.append(f"### {section}")
        lines.append("")
        for sect, breadcrumb, path in entries:
            if sect != section:
                continue
            title = " › ".join(breadcrumb)
            lines.append(f"- **{title}** — `references/{path}`")
            summary = _summarize(docs_dir / path)
            if summary:
                lines.append(f"  {summary}")
        lines.append("")

    if extras:
        lines.append("### Other")
        lines.append("")
        for path in extras:
            title = _h1_title(docs_dir / path)
            lines.append(f"- **{title}** — `references/{path}`")
            summary = _summarize(docs_dir / path)
            if summary:
                lines.append(f"  {summary}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate(*, out_dir: pathlib.Path, commit: str | None) -> pathlib.Path:
    """Assemble the published skill under ``out_dir/soliplex-docs/``.

    Copies the committed ``skills/soliplex-docs/`` tree, fills ``references/``
    from ``docs/``, appends the nav-derived documentation map to ``SKILL.md``,
    and stamps the source *commit* (when given).
    """
    if not DOCS.is_dir():
        raise DocsDirNotFound(DOCS)

    out = out_dir / SKILL_NAME
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(SRC, out, ignore=shutil.ignore_patterns("__pycache__"))

    # Fill the template's empty references/ with a verbatim copy of docs/.
    references = out / "references"
    shutil.rmtree(references)
    shutil.copytree(DOCS, references)

    # Append the nav-derived documentation map to the static body.
    skill_md = out / "SKILL.md"
    nav = _load_nav(ZENSICAL)
    body = skill_md.read_text(encoding="utf-8").rstrip()
    skill_md.write_text(f"{body}\n\n{_doc_map(DOCS, nav)}", encoding="utf-8")

    # Stamp the build's source commit via the shared library helper.
    if commit:
        metadata.stamp_source_commit(skill_md, commit)

    return out


def _validate(skill_dir: pathlib.Path) -> None:
    """Validate the assembled skill with the Agent Skills reference library.

    ``skills_ref`` is an unconditional dependency of ``soliplex-skills`` (a
    ``dev`` dependency), so it is always available here -- matching how
    ``soliplex_skills.build`` validates a built skill.
    """
    errors = skills_ref.validate(skill_dir)
    if errors:
        raise SkillValidationFailed(errors)
    print(f"Validated skill: {skill_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assemble the soliplex-docs skill into dist/."
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=DIST,
        help="Output directory for the assembled skill (default: dist).",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Source commit to stamp into SKILL.md (default: git HEAD).",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip skills-ref validation of the assembled skill.",
    )
    args = parser.parse_args(argv)

    commit = args.commit or build.git_head_commit(REPO_DIR)
    out = generate(out_dir=args.out.resolve(), commit=commit)
    print(f"Generated skill: {out}")
    if not args.no_validate:
        _validate(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
