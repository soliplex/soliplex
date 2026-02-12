import dataclasses
import pathlib
import typing
from collections import abc

from haiku.rag import client as hr_client
from haiku.rag.agents import chat as hr_agents_chat
from haiku.rag.agents.chat import agent as hr_agents_chat_agent
from haiku.rag.config import models as hr_config_models
from haiku.rag.tools import context as hr_tools_context
from pydantic_ai import messages as ai_messages
from pydantic_ai import run as ai_run
from pydantic_ai.agent import abstract as ai_ag_abstract

from soliplex import agents
from soliplex import config

NativeEvent = (
    ai_messages.AgentStreamEvent | ai_run.AgentRunResultEvent[typing.Any]
)

AGUI_STATE_KEY = hr_agents_chat.AGUI_STATE_KEY


@dataclasses.dataclass
class ChatAgentWrapper:
    """Wrapper around haiku.rag chat agent that translates dependencies.

    This wrapper accepts Soliplex's AgentDependencies and internally creates
    haiku.rag's ChatDeps, managing the HaikuRAG client lifecycle.

    The agent is created per-request because it requires a live
    HaikuRAG client and ToolContext for agent creation.
    """

    config: hr_config_models.AppConfig
    db_path: pathlib.Path
    background_context: str | None = None
    features: list[str] | None = None
    _context_cache: hr_tools_context.ToolContextCache = dataclasses.field(
        default_factory=hr_tools_context.ToolContextCache,
    )

    output_type = None

    async def _translate_document_filter(
        self,
        client: hr_client.HaikuRAG,
        state: dict,
    ) -> list[str]:
        """Translate document IDs from AG-UI state to document names."""
        filter_docs = state.get("filter_documents")
        if not filter_docs:
            return []

        doc_ids = filter_docs.get("document_ids")
        if not doc_ids:
            return []

        doc_names = []
        for doc_id in doc_ids:
            doc = await client.get_document_by_id(doc_id)
            if doc is not None:
                doc_names.append(doc.title or doc.uri)
        return doc_names

    async def run_stream_events(
        self,
        output_type=None,
        message_history=None,
        deferred_tool_results=None,
        deps: agents.AgentDependencies = None,
        **kwargs,
    ) -> abc.AsyncIterator[NativeEvent]:
        """Run the agent and stream events.

        Creates a fresh chat agent per-request with a live HaikuRAG client
        and ToolContext. Translates AgentDependencies state to ChatDeps.
        """
        thread_id = deps.thread_id or "default"
        context, _is_new = self._context_cache.get_or_create(thread_id)

        state = dict(deps.state) if deps.state else {}
        chat_state = dict(state.get(AGUI_STATE_KEY, {}))

        async with hr_client.HaikuRAG(
            db_path=self.db_path,
            config=self.config,
        ) as client:
            doc_names = await self._translate_document_filter(
                client,
                state,
            )
            if doc_names:
                chat_state["document_filter"] = doc_names

            if self.background_context:
                chat_state.setdefault(
                    "initial_context",
                    self.background_context,
                )

            state[AGUI_STATE_KEY] = chat_state

            agent = hr_agents_chat_agent.create_chat_agent(
                self.config,
                client,
                context,
                features=self.features,
            )

            chat_deps = hr_agents_chat_agent.ChatDeps(
                config=self.config,
                tool_context=context,
                state_key=AGUI_STATE_KEY,
            )
            chat_deps.state = state

            try:
                async for event in agent.run_stream_events(
                    output_type=output_type,
                    message_history=message_history,
                    deferred_tool_results=deferred_tool_results,
                    deps=chat_deps,
                    **kwargs,
                ):
                    yield event
            finally:
                hr_agents_chat_agent.trigger_background_summarization(
                    chat_deps,
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
    features: list[str] = None

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

            features = config_dict.pop("features", None)
            if features is not None:
                config_dict["features"] = features

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

        if self.features is not None:
            result["features"] = self.features

        if self.rag_lancedb_override_path is not None:
            result["rag_lancedb_override_path"] = (
                self.rag_lancedb_override_path
            )
        else:
            result["rag_lancedb_stem"] = self.rag_lancedb_stem

        return result

    def factory(self, **_kwargs) -> ai_ag_abstract.AbstractAgent:
        return ChatAgentWrapper(
            config=self.haiku_rag_config,
            db_path=self.rag_lancedb_path,
            background_context=self.background_context,
            features=self.features,
        )


def register_metaconfig():
    ac_klass_registry = config.AGENT_CONFIG_CLASSES_BY_KIND
    ac_klass_registry[ChatAgentConfig.kind] = ChatAgentConfig
