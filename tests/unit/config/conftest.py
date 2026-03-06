from unittest import mock

import pytest

from soliplex import config


@pytest.fixture
def installation_config():
    return mock.create_autospec(config.InstallationConfig)
