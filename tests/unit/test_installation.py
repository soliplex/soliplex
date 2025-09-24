import contextlib
from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import convos
from soliplex import installation

KEY = "test-key"
VALUE = "test-value"
DEFAULT = "test-default"


@pytest.mark.parametrize("w_default", [False, True])
def test_installation_get_environment(w_default):
    i_config = mock.create_autospec(config.InstallationConfig)
    the_installation = installation.Installation(i_config)

    kwargs = {}

    if w_default:
        kwargs["default"] = DEFAULT

    found = the_installation.get_environment(KEY, **kwargs)

    assert found is i_config.get_environment.return_value

    if w_default:
        i_config.get_environment.assert_called_once_with(KEY, DEFAULT)
    else:
        i_config.get_environment.assert_called_once_with(KEY, None)


@pytest.mark.parametrize("w_oidc_configs", [[], [object()]])
def test_installation_auth_disabled(w_oidc_configs):
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.oidc_auth_system_configs = w_oidc_configs

    the_installation = installation.Installation(i_config)

    assert the_installation.auth_disabled == (not w_oidc_configs)


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


@pytest.mark.parametrize("w_room_id, raises", [
    ("room_id", False),
    ("nonesuch", True)
])
def test_installation_get_room_config(w_room_id, raises):
    r_config = mock.create_autospec(config.RoomConfig)
    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_room_config(w_room_id, test_user)
    else:
        found = the_installation.get_room_config(w_room_id, test_user)

        assert found is r_config


def test_installation_get_completion_configs():
    c_config = mock.create_autospec(config.CompletionConfig)
    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    assert the_installation.get_completion_configs(test_user) == c_configs


@pytest.mark.parametrize("w_completion_id, raises", [
    ("completion_id", False),
    ("nonesuch", True)
])
def test_installation_get_completion_config(w_completion_id, raises):
    c_config = mock.create_autospec(config.CompletionConfig)
    c_configs = {"completion_id": c_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = c_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_completion_config(
                w_completion_id, test_user,
            )
    else:
        found = the_installation.get_completion_configs(test_user)

        assert found is c_configs


@pytest.mark.parametrize("w_room_id, raises", [
    ("room_id", False),
    ("nonesuch", True)
])
@mock.patch("soliplex.agents.get_agent_from_configs")
def test_installation_get_agent_for_room(gafc, w_room_id, raises):
    a_config = mock.create_autospec(config.AgentConfig)

    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    mcp_stdio_config = mock.create_autospec(
        config.Stdio_MCP_ClientToolsetConfig
    )
    mcp_http_streaming_config = mock.create_autospec(
        config.HTTP_MCP_ClientToolsetConfig
    )

    r_config = mock.create_autospec(config.RoomConfig)
    r_config.agent_config = a_config
    t_configs = r_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }
    mcp_configs = r_config.mcp_client_toolset_configs = {
        "test_stdio": mcp_stdio_config,
        "test_http": mcp_http_streaming_config,
    }

    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_agent_for_room(w_room_id, test_user)
    else:
        found = the_installation.get_agent_for_room(w_room_id, test_user)
        assert found is gafc.return_value
        gafc.assert_called_once_with(a_config, t_configs, mcp_configs)


@pytest.mark.parametrize("w_completion_id, raises", [
    ("completion_id", False),
    ("nonesuch", True)
])
@mock.patch("soliplex.agents.get_agent_from_configs")
def test_installation_get_agent_for_completion(gafc, w_completion_id, raises):
    a_config = mock.create_autospec(config.AgentConfig)

    tc_config = mock.create_autospec(config.ToolConfig)
    sdtc_config = mock.create_autospec(config.SearchDocumentsToolConfig)

    mcp_stdio_config = mock.create_autospec(
        config.Stdio_MCP_ClientToolsetConfig
    )
    mcp_http_streaming_config = mock.create_autospec(
        config.HTTP_MCP_ClientToolsetConfig
    )

    r_config = mock.create_autospec(config.RoomConfig)
    r_config.agent_config = a_config
    t_configs = r_config.tool_configs = {
        "test_tool": tc_config,
        "test_sdtc": sdtc_config,
    }
    mcp_configs = r_config.mcp_client_toolset_configs = {
        "test_stdio": mcp_stdio_config,
        "test_http": mcp_http_streaming_config,
    }

    r_configs = {"completion_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.completion_configs = r_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_agent_for_completion(
                w_completion_id, test_user,
            )
    else:
        found = the_installation.get_agent_for_completion(
            w_completion_id, test_user,
        )
        assert found is gafc.return_value
        gafc.assert_called_once_with(a_config, t_configs, mcp_configs)


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

    the_convos = found[0]["the_convos"]
    assert isinstance(the_convos, convos.Conversations)
