from unittest import mock

import pytest

from soliplex.config import installation as config_installation


@pytest.fixture
def installation_config():
    return mock.create_autospec(config_installation.InstallationConfig)


@pytest.fixture
def no_skill_discovery():
    """Stub installation skill-discovery loaders to return empty maps.

    Opt-in fixture for tests that construct an 'InstallationConfig' and
    access the 'skill_configs' / 'available_filesystem_skill_configs'
    properties without pre-seeding the discovery cache. Without the stub,
    those property accesses would scan the real environment.

    Yields a dict containing the loader mock so tests may assert on call
    behavior (e.g. 'loaders["_load_filesystem_skill_configs"]
    .assert_not_called()').
    """
    loaders = {
        "_load_filesystem_skill_configs": mock.Mock(return_value={}),
    }
    with mock.patch.multiple(config_installation, **loaders):
        yield loaders
