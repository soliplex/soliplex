#!/usr/bin/env python
# /// script
# requires-python = ">=3.13"
# dependencies = ["packaging"]
# ///
"""Compute the container image tags for a soliplex project version.

Prints one tag per line, for ``.github/workflows/image.yaml``:

- A final release (e.g. ``0.85.1``, or ``0.85``) gets its exact version,
  padded to at least three components (``0.85.1``, ``0.85.0``), plus the
  moving ``<major>.<minor>`` tag (``0.85``).  It also gets ``latest`` when no
  released ``v*`` tag names a higher version, so a release from a
  maintenance branch (e.g. ``v0.82.5`` after ``v0.85``) moves only its own
  ``<major>.<minor>`` tag.

- Any other version (pre-, post-, dev- or local release, e.g. ``0.86dev0``)
  gets only its exact, normalized version.

Released tags which are not ``v<version>`` (e.g. ``docs-...``) are ignored.

Usage::

    uv run scripts/image_tags.py --version "$(uv version --short)" \\
        $(git tag --list 'v*')
"""

from __future__ import annotations

import argparse
import sys

from packaging import version as pkg_version

LATEST = "latest"


def released_versions(tags):
    """Yield the version named by each ``v<version>`` tag in 'tags'.

    Tags which do not name a version are skipped.
    """
    for tag in tags:
        if not tag.startswith("v"):
            continue

        try:
            yield pkg_version.Version(tag[1:])
        except pkg_version.InvalidVersion:
            continue


def image_tags(project_version, tags=()):
    """Return the image tags for 'project_version', in order.

    'tags' are the repository's released git tags, used to decide whether
    the version is the latest release.

    Raises:

    - 'packaging.version.InvalidVersion' if 'project_version' is not a
      valid version.
    """
    version = pkg_version.Version(project_version)

    if str(version) != version.base_version:
        return [str(version)]

    release = version.release + (0,) * (3 - len(version.release))
    major, minor = release[:2]
    exact = ".".join(str(part) for part in release)
    result = [exact, f"{major}.{minor}"]

    if all(released <= version for released in released_versions(tags)):
        result.append(LATEST)

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compute container image tags for a project version.",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Project version, as reported by 'uv version --short'.",
    )
    parser.add_argument(
        "tags",
        nargs="*",
        help="Released git tags, used to decide whether to tag 'latest'.",
    )
    args = parser.parse_args(argv)

    try:
        tags = image_tags(args.version, args.tags)
    except pkg_version.InvalidVersion as exc:
        print(f"image_tags: error: {exc}", file=sys.stderr)
        return 1

    for tag in tags:
        print(tag)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
