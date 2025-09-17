import functools
from unittest import mock

import pytest
from pydantic_ai import tools as ai_tools

from soliplex import agents
from soliplex import config
from soliplex import models
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

ROOM_ID = "test-room"
RAG_LANCEDB_OVERRIDE_PATH = "/path/to/db/rag"

TC_TOOL_CONFIG = config.ToolConfig(
    kind="test_tool",
    tool_name="soliplex.tools.test_tool"
)

def test_tool():
    """This is a test"""

SDTC_TOOL_CONFIG = config.SearchDocumentsToolConfig(
    rag_lancedb_override_path = RAG_LANCEDB_OVERRIDE_PATH
)

@pytest.fixture(scope="module", params=[
    None,
    TC_TOOL_CONFIG,
    SDTC_TOOL_CONFIG,
])
def tool_configs_tools(request):
    # Ensure that 'soliplex.tools.test_tool' can be found.
    with mock.patch.dict(tools.__dict__, test_tool=test_tool):
        if request.param is None:
            yield []
        else:
            tc = request.param
            ai_tool = ai_tools.Tool(tc.tool_with_config, name=tc.tool_id)
            yield [(tc, ai_tool)]


@pytest.fixture(scope="module", params=[
    [],
])
def mcp_ct_configs_tools(request):
    # Ensure that 'soliplex.tools.test_tool' can be found.
    with mock.patch.dict(tools.__dict__, test_tool=test_tool):
        yield request.param


@pytest.mark.parametrize("llm_provider_kw, w_oai", [
    (OLLAMA_PROVIDER_KW, False),
    (OPENAI_PROVIDER_KW, True),
])
@mock.patch("pydantic_ai.providers.ollama.OllamaProvider")
@mock.patch("pydantic_ai.providers.openai.OpenAIProvider")
@mock.patch("pydantic_ai.models.openai.OpenAIChatModel")
@mock.patch("pydantic_ai.Agent")
def test_get_agent_from_configs_wo_hit(
    agent_klass,
    model_klass,
    oai_provider_klass,
    oll_provider_klass,
    tool_configs_tools,
    mcp_ct_configs_tools,
    llm_provider_kw,
    w_oai,
):
    agent_config = mock.create_autospec(config.AgentConfig)
    agent_config.id = ROOM_ID
    agent_config.model_name = MODEL
    agent_config.get_system_prompt.return_value = SYSTEM_PROMPT

    if w_oai:
        agent_config.provider_type = config.LLMProviderType.OPENAI
    else:
        agent_config.provider_type = config.LLMProviderType.OLLAMA

    agent_config.llm_provider_kw = llm_provider_kw

    tool_configs = {
        tc.tool_id: tc
        for (tc, _) in tool_configs_tools
    }
    exp_tools = [tool for (_, tool) in tool_configs_tools]

    mcp_tc_configs = {
        f"MCTC_{mctc_id:03}": mctc.mctc.mctc
        for mctc_id, (mctc, _) in enumerate(mcp_ct_configs_tools)
    }
    exp_toolsets = [tool for (_, tool) in mcp_ct_configs_tools]

    with (
        mock.patch.dict("soliplex.agents._agent_cache", clear=True) as cache,
    ):
        found = agents.get_agent_from_configs(
            agent_config, tool_configs, mcp_tc_configs,
        )

        assert cache[ROOM_ID] is found

    assert found is agent_klass.return_value

    agent_klass.assert_called_once()

    akc = agent_klass.call_args_list[0]

    assert akc.args == ()
    akc_kw = akc.kwargs
    assert akc_kw["model"] == model_klass.return_value
    assert akc_kw["instructions"] == SYSTEM_PROMPT

    for akc_tool, exp_tool in zip(akc_kw["tools"], exp_tools, strict=True):
        if isinstance(akc_tool.function, functools.partial):
            assert akc_tool.function.func is exp_tool.function.func
            assert akc_tool.function.args == exp_tool.function.args
            assert akc_tool.function.keywords == exp_tool.function.keywords
        else:
            assert akc_tool.function is exp_tool.function

    for _akc_toolset, _exp_toolset in zip(
        akc_kw["toolsets"], exp_toolsets, strict=True,
    ):
        pass  # TODO

    assert akc_kw["deps_type"] is models.AgentDependencies

    if w_oai:
        model_klass.assert_called_once_with(
            model_name=MODEL, provider=oai_provider_klass.return_value,
        )

        oai_provider_klass.assert_called_once_with(**llm_provider_kw)
        oll_provider_klass.assert_not_called()

    else:
        model_klass.assert_called_once_with(
            model_name=MODEL, provider=oll_provider_klass.return_value,
        )

        oll_provider_klass.assert_called_once_with(**llm_provider_kw)
        oai_provider_klass.assert_not_called()


def test_get_agent_from_configs_w_hit():
    expected = object()
    a_config = mock.create_autospec(config.AgentConfig)
    a_config.id = ROOM_ID

    with mock.patch.dict(
        "soliplex.agents._agent_cache", clear=True
    ) as ac:
        ac[ROOM_ID] = expected

        found = agents.get_agent_from_configs(a_config, [], {})

    assert found is expected
