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
from haiku.rag.agents.chat import state as hr_agents_chat_state
from haiku.rag.config import models as hr_config_models
from pydantic_ai import messages as ai_messages
from pydantic_ai import run as ai_run
from pydantic_ai.agent import abstract as ai_ag_abstract

from soliplex import agents
from soliplex import config

NativeEvent = (
    ai_messages.AgentStreamEvent | ai_run.AgentRunResultEvent[typing.Any]
)


@dataclasses.dataclass
class ChatAgentWrapper:
    """Wrapper around haiku.rag chat agent that translates dependencies.

    This wrapper accepts Soliplex's AgentDependencies and internally creates
    haiku.rag's ChatDeps, managing the HaikuRAG client lifecycle.
    """

    agent: pydantic_ai.Agent[hr_agents_chat_state.ChatDeps, str]
    config: hr_config_models.AppConfig
    db_path: pathlib.Path
    background_context: str | None = None

    output_type = None

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
        state_dict = deps.state.get(hr_agents_chat.AGUI_STATE_KEY, {})
        if state_dict:
            session_state = (
                hr_agents_chat_state.ChatSessionState.model_validate(
                    state_dict
                )
            )
        else:
            session_state = hr_agents_chat_state.ChatSessionState()

        if self.background_context and not session_state.initial_context:
            session_state.initial_context = self.background_context

        async with hr_client.HaikuRAG(
            db_path=self.db_path,
            config=self.config,
        ) as client:
            chat_deps = hr_agents_chat_state.ChatDeps(
                client=client,
                config=self.config,
                session_state=session_state,
                state_key=hr_agents_chat.AGUI_STATE_KEY,
            )

            async for event in self.agent.run_stream_events(
                output_type=output_type,
                message_history=message_history,
                deferred_tool_results=deferred_tool_results,
                deps=chat_deps,
                **kwargs,
            ):
                yield event


def _resolve_db_path(
    extra_config: dict,
    installation_config: config.InstallationConfig,
) -> pathlib.Path:
    """Resolve the RAG database path from agent config."""
    if "rag_lancedb_override_path" in extra_config:
        return pathlib.Path(extra_config["rag_lancedb_override_path"])

    stem = extra_config.get("rag_lancedb_stem", "rag")
    base_path = installation_config.get_environment("RAG_LANCE_DB_PATH")
    return pathlib.Path(base_path) / f"{stem}.lancedb"


def chat_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
) -> ChatAgentWrapper:
    """Factory function that creates a haiku.rag chat agent wrapper.

    DEPRECATED:  use 'ChatAgentConfig' below instead.

    This factory is intended to be used with Soliplex's factory agent
    configuration:

        agent:
          kind: "factory"
          factory_name: "soliplex.haiku_chat.chat_agent_factory"
          with_agent_config: true
          extra_config:
            rag_lancedb_stem: "rag"

    Args:
        agent_config: The factory agent configuration
        tool_configs: Tool configurations (unused - chat agent has built-in
            tools)
        mcp_client_toolset_configs: MCP toolset configs (unused)

    Returns:
        ChatAgentWrapper instance ready for use with Soliplex
    """
    installation_config = agent_config._installation_config
    hr_config = installation_config.haiku_rag_config
    db_path = _resolve_db_path(agent_config.extra_config, installation_config)
    background_context = agent_config.extra_config.get("background_context")

    agent = hr_agents_chat_agent.create_chat_agent(hr_config)

    return ChatAgentWrapper(
        agent=agent,
        config=hr_config,
        db_path=db_path,
        background_context=background_context,
    )


@dataclasses.dataclass(kw_only=True)
class ChatAgentConfig(config._RAGConfigBase):
    """Custom config type for the 'haiku.rag.chat' agent
    This config class is intended to be used in a Soliplex room or
    completion configuration:

        agent:
          kind: "haiku_chat"
          rag_lancedb_stem: "rag"
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
        return (hr_agents_chat.AGUI_STATE_KEY,)

    @property
    def as_yaml(self):
        result = {
            "id": self.id,
        }

        if self.background_context is not None:
            result["background_context"] = self.background_context

        if self.rag_lancedb_override_path is not None:
            result["rag_lancedb_override_path"] = (
                self.rag_lancedb_override_path
            )
        else:
            result["rag_lancedb_stem"] = self.rag_lancedb_stem

        return result

    def factory(self, **_kwargs) -> ai_ag_abstract.AbstractAgent:
        agent = hr_agents_chat_agent.create_chat_agent(self.haiku_rag_config)

        return ChatAgentWrapper(
            agent=agent,
            config=self.haiku_rag_config,
            db_path=self.rag_lancedb_path,
            background_context=self.background_context,
        )


def register_metaconfig():
    ac_klass_registry = config.AGENT_CONFIG_CLASSES_BY_KIND
    ac_klass_registry[ChatAgentConfig.kind] = ChatAgentConfig
