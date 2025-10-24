from __future__ import annotations

import dataclasses
import pathlib
import typing
import uuid

import pydantic

from soliplex import config
from soliplex import convos

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
    extra_parameters: dict[str, typing.Any]

    @classmethod
    def from_config(cls, tool_config: config.ToolConfig):
        return cls(
            kind=tool_config.kind,
            tool_name=tool_config.tool_name,
            tool_description=tool_config.tool_description,
            tool_requires=tool_config.tool_requires,
            allow_mcp=tool_config.allow_mcp,
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


class Agent(pydantic.BaseModel):
    id: str
    model_name: str
    system_prompt: str
    provider_type: config.LLMProviderType  # enum, not dataclass
    provider_base_url: str
    provider_key: str

    @classmethod
    def from_config(cls, agent_config: config.AgentConfig):
        llm_provider_kw = agent_config.llm_provider_kw
        return cls(
            id=agent_config.id,
            model_name=agent_config.model_name,
            system_prompt=agent_config.get_system_prompt(),
            provider_type=agent_config.provider_type,
            provider_base_url=llm_provider_kw["base_url"],
            provider_key=agent_config.provider_key or "dummy",
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

    @classmethod
    def from_config(cls, room_config: config.RoomConfig):
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
            agent=Agent.from_config(room_config.agent_config),
        )


ConfiguredRooms = dict[str, Room]


class Completion(pydantic.BaseModel):
    id: str
    name: str
    tools: ConfiguredTools
    agent: Agent

    @classmethod
    def from_config(cls, completion_config: config.CompletionConfig):
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
            agent=Agent.from_config(completion_config.agent_config),
        )


ConfiguredCompletions = dict[str, Completion]


class OIDCAuthSystem(pydantic.BaseModel):
    id: str
    title: str
    server_url: str
    client_id: str
    include_return_to: bool
    token_validation_pem: str | None = None
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
    environment: dict[str, str] = {}
    agents: list[Agent] = []
    oidc_paths: list[pathlib.Path] = []
    room_paths: list[pathlib.Path] = []
    completion_paths: list[pathlib.Path] = []
    quizzes_paths: list[pathlib.Path] = []
    oidc_auth_systems: list[OIDCAuthSystem] = []

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
            Agent.from_config(agent_config)
            for agent_config in installation_config.agent_configs
        ]
        return cls(
            id=installation_config.id,
            secrets=secrets,
            agents=agents,
            environment=installation_config.environment,
            oidc_paths=installation_config.oidc_paths,
            room_paths=installation_config.room_paths,
            completion_paths=installation_config.completion_paths,
            quizzes_paths=installation_config.quizzes_paths,
            oidc_auth_systems=oidc_auth_systems,
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


class AgentDependencies(pydantic.BaseModel):
    the_installation: typing.Any  # installation.Installation
    user: UserProfile = None  # TBD make required


class SearchResult(pydantic.BaseModel):
    content: str
    score: float
    document_uri: str | None = None


UserInfo = dict[str, typing.Any]

# ----------------------------------------------------------------------------
#   Convos-related models
# ----------------------------------------------------------------------------


class ConvoHistoryMessage(pydantic.BaseModel):
    """Message fetched from a convo history."""

    origin: typing.Literal["user", "llm"]
    text: str
    timestamp: str | None

    @classmethod
    def from_convos_message(cls, message: convos.ConvoHistoryMessage):
        return cls(
            origin=message.origin,
            text=message.text,
            timestamp=message.timestamp,
        )


class Conversation(pydantic.BaseModel):
    convo_uuid: uuid.UUID
    name: str
    room_id: str
    message_history: list[ConvoHistoryMessage]

    @classmethod
    def from_convos_info(cls, info: convos.ConversationInfo):
        return cls(
            convo_uuid=info.convo_uuid,
            name=info.name,
            room_id=info.room_id,
            message_history=[
                ConvoHistoryMessage.from_convos_message(message)
                for message in info.message_history
            ],
        )


ConversationMap = dict[uuid.UUID, Conversation]


class UserPromptClientMessage(pydantic.BaseModel):
    text: str


class NewConvoClientMessage(pydantic.BaseModel):
    text: str
    room_id: str


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
