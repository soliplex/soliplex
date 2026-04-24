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
    access the 'skill_configs' / 'available_*_skill_configs' properties
    without pre-seeding '_available_*_skill_configs'. Without the stub
    those property accesses would call 'hs_discovery.discover_from_paths'
    / 'discover_from_entrypoints' against the real environment.

    Yields a dict of the two loader mocks so tests may assert on call
    behavior (e.g. 'loaders["_load_filesystem_skill_configs"]
    .assert_not_called()').
    """
    loaders = {
        "_load_filesystem_skill_configs": mock.Mock(return_value={}),
        "_load_entrypoint_skill_configs": mock.Mock(return_value={}),
    }
    with mock.patch.multiple(config_installation, **loaders):
        yield loaders
