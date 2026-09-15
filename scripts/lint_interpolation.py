#!/usr/bin/env python
"""Reject ad-hoc field interpolation in 'src/soliplex/config/'.

A config field which carries 'secret:' / 'env:' markers declares that
contract on the field itself, and 'interpolation.resolve_field' is the
one place which reads the declaration and applies it. A property which
instead calls 'get_secret' or 'interpolate_environment' by hand resolves
markers that no declaration describes: the field is then invisible to
'soliplex-cli audit', which cannot flag an undeclared name in a field it
does not know interpolates.

Nothing else catches that. A declaration-vs-reality inventory cannot: an
un-annotated field yields no inventory entry, so there is no difference
to notice. The omission is only visible at the call site, which is what
this check reads.

A call passing a *string literal* is a fixed-key lookup, not field
interpolation ('get_environment("OLLAMA_BASE_URL")'), and is allowed. So
is anything in the two modules which implement the machinery.

Exits non-zero when any offending call or binding is found.

Usage::

    python scripts/lint_interpolation.py
    python scripts/lint_interpolation.py --verbose
    python scripts/lint_interpolation.py src/soliplex/config/agents.py
    python scripts/lint_interpolation.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from typing import NamedTuple

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_DIR / "src" / "soliplex" / "config"

# Methods on an installation config which resolve markers.
INTERPOLATION_NAMES = frozenset(
    {
        "get_environment",
        "get_secret",
        "interpolate",
        "interpolate_environment",
        "interpolate_secrets",
    },
)

# 'interpolation' defines the resolvers these names belong to, and
# 'installation' implements the methods themselves; both necessarily call
# them on non-literal values.
EXEMPT_FILENAMES = frozenset({"installation.py", "interpolation.py"})

CALL = "call"
BINDING = "binding"


class Finding(NamedTuple):
    """One interpolation reached without 'resolve_field'."""

    label: str
    lineno: int
    end_lineno: int
    name: str
    kind: str

    def __str__(self) -> str:
        return f"{self.label}:{self.lineno}: {self.name} ({self.kind})"


def _attr_name(node: ast.AST) -> str | None:
    """Return the attribute name when it is an interpolation method."""
    if not isinstance(node, ast.Attribute):
        return None

    if node.attr not in INTERPOLATION_NAMES:
        return None

    return node.attr


def _is_fixed_key(node: ast.Call) -> bool:
    """True when the first argument is a string literal.

    A literal names one known entry -- 'get_environment("OLLAMA_BASE_URL")'
    -- rather than resolving whatever a field happens to hold.
    """
    if not node.args:
        return False

    first = node.args[0]

    return isinstance(first, ast.Constant) and isinstance(first.value, str)


def ad_hoc_interpolation(source: str, label: str) -> list[Finding]:
    """Return a 'Finding' per offending call or binding in 'source'.

    A call is reported when it names an interpolation method and does not
    pass a string literal. A binding is reported whenever one of those
    methods is assigned to a name: 'interpolate = ic.interpolate' hides
    the call site from a reader grepping for it, and hid two of them from
    the survey which motivated this check.
    """
    findings = []

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            name = _attr_name(node.func)

            if name is not None and not _is_fixed_key(node):
                findings.append(
                    Finding(
                        label,
                        node.lineno,
                        node.end_lineno or node.lineno,
                        name,
                        CALL,
                    )
                )

        elif isinstance(node, ast.Assign):
            name = _attr_name(node.value)

            if name is not None:
                findings.append(
                    Finding(
                        label,
                        node.lineno,
                        node.end_lineno or node.lineno,
                        name,
                        BINDING,
                    )
                )

    return sorted(findings, key=lambda one: (one.lineno, one.name))


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
    """The outcome of scanning a set of targets."""

    findings: list[Finding]
    errors: list[str]
    # Source text of each scanned file, keyed by its finding label.
    sources: dict[str, str]


def scan(targets: list[pathlib.Path]) -> Scan:
    """Scan every '*.py' file under 'targets'."""
    result = Scan([], [], {})

    for path in iter_sources(targets):
        if path.name in EXEMPT_FILENAMES:
            continue

        label = _label(path)

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            result.errors.append(f"{label}: cannot read: {exc}")
            continue

        try:
            findings = ad_hoc_interpolation(source, label)
        except SyntaxError as exc:
            result.errors.append(f"{label}: cannot parse: {exc}")
            continue

        result.findings.extend(findings)
        result.sources[label] = source

    return result


def chunk(source: str, finding: Finding) -> list[str]:
    """Return the numbered source lines spanned by 'finding'."""
    lines = source.splitlines()
    width = len(str(finding.end_lineno))

    return [
        f"  {lineno:>{width}} | {lines[lineno - 1]}"
        for lineno in range(finding.lineno, finding.end_lineno + 1)
    ]


def report(scanned: Scan, verbose: bool) -> None:
    """Print findings to stderr, with source chunks when 'verbose'."""
    findings = scanned.findings

    for finding in findings:
        print(finding, file=sys.stderr)

        if verbose:
            for line in chunk(scanned.sources[finding.label], finding):
                print(line, file=sys.stderr)

    print(
        f"\nlint_interpolation: {len(findings)} interpolation(s) reached "
        "without 'resolve_field'; declare the contract on the field and "
        "resolve it through 'config.interpolation.resolve_field'.",
        file=sys.stderr,
    )


# Every form the check must catch, and every form it must let through.
# Line numbers are asserted on below, so keep the layout stable.
SELF_TEST_SOURCE = """\
from . import interpolation

KEY = "OLLAMA_BASE_URL"


class Faux:
    def fixed_key(self):
        return self._installation_config.get_environment("OLLAMA_BASE_URL")

    def declared(self):
        return interpolation.resolve_field(self, "model_name")

    def ad_hoc_secret(self):
        return self._installation_config.get_secret(self.provider_key)

    def ad_hoc_env(self):
        return self._installation_config.interpolate_environment(
            self.provider_base_url
        )

    def bound(self):
        interpolate = self._installation_config.interpolate
        return interpolate(self.command)

    def via_variable(self):
        return self._installation_config.get_environment(KEY)

    def unrelated(self):
        return self._installation_config.get_room_configs()
"""

SELF_TEST_EXPECTED = [
    # A field's value, not a fixed key.
    Finding("self-test", 14, 14, "get_secret", CALL),
    # Multi-line call: spans lines 17-19.
    Finding("self-test", 17, 19, "interpolate_environment", CALL),
    # The binding, and the call made through it.
    Finding("self-test", 22, 22, "interpolate", BINDING),
    # A name, not a literal: reported rather than assumed fixed.
    Finding("self-test", 26, 26, "get_environment", CALL),
]


def self_test(verbose: bool) -> int:
    """Check that the scan bites -- rather than passing by finding nothing.

    Returns '0' when the embedded source yields exactly the expected
    findings, '1' otherwise.
    """
    found = ad_hoc_interpolation(SELF_TEST_SOURCE, "self-test")

    if found == SELF_TEST_EXPECTED:
        if verbose:
            for finding in found:
                print(finding, file=sys.stderr)
                for line in chunk(SELF_TEST_SOURCE, finding):
                    print(line, file=sys.stderr)

        print(
            f"lint_interpolation: self-test passed "
            f"({len(SELF_TEST_EXPECTED)} expected findings).",
            file=sys.stderr,
        )
        return 0

    missed = [one for one in SELF_TEST_EXPECTED if one not in found]
    spurious = [one for one in found if one not in SELF_TEST_EXPECTED]

    for finding in missed:
        print(
            f"lint_interpolation: self-test: missed {finding}",
            file=sys.stderr,
        )

    for finding in spurious:
        print(
            f"lint_interpolation: self-test: spurious {finding}",
            file=sys.stderr,
        )

    print(
        "\nlint_interpolation: self-test FAILED -- the check no longer "
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
        default=[DEFAULT_TARGET],
        help="Files or directories to scan (default: src/soliplex/config).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Dump the source chunk containing each offending call.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Verify the check against an embedded source holding every "
        "offending form, then exit without scanning anything.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test(args.verbose)

    scanned = scan(args.targets or [DEFAULT_TARGET])

    for error in scanned.errors:
        print(f"lint_interpolation: error: {error}", file=sys.stderr)

    if scanned.findings:
        report(scanned, args.verbose)

    return 1 if scanned.findings or scanned.errors else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
