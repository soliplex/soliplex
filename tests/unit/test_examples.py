from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pydantic_ai
import pytest
from pydantic_ai import agent as ai_agent
from pydantic_ai import messages as ai_messages
from pydantic_ai import run as ai_run
from pydantic_ai import usage as ai_usage
from pydantic_ai.models import openai as openai_models

from soliplex import agents
from soliplex import examples
from soliplex.config import agents as config_agents
from soliplex.config import installation as config_installation

OLLAMA_BASE_URL = "http://ollama.example.com:11434"
BARE_ENV = {
    "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
}


@pytest.fixture
def the_installation_config():
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    i_config.get_environment.side_effect = BARE_ENV.get

    return i_config


@pytest.fixture
def the_agent_config(the_installation_config):
    return mock.create_autospec(config_agents.AgentConfig)


@pytest.fixture
def o_providers():
    with mock.patch("soliplex.examples.ollama_providers") as patched:
        yield patched


@pytest.fixture
def p_ai():
    with mock.patch("soliplex.examples.pydantic_ai") as patched:
        yield patched


@pytest.fixture
def oai_models():
    with mock.patch("soliplex.examples.openai_models") as patched:
        yield patched


def test_joker_agent_factory(
    o_providers,
    p_ai,
    oai_models,
    the_agent_config,
):
    op_klass = o_providers.OllamaProvider
    exp_provider = op_klass.return_value

    sel_agent = mock.create_autospec(ai_agent.Agent)
    sel_agent.tool = mock.MagicMock(spec_set=())
    gen_agent = mock.create_autospec(ai_agent.Agent)

    agent_klass = p_ai.Agent
    agent_klass.side_effect = [sel_agent, gen_agent]

    exp_model = mock.create_autospec(openai_models.OpenAIChatModel)
    chatmodel_klass = oai_models.OpenAIChatModel
    chatmodel_klass.return_value = exp_model

    found = examples.joker_agent_factory(the_agent_config)

    assert found is sel_agent

    sel_call, gen_call = agent_klass.call_args_list

    assert sel_call == mock.call(
        model=exp_model,
        system_prompt=examples.JOKER_AGENT_PROMPT,
    )

    assert gen_call == mock.call(
        model=exp_model,
        output_type=list[str],
    )

    sel_model_call, gen_model_call = chatmodel_klass.call_args_list

    assert sel_model_call == mock.call(
        model_name="gpt-oss:latest",
        provider=exp_provider,
    )

    assert gen_model_call == mock.call(
        model_name="gpt-oss:latest",
        provider=exp_provider,
    )


@pytest.fixture
def faux_agent():
    return examples.faux_agent_factory(agent_config=None, tool_configs={})


@pytest.mark.anyio
async def test_faux_agent_run_returns_canned_answer(faux_agent):
    result = await faux_agent.run("what is up?")

    assert result.output == "I don't know!"
    assert isinstance(result.usage(), ai_usage.RunUsage)


@pytest.mark.anyio
async def test_faux_agent_run_derives_prompt_from_message_history(faux_agent):
    history = [
        ai_messages.ModelRequest(
            parts=[ai_messages.UserPromptPart(content="what is up?")],
        ),
    ]

    result = await faux_agent.run(message_history=history)

    assert result.output == "I don't know!"


@pytest.mark.anyio
async def test_faux_agent_run_raises_on_fail_prompt(faux_agent):
    with pytest.raises(ValueError, match="failing on request"):
        await faux_agent.run("fail")


@pytest.mark.anyio
async def test_faux_agent_run_ignores_non_request_history(faux_agent):
    history = [ai_messages.ModelResponse(parts=[ai_messages.TextPart("hi")])]

    result = await faux_agent.run(message_history=history)

    assert result.output == "I don't know!"


@pytest.mark.anyio
async def test_faux_agent_run_ignores_history_without_user_prompt(faux_agent):
    history = [
        ai_messages.ModelRequest(
            parts=[ai_messages.SystemPromptPart(content="sys")],
        ),
    ]

    result = await faux_agent.run(message_history=history)

    assert result.output == "I don't know!"


@pytest.fixture
def no_sleep():
    with mock.patch(
        "soliplex.examples.asyncio.sleep",
        new_callable=mock.AsyncMock,
    ) as patched:
        yield patched


@pytest.mark.anyio
async def test_faux_tool_emits_state_delta_for_user_prompt(no_sleep):
    agui_state = {}
    ctx = SimpleNamespace(deps=SimpleNamespace(state=agui_state))
    user_prompt = ai_messages.UserPromptPart(content="hi")

    result = await examples.faux_tool(ctx, user_prompt=user_prompt)

    assert result.return_value == "something random"
    assert len(result.metadata) == 1
    assert agui_state["faux"] == "hi"


@pytest.mark.anyio
async def test_faux_tool_without_user_prompt_has_no_metadata(no_sleep):
    agui_state = {}
    ctx = SimpleNamespace(deps=SimpleNamespace(state=agui_state))

    result = await examples.faux_tool(ctx)

    assert result.return_value == "something random"
    assert result.metadata is None
    assert agui_state == {}


@pytest.fixture
def stub_tool_config():
    async def tool(ctx, user_prompt=None):
        return pydantic_ai.ToolReturn(return_value="ok", metadata=None)

    return SimpleNamespace(tool=tool)


def _user_request(content):
    return ai_messages.ModelRequest(
        parts=[ai_messages.UserPromptPart(content=content)],
    )


@pytest.mark.anyio
async def test_run_stream_events_yields_final_answer(
    no_sleep,
    stub_tool_config,
):
    agent = examples.faux_agent_factory(
        agent_config=None,
        tool_configs={"faux": stub_tool_config},
    )
    deps = agents.AgentDependencies(the_installation=None)

    events = [
        event
        async for event in agent._run_stream_events(
            message_history=[_user_request("hi")],
            deps=deps,
        )
    ]

    assert isinstance(events[-1], ai_run.AgentRunResultEvent)
    assert events[-1].result == "I don't know!"


@pytest.mark.anyio
async def test_run_stream_events_raises_on_fail(no_sleep, faux_agent):
    deps = agents.AgentDependencies(the_installation=None)

    with pytest.raises(ValueError, match="failing on request"):
        [
            event
            async for event in faux_agent._run_stream_events(
                message_history=[_user_request("fail")],
                deps=deps,
            )
        ]


@pytest.mark.anyio
async def test_run_stream_events_handles_non_request_history(
    no_sleep,
    faux_agent,
):
    history = [ai_messages.ModelResponse(parts=[ai_messages.TextPart("hi")])]
    deps = agents.AgentDependencies(the_installation=None)

    events = [
        event
        async for event in faux_agent._run_stream_events(
            message_history=history,
            deps=deps,
        )
    ]

    assert events[-1].result == "I don't know!"


@pytest.mark.anyio
async def test_run_stream_events_handles_history_without_user_prompt(
    no_sleep,
    faux_agent,
):
    history = [
        ai_messages.ModelRequest(
            parts=[ai_messages.SystemPromptPart(content="sys")],
        ),
    ]
    deps = agents.AgentDependencies(the_installation=None)

    events = [
        event
        async for event in faux_agent._run_stream_events(
            message_history=history,
            deps=deps,
        )
    ]

    assert events[-1].result == "I don't know!"


@pytest.mark.anyio
async def test_run_stream_events_returns_event_stream(faux_agent):
    history = [_user_request("hi")]

    stream = faux_agent.run_stream_events(message_history=history)
    async with stream as events:
        collected = [event async for event in events]

    assert collected[-1].result == "I don't know!"
