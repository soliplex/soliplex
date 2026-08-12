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

import pytest

from tests._dburi import sqlite_dburi


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
