import pathlib
import tempfile
from unittest import mock

import pytest

from soliplex.agui import features as agui_features
from soliplex.config import agents as config_agents
from soliplex.config import agui as config_agui
from soliplex.config import authsystem as config_authsystem
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

AGUI_FEATURE_NAME = "test-agui-feature"


def _auth_systems(n_auth_systems):
    return [
        config_authsystem.OIDCAuthSystemConfig(
            id=f"auth-system-{i_auth_system}",
            title=f"Auth System #{i_auth_system}",
            token_validation_pem=f"PEM {i_auth_system:3d}",
            server_url=f"http://auth{i_auth_system:03}.example.com/",
            client_id=f"AUTH_SYSTEM_{i_auth_system:03}",
        )
        for i_auth_system in range(n_auth_systems)
    ]


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td)


@pytest.fixture(params=[0, 1, 2])
def with_auth_systems(request):
    return _auth_systems(request.param)


@pytest.fixture
def the_agui_feature():
    return config_agui.AGUI_Feature(
        name=AGUI_FEATURE_NAME,
        model_klass=agui_features.EmptyFeatureModel,
        source=config_agui.AGUI_FeatureSource.CLIENT,
    )


@pytest.fixture
def patched_agui_features():
    with mock.patch.dict(config_agui.__dict__) as patched:
        registry = patched["AGUI_FEATURES_BY_NAME"] = {}

        yield registry


@pytest.fixture
def patched_tool_registries():
    with mock.patch.dict(config_tools.__dict__) as patched:
        patched["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"] = {}
        patched["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"] = {}
        patched["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"] = {}
        yield patched


@pytest.fixture
def patched_tool_configs(patched_tool_registries):
    return patched_tool_registries["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"]


@pytest.fixture
def patched_mcp_toolset_configs(patched_tool_registries):
    return patched_tool_registries["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"]


@pytest.fixture
def patched_mcp_tool_wrappers(patched_tool_registries):
    return patched_tool_registries["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"]


@pytest.fixture
def patched_soliplex_config():
    from soliplex import config

    with mock.patch.dict(config.__dict__, patched_for_testing=True) as patched:
        yield patched


@pytest.fixture
def patched_skill_configs():
    with mock.patch.dict(config_skills.__dict__) as patched:
        result = patched["SKILL_CONFIG_CLASSES_BY_KIND"] = {}

        yield result


@pytest.fixture
def patched_agent_configs():
    with mock.patch.dict(config_agents.__dict__) as patched:
        result = patched["AGENT_CONFIG_CLASSES_BY_KIND"] = {}

        yield result


@pytest.fixture
def patched_secret_getters():
    with mock.patch.dict(config_secrets.__dict__) as patched:
        result = patched["SECRET_GETTERS_BY_KIND"] = {}

        yield result
