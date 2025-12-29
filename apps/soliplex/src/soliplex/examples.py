from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import random
import typing
import uuid
from collections import abc

import pydantic_ai
from pydantic_ai import messages as ai_messages
from pydantic_ai import output as ai_output
from pydantic_ai import run as ai_run
from pydantic_ai import tools as ai_tools
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import ollama as ollama_providers

from soliplex import config

JOKER_AGENT_PROMPT = """\
Use the `joke_factory` to generate some jokes, then choose the best. 

You must return just a single joke.
"""


def joker_agent_factory(
    agent_config,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
):  # pragma NO COVER
    installation_config = agent_config._installation_config

    provider_base_url = installation_config.get_environment("OLLAMA_BASE_URL")
    provider_kw = {
        "base_url": f"{provider_base_url}/v1",
    }
    provider = ollama_providers.OllamaProvider(**provider_kw)

    joke_selection_agent = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name="gpt-oss:latest",
            provider=provider,
        ),
        system_prompt=JOKER_AGENT_PROMPT,
    )

    joke_generation_agent = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name="gpt-oss:latest",
            provider=provider,
        ),
        output_type=list[str],
    )

    @joke_selection_agent.tool
    async def joke_factory(
        ctx: pydantic_ai.RunContext[None], count: int, topic: str = None
    ) -> list[str]:
        if topic is None:
            prompt = f"Please generate {count} jokes."
        else:
            prompt = f"Please generate {count} jokes about {topic}."

        r = await joke_generation_agent.run(
            prompt,
            usage=ctx.usage,
        )
        return r.output

    return joke_selection_agent


NativeEvent = (
    ai_messages.AgentStreamEvent | ai_run.AgentRunResultEvent[typing.Any]
)
MessageHistory = typing.Sequence[ai_messages.ModelMessage]


async def faux_tool(ctx: pydantic_ai.RunContext) -> str:
    """Return something random"""
    agui_emitter = ctx.deps.agui_emitter
    activity_id = str(uuid.uuid4())

    await asyncio.sleep(random.uniform(0.25, 0.5))

    agui_emitter.update_activity(
        "idling",
        {"how": "head scratching"},
        activity_id,
    )

    await asyncio.sleep(random.uniform(0.25, 0.5))

    return "something random"


@dataclasses.dataclass
class FauxAgentRun:
    prompt: str
    _faux_agent: FauxAgent

    def new_messages(self):
        return [
            ai_messages.ModelRequest(
                parts=[
                    ai_messages.UserPromptPart(
                        content=self.prompt,
                    )
                ],
            ),
            ai_messages.ModelResponse(
                parts=[
                    ai_messages.TextPart(
                        content="I don't know",
                    ),
                ],
            ),
        ]

    async def stream_responses(self):
        yield (
            ai_messages.ModelResponse(
                parts=[
                    ai_messages.TextPart(
                        content="I don't know",
                    ),
                ],
            ),
            True,
        )


@dataclasses.dataclass
class FauxAgent:
    agent_config: config.FactoryAgentConfig
    tool_configs: config.ToolConfigMap = None
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None

    output_type = None

    async def run(
        self,
        prompt: str,
        message_history: MessageHistory | None = None,
        deps: ai_tools.AgentDepsT = None,
    ):
        return FauxAgentRun(prompt, self)

    @contextlib.asynccontextmanager
    async def run_stream(
        self,
        prompt,
        message_history: MessageHistory | None = None,
        deps: ai_tools.AgentDepsT = None,
    ):
        yield FauxAgentRun(prompt, self)

    async def run_stream_events(
        self,
        output_type: ai_output.OutputSpec[typing.Any] | None = None,
        message_history: MessageHistory | None = None,
        deferred_tool_results: pydantic_ai.DeferredToolResults | None = None,
        deps: ai_tools.AgentDepsT = None,
        # model=model,
        # model_settings=model_settings,
        # toolsets=toolsets,
        # builtin_tools=builtin_tools,
        # infer_name=infer_name,
        # usage_limits=usage_limits,
        # usage=usage,
        **kwargs,
    ) -> abc.AsyncIterator[NativeEvent]:
        think_part = ai_messages.ThinkingPart("I'm thinking")
        part_index = 0

        yield ai_messages.PartStartEvent(
            index=part_index,
            part=think_part,
        )
        last_message = message_history[-1]

        await asyncio.sleep(random.uniform(0.5, 2.0))

        if isinstance(last_message, ai_messages.ModelRequest):
            ups = [
                part
                for part in last_message.parts
                if isinstance(part, ai_messages.UserPromptPart)
            ]
            if ups:
                up = ups[0]
                delta = f"\n\nHmm, you asked {up.content}"
                think_part.content += delta
                yield ai_messages.PartDeltaEvent(
                    index=0,
                    delta=ai_messages.ThinkingPartDelta(
                        content_delta=delta,
                    ),
                )

            await asyncio.sleep(random.uniform(0.5, 2.0))

        yield ai_messages.PartEndEvent(
            index=part_index,
            part=think_part,
        )

        ctx = pydantic_ai.RunContext(
            deps=deps,
            model=None,
            usage=None,
        )

        for tool_name, tool_config in self.tool_configs.items():
            tc_part = ai_messages.ToolCallPart(tool_name)
            part_index += 1

            yield ai_messages.PartStartEvent(
                index=part_index,
                part=tc_part,
            )

            await tool_config.tool(ctx)

            await asyncio.sleep(random.uniform(0.5, 2.0))

            yield ai_messages.PartEndEvent(
                index=part_index,
                part=tc_part,
            )

        await asyncio.sleep(random.uniform(2.5, 3.0))

        text_part = ai_messages.TextPart("I don't know!")
        part_index += 1
        yield ai_messages.PartStartEvent(
            index=part_index,
            part=text_part,
        )
        yield ai_messages.PartEndEvent(
            index=part_index,
            part=text_part,
        )

        yield ai_run.AgentRunResultEvent(result=text_part.content)


def faux_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
):
    return FauxAgent(agent_config, tool_configs, mcp_client_toolset_configs)
