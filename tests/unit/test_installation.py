from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import installation


def test_installation_oidc_auth_system_configs():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    assert (
        the_installation.oidc_auth_system_configs is
        i_config.oidc_auth_system_configs
    )


def test_installation_get_room_configs():
    r_config = mock.create_autospec(config.RoomConfig)
    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    assert the_installation.get_room_configs(test_user) == r_configs


def test_installation_get_completion_configs():
    c_config = mock.create_autospec(config.CompletionConfig)
    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    assert the_installation.get_completion_configs(test_user) == c_configs


@pytest.mark.anyio
async def test_get_the_installation():
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)
    request = mock.create_autospec(fastapi.Request)
    request.state.the_installation = the_installation

    found = await installation.get_the_installation(request)

    assert found is the_installation


@pytest.mark.anyio
@mock.patch("soliplex.config.load_installation")
async def test_lifespan(lc):
    INSTALLATION_PATH = "/path/to/installation"
    i_config = mock.create_autospec(config.InstallationConfig)
    lc.return_value = i_config
    app = mock.create_autospec(fastapi.FastAPI)

    found = [
        item async for item in installation.lifespan(app, INSTALLATION_PATH)
    ]

    assert len(found) == 1

    the_installation = found[0]["the_installation"]
    assert isinstance(the_installation, installation.Installation)
    assert the_installation._config is i_config

    i_config.reload_configurations.assert_called_once_with()

    lc.assert_called_once_with(INSTALLATION_PATH)
