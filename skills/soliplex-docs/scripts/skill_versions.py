#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["soliplex-skills>=0.4"]
# ///
"""List, diff, and upgrade published versions of the ``soliplex-docs`` skill.

This script is bundled inside the skill (under ``scripts/``) so an agent -- or
a human -- can manage the installed copy without leaving the skill:

* ``list``    -- which versions have been published? Rolling builds
  (``docs-YYYY.MM.DD-<sha>``) and release snapshots are shown newest-first,
  with the installed copy and the current ``latest`` pointer marked.
* ``diff``    -- how does the installed documentation differ from a published
  version (default: ``latest``)? Pass two tags to compare them against each
  other instead. The whole skill tree is compared (including the build-time
  ``## Documentation map``, which flags structural changes); the per-build
  ``source_commit`` stamp in ``SKILL.md`` is ignored.
* ``upgrade`` -- download a published version (default: ``latest``) and install
  it in place, so documents deleted upstream do not linger.

The logic lives in the shared ``soliplex-skills`` library; this script is a
thin shim that fills in the skill's identity and delegates.

For more information see the ``soliplex-skills`` documentation:
https://soliplex.github.io/soliplex-skills/

Run this script with ``uv`` so that dependency is provisioned automatically:

    uv run scripts/skill_versions.py list

Network access to ``api.github.com`` / ``github.com`` is needed; set
``GITHUB_TOKEN`` or ``GH_TOKEN`` to raise the API rate limit.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from soliplex_skills import versions

# The skill root is the parent of this script's ``scripts/`` directory.
SKILL_ROOT = Path(__file__).resolve().parent.parent

# The only values that distinguish this skill from any other; everything else
# is handled by the library.
SPEC = versions.SkillSpec(
    owner="soliplex",
    repo="soliplex",
    skill_name="soliplex-docs",
    asset_tarball="soliplex-docs-skill.tar.gz",
    pointer_tag="docs-latest",
    rolling_re=re.compile(r"^docs-\d{4}\.\d{2}\.\d{2}-[0-9a-f]+$"),
)


def cmd_list(args: argparse.Namespace) -> int:
    rows = versions.SkillVersions(SPEC).list(
        kind=args.kind, installed_path=SKILL_ROOT, mark_latest=True
    )
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    print(versions.format_list_table(rows))
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    skill_versions = versions.SkillVersions(SPEC)
    if args.other is not None:
        return skill_versions.diff_published(
            args.target, args.other, name_only=args.name_only
        )
    return skill_versions.diff(
        SKILL_ROOT, args.target, name_only=args.name_only
    )


def cmd_upgrade(args: argparse.Namespace) -> int:
    return versions.SkillVersions(SPEC).upgrade(
        SKILL_ROOT, args.tag, force=args.force, dry_run=args.dry_run
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
        help="Diff the installed docs against a published version, or two "
        "published versions against each other.",
    )
    p_diff.add_argument(
        "target",
        nargs="?",
        default="latest",
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
    p_diff.set_defaults(func=cmd_diff)

    p_upgrade = sub.add_parser(
        "upgrade",
        help="Download a published version and install it in place.",
    )
    p_upgrade.add_argument(
        "tag",
        nargs="?",
        default="latest",
        help="Version tag to upgrade to (default: latest).",
    )
    p_upgrade.add_argument(
        "--force",
        action="store_true",
        help="Reinstall even when the installed copy is already current.",
    )
    p_upgrade.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be installed without writing any files.",
    )
    p_upgrade.set_defaults(func=cmd_upgrade)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except versions.PointerUnavailable as exc:
        print(f"skill_versions: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: NO COVER
    sys.exit(main())
