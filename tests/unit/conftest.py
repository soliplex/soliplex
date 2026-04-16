import pathlib
import tempfile
from unittest import mock

import _test_features as agui_features
import httpx
import pytest

from soliplex import authz as authz_package
from soliplex.config import agents as config_agents
from soliplex.config import agui as config_agui
from soliplex.config import authsystem as config_authsystem
from soliplex.config import routing as config_routing
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

# ---------------------------------------------------------------------------
# LTI shared test constants
# ---------------------------------------------------------------------------

LTI_TEST_ISSUER = "https://moodle.example.com"
LTI_TEST_CLIENT_ID = "soliplex-lti-tool"
LTI_TEST_PLATFORM_ID = "moodle-workplace"
LTI_TEST_DEFAULT_ROOM = "moodle-tools"


# ---------------------------------------------------------------------------
# Moodle shared test helpers
# ---------------------------------------------------------------------------


def mock_moodle_response(json_data, status_code=200):
    """Create a mock httpx.Response for Moodle API tests."""
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=mock.MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def patch_moodle_httpx(response):
    """Context manager to patch httpx.AsyncClient for Moodle tests."""
    mock_client = mock.AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    return mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    )


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


@pytest.fixture(scope="module")
def anyio_backend():
    """Run anyio-marked tests on asyncio only (no trio)."""
    return "asyncio"


@pytest.fixture
def temp_dir() -> pathlib.Path:
    with tempfile.TemporaryDirectory() as td:
        yield pathlib.Path(td).resolve()


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
def patched_app_routers():
    with mock.patch.dict(config_routing.__dict__) as patched:
        registry = patched["APP_ROUTERS_BY_GROUP_NAME"] = {}

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
def patched_agent_capabilities():
    with mock.patch.dict(config_agents.__dict__) as patched:
        registry = patched["AGENT_CAPABILITY_CLASSES_BY_NAME"] = {}

        yield registry


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


@pytest.fixture
def patched_jsonpath_functions():
    env = authz_package.the_jsonpath_environment
    with mock.patch.dict(env.function_extensions) as registry:
        yield registry
