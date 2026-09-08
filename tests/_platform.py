"""Platform capability probes for tests needing a POSIX backend.

Soliplex sandboxes run on Linux, so a handful of unit tests exercise
behaviour the standard library offers only on POSIX hosts: 'O_NOFOLLOW'
opens, FIFOs, and symlinks. Nothing here changes what those tests
assert -- on Linux they run exactly as they did. On a host which cannot
express the precondition (Windows, most obviously) the test warns and
skips, rather than failing on an 'AttributeError' or a 'WinError 1314'.

Each 'requires_*' helper is called from inside the test that needs it,
so the warning names the skipped test instead of firing once at import
time. 'HAVE_*' is the same answer as a plain boolean, for a test which
must decide per parameter rather than skip outright.

This module lives in 'tests/', not 'tests/unit/', on purpose: the
coverage targets in 'pyproject.toml' include 'tests/unit', and a probe
whose branches are by definition unreachable on whichever platform is
running could never satisfy the 100% gate.
"""

import os
import pathlib
import tempfile
import warnings

import pytest


class UnsupportedPlatformWarning(UserWarning):
    """A test was skipped: the host cannot express its precondition."""


def _probe_symlinks() -> bool:
    """Report whether this host lets the test user create a symlink

    Windows does, but only for an administrator or with Developer Mode
    turned on, so 'os.name' alone does not answer it -- make one and
    see.
    """
    with tempfile.TemporaryDirectory() as td:
        temp_path = pathlib.Path(td)
        target = temp_path / "probe-target"
        target.write_text("probe", encoding="utf-8")

        try:
            (temp_path / "probe-link").symlink_to(target)
        except (OSError, NotImplementedError):
            return False
        else:
            return True


HAVE_SYMLINKS = _probe_symlinks()
HAVE_MKFIFO = hasattr(os, "mkfifo")
HAVE_O_NOFOLLOW = hasattr(os, "O_NOFOLLOW")


def _warn_and_skip(reason: str) -> None:
    warnings.warn(reason, UnsupportedPlatformWarning, stacklevel=3)
    pytest.skip(reason)


def requires_symlinks() -> None:
    """Skip unless this host can create a symlink"""
    if not HAVE_SYMLINKS:
        _warn_and_skip(
            "needs symlinks: this host refuses to create one (on Windows, "
            "run as an administrator or enable Developer Mode)"
        )


def requires_mkfifo() -> None:
    """Skip unless this host has 'os.mkfifo'"""
    if not HAVE_MKFIFO:
        _warn_and_skip("needs FIFOs: 'os.mkfifo' is POSIX-only")


def requires_o_nofollow() -> None:
    """Skip unless 'os.open' accepts the POSIX-only 'O_NOFOLLOW'"""
    if not HAVE_O_NOFOLLOW:
        _warn_and_skip("needs a no-follow open: 'os.O_NOFOLLOW' is POSIX-only")


def requires_posix_paths() -> None:
    """Skip unless 'pathlib' resolves paths the POSIX way

    'PosixPath.resolve' rejects an embedded NUL with 'ValueError';
    'WindowsPath.resolve' returns a path nothing can open. Code relying
    on the former to reject a name has nothing to assert on Windows.
    """
    if os.name != "posix":
        _warn_and_skip(
            "needs POSIX path resolution: 'pathlib' on this host does not "
            "raise on the paths the test feeds it"
        )
