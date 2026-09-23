from __future__ import annotations

from unittest import mock

import pytest
import typer

from soliplex import installation
from soliplex.config import installation as config_installation


@pytest.fixture
def ctx():
    return mock.create_autospec(typer.Context, obj={})


@pytest.fixture
def installation_path(tmp_path):
    installation_path = tmp_path / "installation.yaml"
    installation_path.write_text("id: test")
    return installation_path


@pytest.fixture
def the_installation() -> installation.Installation:
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    return installation.Installation(_config=i_config)
