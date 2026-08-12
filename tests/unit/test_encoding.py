"""Guard against locale-dependent text file IO in 'src/soliplex/'.

Text-mode 'read_text()' / 'write_text()' / 'open()' without an explicit
'encoding=' fall back to 'locale.getpreferredencoding(False)' -- UTF-8
on Linux, but 'cp1252' on a typical Windows host. Configuration YAML,
quiz JSON, prompt files, and '.env' files are UTF-8 by specification, so
that fallback silently mojibakes non-ASCII content on Windows: a file
holding 'Ada Lovelace’s — terse.' reads back as
'Ada Lovelaceâ€™s â€” terse.' with no exception raised.

The behavioural regression tests for this live next to the code they
cover (prompt files in 'config/test_config_agents.py', installation YAML
in 'config/test_config__utils.py', secrets in 'test_secrets.py'), but
those can only fail on a host whose locale encoding is not UTF-8. This
guard is the part with teeth on every platform: it rejects the *pattern*
rather than waiting for a mojibaked byte to reach an assertion.

'ruff PLW1514' covers only the 'open()' form -- not 'read_text()' /
'write_text()' -- which is why this is a test rather than a lint rule.
It deliberately scans 'src/' only; the test suite's own ~100 call sites
are a separate cleanup.
"""

import ast
import pathlib

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "soliplex"

# 'pathlib.Path' text helpers, plus builtin 'open' / 'Path.open'.
_TEXT_IO_NAMES = frozenset({"read_text", "write_text", "open"})


def _call_name(node: ast.Call) -> str | None:
    """Return the called attribute / bare name, or 'None' if neither."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr

    return getattr(func, "id", None)


def _is_binary(node: ast.Call) -> bool:
    """True when a literal mode argument selects binary mode."""
    return any(
        isinstance(arg.value, str) and "b" in arg.value
        for arg in node.args
        if isinstance(arg, ast.Constant)
    )


def unencoded_text_io(source: str, label: str) -> list[str]:
    """Return a '<label>:<lineno>: <call>()' line per offending call.

    A call is reported when it names a text IO helper, passes no
    'encoding=', and carries no literal binary mode. A non-literal mode
    (e.g. 'path.open(mode)') is reported rather than assumed binary --
    the guard prefers a false positive to a silent miss.
    """
    findings = []

    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue

        name = _call_name(node)

        if name not in _TEXT_IO_NAMES:
            continue

        if any(kw.arg == "encoding" for kw in node.keywords):
            continue

        if _is_binary(node):
            continue

        findings.append(f"{label}:{node.lineno}: {name}()")

    return findings


def test_src_has_no_unencoded_text_io():
    findings = []

    for path in sorted(_SRC.rglob("*.py")):
        findings.extend(
            unencoded_text_io(
                path.read_text(encoding="utf-8"),
                path.relative_to(_REPO_ROOT).as_posix(),
            )
        )

    assert not findings, (
        "text IO without 'encoding=' falls back to the host locale "
        "encoding ('cp1252' on Windows); pass encoding=\"utf-8\":\n"
        + "\n".join(findings)
    )


# Line numbers below are asserted on, so keep the layout stable.
_SYNTHETIC_SOURCE = """\
import pathlib

path = pathlib.Path("f")
data = "x"
mode = "rb"

path.read_text()
path.read_text(encoding="utf-8")
path.write_text(data)
path.write_text(data, encoding="utf-8")
path.open()
path.open("rb")
path.open(mode)
open("f")
len("not file io")
"""


def test_guard_detects_every_offending_form():
    """The guard must actually bite -- not pass because it found nothing."""
    found = unencoded_text_io(_SYNTHETIC_SOURCE, "synthetic")

    assert found == [
        "synthetic:7: read_text()",
        "synthetic:9: write_text()",
        "synthetic:11: open()",
        "synthetic:13: open()",  # non-literal mode
        "synthetic:14: open()",  # builtin, not a method
    ]
