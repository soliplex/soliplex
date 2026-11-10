from unittest import mock

import _dotenv_guard
import pytest


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "checkout"
    root.mkdir()
    return root


@pytest.mark.parametrize("w_file", [False, True])
def test_guard_load_dotenv_w_repo_path(repo_root, w_file):
    dotenv_path = repo_root / ".env"

    if w_file:
        dotenv_path.write_text("KEY=value\n", encoding="utf-8")

    load_dotenv = mock.Mock()
    guarded = _dotenv_guard.guard_load_dotenv(load_dotenv, repo_root)

    with pytest.raises(pytest.fail.Exception):
        guarded(dotenv_path)

    load_dotenv.assert_not_called()


def test_guard_load_dotenv_w_outside_path(tmp_path, repo_root):
    dotenv_path = tmp_path / ".env"
    load_dotenv = mock.Mock()
    guarded = _dotenv_guard.guard_load_dotenv(load_dotenv, repo_root)

    found = guarded(dotenv_path)

    assert found is load_dotenv.return_value
    load_dotenv.assert_called_once_with(dotenv_path)
