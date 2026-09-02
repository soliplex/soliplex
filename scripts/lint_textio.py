#!/usr/bin/env python
"""Reject locale-dependent text file IO in 'src/soliplex/'.

Text-mode 'read_text()' / 'write_text()' / 'open()' without an explicit
'encoding=' fall back to 'locale.getpreferredencoding(False)' -- UTF-8
on Linux, but 'cp1252' on a typical Windows host. Configuration YAML,
quiz JSON, prompt files, and '.env' files are UTF-8 by specification, so
that fallback silently mojibakes non-ASCII content on Windows: a file
holding 'Ada Lovelace's -- terse.' reads back mangled, with no exception
raised.

'ruff PLW1514' covers only the 'open()' form -- not 'read_text()' /
'write_text()' -- which is why this lives here rather than in the ruff
configuration. The behavioural regression tests for the underlying bug
live next to the code they cover, but those can only fail on a host
whose locale encoding is not UTF-8; this check has teeth on every
platform, because it rejects the *pattern* rather than waiting for a
mojibaked byte to reach an assertion.

Exits non-zero when any offending call is found.

Usage::

    python scripts/lint_textio.py
    python scripts/lint_textio.py --verbose
    python scripts/lint_textio.py src/soliplex/config tests/unit/foo.py
    python scripts/lint_textio.py --self-test
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from typing import NamedTuple

REPO_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_TARGET = REPO_DIR / "src" / "soliplex"

# 'pathlib.Path' text helpers, plus builtin 'open' / 'Path.open', and
# 'os.fdopen', which wraps a descriptor in a text stream by default.
TEXT_IO_NAMES = frozenset(
    {"read_text", "write_text", "open", "fdopen"},
)

# Qualified calls whose trailing name collides with one above, but which
# do no text IO at all. 'os.open' is the POSIX 'open(2)' wrapper: it
# returns an integer file descriptor, takes flags rather than a mode
# string, and raises 'TypeError' if handed an 'encoding='.
NOT_TEXT_IO_QUALNAMES = frozenset({"os.open"})


class Finding(NamedTuple):
    """One text IO call made without an explicit 'encoding='."""

    label: str
    lineno: int
    end_lineno: int
    name: str

    def __str__(self) -> str:
        return f"{self.label}:{self.lineno}: {self.name}()"


def _call_name(node: ast.Call) -> str | None:
    """Return the called attribute / bare name, or 'None' if neither.

    A qualified call listed in 'NOT_TEXT_IO_QUALNAMES' returns 'None':
    matching on the trailing attribute alone cannot tell 'os.open' from
    the builtin 'open', and the former admits no 'encoding='.
    """
    func = node.func
    if isinstance(func, ast.Attribute):
        base = getattr(func.value, "id", None)

        if base is not None:
            if f"{base}.{func.attr}" in NOT_TEXT_IO_QUALNAMES:
                return None

        return func.attr

    return getattr(func, "id", None)


def _is_binary(node: ast.Call) -> bool:
    """True when a literal mode argument selects binary mode."""
    return any(
        isinstance(arg.value, str) and "b" in arg.value
        for arg in node.args
        if isinstance(arg, ast.Constant)
    )


def unencoded_text_io(source: str, label: str) -> list[Finding]:
    """Return a 'Finding' per offending call in 'source'.

    A call is reported when it names a text IO helper, passes no
    'encoding=', and carries no literal binary mode. A non-literal mode
    (e.g. 'path.open(mode)') is reported rather than assumed binary --
    the check prefers a false positive to a silent miss.
    """
    findings = []

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)

        if name not in TEXT_IO_NAMES:
            continue

        if any(kw.arg == "encoding" for kw in node.keywords):
            continue

        if _is_binary(node):
            continue

        findings.append(
            Finding(label, node.lineno, node.end_lineno or node.lineno, name)
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
    """The outcome of scanning a set of targets."""

    findings: list[Finding]
    errors: list[str]
    # Source text of each scanned file, keyed by its finding label.
    sources: dict[str, str]


def scan(targets: list[pathlib.Path]) -> Scan:
    """Scan every '*.py' file under 'targets'."""
    result = Scan([], [], {})

    for path in iter_sources(targets):
        label = _label(path)

        try:
            source = path.read_text(encoding="utf-8")
        except OSError as exc:
            result.errors.append(f"{label}: cannot read: {exc}")
            continue

        try:
            findings = unencoded_text_io(source, label)
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
        f"\nlint_textio: {len(findings)} text IO call(s) without "
        "'encoding='; the host locale encoding ('cp1252' on Windows) "
        'applies instead -- pass encoding="utf-8".',
        file=sys.stderr,
    )


# Every form the check must catch, and every form it must let through.
# Line numbers are asserted on below, so keep the layout stable.
SELF_TEST_SOURCE = """\
import os
import pathlib

path = pathlib.Path("f")
data = "x"
mode = "rb"
fd = 0

path.read_text()
path.read_text(encoding="utf-8")
path.write_text(data)
path.write_text(data, encoding="utf-8")
path.open()
path.open("rb")
path.open(mode)
open("f")
os.open("f", os.O_RDONLY)
os.fdopen(fd)
os.fdopen(fd, "rb")
len("not file io")
path.write_text(
    data,
    newline="\\n",
)
"""

SELF_TEST_EXPECTED = [
    Finding("self-test", 9, 9, "read_text"),
    Finding("self-test", 11, 11, "write_text"),
    Finding("self-test", 13, 13, "open"),
    # Non-literal mode: reported rather than assumed binary.
    Finding("self-test", 15, 15, "open"),
    # Builtin, not a method.
    Finding("self-test", 16, 16, "open"),
    # 'os.open' on line 17 is absent: a POSIX descriptor call, which
    # takes no 'encoding='. 'os.fdopen' below it is text IO by default.
    Finding("self-test", 18, 18, "fdopen"),
    # Multi-line call: spans lines 21-24.
    Finding("self-test", 21, 24, "write_text"),
]


def self_test(verbose: bool) -> int:
    """Check that the scan bites -- rather than passing by finding nothing.

    Returns '0' when the embedded source yields exactly the expected
    findings, '1' otherwise.
    """
    found = unencoded_text_io(SELF_TEST_SOURCE, "self-test")

    if found == SELF_TEST_EXPECTED:
        if verbose:
            for finding in found:
                print(finding, file=sys.stderr)
                for line in chunk(SELF_TEST_SOURCE, finding):
                    print(line, file=sys.stderr)

        print(
            f"lint_textio: self-test passed "
            f"({len(SELF_TEST_EXPECTED)} expected findings).",
            file=sys.stderr,
        )
        return 0

    missed = [one for one in SELF_TEST_EXPECTED if one not in found]
    spurious = [one for one in found if one not in SELF_TEST_EXPECTED]

    for finding in missed:
        print(f"lint_textio: self-test: missed {finding}", file=sys.stderr)

    for finding in spurious:
        print(f"lint_textio: self-test: spurious {finding}", file=sys.stderr)

    print(
        "\nlint_textio: self-test FAILED -- the check no longer reports "
        "what it is supposed to report.",
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
        help="Files or directories to scan (default: src/soliplex).",
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
        print(f"lint_textio: error: {error}", file=sys.stderr)

    if scanned.findings:
        report(scanned, args.verbose)

    return 1 if scanned.findings or scanned.errors else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
