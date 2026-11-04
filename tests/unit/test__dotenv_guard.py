import warnings
from unittest import mock

import _dotenv_guard
import pytest


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    return root


def test_guard_load_dotenv_w_repo_dotenv(repo_root):
    dotenv_path = repo_root / ".env"
    dotenv_path.write_text("KEY=value\n", encoding="utf-8")
    load_dotenv = mock.Mock()
    guarded = _dotenv_guard.guard_load_dotenv(load_dotenv, repo_root)

    with pytest.warns(
        _dotenv_guard.RepoDotenvIgnoredWarning,
        match=r"unit tests ignore .*\.env",
    ):
        found = guarded(dotenv_path)

    assert found is None
    load_dotenv.assert_not_called()


def test_guard_load_dotenv_w_repo_path_wo_file(repo_root):
    load_dotenv = mock.Mock()
    guarded = _dotenv_guard.guard_load_dotenv(load_dotenv, repo_root)

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        found = guarded(repo_root / ".env")

    assert found is None
    load_dotenv.assert_not_called()


def test_guard_load_dotenv_w_outside_path(tmp_path, repo_root):
    dotenv_path = tmp_path / ".env"
    load_dotenv = mock.Mock()
    guarded = _dotenv_guard.guard_load_dotenv(load_dotenv, repo_root)

    found = guarded(dotenv_path)

    assert found is load_dotenv.return_value
    load_dotenv.assert_called_once_with(dotenv_path)
