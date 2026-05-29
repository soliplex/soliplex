#!/usr/bin/env python
"""List and diff published versions of the ``soliplex-docs`` skill.

This script is bundled inside the skill (under ``scripts/``) so an agent --
or a human -- can answer two questions without leaving the skill:

* ``list``  -- which versions have been published? Both the rolling builds
  (``docs-YYYY.MM.DD-<sha>``) and the snapshots attached to software
  releases (``v...``) are shown, newest first, with the installed copy and
  the current ``latest`` pointer marked.
* ``diff``  -- how does the installed documentation differ from a published
  version (default: ``latest``)? Only Markdown under ``references/`` is
  compared.

Standard library only -- no third-party packages are required. Network
access to ``api.github.com`` / ``github.com`` is needed; set ``GITHUB_TOKEN``
or ``GH_TOKEN`` to raise the API rate limit.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

OWNER = "soliplex"
REPO = "soliplex"
ASSET_TARBALL = "soliplex-docs-skill.tar.gz"
POINTER_TAG = "docs-latest"
POINTER_MANIFEST = "latest.json"

_API = f"https://api.github.com/repos/{OWNER}/{REPO}"
_DL = f"https://github.com/{OWNER}/{REPO}/releases/download"
_USER_AGENT = "soliplex-docs-skill"

# The skill root is the parent of this script's ``scripts/`` directory.
_SKILL_ROOT = Path(__file__).resolve().parent.parent
_REFERENCES = _SKILL_ROOT / "references"
_SKILL_MD = _SKILL_ROOT / "SKILL.md"

# Rolling build tags look like ``docs-2026.05.29-abc1234``.
_ROLLING_RE = re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$")
_COMMIT_RE = re.compile(r'^\s*source_commit:\s*"?([0-9a-fA-F]+)"?\s*$')


class GitHubAPIError(SystemExit):
    """A request to GitHub failed."""

    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"GitHub request failed ({reason}): {url}")


class AssetNotFound(SystemExit):
    """A release does not carry the expected asset."""

    def __init__(self, tag: str, name: str):
        self.tag = tag
        self.name = name
        super().__init__(f"Release {tag!r} has no asset named {name!r}.")


class ChecksumMismatch(SystemExit):
    """A downloaded asset did not match its recorded sha256."""

    def __init__(self, name: str, expected: str, actual: str):
        super().__init__(
            f"Checksum mismatch for {name!r}: "
            f"expected {expected}, got {actual}."
        )


class NoSuchReference(SystemExit):
    """A skill archive did not contain a ``references/`` tree."""

    def __init__(self, tag: str | None):
        self.tag = tag
        where = f"version {tag!r}" if tag else "the installed skill"
        super().__init__(f"No references/ directory found in {where}.")


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _get(url: str, *, accept: str = "application/vnd.github+json") -> bytes:
    request = urllib.request.Request(url)
    request.add_header("User-Agent", _USER_AGENT)
    request.add_header("Accept", accept)
    token = _token()
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310
            return response.read()
    except urllib.error.HTTPError as exc:
        raise GitHubAPIError(url, f"HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise GitHubAPIError(url, str(exc.reason)) from exc


def _asset_url(tag: str, name: str) -> str:
    return f"{_DL}/{tag}/{name}"


def _list_releases() -> list[dict]:
    releases: list[dict] = []
    page = 1
    while True:
        url = f"{_API}/releases?per_page=100&page={page}"
        batch = json.loads(_get(url))
        if not batch:
            break
        releases.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return releases


def _has_asset(release: dict, name: str) -> bool:
    return any(asset["name"] == name for asset in release.get("assets", []))


def _classify(release: dict) -> tuple[str, str]:
    """Return ``(kind, commit)`` for a docs-bearing release."""
    tag = release["tagName"] if "tagName" in release else release["tag_name"]
    if _ROLLING_RE.match(tag):
        return "rolling", tag.rsplit("-", 1)[1]
    target = release.get("target_commitish", "")
    commit = target[:7] if re.fullmatch(r"[0-9a-f]{7,40}", target) else "-"
    return "release", commit


def _installed_commit() -> str | None:
    if not _SKILL_MD.exists():
        return None
    for line in _SKILL_MD.read_text(encoding="utf-8").splitlines():
        match = _COMMIT_RE.match(line)
        if match:
            return match.group(1)[:7]
    return None


def _read_pointer() -> dict | None:
    """Return the ``latest.json`` manifest, or ``None`` if unavailable."""
    try:
        raw = _get(
            _asset_url(POINTER_TAG, POINTER_MANIFEST),
            accept="application/octet-stream",
        )
    except GitHubAPIError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _versions() -> list[dict]:
    """Docs-bearing releases, newest first, excluding the pointer."""
    out = []
    for release in _list_releases():
        tag = release["tag_name"]
        if tag == POINTER_TAG:
            continue
        if not _has_asset(release, ASSET_TARBALL):
            continue
        kind, commit = _classify(release)
        out.append(
            {
                "tag": tag,
                "date": (release.get("published_at") or "")[:10],
                "kind": kind,
                "commit": commit,
                "prerelease": release.get("prerelease", False),
            }
        )
    out.sort(key=lambda item: item["date"], reverse=True)
    return out


def cmd_list(args: argparse.Namespace) -> int:
    versions = _versions()
    if args.kind:
        versions = [v for v in versions if v["kind"] == args.kind]

    installed = _installed_commit()
    pointer = _read_pointer() or {}
    latest_tag = pointer.get("tag")

    if args.json:
        for version in versions:
            version["installed"] = version["commit"] == installed
            version["latest"] = version["tag"] == latest_tag
        json.dump(versions, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not versions:
        print("No published versions found.")
        return 0

    widths = {
        "tag": max(len(v["tag"]) for v in versions + [{"tag": "TAG"}]),
        "date": 10,
        "kind": 7,
    }
    header = (
        f"{'TAG':<{widths['tag']}}  {'DATE':<{widths['date']}}  "
        f"{'KIND':<{widths['kind']}}  COMMIT"
    )
    print(header)
    for version in versions:
        marks = []
        if version["commit"] == installed:
            marks.append("installed")
        if version["tag"] == latest_tag:
            marks.append("latest")
        suffix = f"  ← {', '.join(marks)}" if marks else ""
        print(
            f"{version['tag']:<{widths['tag']}}  "
            f"{version['date']:<{widths['date']}}  "
            f"{version['kind']:<{widths['kind']}}  "
            f"{version['commit']}{suffix}"
        )
    return 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _fetch_references(
    tag: str, dest: Path, *, asset_url: str | None, sha256: str | None
) -> Path:
    """Download + extract a version's tarball; return its ``references/``."""
    url = asset_url or _asset_url(tag, ASSET_TARBALL)
    tarball = dest / ASSET_TARBALL
    tarball.write_bytes(_get(url, accept="application/octet-stream"))

    if sha256:
        actual = _sha256(tarball)
        if actual != sha256:
            raise ChecksumMismatch(ASSET_TARBALL, sha256, actual)

    extract_dir = dest / "extract"
    extract_dir.mkdir()
    with tarfile.open(tarball) as archive:
        archive.extractall(extract_dir, filter="data")

    matches = list(extract_dir.glob("*/references"))
    if not matches:
        raise NoSuchReference(tag)
    return matches[0]


def _markdown(root: Path) -> dict[str, list[str]]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): path.read_text(
            encoding="utf-8"
        ).splitlines()
        for path in root.rglob("*.md")
    }


def _diff_trees(
    left: dict[str, list[str]],
    right: dict[str, list[str]],
    *,
    left_label: str,
    right_label: str,
    name_only: bool,
) -> int:
    added = sorted(set(right) - set(left))
    removed = sorted(set(left) - set(right))
    common = sorted(set(left) & set(right))
    changed = [name for name in common if left[name] != right[name]]

    if not (added or removed or changed):
        print("No Markdown differences.")
        return 0

    for name in removed:
        print(f"- removed: {name}")
    for name in added:
        print(f"+ added:   {name}")
    for name in changed:
        print(f"~ changed: {name}")

    if name_only:
        return 1

    print()
    for name in changed:
        diff = difflib.unified_diff(
            left[name],
            right[name],
            fromfile=f"{left_label}/{name}",
            tofile=f"{right_label}/{name}",
            lineterm="",
        )
        print("\n".join(diff))
        print()
    return 1


def cmd_diff(args: argparse.Namespace) -> int:
    if not _REFERENCES.is_dir():
        raise NoSuchReference(None)

    target = args.target or "latest"
    asset_url = args.asset_url
    sha256 = None
    if target == "latest" and asset_url is None:
        pointer = _read_pointer()
        if not pointer:
            print("Could not resolve the 'latest' pointer.", file=sys.stderr)
            return 2
        target = pointer.get("tag", "latest")
        asset_url = pointer.get("asset_url")
        sha256 = pointer.get("sha256")

    installed = _markdown(_REFERENCES)
    with tempfile.TemporaryDirectory() as tmp:
        refs = _fetch_references(
            target, Path(tmp), asset_url=asset_url, sha256=sha256
        )
        published = _markdown(refs)

        if args.other:
            with tempfile.TemporaryDirectory() as tmp2:
                other_refs = _fetch_references(
                    args.other, Path(tmp2), asset_url=None, sha256=None
                )
                return _diff_trees(
                    published,
                    _markdown(other_refs),
                    left_label=target,
                    right_label=args.other,
                    name_only=args.name_only,
                )

        return _diff_trees(
            installed,
            published,
            left_label="installed",
            right_label=target,
            name_only=args.name_only,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List published skill versions.")
    p_list.add_argument(
        "--kind",
        choices=["rolling", "release"],
        help="Show only rolling builds or only software-release builds.",
    )
    p_list.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON."
    )
    p_list.set_defaults(func=cmd_list)

    p_diff = sub.add_parser(
        "diff",
        help="Diff the installed docs against a published version.",
    )
    p_diff.add_argument(
        "target",
        nargs="?",
        help="Version tag to compare against (default: latest).",
    )
    p_diff.add_argument(
        "other",
        nargs="?",
        help="Optional second tag: diff 'target' against 'other' instead "
        "of against the installed skill.",
    )
    p_diff.add_argument(
        "--name-only",
        action="store_true",
        help="List changed files without printing unified diffs.",
    )
    p_diff.add_argument(
        "--asset-url",
        help="Override the tarball URL for 'target' (advanced/testing; "
        "accepts file:// URLs).",
    )
    p_diff.set_defaults(func=cmd_diff)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
