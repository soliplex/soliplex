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

from tests import _platform
from tests._dburi import sqlite_dburi

COVERAGE_NOT_REPORTED = (
    "coverage is not reported for the POSIX-only sandbox on this host: "
    "the tests covering it skip here (see 'tests/_platform.py'), so "
    "these are omitted from the report rather than dropping the 100% "
    "gate for everything else -- re-check them on Linux: {omitted}"
)


def _cov_config_objects(config):
    """The 'CoverageConfig' objects the report at the end will consult

    pytest-cov measures with one 'Coverage' and reports with another:
    'CovController.finish' swaps in the 'combining_cov' it built at
    start-up. Both are already constructed by the time 'pytest_configure'
    runs, and neither is reachable through 'config.option', so hand back
    whichever of them this run has.
    """
    cov_plugin = config.pluginmanager.get_plugin("_cov")

    if cov_plugin is None:  # coverage not installed
        return []

    if cov_plugin.cov_controller is None:  # '--no-cov'
        return []

    controller = cov_plugin.cov_controller

    covs = (
        getattr(controller, "cov", None),
        getattr(controller, "combining_cov", None),
    )
    return [cov.config for cov in covs if cov is not None]


def pytest_configure(config):
    """Stop reporting coverage of what the platform skips off POSIX

    'addopts' applies '--cov-fail-under=100' to every run. The tests of
    the bubblewrap sandbox skip on a host which cannot express their
    preconditions, leaving the code they cover unmeasured -- so the gate
    would fail however the tests themselves fared.

    Omit those modules, and the test modules that skipped, from the
    report instead: the 100% gate then still means 100% of everything
    this host can measure. The omission is a 'report' one rather than a
    'run' one because measurement has already begun by now; it also
    keeps the data file complete, so a later 'coverage report' can still
    be pointed at it.
    """
    if _platform.HAVE_POSIX_SANDBOX:
        return

    omit = list(_platform.POSIX_ONLY_COVERAGE_OMIT)
    cov_configs = _cov_config_objects(config)

    for cov_config in cov_configs:
        cov_config.report_omit = [*(cov_config.report_omit or []), *omit]

    # Every xdist worker runs this hook too, but only the controller
    # prints a report -- warn where the caveat can be read next to the
    # numbers it applies to.
    if cov_configs and not hasattr(config, "workerinput"):
        config.issue_config_time_warning(
            _platform.UnsupportedPlatformWarning(
                COVERAGE_NOT_REPORTED.format(omitted=", ".join(omit)),
            ),
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
