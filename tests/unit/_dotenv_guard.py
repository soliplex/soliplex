"""Fail any unit test which would read a '.env' inside the checkout.

'InstallationConfig.from_dotenv' reads the '.env' beside the installation
config, falling back to one in the cwd -- under pytest, the repo root.
'tests/unit/conftest.py' wraps 'InstallationConfig._load_dotenv' with
'guard_load_dotenv' for the whole session:  loading any path inside the
checkout fails the test, whether or not the file exists.

A test whose installation config lives under a tmp dir writes a '.env'
(empty is fine) beside it, which stops the search before the cwd.
"""

import pathlib

import pytest

# 'tests/unit/_dotenv_guard.py' -> parents[2] is the repo root.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

REPO_DOTENV_REFUSED = (
    "unit tests must not read {path}: write a '.env' (empty is fine) "
    "beside the installation config, under 'tmp_path'."
)


def guard_load_dotenv(load_dotenv, repo_root: pathlib.Path):
    """Wrap 'load_dotenv' to fail on any path inside 'repo_root'"""

    def _load_dotenv(from_path: pathlib.Path):
        # Not 'pathlib.Path(from_path)':  some tests patch 'pathlib.Path'.
        resolved = from_path.resolve()

        if resolved.is_relative_to(repo_root):
            pytest.fail(REPO_DOTENV_REFUSED.format(path=resolved))

        return load_dotenv(from_path)

    return _load_dotenv
