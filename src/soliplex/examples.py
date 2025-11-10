import dataclasses
import random
import time
import typing
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


def joker_agent_factory(agent_config):  # pragma NO COVER
    installation_config = agent_config._installation_config

    provider_base_url = installation_config.get_environment("OLLAMA_BASE_URL")
    provider_kw = {
        "base_url": f"{provider_base_url}/v1",
    }
    provider = ollama_providers.OllamaProvider(**provider_kw)

    joke_selection_agent = pydantic_ai.Agent(
        model=openai_models.OpenAIChatModel(
            model_name="qwen3:latest",
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


@dataclasses.dataclass
class FauxAgent:
    agent_config: config.FactoryAgentConfig

    output_type = None

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

        yield ai_messages.PartStartEvent(
            index=0,
            part=think_part,
        )
        last_message = message_history[-1]

        time.sleep(random.uniform(0.5, 2.0))

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

            time.sleep(random.uniform(0.5, 2.0))

        yield ai_messages.PartEndEvent(
            index=0,
            part=think_part,
        )

        time.sleep(random.uniform(2.5, 3.0))

        text_part = ai_messages.TextPart("I don't know!")
        yield ai_messages.PartStartEvent(
            index=1,
            part=text_part,
        )
        yield ai_messages.PartEndEvent(
            index=1,
            part=text_part,
        )


def faux_agent_factory(agent_config: config.FactoryAgentConfig):
    return FauxAgent(agent_config)


@dataclasses.dataclass
class ResearchGraphAgent:
    agent_config: config.FactoryAgentConfig

    output_type = None

    async def run_stream_events(
        self,
        output_type: ai_output.OutputSpec[typing.Any] | None = None,
        message_history: MessageHistory | None = None,
        deferred_tool_results: pydantic_ai.DeferredToolResults | None = None,
        deps: ai_tools.AgentDepsT = None,
        **kwargs,
    ) -> abc.AsyncIterator[NativeEvent]:
        from haiku.rag import client as rag_client
        from haiku.rag.research import dependencies as research_deps
        from haiku.rag.research import graph as research_graph
        from haiku.rag.research import state as research_state

        installation_config = self.agent_config._installation_config
        extra_config = self.agent_config.extra_config

        max_iterations = extra_config.get("max_iterations", 3)
        confidence_threshold = extra_config.get("confidence_threshold", 0.8)
        max_concurrency = extra_config.get("max_concurrency", 1)

        if not message_history or len(message_history) == 0:
            yield ai_messages.PartStartEvent(
                index=0,
                part=ai_messages.TextPart(
                    "Please ask me a research question to get started."
                ),
            )
            yield ai_messages.PartEndEvent(
                index=0,
                part=ai_messages.TextPart(
                    "Please ask me a research question to get started."
                ),
            )
            return

        last_message = message_history[-1]
        if not isinstance(last_message, ai_messages.ModelRequest):
            msg = "I can only respond to user messages."
            yield ai_messages.PartStartEvent(
                index=0,
                part=ai_messages.TextPart(msg),
            )
            yield ai_messages.PartEndEvent(
                index=0,
                part=ai_messages.TextPart(msg),
            )
            return

        user_prompts = [
            part
            for part in last_message.parts
            if isinstance(part, ai_messages.UserPromptPart)
        ]
        if not user_prompts:
            yield ai_messages.PartStartEvent(
                index=0,
                part=ai_messages.TextPart("I didn't receive a question."),
            )
            yield ai_messages.PartEndEvent(
                index=0,
                part=ai_messages.TextPart("I didn't receive a question."),
            )
            return

        question = user_prompts[0].content

        room_id = self.agent_config.id.removeprefix("room-")

        try:
            room_config = deps.the_installation.get_room_config(
                room_id, user={}
            )
        except KeyError:
            error_msg = f"Error: Room '{room_id}' not found."
            yield ai_messages.PartStartEvent(
                index=0,
                part=ai_messages.TextPart(error_msg),
            )
            yield ai_messages.PartEndEvent(
                index=0,
                part=ai_messages.TextPart(error_msg),
            )
            return

        search_tool = room_config.tool_configs.get("search_documents")
        if not search_tool:
            error_msg = (
                "Error: No RAG database configured for this room."
            )
            yield ai_messages.PartStartEvent(
                index=0,
                part=ai_messages.TextPart(error_msg),
            )
            yield ai_messages.PartEndEvent(
                index=0,
                part=ai_messages.TextPart(error_msg),
            )
            return

        rag_db_path = search_tool.rag_lancedb_path

        haiku_config = installation_config.haiku_rag_config

        async with rag_client.HaikuRAG(
            db_path=rag_db_path,
            config=haiku_config,
        ) as rag:
            context = research_deps.ResearchContext(original_question=question)
            state = research_state.ResearchState(
                context=context,
                max_iterations=max_iterations,
                confidence_threshold=confidence_threshold,
                max_concurrency=max_concurrency,
            )
            deps_obj = research_state.ResearchDeps(client=rag)

            graph = research_graph.build_research_graph(config=haiku_config)

            part_index = 0
            current_part = None

            try:
                from haiku.rag.research import stream as research_stream

                async for event in research_stream.stream_research_graph(
                    graph, state, deps_obj
                ):
                    if event.type == "log":
                        if current_part:
                            yield ai_messages.PartEndEvent(
                                index=part_index,
                                part=current_part,
                            )
                            part_index += 1

                        current_part = ai_messages.TextPart(
                            f"{event.message}\n"
                        )
                        yield ai_messages.PartStartEvent(
                            index=part_index,
                            part=current_part,
                        )

                    elif event.type == "report":
                        if current_part:
                            yield ai_messages.PartEndEvent(
                                index=part_index,
                                part=current_part,
                            )
                            part_index += 1

                        report = event.report
                        report_text = self._format_report(report)

                        final_part = ai_messages.TextPart(report_text)
                        yield ai_messages.PartStartEvent(
                            index=part_index,
                            part=final_part,
                        )
                        yield ai_messages.PartEndEvent(
                            index=part_index,
                            part=final_part,
                        )
                        current_part = None

                    elif event.type == "error":
                        if current_part:
                            yield ai_messages.PartEndEvent(
                                index=part_index,
                                part=current_part,
                            )
                            part_index += 1

                        error_part = ai_messages.TextPart(
                            f"\n\n❌ Error: {event.error}\n"
                        )
                        yield ai_messages.PartStartEvent(
                            index=part_index,
                            part=error_part,
                        )
                        yield ai_messages.PartEndEvent(
                            index=part_index,
                            part=error_part,
                        )
                        current_part = None

                if current_part:
                    yield ai_messages.PartEndEvent(
                        index=part_index,
                        part=current_part,
                    )

            except Exception as exc:
                error_part = ai_messages.TextPart(
                    f"\n\n❌ Research failed: {exc}\n"
                )
                yield ai_messages.PartStartEvent(
                    index=part_index,
                    part=error_part,
                )
                yield ai_messages.PartEndEvent(
                    index=part_index,
                    part=error_part,
                )

    def _format_report(self, report) -> str:
        lines = []
        lines.append(f"\n\n# {report.title}\n")

        if report.executive_summary:
            lines.append(
                f"\n## Executive Summary\n\n{report.executive_summary}\n"
            )

        if report.main_findings:
            lines.append("\n## Main Findings\n")
            for finding in report.main_findings:
                lines.append(f"- {finding}\n")

        if report.conclusions:
            lines.append(f"\n## Conclusions\n\n{report.conclusions}\n")

        if report.limitations:
            lines.append("\n## Limitations\n")
            for limitation in report.limitations:
                lines.append(f"- {limitation}\n")

        if report.recommendations:
            lines.append("\n## Recommendations\n")
            for rec in report.recommendations:
                lines.append(f"- {rec}\n")

        if report.sources_summary:
            lines.append(f"\n## Sources\n\n{report.sources_summary}\n")

        return "".join(lines)


def research_graph_agent_factory(
    agent_config: config.FactoryAgentConfig,
):  # pragma NO COVER
    return ResearchGraphAgent(agent_config)
