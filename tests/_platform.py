"""Platform gating for the tests of the POSIX-only sandbox.

Soliplex sandboxes a room's tool calls with bubblewrap, which exists
only on Linux: 'src/soliplex/skills/bwrap_sandbox/' drives 'bwrap'
itself, and 'src/soliplex/views/sandbox_workdirs.py' serves the workdir
tree it leaves behind, guarding the walk with an 'O_NOFOLLOW' open.

Their tests build the same preconditions the machinery does -- a
symlink, a FIFO, a name with an embedded NUL that 'PosixPath.resolve'
rejects -- so on a host offering none of them there is nothing left to
assert. Rather than skip test by test, each module skips whole: mark it
with 'requires_posix_sandbox' and name it (with the module it covers)
in 'POSIX_ONLY_COVERAGE_OMIT', which 'tests/conftest.py' drops from the
coverage report so the 100% gate keeps its meaning off POSIX.

This module lives in 'tests/', not 'tests/unit/', on purpose: the
coverage targets in 'pyproject.toml' include 'tests/unit', and a
platform gate whose other branch is by definition unreachable on
whichever host is running could never satisfy the 100% gate.
'tests/_dburi.py' is the existing precedent.
"""

import os

import pytest


class UnsupportedPlatformWarning(UserWarning):
    """Something was skipped: the host cannot express its precondition."""


HAVE_POSIX_SANDBOX = os.name == "posix"

POSIX_ONLY_REASON = (
    "needs a POSIX host: the bubblewrap sandbox, and the workdir tree "
    "it leaves behind, are Linux-only, and so are the symlinks, FIFOs "
    "and NUL-rejecting path resolution these tests set up"
)

requires_posix_sandbox = pytest.mark.skipif(
    not HAVE_POSIX_SANDBOX,
    reason=POSIX_ONLY_REASON,
)

# The test modules 'requires_posix_sandbox' skips, plus the modules
# under test they are the only coverage for. Coverage patterns,
# relative to the repository root (see 'tests/conftest.py').
POSIX_ONLY_COVERAGE_OMIT = (
    "src/soliplex/skills/bwrap_sandbox/*",
    "src/soliplex/views/sandbox_workdirs.py",
    "tests/unit/skills/test_bwrap_sandbox.py",
    "tests/unit/views/test_sandbox_workdirs.py",
)
