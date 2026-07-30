import dataclasses
from unittest import mock

import pytest
from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import tools as ai_tools

from soliplex import agents
from soliplex import mcp_client
from soliplex import tools
from soliplex.config import agents as config_agents
from soliplex.config import installation as config_installation
from soliplex.config import tools as config_tools

SYSTEM_PROMPT = "You are a test"
MODEL_SETTINGS = {"temperature": 0.875}

ROOM_ID = "test-room"
RAG_LANCEDB_OVERRIDE_PATH = "/path/to/db/rag"
DOMAIN_PREAMBLE = "test domain preamble"

TOOL_ID = "test-tool-id"
AI_TOOL_PARAM_NAME = "test-ai-tool-param-name"

TC_TOOL_CONFIG = config_tools.ToolConfig(tool_name="soliplex.tools.test_tool")

STDIO_MCTC = config_tools.Stdio_MCP_ClientToolsetConfig(
    command="cat",
    args=["-"],
)
STDIO_TOOL = mock.sentinel.stdio_toolset

HTTP_MCTC = config_tools.HTTP_MCP_ClientToolsetConfig(
    url="https://example.com/mcp",
)
HTTP_TOOL = mock.sentinel.http_toolset

SSE_MCTC = config_tools.SSE_MCP_ClientToolsetConfig(
    url="https://example.com/sse",
)
SSE_TOOL = mock.sentinel.sse_toolset

_MCP_TOOLSET_BY_KIND = {
    "stdio": STDIO_TOOL,
    "http": HTTP_TOOL,
    "sse": SSE_TOOL,
}


def _fake_mcp_toolset_factory(kind):
    def factory(**_kw):
        return _MCP_TOOLSET_BY_KIND[kind]

    return factory


_FAKE_TOOLSET_FACTORY_BY_KIND = {
    kind: _fake_mcp_toolset_factory(kind) for kind in _MCP_TOOLSET_BY_KIND
}


def test_tool():
    """This is a test"""


@pytest.fixture(
    scope="module",
    params=[
        None,
        TC_TOOL_CONFIG,
    ],
)
def tool_configs_tools(request):
    # Ensure that 'soliplex.tools.test_tool' can be found.
    with mock.patch.dict(tools.__dict__, test_tool=test_tool):
        if request.param is None:
            yield []
        else:
            tc = request.param
            ai_tool = ai_tools.Tool(tc.tool_with_config, name=tc.tool_id)
            yield [(tc, ai_tool)]


@pytest.fixture
def installation_config():
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    i_config.interpolate.side_effect = lambda value: value
    return i_config


@pytest.fixture(
    params=[
        [],
        [(STDIO_MCTC, STDIO_TOOL)],
        [(HTTP_MCTC, HTTP_TOOL)],
        [(SSE_MCTC, SSE_TOOL)],
    ],
)
def mcp_ct_configs_tools(request, installation_config):
    return [
        (
            dataclasses.replace(
                mctc, _installation_config=installation_config
            ),
            tool,
        )
        for (mctc, tool) in request.param
    ]


@pytest.mark.parametrize(
    "w_aitp, exp_aitp",
    [
        ({}, {"name": "test_tool"}),
        ({"takes_ctx": True}, {"name": "test_tool", "takes_ctx": True}),
        (
            {"name": AI_TOOL_PARAM_NAME},
            {"name": AI_TOOL_PARAM_NAME},
        ),
    ],
)
def test_make_ai_tool(w_aitp, exp_aitp):
    if w_aitp:
        tool_config = dataclasses.replace(
            TC_TOOL_CONFIG,
            _ai_tool_params=config_tools.AIToolParams(**w_aitp),
        )
    else:
        tool_config = TC_TOOL_CONFIG

    with mock.patch.dict(tools.__dict__, test_tool=test_tool):
        found = agents.make_ai_tool(tool_config)

    assert isinstance(found, ai_tools.Tool)

    for key, e_value in exp_aitp.items():
        f_value = getattr(found, key)
        assert f_value == e_value


@pytest.mark.parametrize(
    "mcp_toolset_config, expected, exp_interpolated",
    [
        (STDIO_MCTC, STDIO_TOOL, [mock.call("cat"), mock.call("-")]),
        (HTTP_MCTC, HTTP_TOOL, [mock.call("https://example.com/mcp")]),
        (SSE_MCTC, SSE_TOOL, [mock.call("https://example.com/sse")]),
    ],
)
def test_make_mcp_client_toolset(
    installation_config,
    mcp_toolset_config,
    expected,
    exp_interpolated,
):
    mcp_toolset_config = dataclasses.replace(
        mcp_toolset_config,
        _installation_config=installation_config,
    )

    with mock.patch.object(
        mcp_client,
        "TOOLSET_FACTORY_BY_KIND",
        _FAKE_TOOLSET_FACTORY_BY_KIND,
    ):
        found = agents.make_mcp_client_toolset(mcp_toolset_config)

    assert found is expected

    interpolated = installation_config.interpolate.call_args_list
    for found_call, exp_call in zip(
        interpolated, exp_interpolated, strict=True
    ):
        assert found_call == exp_call


@pytest.mark.parametrize("w_capabilities", [False, True])
@pytest.mark.parametrize("w_room_capabilities", [False, True])
@pytest.mark.parametrize("w_rag_audit", [False, True])
@pytest.mark.parametrize("w_model_settings", [None, MODEL_SETTINGS])
@mock.patch.object(
    mcp_client,
    "TOOLSET_FACTORY_BY_KIND",
    _FAKE_TOOLSET_FACTORY_BY_KIND,
)
@mock.patch("soliplex.config.agents.get_model_from_config")
@mock.patch("pydantic_ai.Agent")
def test_get_default_agent_from_configs(
    agent_klass,
    gmfc,
    tool_configs_tools,
    mcp_ct_configs_tools,
    w_model_settings,
    w_rag_audit,
    w_room_capabilities,
    w_capabilities,
):
    agent_config = mock.create_autospec(config_agents.AgentConfig)
    agent_config.kind = "default"
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT
    agent_config.model_settings = w_model_settings
    exp_retries = agent_config.retries = 7  # See #926

    if w_capabilities:
        capability = mock.create_autospec(ai_capabilities.AbstractCapability)
        agent_config.capabilities = [capability]
    else:
        agent_config.capabilities = []
    exp_capabilities = list(agent_config.capabilities)

    tool_configs = {tc.tool_id: tc for (tc, _) in tool_configs_tools}
    exp_tools = [tool for (_, tool) in tool_configs_tools]

    mcp_tc_configs = {
        f"MCTC_{mctc_id:03}": mctc
        for mctc_id, (mctc, _) in enumerate(mcp_ct_configs_tools)
    }
    exp_toolsets = [tool for (_, tool) in mcp_ct_configs_tools]

    kwargs = {}
    if w_room_capabilities:
        room_capability = mock.create_autospec(
            ai_capabilities.AbstractCapability
        )
        capability_config = mock.Mock(
            capabilities=[room_capability],
            rag_db_paths=(
                {"haiku-rag": RAG_LANCEDB_OVERRIDE_PATH} if w_rag_audit else {}
            ),
        )
        kwargs["capability_config"] = capability_config
        exp_capabilities.append(room_capability)
    else:
        kwargs["capability_config"] = None

    found = agents.get_default_agent_from_configs(
        agent_config=agent_config,
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcp_tc_configs,
        **kwargs,
    )

    assert found is agent_klass.return_value

    agent_klass.assert_called_once()

    akc = agent_klass.call_args_list[0]

    assert akc.args == ()
    akc_kw = akc.kwargs

    assert akc_kw["model"] is gmfc.return_value
    gmfc.assert_called_once_with(agent_config=agent_config)

    assert akc_kw["instructions"] == SYSTEM_PROMPT
    found_capabilities = akc_kw["capabilities"]
    if w_room_capabilities and w_rag_audit:
        audit_capability = found_capabilities.pop()
        assert audit_capability.id == "soliplex-rag-access-audit"
        assert audit_capability.db_paths == {
            "haiku-rag": RAG_LANCEDB_OVERRIDE_PATH
        }
    assert found_capabilities == exp_capabilities
    assert akc_kw["retries"] == exp_retries

    assert akc_kw["model_settings"] == w_model_settings

    for akc_tool, exp_tool in zip(akc_kw["tools"], exp_tools, strict=True):
        assert akc_tool.function is exp_tool.function

    assert akc_kw["toolsets"] == exp_toolsets

    assert akc_kw["deps_type"] is agents.AgentDependencies


@pytest.mark.parametrize("multimodal", [False, True])
@mock.patch("soliplex.config.agents.get_model_from_config")
@mock.patch("pydantic_ai.Agent")
def test_get_default_agent_aligns_rag_capability_vision(
    agent_klass,
    gmfc,
    multimodal,
    tmp_path,
):
    from haiku.rag.capabilities.rag import create_capability as create_rag
    from haiku.rag.config.models import AppConfig

    agent_config = mock.create_autospec(config_agents.AgentConfig)
    agent_config.kind = "default"
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT
    agent_config.model_settings = None
    agent_config.retries = 3
    agent_config.capabilities = []
    agent_config.multimodal = multimodal

    rag_capability = create_rag(
        db_path=tmp_path / "kb.lancedb", config=AppConfig()
    )
    capability_config = mock.Mock(
        capabilities=[rag_capability],
        rag_db_paths={},
    )

    agents.get_default_agent_from_configs(
        agent_config=agent_config,
        tool_configs={},
        mcp_client_toolset_configs={},
        capability_config=capability_config,
    )

    assert rag_capability.vision is multimodal


@pytest.mark.parametrize(
    "n_caps, w_audit, expected_defer",
    [
        (1, False, False),
        (2, False, True),
        (1, True, False),
    ],
)
@mock.patch("soliplex.config.agents.get_model_from_config")
@mock.patch("pydantic_ai.Agent")
def test_get_default_agent_defers_only_with_multiple_capabilities(
    agent_klass,
    gmfc,
    n_caps,
    w_audit,
    expected_defer,
):
    agent_config = mock.create_autospec(config_agents.AgentConfig)
    agent_config.kind = "default"
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT
    agent_config.model_settings = None
    agent_config.retries = 3
    agent_config.multimodal = False
    agent_config.capabilities = []

    caps = [
        mock.create_autospec(ai_capabilities.AbstractCapability)
        for _ in range(n_caps)
    ]
    capability_config = mock.Mock(
        capabilities=caps,
        rag_db_paths=(
            {"haiku-rag": RAG_LANCEDB_OVERRIDE_PATH} if w_audit else {}
        ),
    )

    agents.get_default_agent_from_configs(
        agent_config=agent_config,
        tool_configs={},
        mcp_client_toolset_configs={},
        capability_config=capability_config,
    )

    for capability in caps:
        assert capability.defer_loading is expected_defer

    if w_audit:
        built = agent_klass.call_args.kwargs["capabilities"]
        (audit,) = [
            capability
            for capability in built
            if getattr(capability, "id", None) == "soliplex-rag-access-audit"
        ]
        # The hook-only audit capability is never counted and stays eager.
        assert audit.defer_loading is False


@pytest.mark.parametrize("w_room_capabilities", [False, True])
@mock.patch("soliplex.agents.get_default_agent_from_configs")
def test_get_agent_from_configs_w_default_kind(
    gdafc,
    tool_configs_tools,
    mcp_ct_configs_tools,
    w_room_capabilities,
):
    agent_config = mock.create_autospec(config_agents.AgentConfig)
    agent_config.id = ROOM_ID
    agent_config.kind = "default"

    tool_configs = {tc.tool_id: tc for (tc, _) in tool_configs_tools}

    mcp_tc_configs = {
        f"MCTC_{mctc_id:03}": mctc
        for mctc_id, (mctc, _) in enumerate(mcp_ct_configs_tools)
    }

    kwargs = {}

    if w_room_capabilities:
        capability_config = mock.create_autospec(agents.CapabilityConfig)
        kwargs["capability_config"] = capability_config
    else:
        kwargs["capability_config"] = None

    found = agents.get_agent_from_configs(
        agent_config=agent_config,
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcp_tc_configs,
        **kwargs,
    )

    assert found is gdafc.return_value

    gdafc.assert_called_once_with(
        agent_config=agent_config,
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcp_tc_configs,
        **kwargs,
    )


@pytest.mark.parametrize("w_room_capabilities", [False, True])
def test_get_agent_from_configs_w_python_kind(w_room_capabilities):
    agent_config = mock.create_autospec(config_agents.FactoryAgentConfig)
    agent_config.kind = "factory"
    agent_config.id = ROOM_ID

    tool_config = mock.create_autospec(config_tools.ToolConfig)
    tool_configs = {"test_tool": tool_config}

    mcpcts = mock.create_autospec(config_tools.MCP_ClientToolsetConfig)
    mcpcts_configs = {"test_mcpcts": mcpcts}

    kwargs = {}

    if w_room_capabilities:
        capability_config = mock.create_autospec(agents.CapabilityConfig)
        kwargs["capability_config"] = capability_config
    else:
        kwargs["capability_config"] = None

    found = agents.get_agent_from_configs(
        agent_config=agent_config,
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcpcts_configs,
        **kwargs,
    )

    assert found is agent_config.factory.return_value

    agent_config.factory.assert_called_once_with(
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcpcts_configs,
        **kwargs,
    )
