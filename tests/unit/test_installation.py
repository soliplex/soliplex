import contextlib
from unittest import mock

import fastapi
import pytest

from soliplex import config
from soliplex import convos
from soliplex import installation
from soliplex import secrets

KEY = "test-key"
VALUE = "test-value"
DEFAULT = "test-default"

SECRET_NAME_1 = "TEST_SECRET"
SECRET_NAME_2 = "OTHER_SECRET"
SECRET_CONFIG_1 = config.SecretConfig(SECRET_NAME_1)
SECRET_CONFIG_2 = config.SecretConfig(SECRET_NAME_2)
MISS_ERROR = object()
OLLAMA_BASE_URL = "http://ollama.example.com:11434"

NoSuchSecret = pytest.raises(KeyError)
RaisesSecretError = pytest.raises(secrets.SecretError)
NoRaise = contextlib.nullcontext()


@pytest.mark.parametrize(
    "secrets_map, expectation",
    [
        ({}, NoSuchSecret),
        ({SECRET_NAME_1: SECRET_CONFIG_1}, NoRaise),
    ],
)
@mock.patch("soliplex.secrets.get_secret")
def test_installation_get_secret(gs, secrets_map, expectation):
    i_config = mock.create_autospec(
        config.InstallationConfig,
        secrets_map=secrets_map,
    )
    the_installation = installation.Installation(i_config)

    with mock.patch("os.environ", clear=True):
        with expectation as expected:
            found = the_installation.get_secret(SECRET_NAME_1)

    if expected is None:
        assert found is gs.return_value
        gs.assert_called_once_with(SECRET_CONFIG_1)
    else:
        gs.assert_not_called()


@pytest.mark.parametrize(
    "secret_configs, expectation",
    [
        ((), NoRaise),
        ([SECRET_CONFIG_1], RaisesSecretError),
        ([SECRET_CONFIG_1, SECRET_CONFIG_2], RaisesSecretError),
    ],
)
@mock.patch("soliplex.secrets.resolve_secrets")
def test_installation_resolve_secrets(srs, secret_configs, expectation):
    i_config = mock.create_autospec(
        config.InstallationConfig,
    )
    i_config.secrets = secret_configs
    the_installation = installation.Installation(i_config)

    with expectation as expected:
        if expected is not None:
            srs.side_effect = secrets.SecretError("testing")

        the_installation.resolve_secrets()

    srs.assert_called_once_with(secret_configs)


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


@pytest.mark.parametrize("w_raise", [False, True])
def test_installation_resolve_environment(w_raise):
    i_config = mock.create_autospec(config.InstallationConfig)

    if w_raise:
        i_config.resolve_environment.side_effect = config.MissingEnvVars(
            "test1,test2",
            [
                config.MissingEnvVar("test1"),
                config.MissingEnvVar("test2"),
            ],
        )
    else:
        i_config.resolve_environment.return_value = None

    the_installation = installation.Installation(i_config)

    if w_raise:
        with pytest.raises(config.MissingEnvVars):
            the_installation.resolve_environment()
    else:
        the_installation.resolve_environment()


def test_installation_configure_haiku_rag():
    from haiku.rag import config as hr_config

    copied = hr_config.Config.model_copy()

    i_config = mock.create_autospec(
        config.InstallationConfig,
        environment={"OLLAMA_BASE_URL": OLLAMA_BASE_URL},
    )
    the_installation = installation.Installation(i_config)

    with mock.patch("haiku.rag.config.Config", copied):
        the_installation.configure_haiku_rag()

    # Check that the 'haiku.rag.config.Config' object was reconfigured
    # using our config's environment.
    assert copied.OLLAMA_BASE_URL == OLLAMA_BASE_URL


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
        the_installation.oidc_auth_system_configs
        is i_config.oidc_auth_system_configs
    )


def test_installation_get_room_configs():
    r_config = mock.create_autospec(config.RoomConfig)
    r_configs = {"room_id": r_config}
    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.room_configs = r_configs
    test_user = {"name": "test"}

    the_installation = installation.Installation(i_config)

    assert the_installation.get_room_configs(test_user) == r_configs


@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
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


@pytest.mark.parametrize(
    "w_completion_id, raises", [("completion_id", False), ("nonesuch", True)]
)
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
                w_completion_id,
                test_user,
            )
    else:
        found = the_installation.get_completion_configs(test_user)

        assert found is c_configs


@pytest.mark.parametrize(
    "w_agent_id, raises", [("agent_id", False), ("nonesuch", True)]
)
@mock.patch("soliplex.agents.get_agent_from_configs")
def test_installation_get_agent_by_id(gafc, w_agent_id, raises):
    a_config = mock.create_autospec(config.AgentConfig)

    i_config = mock.create_autospec(config.InstallationConfig)
    i_config.agent_configs_map = {"agent_id": a_config}

    the_installation = installation.Installation(i_config)

    if raises:
        with pytest.raises(KeyError):
            the_installation.get_agent_by_id(w_agent_id)
    else:
        found = the_installation.get_agent_by_id(w_agent_id)
        assert found is gafc.return_value
        gafc.assert_called_once_with(a_config, {}, {})


@pytest.mark.parametrize(
    "w_room_id, raises", [("room_id", False), ("nonesuch", True)]
)
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


@pytest.mark.parametrize(
    "w_completion_id, raises", [("completion_id", False), ("nonesuch", True)]
)
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
                w_completion_id,
                test_user,
            )
    else:
        found = the_installation.get_agent_for_completion(
            w_completion_id,
            test_user,
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


def _mock_mcp_app(key):
    async def _mock_lifespan(_ignored):
        yield None

    result = mock.MagicMock(spec_set=["lifespan"])
    result.lifespan = contextlib.asynccontextmanager(_mock_lifespan)
    return result


@pytest.fixture
def mcp_apps():
    return {key: _mock_mcp_app(key) for key in ["room1", "room2"]}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_no_auth_mode, exp_oidc_paths",
    [
        (None, ["oidc"]),
        (False, ["oidc"]),
        (True, []),
    ],
)
@mock.patch("soliplex.secrets.resolve_secrets")
@mock.patch("soliplex.mcp_server.setup_mcp_for_rooms")
@mock.patch("soliplex.config.load_installation")
async def test_lifespan(
    load_installation,
    smfr,
    srs,
    mcp_apps,
    w_no_auth_mode,
    exp_oidc_paths,
):
    from haiku.rag import config as hr_config

    copied = hr_config.Config.model_copy()

    INSTALLATION_PATH = "/path/to/installation"

    smfr.return_value = mcp_apps

    i_config = mock.create_autospec(
        config.InstallationConfig,
        secrets=(),
        oidc_paths=["oidc"],
        environment={"OLLAMA_BASE_URL": OLLAMA_BASE_URL},
    )
    load_installation.return_value = i_config
    app = mock.create_autospec(fastapi.FastAPI)

    kwargs = {}
    if w_no_auth_mode is not None:
        kwargs["no_auth_mode"] = w_no_auth_mode

    with mock.patch("haiku.rag.config.Config", copied):
        found = [
            item
            async for item in installation.lifespan(
                app,
                INSTALLATION_PATH,
                **kwargs,
            )
        ]

    # Check that the 'haiku.rag.config.Config' object was reconfigured
    # using our config's environment.
    assert copied.OLLAMA_BASE_URL == OLLAMA_BASE_URL

    assert len(found) == 1

    the_installation = found[0]["the_installation"]
    assert isinstance(the_installation, installation.Installation)
    assert the_installation._config is i_config

    assert i_config.oidc_paths == exp_oidc_paths

    i_config.reload_configurations.assert_called_once_with()

    load_installation.assert_called_once_with(INSTALLATION_PATH)

    the_convos = found[0]["the_convos"]
    assert isinstance(the_convos, convos.Conversations)

    for f_call, (key, mcp_app) in zip(
        app.mount.call_args_list,
        mcp_apps.items(),
        strict=True,
    ):
        assert f_call.args == ("/mcp/" + key, mcp_app)

    srs.assert_called_once_with(the_installation._config.secrets)
    smfr.assert_called_once_with(the_installation)
