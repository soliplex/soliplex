"""Factory agent for haiku.rag conversational chat agent.

This module provides a factory that creates a wrapper around haiku.rag's
chat agent, translating Soliplex's AgentDependencies to haiku.rag's ChatDeps.
"""

import dataclasses
import pathlib
import typing
from collections import abc

import pydantic_ai
from haiku.rag import client as hr_client
from haiku.rag.agents import chat as hr_agents_chat
from haiku.rag.agents.chat import agent as hr_agents_chat_agent
from haiku.rag.config import models as hr_config_models
from haiku.rag.tools import context as hr_tools_context
from haiku.rag.tools import toolkit as hr_toolkit
from pydantic_ai import messages as ai_messages
from pydantic_ai import run as ai_run
from pydantic_ai.agent import abstract as ai_ag_abstract

from soliplex import agents
from soliplex import config

AGUI_STATE_KEY = hr_agents_chat.AGUI_STATE_KEY

NativeEvent = (
    ai_messages.AgentStreamEvent | ai_run.AgentRunResultEvent[typing.Any]
)


@dataclasses.dataclass
class ChatAgentWrapper:
    """Wrapper around haiku.rag chat agent that translates dependencies.

    This wrapper accepts Soliplex's AgentDependencies and internally creates
    haiku.rag's ChatDeps, managing the HaikuRAG client lifecycle.

    A ToolContextCache maintains ToolContext instances across requests for
    the same thread, allowing background summarization results to persist.
    """

    agent: pydantic_ai.Agent[hr_agents_chat_agent.ChatDeps, str]
    toolkit: hr_toolkit.Toolkit
    config: hr_config_models.AppConfig
    db_path: pathlib.Path
    background_context: str | None = None
    _context_cache: hr_tools_context.ToolContextCache = dataclasses.field(
        default_factory=hr_tools_context.ToolContextCache
    )

    output_type = None

    def _get_context(
        self, thread_id: str | None
    ) -> hr_tools_context.ToolContext:
        if thread_id is None:
            context = self.toolkit.create_context(state_key=AGUI_STATE_KEY)
            return context

        context, is_new = self._context_cache.get_or_create(thread_id)
        if is_new:
            self.toolkit.prepare(context, state_key=AGUI_STATE_KEY)
        return context

    async def run_stream_events(
        self,
        output_type=None,
        message_history=None,
        deferred_tool_results=None,
        deps: agents.AgentDependencies = None,
        **kwargs,
    ) -> abc.AsyncIterator[NativeEvent]:
        """Run the agent and stream events.

        Translates AgentDependencies to ChatDeps and manages the HaikuRAG
        client lifecycle.
        """
        context = self._get_context(deps.thread_id)

        async with hr_client.HaikuRAG(
            db_path=self.db_path, config=self.config, read_only=True
        ) as client:
            chat_deps = hr_agents_chat_agent.ChatDeps(
                config=self.config,
                client=client,
                tool_context=context,
            )

            # Inject background_context as initial_context if not present
            agui_state = deps.state
            if self.background_context:
                state_data = agui_state.get(AGUI_STATE_KEY, {})
                if not state_data.get("initial_context"):
                    state_data = {
                        **state_data,
                        "initial_context": self.background_context,
                    }
                    agui_state = {**agui_state, AGUI_STATE_KEY: state_data}

            chat_deps.state = agui_state

            async for event in self.agent.run_stream_events(
                output_type=output_type,
                message_history=message_history,
                deferred_tool_results=deferred_tool_results,
                deps=chat_deps,
                **kwargs,
            ):
                yield event


@dataclasses.dataclass(kw_only=True)
class ChatAgentConfig(config._RAGConfigBase):
    """Custom config type for the 'haiku.rag.chat' agent

    This config class is intended to be used in a Soliplex room or
    completion configuration:

        agent:
          kind: "haiku_chat"
          rag_lancedb_stem: "rag"
          rag_features: ["search", "documents", "qa"]
          background_context: |
            <your context here>

    or with a path override:

        agent:
          kind: "haiku_chat"
          rag_lancedb_override_path: "/path/to/rag.lancedb"
          background_context: |
            <your context here>
    """

    id: str
    kind: typing.ClassVar[str] = "haiku_chat"
    background_context: str = None
    rag_features: list[str] = None
    preamble: str = None

    # Use a config from the top-level InstallationConfig's 'agent_configs'
    # as a template.
    _template_id: str = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: config.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            bkg_context = config_dict.pop("background_context", None)
            if bkg_context is not None:
                config_dict["background_context"] = bkg_context.strip()

            preamble = config_dict.pop("preamble", None)
            if preamble is not None:
                config_dict["preamble"] = preamble.strip()

            had_stem = "rag_lancedb_stem" in config_dict
            had_override = "rag_lancedb_override_path" in config_dict

            config_dict = config._apply_agent_config_template(
                config_dict,
                installation_config,
                config_path,
            )

            # Template stem / override must not conflict w/ local.
            if had_stem:
                if not had_override:
                    config_dict.pop("rag_lancedb_override_path", None)
                else:  # pragma: NO COVER
                    pass
            elif had_override:
                config_dict.pop("rag_lancedb_stem", None)
            else:  # pragma: NO COVER
                pass

            instance = cls(**config_dict)
        except Exception as exc:
            raise config.FromYamlException(
                config_path,
                "chatagent",
                config_dict,
            ) from exc

        return instance

    @property
    def agui_feature_names(self) -> tuple[str]:
        return (AGUI_STATE_KEY,)

    @property
    def as_yaml(self):
        result = {
            "id": self.id,
        }

        if self.background_context is not None:
            result["background_context"] = self.background_context

        if self.rag_features is not None:
            result["rag_features"] = self.rag_features

        if self.preamble is not None:
            result["preamble"] = self.preamble

        if self.rag_lancedb_override_path is not None:
            result["rag_lancedb_override_path"] = (
                self.rag_lancedb_override_path
            )
        else:
            result["rag_lancedb_stem"] = self.rag_lancedb_stem

        return result

    def factory(self, **_kwargs) -> ai_ag_abstract.AbstractAgent:
        hr_config = self.haiku_rag_config
        toolkit = hr_agents_chat_agent.build_chat_toolkit(
            hr_config, features=self.rag_features
        )
        agent = hr_agents_chat_agent.create_chat_agent(
            hr_config,
            features=self.rag_features,
            preamble=self.preamble,
            toolkit=toolkit,
        )

        return ChatAgentWrapper(
            agent=agent,
            toolkit=toolkit,
            config=hr_config,
            db_path=self.rag_lancedb_path,
            background_context=self.background_context,
        )


def register_metaconfig():
    ac_klass_registry = config.AGENT_CONFIG_CLASSES_BY_KIND
    ac_klass_registry[ChatAgentConfig.kind] = ChatAgentConfig
