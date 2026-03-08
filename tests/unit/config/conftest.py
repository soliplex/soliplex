from unittest import mock

import pytest

from soliplex.config import installation as config_installation


@pytest.fixture
def installation_config():
    return mock.create_autospec(config_installation.InstallationConfig)
