"""Fixtures shared by 'tests/unit' and 'tests/functional'.

pytest loads the 'conftest.py' of every parent directory of a test, so
definitions here reach both suites. Definitions in
'tests/unit/conftest.py' reach only 'tests/unit' and below.

These are function-scoped, because 'tmp_path' is. A module- or
session-scoped fixture cannot request them (pytest raises
'ScopeMismatch'); such a fixture should build its own path from
'tmp_path_factory' and call 'tests._dburi.sqlite_dburi' directly, as
'tests/unit/cli/conftest.py' does.
"""

import os

import pytest

from tests._dburi import sqlite_dburi
from tests._platform import UnsupportedPlatformWarning

COVERAGE_NOT_ENFORCED = (
    "coverage is not gated on a non-POSIX host: the tests covering the "
    "POSIX-only sandbox paths skip here, so '--cov-fail-under' has been "
    "relaxed to 0 for this run. The 100% gate is enforced on Linux (and "
    "in CI); re-check coverage there before relying on it."
)


def pytest_configure(config):
    """Relax the coverage gate where platform skips make it unmeetable

    'addopts' applies '--cov-fail-under=100' to every run. On a host
    which cannot express the POSIX preconditions a few tests need (see
    'tests/_platform.py'), those tests skip, and the lines they cover
    go unmeasured -- so the gate fails however the tests themselves
    fared. Drop the threshold there, loudly, and leave POSIX hosts
    (CI included) alone.
    """
    if os.name == "posix":
        return

    # pytest-cov reads its threshold from the namespace it captured in
    # 'pytest_load_initial_conftests' ('known_args_namespace'), not from
    # 'config.option', so reach the registered plugin's own copy.
    cov_plugin = config.pluginmanager.get_plugin("_cov")

    if cov_plugin is None:  # '--no-cov', or coverage not installed
        return

    if not getattr(cov_plugin.options, "cov_fail_under", None):
        return

    cov_plugin.options.cov_fail_under = 0
    config.issue_config_time_warning(
        UnsupportedPlatformWarning(COVERAGE_NOT_ENFORCED),
        stacklevel=2,
    )


@pytest.fixture
def authz_db_path(tmp_path):
    """The scratch authz sqlite file an installation is repointed at.

    Derived from the per-test 'tmp_path', so a fixture that rewrites a
    config and a test that seeds rows directly resolve to the same file
    -- letting a test create state the CLI cannot (e.g. an ACL entry
    whose stored 'json_path' no longer compiles).
    """
    return tmp_path / "authz.sqlite"


@pytest.fixture
def authz_dburi_sync(authz_db_path):
    """Synchronous 'sqlite:///' URI for 'authz_db_path'."""
    return sqlite_dburi(authz_db_path)


@pytest.fixture
def authz_dburi_async(authz_db_path):
    """Asynchronous 'sqlite+aiosqlite:///' URI for 'authz_db_path'."""
    return sqlite_dburi(authz_db_path, "+aiosqlite")
