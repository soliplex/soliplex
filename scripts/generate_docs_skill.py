#!/usr/bin/env python
"""Generate a filesystem Agent Skill from the Soliplex ``docs/`` tree.

The output is a self-contained `Agent Skills <https://agentskills.io/>`_
package: a directory named after the skill containing a ``SKILL.md`` router
plus a verbatim copy of ``docs/`` under ``references/``.  No embeddings,
vector database, or LLM are involved -- the skill is plain Markdown that any
skills-compatible agent reads on demand via progressive disclosure.

The doc map embedded in ``SKILL.md`` is derived from the ``nav`` table in
``zensical.toml`` so it mirrors the published documentation site.

Usage::

    uv run python scripts/generate_docs_skill.py --out dist/
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib

# Skill ``name``/``description`` per the Agent Skills spec.  ``name`` must be
# 1-64 chars, lowercase ``a-z0-9`` and single hyphens, and match the parent
# directory name.  ``description`` (1-1024 chars) must convey what + when.
DEFAULT_NAME = "soliplex-docs"
DESCRIPTION = (
    "Soliplex documentation: how to install, configure, run, and use "
    "Soliplex -- a self-hosted RAG/AI system with a FastAPI backend, "
    "Flutter client, and terminal UI. Covers configuration (rooms, "
    "agents, completions, RAG, OIDC, skills, quizzes, AG-UI features), "
    "server setup and CLI, environment variables, secrets, Docker "
    "deployment, RAG database setup, and client usage. Use when "
    "answering questions about installing, configuring, operating, or "
    "troubleshooting Soliplex."
)
LICENSE = "MIT"
COMPATIBILITY = (
    "The documentation itself needs no special environment. The bundled "
    "scripts/skill_versions.py requires Python 3.12+ and network access to "
    "api.github.com / github.com (honors GITHUB_TOKEN / GH_TOKEN)."
)

# Files under this directory are copied verbatim onto the generated skill,
# mirroring its layout (e.g. ``docs_skill_template/scripts/foo.py`` lands at
# ``<skill>/scripts/foo.py``).
_SKILL_TEMPLATE = (
    pathlib.Path(__file__).resolve().parent / "docs_skill_template"
)

# Max length of the per-entry summary line in the doc map.
_SUMMARY_MAX = 200

_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# Collapse Markdown links ``[text](url)`` down to their visible ``text``.
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


class InvalidSkillName(SystemExit):
    """The requested skill name violates the Agent Skills spec."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f"Invalid skill name {name!r}: must be 1-64 chars, lowercase "
            f"alphanumerics and single non-leading/trailing hyphens."
        )


class DocsDirNotFound(SystemExit):
    """The docs directory to ingest does not exist."""

    def __init__(self, docs_dir: pathlib.Path):
        self.docs_dir = docs_dir
        super().__init__(f"docs directory not found: {docs_dir}")


class SkillValidationFailed(SystemExit):
    """skills-ref rejected the generated skill."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        joined = "\n  ".join(errors)
        super().__init__(f"Generated skill failed validation:\n  {joined}")


def _yaml_dq(value: str) -> str:
    """Render ``value`` as a double-quoted YAML scalar.

    ``description`` contains ``": "`` (colon-space), which is illegal in an
    unquoted plain scalar, so it must be quoted and escaped.
    """
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _validate_name(name: str) -> None:
    if not (1 <= len(name) <= 64) or not _NAME_RE.match(name):
        raise InvalidSkillName(name)


def _repo_root() -> pathlib.Path:
    out = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], text=True
    )
    return pathlib.Path(out.strip())


def _git_commit(repo_root: pathlib.Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, OSError):  # pragma: no cover
        return "unknown"


def _project_version(repo_root: pathlib.Path) -> str:
    pyproject = repo_root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return data["project"]["version"]


def _load_nav(repo_root: pathlib.Path) -> list:
    zensical = repo_root / "zensical.toml"
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


def _render_skill_md(
    *,
    name: str,
    version: str,
    commit: str,
    generated: str,
    docs_dir: pathlib.Path,
    nav: list,
) -> str:
    entries = flatten_nav(nav)
    in_nav = {path for _, _, path in entries}

    # Docs present on disk but absent from the nav (e.g. examples/, rag.md).
    all_docs = sorted(
        str(p.relative_to(docs_dir)).replace("\\", "/")
        for p in docs_dir.rglob("*.md")
    )
    extras = [p for p in all_docs if p not in in_nav]

    lines: list[str] = []
    lines.append("---")
    lines.append(f"name: {name}")
    lines.append(f"description: {_yaml_dq(DESCRIPTION)}")
    lines.append(f"license: {LICENSE}")
    lines.append(f"compatibility: {_yaml_dq(COMPATIBILITY)}")
    lines.append("metadata:")
    lines.append(f'  version: "{version}"')
    lines.append(f'  source_commit: "{commit}"')
    lines.append(f'  generated: "{generated}"')
    lines.append("  source: https://github.com/soliplex/soliplex")
    lines.append("---")
    lines.append("")
    lines.append("# Soliplex documentation")
    lines.append("")
    lines.append(
        "This skill bundles the full Soliplex documentation. Use it to "
        "answer questions about installing, configuring, operating, or "
        "troubleshooting Soliplex."
    )
    lines.append("")
    lines.append("## How to use this skill")
    lines.append("")
    lines.append(
        "1. Scan the **Documentation map** below and pick the entries "
        "whose topic matches the question."
    )
    lines.append(
        "2. Read the matching file(s) under `references/` (they preserve "
        "the site's structure and cross-links)."
    )
    lines.append(
        "3. Answer strictly from the documentation. If the docs do not "
        "cover it, say so rather than guessing."
    )
    lines.append("")
    lines.append("## Checking for updates")
    lines.append("")
    lines.append(
        "This skill is a point-in-time snapshot (see `metadata` above). To "
        "see what has been published and whether a newer build exists, run "
        "the bundled helper:"
    )
    lines.append("")
    lines.append("```bash")
    lines.append(
        "# List published versions (rolling builds + release snapshots)"
    )
    lines.append("python scripts/skill_versions.py list")
    lines.append("")
    lines.append("# Show what changed upstream since this copy was built")
    lines.append("python scripts/skill_versions.py diff latest")
    lines.append("")
    lines.append("# Compare any two published versions (see 'list' for tags)")
    lines.append(
        "python scripts/skill_versions.py diff "
        "docs-2026.05.20-abc1234 docs-2026.05.29-def5678"
    )
    lines.append("")
    lines.append(
        "# Upgrade this copy in place to the newest build (or a given tag)"
    )
    lines.append("python scripts/skill_versions.py upgrade")
    lines.append("```")
    lines.append("")
    lines.append("## Documentation map")
    lines.append("")

    # Render sections in nav order; "General" first if present.
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


def generate(
    *,
    out_dir: pathlib.Path,
    name: str,
    repo_root: pathlib.Path,
    commit: str,
    generated: str,
) -> pathlib.Path:
    _validate_name(name)
    docs_dir = repo_root / "docs"
    if not docs_dir.is_dir():
        raise DocsDirNotFound(docs_dir)

    nav = _load_nav(repo_root)
    version = _project_version(repo_root)

    skill_dir = out_dir / name
    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    references = skill_dir / "references"
    references.parent.mkdir(parents=True, exist_ok=True)

    shutil.copytree(docs_dir, references)

    skill_md = _render_skill_md(
        name=name,
        version=version,
        commit=commit,
        generated=generated,
        docs_dir=docs_dir,
        nav=nav,
    )
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")

    # Overlay the static template (bundled scripts, etc.) onto the skill.
    if _SKILL_TEMPLATE.is_dir():
        shutil.copytree(_SKILL_TEMPLATE, skill_dir, dirs_exist_ok=True)

    return skill_dir


def _validate(skill_dir: pathlib.Path) -> None:
    """Validate the generated skill with the Agent Skills reference library.

    ``skills-ref`` is provided by the ``dev`` dependency group, so run this
    script with ``uv run --group dev`` to enable the check.
    """
    try:
        import skills_ref
    except ImportError:
        print(
            "skills-ref not installed; skipping validation "
            "(run with 'uv run --group dev' to enable).",
            file=sys.stderr,
        )
        return
    errors = skills_ref.validate(skill_dir)
    if errors:
        raise SkillValidationFailed(errors)
    print(f"Validated skill: {skill_dir}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=pathlib.Path("dist"),
        help="Output directory for the generated skill (default: dist).",
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_NAME,
        help=f"Skill name (default: {DEFAULT_NAME}).",
    )
    parser.add_argument(
        "--commit",
        default=None,
        help="Source commit to record in metadata (default: git HEAD).",
    )
    parser.add_argument(
        "--generated",
        default=None,
        help="ISO date to record in metadata (default: today, UTC).",
    )
    parser.add_argument(
        "--repo-root",
        type=pathlib.Path,
        default=None,
        help="Repository root (default: git toplevel).",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip skills-ref validation of the generated skill.",
    )
    args = parser.parse_args(argv)

    repo_root = (args.repo_root or _repo_root()).resolve()
    commit = args.commit or _git_commit(repo_root)
    generated = (
        args.generated
        or datetime.datetime.now(datetime.UTC).date().isoformat()
    )

    skill_dir = generate(
        out_dir=args.out.resolve(),
        name=args.name,
        repo_root=repo_root,
        commit=commit,
        generated=generated,
    )
    print(f"Generated skill: {skill_dir}")
    if not args.no_validate:
        _validate(skill_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
