"""Factory agent for haiku.rag conversational chat agent.

This module provides a factory that creates a wrapper around haiku.rag's
chat agent, translating Soliplex's AgentDependencies to haiku.rag's ChatDeps.
"""

import dataclasses
import typing
from collections import abc
from pathlib import Path

from haiku.rag import client as rag_client
from haiku.rag.agents.chat import AGUI_STATE_KEY
from haiku.rag.agents.chat import agent as chat_agent
from haiku.rag.agents.chat.state import ChatDeps
from haiku.rag.agents.chat.state import ChatSessionState
from haiku.rag.config.models import AppConfig
from pydantic_ai import Agent
from pydantic_ai import messages as ai_messages
from pydantic_ai import run as ai_run

from soliplex import agents
from soliplex import config

HaikuRAG = rag_client.HaikuRAG
create_chat_agent = chat_agent.create_chat_agent

NativeEvent = (
    ai_messages.AgentStreamEvent | ai_run.AgentRunResultEvent[typing.Any]
)


@dataclasses.dataclass
class ChatAgentWrapper:
    """Wrapper around haiku.rag chat agent that translates dependencies.

    This wrapper accepts Soliplex's AgentDependencies and internally creates
    haiku.rag's ChatDeps, managing the HaikuRAG client lifecycle.
    """

    agent: Agent[ChatDeps, str]
    config: AppConfig
    db_path: Path
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
        state_dict = deps.state.get(AGUI_STATE_KEY, {})
        if state_dict:
            session_state = ChatSessionState.model_validate(state_dict)
        else:
            session_state = ChatSessionState()

        if self.background_context:
            session_state.background_context = self.background_context

        async with HaikuRAG(
            db_path=self.db_path,
            config=self.config,
        ) as client:
            chat_deps = ChatDeps(
                client=client,
                config=self.config,
                session_state=session_state,
                state_key=AGUI_STATE_KEY,
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
) -> Path:
    """Resolve the RAG database path from agent config."""
    if "rag_lancedb_override_path" in extra_config:
        return Path(extra_config["rag_lancedb_override_path"])

    stem = extra_config.get("rag_lancedb_stem", "rag")
    base_path = installation_config.get_environment("RAG_LANCE_DB_PATH")
    return Path(base_path) / f"{stem}.lancedb"


def chat_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
) -> ChatAgentWrapper:
    """Factory function that creates a haiku.rag chat agent wrapper.

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

    agent = create_chat_agent(hr_config)

    return ChatAgentWrapper(
        agent=agent,
        config=hr_config,
        db_path=db_path,
        background_context=background_context,
    )
