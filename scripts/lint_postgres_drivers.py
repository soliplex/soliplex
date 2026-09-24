#!/usr/bin/env python
"""Keep the PostgreSQL drivers optional.

Soliplex imports no PostgreSQL driver: SQLAlchemy loads one only when a
DBURI names it. An installation using PostgreSQL picks a driver through
one of two published extras:

- 'postgres' -- psycopg's pure-Python implementation, over the host's own
  libpq (and so the host's OpenSSL, which FIPS configuration covers). It
  must not pull in the bundled 'psycopg-binary' wheel.
- 'postgres-binary' -- 'psycopg[binary]', bundling its own libpq.

Downstream projects depend on those names, and no unit test needs a
driver, so nothing else notices when one of these breaks:

- a driver added to '[project] dependencies', or to the 'dev' dependency
  group (which CI installs, so the unit suite would stop proving it runs
  without one);
- either extra renamed, or dropped, or 'postgres' switched to the binary
  implementation;
- a driver imported from 'src/soliplex/' or 'tests/unit/', which then
  fails on any installation without that extra.

Exits non-zero when any of those is found.

Usage::

    python scripts/lint_postgres_drivers.py
    python scripts/lint_postgres_drivers.py --verbose
    python scripts/lint_postgres_drivers.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys
import tomllib
from typing import NamedTuple

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = REPO_DIR / "pyproject.toml"
DEFAULT_TARGETS = [
    REPO_DIR / "src" / "soliplex",
    REPO_DIR / "tests" / "unit",
]

# Distribution names, normalized per PEP 503.
DRIVER_DISTRIBUTIONS = frozenset(
    {
        "asyncpg",
        "pg8000",
        "psycopg",
        "psycopg-binary",
        "psycopg-c",
        "psycopg-pool",
        "psycopg2",
        "psycopg2-binary",
    },
)

# Top-level import names of the same drivers.
DRIVER_MODULES = frozenset(
    {
        "asyncpg",
        "pg8000",
        "psycopg",
        "psycopg_binary",
        "psycopg_c",
        "psycopg_pool",
        "psycopg2",
    },
)

# The dependency group CI installs to run the unit suite.
CI_GROUP = "dev"

POSTGRES = "postgres"
POSTGRES_BINARY = "postgres-binary"

# PEP 508: a name, then optional '[extra, ...]'; the rest (version
# specifiers, markers) does not matter here.
_REQUIREMENT_PATTERN = r"""
    ^
    \s*
    (?P<name>                   # the distribution name:
        [A-Za-z0-9]             #   starts alphanumeric,
        (?:
            [A-Za-z0-9._-]*     #   may hold '.', '_' or '-',
            [A-Za-z0-9]         #   and ends alphanumeric
        )?
    )
    \s*
    (?:                         # optional extras:
        \[
        (?P<extras>[^\]]*)      #   whatever lies inside '[...]'
        \]
    )?
"""
_REQUIREMENT = re.compile(_REQUIREMENT_PATTERN, re.VERBOSE)


class Finding(NamedTuple):
    """One way in which a driver stopped being optional."""

    label: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.label}:{self.where}: {self.message}"


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_requirement(line: str) -> tuple[str, frozenset[str]]:
    """Return the normalized name and extras of a PEP 508 requirement.

    A string which does not start with a name names no driver either, so
    it yields an empty name rather than an error.
    """
    match = _REQUIREMENT.match(line)

    if match is None:
        return "", frozenset()

    extras = match["extras"] or ""

    return (
        _normalize(match["name"]),
        frozenset(
            _normalize(extra.strip())
            for extra in extras.split(",")
            if extra.strip()
        ),
    )


def _drivers_in(requirements: list) -> list[str]:
    """Return the requirement strings in 'requirements' naming a driver.

    Non-strings (a '{include-group = ...}' table) are skipped.
    """
    return [
        line
        for line in requirements
        if isinstance(line, str)
        and parse_requirement(line)[0] in DRIVER_DISTRIBUTIONS
    ]


def _psycopg_extras(requirements: list[str]) -> list[frozenset[str]]:
    """Return the extras of each 'psycopg' requirement."""
    return [
        extras
        for name, extras in map(parse_requirement, requirements)
        if name == "psycopg"
    ]


def check_pyproject(data: dict, label: str) -> list[Finding]:
    """Return a 'Finding' per problem in the parsed 'pyproject.toml'."""
    findings = []
    project = data.get("project", {})

    for line in _drivers_in(project.get("dependencies", [])):
        findings.append(
            Finding(
                label,
                "[project] dependencies",
                f"{line!r} is unconditional; move it to an extra",
            )
        )

    groups = data.get("dependency-groups", {})

    for line in _drivers_in(groups.get(CI_GROUP, [])):
        findings.append(
            Finding(
                label,
                f"[dependency-groups] {CI_GROUP}",
                f"{line!r} would let the unit suite need a driver",
            )
        )

    extras = project.get("optional-dependencies", {})
    where = "[project.optional-dependencies]"

    for name in (POSTGRES, POSTGRES_BINARY):
        if name not in extras:
            findings.append(
                Finding(label, where, f"extra {name!r} is missing")
            )

    if POSTGRES in extras:
        requirements = extras[POSTGRES]
        psycopgs = _psycopg_extras(requirements)
        binaries = [
            line
            for line in requirements
            if parse_requirement(line)[0] in {"psycopg-binary", "psycopg-c"}
        ]

        if not psycopgs:
            findings.append(
                Finding(
                    label,
                    f"{where} {POSTGRES}",
                    "does not install 'psycopg'",
                )
            )

        if binaries or any(found & {"binary", "c"} for found in psycopgs):
            findings.append(
                Finding(
                    label,
                    f"{where} {POSTGRES}",
                    "must use the host's libpq: plain 'psycopg', without "
                    "'[binary]' / '[c]'",
                )
            )

    if POSTGRES_BINARY in extras:
        psycopgs = _psycopg_extras(extras[POSTGRES_BINARY])

        if not any("binary" in found for found in psycopgs):
            findings.append(
                Finding(
                    label,
                    f"{where} {POSTGRES_BINARY}",
                    "does not install 'psycopg[binary]'",
                )
            )

    return findings


def driver_imports(source: str, label: str) -> list[Finding]:
    """Return a 'Finding' per absolute import of a driver in 'source'."""
    findings = []

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names = [node.module or ""]
        else:
            continue

        for name in names:
            if name.split(".")[0] in DRIVER_MODULES:
                findings.append(
                    Finding(
                        label,
                        str(node.lineno),
                        f"imports {name!r}; soliplex must not need a driver",
                    )
                )

    return findings


def iter_sources(targets: list[pathlib.Path]) -> list[pathlib.Path]:
    """Expand 'targets' (files or directories) to '*.py' paths."""
    paths = []

    for target in targets:
        if target.is_dir():
            paths.extend(target.rglob("*.py"))
        else:
            paths.append(target)

    return sorted(set(paths))


def _label(path: pathlib.Path) -> str:
    """Return 'path' relative to the repo root when it lies inside it."""
    resolved = path.resolve()

    if resolved.is_relative_to(REPO_DIR):
        return resolved.relative_to(REPO_DIR).as_posix()

    return path.as_posix()


class Scan(NamedTuple):
    """The outcome of checking 'pyproject.toml' and the sources."""

    findings: list[Finding]
    errors: list[str]
    checked: int


def scan(pyproject: pathlib.Path, targets: list[pathlib.Path]) -> Scan:
    """Check 'pyproject' and every '*.py' file under 'targets'."""
    result = Scan([], [], 0)
    label = _label(pyproject)

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        result.findings.extend(check_pyproject(data, label))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        result.errors.append(f"{label}: cannot check: {exc}")

    checked = 0

    for path in iter_sources(targets):
        label = _label(path)

        try:
            source = path.read_text(encoding="utf-8")
            result.findings.extend(driver_imports(source, label))
        except (OSError, SyntaxError) as exc:
            result.errors.append(f"{label}: cannot check: {exc}")
            continue

        checked += 1

    return result._replace(checked=checked)


# Every problem the check must catch.  The pyproject has a driver in
# the base set and in 'dev', 'postgres' on the bundled libpq, and no
# 'postgres-binary'.
SELF_TEST_PYPROJECT = """\
[project]
dependencies = ["sqlalchemy", "asyncpg >= 0.30"]

[project.optional-dependencies]
postgres = ["psycopg[binary]"]

[dependency-groups]
dev = [{include-group = "docs"}, "pytest", "psycopg-binary"]
docs = ["psycopg2"]
"""

SELF_TEST_PYPROJECT_EXPECTED = [
    Finding(
        "self-test.toml",
        "[project] dependencies",
        "'asyncpg >= 0.30' is unconditional; move it to an extra",
    ),
    Finding(
        "self-test.toml",
        "[dependency-groups] dev",
        "'psycopg-binary' would let the unit suite need a driver",
    ),
    Finding(
        "self-test.toml",
        "[project.optional-dependencies]",
        "extra 'postgres-binary' is missing",
    ),
    Finding(
        "self-test.toml",
        "[project.optional-dependencies] postgres",
        "must use the host's libpq: plain 'psycopg', without "
        "'[binary]' / '[c]'",
    ),
]

# Line numbers are asserted on below, so keep the layout stable.  The
# last four imports are allowed: SQLAlchemy's dialect needs no driver,
# a lookalike name is not a driver, and a relative import is local.
SELF_TEST_SOURCE = """\
import asyncpg
import os, psycopg.rows
from psycopg import sql
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.dialects import postgresql
import psycopgish
from . import asyncpg
from .psycopg import thing
"""

SELF_TEST_SOURCE_EXPECTED = [
    Finding(
        "self-test.py",
        "1",
        "imports 'asyncpg'; soliplex must not need a driver",
    ),
    Finding(
        "self-test.py",
        "2",
        "imports 'psycopg.rows'; soliplex must not need a driver",
    ),
    Finding(
        "self-test.py",
        "3",
        "imports 'psycopg'; soliplex must not need a driver",
    ),
    Finding(
        "self-test.py",
        "4",
        "imports 'psycopg_pool'; soliplex must not need a driver",
    ),
]


def self_test(verbose: bool) -> int:
    """Check that the checks bite -- rather than passing by finding nothing.

    Returns '0' when the embedded pyproject and source yield exactly the
    expected findings, '1' otherwise.
    """
    expected = SELF_TEST_PYPROJECT_EXPECTED + SELF_TEST_SOURCE_EXPECTED
    found = check_pyproject(
        tomllib.loads(SELF_TEST_PYPROJECT), "self-test.toml"
    ) + driver_imports(SELF_TEST_SOURCE, "self-test.py")

    if found == expected:
        if verbose:
            for finding in found:
                print(finding, file=sys.stderr)

        print(
            f"lint_postgres_drivers: self-test passed "
            f"({len(expected)} expected findings).",
            file=sys.stderr,
        )
        return 0

    for finding in (one for one in expected if one not in found):
        print(
            f"lint_postgres_drivers: self-test: missed {finding}",
            file=sys.stderr,
        )

    for finding in (one for one in found if one not in expected):
        print(
            f"lint_postgres_drivers: self-test: spurious {finding}",
            file=sys.stderr,
        )

    print(
        "\nlint_postgres_drivers: self-test FAILED -- the check no longer "
        "reports what it is supposed to report.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets",
        nargs="*",
        type=pathlib.Path,
        help="Files or directories to scan for driver imports (default: "
        "src/soliplex and tests/unit).",
    )
    parser.add_argument(
        "--pyproject",
        type=pathlib.Path,
        default=PYPROJECT,
        help="The 'pyproject.toml' to check (default: the repo's).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Report what was checked, even when nothing is found.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify the checks against an embedded pyproject and source "
        "holding every offending form, then exit without scanning.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test(args.verbose)

    scanned = scan(args.pyproject, args.targets or DEFAULT_TARGETS)

    for error in scanned.errors:
        print(f"lint_postgres_drivers: error: {error}", file=sys.stderr)

    for finding in scanned.findings:
        print(finding, file=sys.stderr)

    if scanned.findings:
        print(
            f"\nlint_postgres_drivers: {len(scanned.findings)} problem(s); "
            "the PostgreSQL drivers must stay optional (see "
            "'docs/config/dburis.md').",
            file=sys.stderr,
        )
    elif args.verbose:
        print(
            f"lint_postgres_drivers: {_label(args.pyproject)} and "
            f"{scanned.checked} source file(s) checked; drivers optional.",
            file=sys.stderr,
        )

    return 1 if scanned.findings or scanned.errors else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
