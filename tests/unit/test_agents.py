from unittest import mock

import pytest
from pydantic_ai import tools as ai_tools

from soliplex import agents
from soliplex import config
from soliplex import mcp_client
from soliplex import tools

MODEL = "testing"
SYSTEM_PROMPT = "You are a test"
BASE_URL = "https://example.com:12345"
API_KEY = "DEADBEEF"

OLLAMA_PROVIDER_KW = {
    "base_url": BASE_URL,
}
OPENAI_PROVIDER_KW = {
    "base_url": BASE_URL,
    "api_key": API_KEY,
}
GOOGLE_PROVIDER_KW = {
    "api_key": API_KEY,
}
MODEL_SETTINGS = {
    "temperature": 0.875,
}

ROOM_ID = "test-room"
RAG_LANCEDB_OVERRIDE_PATH = "/path/to/db/rag"

TC_TOOL_CONFIG = config.ToolConfig(tool_name="soliplex.tools.test_tool")


@pytest.mark.parametrize(
    "provider_type, llm_provider_kw",
    [
        (config.LLMProviderType.OLLAMA, OLLAMA_PROVIDER_KW),
        (config.LLMProviderType.OPENAI, OPENAI_PROVIDER_KW),
        (config.LLMProviderType.GOOGLE, GOOGLE_PROVIDER_KW),
    ],
)
@mock.patch("pydantic_ai.providers.google.GoogleProvider")
@mock.patch("pydantic_ai.providers.ollama.OllamaProvider")
@mock.patch("pydantic_ai.providers.openai.OpenAIProvider")
@mock.patch("pydantic_ai.models.google.GoogleModel")
@mock.patch("pydantic_ai.models.openai.OpenAIChatModel")
def test_get_model_from_config(
    oai_model_klass,
    google_model_klass,
    oai_provider_klass,
    oll_provider_klass,
    google_provider_klass,
    provider_type,
    llm_provider_kw,
):
    agent_config = mock.create_autospec(config.AgentConfig)
    agent_config.kind = "default"
    agent_config.id = ROOM_ID
    agent_config.model_name = MODEL
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT
    agent_config.provider_type = provider_type
    agent_config.llm_provider_kw = llm_provider_kw

    model = agents.get_model_from_config(agent_config=agent_config)

    if provider_type == config.LLMProviderType.GOOGLE:
        assert model is google_model_klass.return_value
        google_model_klass.assert_called_once_with(
            model_name=MODEL,
            provider=google_provider_klass.return_value,
        )
        google_provider_klass.assert_called_once_with(**llm_provider_kw)

        oai_model_klass.assert_not_called()
        oai_provider_klass.assert_not_called()
        oll_provider_klass.assert_not_called()

    elif provider_type == config.LLMProviderType.OPENAI:
        assert model is oai_model_klass.return_value
        oai_model_klass.assert_called_once_with(
            model_name=MODEL,
            provider=oai_provider_klass.return_value,
        )
        oai_provider_klass.assert_called_once_with(**llm_provider_kw)

        oll_provider_klass.assert_not_called()
        google_model_klass.assert_not_called()
        google_provider_klass.assert_not_called()

    else:
        assert model is oai_model_klass.return_value
        oai_model_klass.assert_called_once_with(
            model_name=MODEL,
            provider=oll_provider_klass.return_value,
        )
        oll_provider_klass.assert_called_once_with(**llm_provider_kw)

        oai_provider_klass.assert_not_called()
        google_model_klass.assert_not_called()
        google_provider_klass.assert_not_called()


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


STDIO_MCTC = config.Stdio_MCP_ClientToolsetConfig(
    command="cat",
    args=["-"],
)
STDIO_TOOL = mcp_client.Stdio_MCP_Client_Toolset(
    command="cat",
    args=["-"],
    env={},
)

HTTP_MCTC = config.HTTP_MCP_ClientToolsetConfig(
    url="https://example.com/mcp",
)
HTTP_TOOL = mcp_client.HTTP_MCP_Client_Toolset(
    url="https://example.com/mcp",
    headers={},
)


@pytest.fixture(
    scope="module",
    params=[
        [],
        [(STDIO_MCTC, STDIO_TOOL)],
        [(HTTP_MCTC, HTTP_TOOL)],
    ],
)
def mcp_ct_configs_tools(request):
    return request.param


@pytest.mark.parametrize("w_room_skills", [False, True])
@pytest.mark.parametrize("w_model_settings", [None, MODEL_SETTINGS])
@mock.patch("soliplex.agents.get_model_from_config")
@mock.patch("pydantic_ai.Agent")
def test_get_default_agent_from_configs(
    agent_klass,
    gmfc,
    tool_configs_tools,
    mcp_ct_configs_tools,
    w_model_settings,
    w_room_skills,
):
    agent_config = mock.create_autospec(config.AgentConfig)
    agent_config.kind = "default"
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT
    agent_config.model_settings = w_model_settings

    tool_configs = {tc.tool_id: tc for (tc, _) in tool_configs_tools}
    exp_tools = [tool for (_, tool) in tool_configs_tools]

    mcp_tc_configs = {
        f"MCTC_{mctc_id:03}": mctc
        for mctc_id, (mctc, _) in enumerate(mcp_ct_configs_tools)
    }
    exp_toolsets = [tool for (_, tool) in mcp_ct_configs_tools]

    room_skills = mock.create_autospec(agents.SkillToolsetConfig)
    kwargs = {}

    if w_room_skills:
        kwargs["skill_toolset_config"] = room_skills
        exp_toolsets.append(room_skills.skill_toolset)

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
    assert akc_kw["model_settings"] == w_model_settings

    for akc_tool, exp_tool in zip(akc_kw["tools"], exp_tools, strict=True):
        assert akc_tool.function is exp_tool.function

    for akc_toolset, exp_toolset in zip(
        akc_kw["toolsets"],
        exp_toolsets,
        strict=True,
    ):
        assert akc_toolset._params == exp_toolset._params

    assert akc_kw["deps_type"] is agents.AgentDependencies


@pytest.mark.parametrize("w_room_skills", [False, True])
@mock.patch("soliplex.agents.get_default_agent_from_configs")
def test_get_agent_from_configs_wo_hit_w_default_kind(
    gdafc,
    tool_configs_tools,
    mcp_ct_configs_tools,
    w_room_skills,
):
    agent_config = mock.create_autospec(config.AgentConfig)
    agent_config.id = ROOM_ID
    agent_config.kind = "default"

    tool_configs = {tc.tool_id: tc for (tc, _) in tool_configs_tools}

    mcp_tc_configs = {
        f"MCTC_{mctc_id:03}": mctc
        for mctc_id, (mctc, _) in enumerate(mcp_ct_configs_tools)
    }

    room_skills = mock.create_autospec(agents.SkillToolsetConfig)
    kwargs = {}

    if w_room_skills:
        kwargs["skill_toolset_config"] = room_skills
    else:
        kwargs["skill_toolset_config"] = None

    with (
        mock.patch.dict("soliplex.agents._agent_cache", clear=True) as cache,
    ):
        found = agents.get_agent_from_configs(
            agent_config=agent_config,
            tool_configs=tool_configs,
            mcp_client_toolset_configs=mcp_tc_configs,
            **kwargs,
        )

        assert cache[ROOM_ID] is found

    assert found is gdafc.return_value

    gdafc.assert_called_once_with(
        agent_config=agent_config,
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcp_tc_configs,
        **kwargs,
    )


@pytest.mark.parametrize("w_room_skills", [False, True])
def test_get_agent_from_configs_wo_hit_w_python_kind(w_room_skills):
    agent_config = mock.create_autospec(config.FactoryAgentConfig)
    agent_config.kind = "factory"
    agent_config.id = ROOM_ID

    tool_config = mock.create_autospec(config.ToolConfig)
    tool_configs = {"test_tool": tool_config}

    mcpcts = mock.create_autospec(config.MCP_ClientToolsetConfig)
    mcpcts_configs = {"test_mcpcts": mcpcts}

    room_skills = mock.create_autospec(agents.SkillToolsetConfig)
    kwargs = {}

    if w_room_skills:
        kwargs["skill_toolset_config"] = room_skills
    else:
        kwargs["skill_toolset_config"] = None

    with (
        mock.patch.dict("soliplex.agents._agent_cache", clear=True) as cache,
    ):
        found = agents.get_agent_from_configs(
            agent_config=agent_config,
            tool_configs=tool_configs,
            mcp_client_toolset_configs=mcpcts_configs,
            **kwargs,
        )

        assert cache[ROOM_ID] is found

    assert found is agent_config.factory.return_value

    agent_config.factory.assert_called_once_with(
        tool_configs=tool_configs,
        mcp_client_toolset_configs=mcpcts_configs,
        **kwargs,
    )


def test_get_agent_from_configs_w_hit():
    expected = object()
    a_config = mock.create_autospec(config.AgentConfig)
    a_config.id = ROOM_ID

    with mock.patch.dict("soliplex.agents._agent_cache", clear=True) as ac:
        ac[ROOM_ID] = expected

        found = agents.get_agent_from_configs(
            agent_config=a_config,
            tool_configs={},
            mcp_client_toolset_configs={},
        )

    assert found is expected
