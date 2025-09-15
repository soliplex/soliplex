import pathlib
import tempfile

import pytest


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td)
