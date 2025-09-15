import functools
import pathlib
from unittest import mock

import pytest

from soliplex import main

EXPLICIT_INST_PATH = "/explicit"
ENVIRON_INST_PATH = "/environ"


@pytest.fixture(scope="module", params=[None, EXPLICIT_INST_PATH])
def inst_path_kwargs(request):
    kw = {}
    if request.param is not None:
        kw["installation_path"] = request.param
    return kw


@pytest.mark.parametrize("env_patch", [
    {},
    {"SOLIPLEX_INSTALLATION_PATH": ENVIRON_INST_PATH},
])
def test_curry_lifespan(inst_path_kwargs, env_patch):

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        found = main.curry_lifespan(**inst_path_kwargs)

    assert isinstance(found, functools.partial)

    if inst_path_kwargs:
        expected = EXPLICIT_INST_PATH

    elif env_patch:
        expected = ENVIRON_INST_PATH

    else:
        expected = "./example"

    assert found.keywords == {
        "installation_path": pathlib.Path(expected),
    }
