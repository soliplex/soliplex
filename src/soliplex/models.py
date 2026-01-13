from __future__ import annotations

import dataclasses
import datetime
import pathlib
import typing

import pydantic
from ag_ui import core as agui_core

from soliplex import agui as agui_package
from soliplex import authz as authz_package
from soliplex import config

KW_ONLY = pydantic.Field(kw_only=True)
KW_ONLY_NONE = pydantic.Field(kw_only=True, default=None)

# ============================================================================
#   Public config models
#
#   Types returned from API methods describing the installation config
#   These models omit private / implementation fields
# ============================================================================


class QuizQuestionMetadata(pydantic.BaseModel):
    type: str
    uuid: str
    options: list[str] | None

    @classmethod
    def from_config(cls, qq_meta: config.QuizQuestionMetadata):
        return cls(
            type=str(qq_meta.type),
            uuid=qq_meta.uuid,
            options=qq_meta.options,
        )


class QuizQuestion(pydantic.BaseModel):
    inputs: str
    expected_output: str
    metadata: QuizQuestionMetadata

    @classmethod
    def from_config(cls, question: config.QuizQuestionMetadata):
        return cls(
            inputs=question.inputs,
            expected_output=question.expected_output,
            metadata=QuizQuestionMetadata.from_config(question.metadata),
        )


class QuizAnswer(pydantic.BaseModel):
    text: str


class Quiz(pydantic.BaseModel):
    """Metadata about a quiz"""

    id: str
    title: str
    randomize: bool
    max_questions: int | None = None

    questions: list[QuizQuestion]

    @classmethod
    def from_config(cls, quiz_config: config.QuizConfig):
        questions = [
            QuizQuestion.from_config(question)
            for question in quiz_config.get_questions()
        ]
        return cls(
            id=quiz_config.id,
            title=quiz_config.title,
            randomize=quiz_config.randomize,
            max_questions=quiz_config.max_questions,
            questions=questions,
        )


ConfiguredQuizzes = dict[str, Quiz]


class Tool(pydantic.BaseModel):
    kind: str
    tool_name: str
    tool_description: str
    tool_requires: config.ToolRequires  # enum, not dataclass
    allow_mcp: bool
    agui_feature_names: list[str]
    extra_parameters: dict[str, typing.Any]

    @classmethod
    def from_config(cls, tool_config: config.ToolConfig):
        return cls(
            kind=tool_config.kind,
            tool_name=tool_config.tool_name,
            tool_description=tool_config.tool_description,
            tool_requires=tool_config.tool_requires,
            allow_mcp=tool_config.allow_mcp,
            agui_feature_names=list(tool_config.agui_feature_names),
            extra_parameters=tool_config.get_extra_parameters(),
        )


ConfiguredTools = dict[str, Tool]


class MCPClientToolset(pydantic.BaseModel):
    kind: str
    allowed_tools: list[str] | None
    toolset_params: dict[str, typing.Any]

    @classmethod
    def from_config(cls, mcp_ct_config):
        return cls(
            kind=mcp_ct_config.kind,
            allowed_tools=mcp_ct_config.allowed_tools,
            toolset_params=mcp_ct_config.toolset_params,
        )


ConfiguredMCPClientToolsets = dict[str, MCPClientToolset]


class DefaultAgent(pydantic.BaseModel):
    id: str
    model_name: str
    retries: int
    system_prompt: str | None
    provider_type: config.LLMProviderType  # enum, not dataclass
    provider_base_url: str
    provider_key: str

    @classmethod
    def from_config(cls, agent_config: config.AgentConfig):
        llm_provider_kw = agent_config.llm_provider_kw
        return cls(
            id=agent_config.id,
            model_name=agent_config.model_name,
            retries=agent_config.retries,
            system_prompt=agent_config.get_system_prompt(),
            provider_type=agent_config.provider_type,
            provider_base_url=llm_provider_kw["base_url"],
            provider_key=agent_config.provider_key or "dummy",
        )


class FactoryAgent(pydantic.BaseModel):
    id: str
    factory_name: str  # dotted name for import
    with_agent_config: bool
    extra_config: dict[str, typing.Any]

    @classmethod
    def from_config(cls, agent_config: config.AgentConfig):
        return cls(
            id=agent_config.id,
            factory_name=agent_config.factory_name,
            with_agent_config=agent_config.with_agent_config,
            extra_config=agent_config.extra_config,
        )


Agent = DefaultAgent | FactoryAgent


class AGUI_Feature(pydantic.BaseModel):
    name: str
    description: str
    source: config.AGUI_FeatureSource
    json_schema: dict[str, typing.Any]

    @classmethod
    def from_config(cls, agui_feature: config.AGUI_Feature):
        return cls(
            name=agui_feature.name,
            description=agui_feature.description,
            source=agui_feature.source,
            json_schema=agui_feature.json_schema,
        )


class Room(pydantic.BaseModel):
    id: str
    name: str
    description: str
    welcome_message: str
    suggestions: list[str]
    enable_attachments: bool
    tools: ConfiguredTools
    mcp_client_toolsets: ConfiguredMCPClientToolsets
    quizzes: ConfiguredQuizzes
    agent: Agent
    agui_feature_names: list[str]
    allow_mcp: bool

    @classmethod
    def from_config(cls, room_config: config.RoomConfig):
        agent_config = room_config.agent_config

        if agent_config.kind == "factory":
            agent = FactoryAgent.from_config(room_config.agent_config)
        else:
            agent = DefaultAgent.from_config(room_config.agent_config)

        return cls(
            id=room_config.id,
            name=room_config.name,
            description=room_config.description,
            welcome_message=(
                room_config.welcome_message or room_config.description
            ),
            suggestions=room_config.suggestions,
            enable_attachments=room_config.enable_attachments,
            tools={
                key: Tool.from_config(tool_config)
                for (key, tool_config) in room_config.tool_configs.items()
            },
            mcp_client_toolsets={
                key: MCPClientToolset.from_config(mcp_ct_config)
                for (
                    key,
                    mcp_ct_config,
                ) in room_config.mcp_client_toolset_configs.items()
            },
            quizzes={
                quiz.id: Quiz.from_config(quiz) for quiz in room_config.quizzes
            },
            allow_mcp=room_config.allow_mcp,
            agui_feature_names=room_config.agui_feature_names,
            agent=agent,
        )


ConfiguredRooms = dict[str, Room]


class Completion(pydantic.BaseModel):
    id: str
    name: str
    tools: ConfiguredTools
    agent: Agent

    @classmethod
    def from_config(cls, completion_config: config.CompletionConfig):
        agent_config = completion_config.agent_config

        if agent_config.kind == "factory":
            agent = FactoryAgent.from_config(completion_config.agent_config)
        else:
            agent = DefaultAgent.from_config(completion_config.agent_config)

        return cls(
            id=completion_config.id,
            name=completion_config.name,
            tools={
                key: Tool.from_config(tool_config)
                for (
                    key,
                    tool_config,
                ) in completion_config.tool_configs.items()
            },
            agent=agent,
        )


ConfiguredCompletions = dict[str, Completion]


class OIDCAuthSystem(pydantic.BaseModel):
    id: str
    title: str
    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str | None = None

    @classmethod
    def from_config(cls, oas_config: config.OIDCAuthSystemConfig):
        kwargs = dataclasses.asdict(
            dataclasses.replace(oas_config, _installation_config=None)
        )
        return cls(**kwargs)


ConfiguredOIDCAuthSystems = dict[str, OIDCAuthSystem]


class SecretSource(pydantic.BaseModel):
    kind: str
    extra_arguments: dict[str, typing.Any]

    @classmethod
    def from_config(cls, source_config: config.SecretSource):
        return cls(
            kind=source_config.kind,
            extra_arguments=source_config.extra_arguments,
        )


class Secret(pydantic.BaseModel):
    secret_name: str
    sources: list[SecretSource]

    @classmethod
    def from_config(cls, secret_config: config.SecretConfig):
        return cls(
            secret_name=secret_config.secret_name,
            sources=[
                SecretSource.from_config(source)
                for source in secret_config.sources
            ],
        )


class Installation(pydantic.BaseModel):
    """Configuration for a set of rooms, completions, etc."""

    id: str
    secrets: list[Secret] = []
    environment: dict[str, typing.Any] = {}
    haiku_rag_config_file: pathlib.Path | None = None
    agents: list[DefaultAgent] = []
    agui_features: list[AGUI_Feature] = []
    oidc_paths: list[pathlib.Path] = []
    room_paths: list[pathlib.Path] = []
    completion_paths: list[pathlib.Path] = []
    quizzes_paths: list[pathlib.Path] = []
    oidc_auth_systems: list[OIDCAuthSystem] = []
    thread_persistence_dburi_sync: str | None = None
    thread_persistence_dburi_async: str | None = None

    @classmethod
    def from_config(cls, installation_config: config.InstallationConfig):
        oidc_auth_systems = [
            OIDCAuthSystem.from_config(oas_config)
            for oas_config in installation_config.oidc_auth_system_configs
        ]
        secrets = [
            Secret.from_config(secret_config)
            for secret_config in installation_config.secrets
        ]
        agents = [
            DefaultAgent.from_config(agent_config)
            for agent_config in installation_config.agent_configs
        ]
        agui_features = [
            AGUI_Feature.from_config(agui_feature)
            for agui_feature in installation_config.agui_features
        ]
        return cls(
            id=installation_config.id,
            secrets=secrets,
            environment=installation_config.environment,
            haiku_rag_config_file=installation_config._haiku_rag_config_file,
            agents=agents,
            agui_features=agui_features,
            oidc_paths=installation_config.oidc_paths,
            room_paths=installation_config.room_paths,
            completion_paths=installation_config.completion_paths,
            quizzes_paths=installation_config.quizzes_paths,
            oidc_auth_systems=oidc_auth_systems,
            # Use the non-property versions here to avoid exposing
            # interpolated secrets
            thread_persistence_dburi_sync=(
                installation_config._thread_persistence_dburi_sync
                or config.SYNC_MEMORY_ENGINE_URL
            ),
            thread_persistence_dburi_async=(
                installation_config._thread_persistence_dburi_async
                or config.ASYNC_MEMORY_ENGINE_URL
            ),
        )


# ============================================================================
#   API interaction models
# ============================================================================


# ----------------------------------------------------------------------------
#   MCP auth-related models
# ----------------------------------------------------------------------------
class MCPToken(pydantic.BaseModel):
    room_id: str
    mcp_token: str


# ----------------------------------------------------------------------------
#   Tool-related models
# ----------------------------------------------------------------------------


class UserProfile(pydantic.BaseModel):
    given_name: str
    family_name: str
    email: str
    preferred_username: str


# ----------------------------------------------------------------------------
#   Room-related models
# ----------------------------------------------------------------------------


class RAGDocument(pydantic.BaseModel):
    """Documents from a room's RAG database"""

    id: str
    uri: str | None
    title: str | None
    metadata: dict[str, typing.Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime


RAGDocumentSet = dict[str, RAGDocument]


class RoomDocuments(pydantic.BaseModel):
    room_id: str
    document_set: RAGDocumentSet


# ----------------------------------------------------------------------------
#   Authentication-related models
# ----------------------------------------------------------------------------

UserInfo = dict[str, typing.Any]


# ----------------------------------------------------------------------------
#   AG-UI-related models
# ----------------------------------------------------------------------------

AGUI_Events = list[agui_core.Event]


class AGUI_RunMetadata(pydantic.BaseModel):
    """Metadata for a run

    Set all fields to 'None' to erase existing metadata.
    """

    label: str | None = KW_ONLY_NONE

    @classmethod
    def from_run_meta(
        cls,
        a_run_meta: agui_package.RunMeta | None,
    ):
        if a_run_meta is not None:
            return cls(
                label=a_run_meta.label,
            )


class AGUI_RunFeedback(pydantic.BaseModel):
    """Feedback for a run"""

    feedback: str = KW_ONLY
    reason: str | None = KW_ONLY_NONE


class AGUI_NewRunRequest(pydantic.BaseModel):
    parent_run_id: str = KW_ONLY_NONE
    metadata: AGUI_RunMetadata = KW_ONLY_NONE


class AGUI_RunUsage(pydantic.BaseModel):
    input_tokens: int
    output_tokens: int
    requests: int
    tool_calls: int

    @classmethod
    def from_tuple(cls, ru_tuple: agui_package.RunUsageStats):
        return cls(
            input_tokens=ru_tuple.input_tokens,
            output_tokens=ru_tuple.output_tokens,
            requests=ru_tuple.requests,
            tool_calls=ru_tuple.tool_calls,
        )


class AGUI_Run(pydantic.BaseModel):
    thread_id: str = KW_ONLY
    run_id: str = KW_ONLY

    parent_run_id: str | None = KW_ONLY_NONE

    run_input: agui_core.RunAgentInput | None = KW_ONLY_NONE
    created: datetime.datetime = KW_ONLY_NONE
    finished: datetime.datetime | None = KW_ONLY_NONE

    events: AGUI_Events | None = pydantic.Field(
        kw_only=True,
        default_factory=list,
    )
    metadata: AGUI_RunMetadata | None = KW_ONLY_NONE
    usage: AGUI_RunUsage | None = KW_ONLY_NONE

    @classmethod
    def from_run(
        cls,
        a_run: agui_package.Run,
        a_run_input: agui_core.RunAgentInput | None = None,
        a_run_meta: agui_package.RunMetadata = None,
        a_run_events: list[agui_package.RunEvent] = None,
        a_run_usage: agui_package.RunUsageStats | None = None,
    ):
        return cls(
            thread_id=a_run.thread_id,
            run_id=a_run.run_id,
            created=a_run.created,
            finished=a_run.finished,
            parent_run_id=a_run.parent_run_id,
            run_input=a_run_input,
            events=a_run_events,
            metadata=AGUI_RunMetadata.from_run_meta(a_run_meta),
            usage=(
                AGUI_RunUsage.from_tuple(a_run_usage) if a_run_usage else None
            ),
        )


AGUI_Runs = dict[str, AGUI_Run]


class AGUI_ThreadMetadata(pydantic.BaseModel):
    """Metadata for a thread

    Set all fields to 'None' to erase existing metadata.
    """

    name: str | None = KW_ONLY_NONE
    description: str | None = KW_ONLY_NONE

    @classmethod
    def from_thread_meta(
        cls,
        a_thread_meta: agui_package.ThreadMeta | None,
    ):
        if a_thread_meta is not None:
            return cls(
                name=a_thread_meta.name,
                description=a_thread_meta.description,
            )


class AGUI_NewThreadRequest(pydantic.BaseModel):
    metadata: AGUI_ThreadMetadata = KW_ONLY_NONE


class AGUI_Thread(pydantic.BaseModel):
    room_id: str = KW_ONLY
    thread_id: str = KW_ONLY

    runs: AGUI_Runs | None = pydantic.Field(
        kw_only=True,
        default_factory=dict,
    )

    created: datetime.datetime | None = KW_ONLY_NONE
    metadata: AGUI_ThreadMetadata | None = KW_ONLY_NONE

    @classmethod
    def from_thread(
        cls,
        a_thread: agui_package.Thread,
        a_thread_meta: AGUI_ThreadMetadata,
        a_thread_runs: AGUI_Runs = None,
    ):
        return cls(
            room_id=a_thread.room_id,
            thread_id=a_thread.thread_id,
            created=a_thread.created,
            metadata=a_thread_meta,
            runs=a_thread_runs,
        )


class AGUI_Threads(pydantic.BaseModel):
    threads: list[AGUI_Thread]


# ----------------------------------------------------------------------------
#   Room Authorization models
# ----------------------------------------------------------------------------


class ACLEntry(pydantic.BaseModel):
    allow_deny: authz_package.AllowDeny = authz_package.AllowDeny.DENY
    everyone: bool = False
    authenticated: bool = False
    preferred_username: str | None = None
    email: str | None = None


class RoomPolicy(pydantic.BaseModel):
    room_id: str
    default_allow_deny: authz_package.AllowDeny = authz_package.AllowDeny.DENY
    acl_entries: list[ACLEntry] = pydantic.Field(default_factory=list)


# ----------------------------------------------------------------------------
#   'ask_with_rich_citations' tool models
# ----------------------------------------------------------------------------


class ChunkVisualization(pydantic.BaseModel):
    """Page images for a chunk, with chunk text highlighted"""

    chunk_id: str
    document_uri: str | None
    images_base_64: list[str]


# ----------------------------------------------------------------------------
#   Quiz-related models
# ----------------------------------------------------------------------------


class QuizLLMJudgeResponse(pydantic.BaseModel):
    equivalent: bool


class QuizQuestionResponse(pydantic.BaseModel):
    correct: str  # client expects 'true' or 'false'
    expected_output: str = None


# ----------------------------------------------------------------------------
#   Completion-related models
# ----------------------------------------------------------------------------


class ChatMessage(pydantic.BaseModel):
    role: str
    content: str


class ChatCompletionRequest(pydantic.BaseModel):
    model: str
    messages: list[ChatMessage]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    stop: list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    user: str | None = None
    Config: dict[str, str] = {"extra": "allow"}
