from __future__ import annotations

import dataclasses
import datetime
import pathlib
import typing

import pydantic
from ag_ui import core as agui_core
from haiku.rag.store.models import chunk as hr_chunk

from soliplex import agui
from soliplex import authz
from soliplex.config import agents as config_agents
from soliplex.config import agui as config_agui
from soliplex.config import authsystem as config_authsystem
from soliplex.config import completions as config_completions
from soliplex.config import installation as config_installation
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rooms as config_rooms
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

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
    def from_config(cls, qq_meta: config_quizzes.QuizQuestionMetadata):
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
    def from_config(cls, question: config_quizzes.QuizQuestionMetadata):
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
    def from_config(cls, quiz_config: config_quizzes.QuizConfig):
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
    tool_requires: config_tools.ToolRequires  # enum, not dataclass
    allow_mcp: bool
    agui_feature_names: list[str]
    extra_parameters: dict[str, typing.Any]

    @classmethod
    def from_config(cls, tool_config: config_tools.ToolConfig):
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


SkillAllowedTools = str | None
SkillMetadata = dict[str, typing.Any] | None


class Skill(pydantic.BaseModel):
    source: config_skills.SkillKind | None = None
    name: str
    description: str
    license: str | None
    compatibility: str | None
    allowed_tools: SkillAllowedTools = None
    metadata: SkillMetadata = None
    state_type_schema: dict[str, typing.Any] | None = None
    state_namespace: str | None = None
    extra_parameters: dict[str, typing.Any] = {}

    @classmethod
    def from_config(cls, skill_config: config_skills.SkillConfigTypes):
        kwargs = {}

        if skill_config.state_type is not None:
            kwargs["state_type_schema"] = (
                skill_config.state_type.model_json_schema()
            )

        extra_parameters = skill_config.extra_parameters
        if extra_parameters:
            kwargs["extra_parameters"] = extra_parameters

        return cls(
            source=skill_config.source,
            name=skill_config.name,
            description=skill_config.description,
            license=skill_config.license,
            compatibility=skill_config.compatibility,
            allowed_tools=" ".join(skill_config.allowed_tools),
            metadata=skill_config.metadata,
            state_namespace=skill_config.state_namespace,
            **kwargs,
        )


ConfiguredSkills = dict[str, Skill]


class DefaultAgent(pydantic.BaseModel):
    id: str
    model_name: str
    retries: int
    system_prompt: str | None
    provider_type: config_agents.LLMProviderType  # enum, not dataclass
    provider_base_url: str | None
    provider_key: str
    agui_feature_names: list[str] = pydantic.Field(default_factory=list)

    @classmethod
    def from_config(cls, agent_config: config_agents.AgentConfig):
        llm_provider_kw = agent_config.llm_provider_kw
        return cls(
            id=agent_config.id,
            model_name=agent_config.model_name,
            retries=agent_config.retries,
            system_prompt=agent_config.get_system_prompt(),
            provider_type=agent_config.provider_type,
            provider_base_url=llm_provider_kw.get("base_url"),
            provider_key=agent_config.provider_key or "dummy",
        )


class FactoryAgent(pydantic.BaseModel):
    id: str
    factory_name: str  # dotted name for import
    with_agent_config: bool
    extra_config: dict[str, typing.Any]
    agui_feature_names: list[str] = pydantic.Field(default_factory=list)

    @classmethod
    def from_config(cls, agent_config: config_agents.AgentConfig):
        agui_feature_names = getattr(agent_config, "agui_feature_names", [])
        return cls(
            id=agent_config.id,
            factory_name=agent_config.factory_name,
            with_agent_config=agent_config.with_agent_config,
            extra_config=agent_config.extra_config,
            agui_feature_names=agui_feature_names,
        )


class OtherAgent(pydantic.BaseModel):
    id: str
    kind: str
    agui_feature_names: list[str] = pydantic.Field(default_factory=list)

    @classmethod
    def from_config(cls, agent_config):
        agui_feature_names = getattr(agent_config, "agui_feature_names", [])
        return cls(
            id=agent_config.id,
            kind=agent_config.kind,
            agui_feature_names=agui_feature_names,
        )


Agent = DefaultAgent | FactoryAgent | OtherAgent


class AGUI_Feature(pydantic.BaseModel):
    name: str
    description: str
    source: config_agui.AGUI_FeatureSource
    json_schema: dict[str, typing.Any]

    @classmethod
    def from_config(cls, agui_feature: config_agui.AGUI_Feature):
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
    tools: ConfiguredTools
    mcp_client_toolsets: ConfiguredMCPClientToolsets
    skills: ConfiguredSkills
    quizzes: ConfiguredQuizzes
    agent: Agent
    agui_feature_names: list[str]
    allow_mcp: bool

    @classmethod
    def from_config(cls, room_config: config_rooms.RoomConfig):
        agent_config = room_config.agent_config

        if agent_config.kind == "factory":
            agent = FactoryAgent.from_config(room_config.agent_config)
        elif agent_config.kind == "default":
            agent = DefaultAgent.from_config(room_config.agent_config)
        else:
            agent = OtherAgent.from_config(room_config.agent_config)

        return cls(
            id=room_config.id,
            name=room_config.name,
            description=room_config.description,
            welcome_message=(
                room_config.welcome_message or room_config.description
            ),
            suggestions=room_config.suggestions,
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
            skills={
                key: Skill.from_config(skill_config)
                for key, skill_config in room_config.skill_configs.items()
            },
            quizzes={
                quiz.id: Quiz.from_config(quiz) for quiz in room_config.quizzes
            },
            allow_mcp=room_config.allow_mcp,
            agui_feature_names=list(room_config.agui_feature_names),
            agent=agent,
        )


ConfiguredRooms = dict[str, Room]


class RoomStats(pydantic.BaseModel):
    room_id: str = KW_ONLY
    # None means the user has no runs in the room.
    last_activity: pydantic.AwareDatetime | None = KW_ONLY_NONE


class Completion(pydantic.BaseModel):
    id: str
    name: str
    tools: ConfiguredTools
    agent: Agent

    @classmethod
    def from_config(
        cls,
        completion_config: config_completions.CompletionConfig,
    ):
        agent_config = completion_config.agent_config

        if agent_config.kind == "factory":
            agent = FactoryAgent.from_config(completion_config.agent_config)
        elif agent_config.kind == "default":
            agent = DefaultAgent.from_config(completion_config.agent_config)
        else:
            agent = OtherAgent.from_config(completion_config.agent_config)

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
    def from_config(cls, oas_config: config_authsystem.OIDCAuthSystemConfig):
        kwargs = dataclasses.asdict(
            dataclasses.replace(oas_config, _installation_config=None)
        )
        return cls(**kwargs)


ConfiguredOIDCAuthSystems = dict[str, OIDCAuthSystem]


class SecretSource(pydantic.BaseModel):
    kind: str
    extra_arguments: dict[str, typing.Any]

    @classmethod
    def from_config(cls, source_config: config_secrets.SecretSource):
        return cls(
            kind=source_config.kind,
            extra_arguments=source_config.extra_arguments,
        )


class Secret(pydantic.BaseModel):
    secret_name: str
    sources: list[SecretSource]

    @classmethod
    def from_config(cls, secret_config: config_secrets.SecretConfig):
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
    agents: list[Agent] = []
    agui_features: list[AGUI_Feature] = []
    skills: ConfiguredSkills
    oidc_paths: list[pathlib.Path] = []
    room_paths: list[pathlib.Path] = []
    completion_paths: list[pathlib.Path] = []
    quizzes_paths: list[pathlib.Path] = []
    filesystem_skills_paths: list[pathlib.Path] = []
    oidc_auth_systems: list[OIDCAuthSystem] = []
    thread_persistence_dburi_sync: str | None = None
    thread_persistence_dburi_async: str | None = None
    logging_config_file: pathlib.Path | None = None
    logging_headers_map: dict[str, str] | None = {}
    logging_claims_map: dict[str, str] | None = {}

    @classmethod
    def from_config(
        cls, installation_config: config_installation.InstallationConfig
    ):
        oidc_auth_systems = [
            OIDCAuthSystem.from_config(oas_config)
            for oas_config in installation_config.oidc_auth_system_configs
        ]
        secrets = [
            Secret.from_config(secret_config)
            for secret_config in installation_config.secrets
        ]

        agents = []
        for agent_config in installation_config.agent_configs:
            if agent_config.kind == "factory":
                agent = FactoryAgent.from_config(agent_config)
            else:
                agent = DefaultAgent.from_config(agent_config)

            agents.append(agent)

        agui_features = [
            AGUI_Feature.from_config(agui_feature)
            for agui_feature in installation_config.agui_features
        ]
        skills = {
            key: Skill.from_config(skill_config)
            for key, skill_config in installation_config.skill_configs.items()
        }
        return cls(
            id=installation_config.id,
            secrets=secrets,
            environment=installation_config.environment,
            haiku_rag_config_file=installation_config._haiku_rag_config_file,
            agents=agents,
            agui_features=agui_features,
            skills=skills,
            filesystem_skills_paths=(
                installation_config.filesystem_skills_paths
            ),
            oidc_paths=installation_config.oidc_paths,
            room_paths=installation_config.room_paths,
            completion_paths=installation_config.completion_paths,
            quizzes_paths=installation_config.quizzes_paths,
            oidc_auth_systems=oidc_auth_systems,
            # Use the non-property versions here to avoid exposing
            # interpolated secrets
            thread_persistence_dburi_sync=(
                installation_config._thread_persistence_dburi_sync
                or config_installation.SYNC_MEMORY_ENGINE_URL
            ),
            thread_persistence_dburi_async=(
                installation_config._thread_persistence_dburi_async
                or config_installation.ASYNC_MEMORY_ENGINE_URL
            ),
            # Don't resolve path to logging config
            logging_config_file=installation_config._logging_config_file,
            logging_headers_map=installation_config.logging_headers_map,
            logging_claims_map=installation_config.logging_claims_map,
        )


# ============================================================================
#   API interaction models
# ============================================================================


# ----------------------------------------------------------------------------
#   Python software manifest models
# ----------------------------------------------------------------------------
InstalledPackage = dict[str, str]


InstalledPackages = dict[str, InstalledPackage]


# ----------------------------------------------------------------------------
#   Server identity
# ----------------------------------------------------------------------------
class ServerInfo(pydantic.BaseModel):
    """Human-readable identity for a Soliplex server.

    Exposed publicly via `GET /api/v1/installation/identity` so clients can
    show a friendly name and description in place of the raw server address.
    At least one of
    ``name`` / ``description`` is set whenever this is returned; the endpoint
    responds 404 when the installation configures neither.
    """

    installation_id: str
    name: str | None = None
    description: str | None = None

    @classmethod
    def from_config(
        cls,
        installation_config: config_installation.InstallationConfig,
    ) -> ServerInfo:
        return cls(
            installation_id=installation_config.id,
            name=installation_config.server_name,
            description=installation_config.server_description,
        )


# ----------------------------------------------------------------------------
#   Git metadata
# ----------------------------------------------------------------------------
class GitMetadata(pydantic.BaseModel):
    git_hash: str | None
    git_branch: str | None
    git_tag: str | None


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
    model_config = pydantic.ConfigDict(extra="allow")

    given_name: str
    family_name: str
    email: str
    preferred_username: str

    # Lets a client paint the administrator-only affordances it has --
    # the label management tab, for one -- rather than showing controls
    # that 403 on use. It is a display hint only: every privileged
    # operation is still gated server-side.
    is_admin: bool = False

    @classmethod
    def from_user_claims(
        cls,
        user_claims: dict[str, typing.Any],
        is_admin: bool = False,
    ):
        defaults = {
            "given_name": user_claims.get("given_name", "<unknown>"),
            "family_name": user_claims.get("family_name", "<unknown>"),
            "email": user_claims.get("email", "<unknown>"),
            "preferred_username": user_claims.get(
                "preferred_username",
                "<unknown>",
            ),
            # Applied over the claims, never from them: this model
            # allows extra fields, so a token carrying its own
            # 'is_admin' claim would otherwise decide the answer for us.
            "is_admin": is_admin,
        }
        return cls(**(user_claims | defaults))


# ----------------------------------------------------------------------------
#   Room-related models
# ----------------------------------------------------------------------------


RAGSourceType = typing.Literal["agent", "skill", "tool"]


class RAGSource(pydantic.BaseModel):
    source_type: RAGSourceType
    name: str | None  # "agent" type has no name

    @classmethod
    def from_source_tag(cls, source_tag: str):
        if source_tag == "agent":
            source_type = "agent"
            name = None
        else:
            source_type, name = source_tag.split(":")

        return cls(source_type=source_type, name=name)


class SearchHit(pydantic.BaseModel):
    source: RAGSource
    content: str
    score: float
    chunk_id: str
    document_id: str
    document_uri: str
    document_title: str
    document_meta: dict[str, typing.Any] = {}
    headings: list[str]
    page_numbers: list[int]
    labels: list[str]


class SearchResults(pydantic.BaseModel):
    query: str
    search_type: hr_chunk.SearchType
    hits: list[SearchHit]


class RAGDocument(pydantic.BaseModel):
    source: RAGSource
    id: str
    uri: str | None
    title: str | None
    metadata: dict[str, typing.Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime


RAGDocumentSet = dict[str, RAGDocument]


class RoomRAGDocuments(pydantic.BaseModel):
    room_id: str
    document_set: RAGDocumentSet


class FileUpload(pydantic.BaseModel):
    filename: str
    url: pydantic.HttpUrl


class RoomUploads(pydantic.BaseModel):
    room_id: str
    uploads: list[FileUpload]


class ThreadUploads(pydantic.BaseModel):
    room_id: str
    thread_id: str
    uploads: list[FileUpload]


class WorkdirFile(pydantic.BaseModel):
    filename: str
    url: pydantic.HttpUrl


class RunWorkdirFiles(pydantic.BaseModel):
    room_id: str
    thread_id: str
    run_id: str
    files: list[WorkdirFile]


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
        a_run_meta: agui.RunMetadata | None,
    ):
        if a_run_meta is not None:
            return cls(
                label=a_run_meta.label,
            )


class AGUI_RunFeedbackReview(pydantic.BaseModel):
    """Review payload for API endpoint"""

    user_name: str = KW_ONLY
    room_id: str = KW_ONLY
    thread_id: pydantic.UUID4 = KW_ONLY
    run_id: pydantic.UUID4 = KW_ONLY
    note: str | None = KW_ONLY_NONE


class AGUI_RunFeedbackResolution(pydantic.BaseModel):
    """Resolution payload for API endpoint"""

    user_name: str = KW_ONLY
    room_id: str = KW_ONLY
    thread_id: pydantic.UUID4 = KW_ONLY
    run_id: pydantic.UUID4 = KW_ONLY
    note: str | None = KW_ONLY_NONE


class AGUI_RunFeedbackHistoryEntry(pydantic.BaseModel):
    """Review / resolution record"""

    status: agui.FeedbackReviewStatus = KW_ONLY
    note: str | None = KW_ONLY_NONE


class AGUI_RunFeedback(pydantic.BaseModel):
    """Feedback for a run"""

    feedback: str = KW_ONLY
    reason: str | None = KW_ONLY_NONE


class AGUI_FeedbackQueryTerms(pydantic.BaseModel):
    """Narrow feedback"""

    limit: int | None = KW_ONLY_NONE
    since: datetime.datetime | None = KW_ONLY_NONE

    @property
    def as_dict(self) -> dict:
        result = {}

        if self.limit is not None:
            result["limit"] = self.limit

        if self.since is not None:
            result["since"] = self.since

        return result


class AGUI_NewRunRequest(pydantic.BaseModel):
    parent_run_id: pydantic.UUID4 = KW_ONLY_NONE
    metadata: AGUI_RunMetadata = KW_ONLY_NONE


class AGUI_RunUsage(pydantic.BaseModel):
    input_tokens: int
    output_tokens: int
    requests: int
    tool_calls: int

    @classmethod
    def from_tuple(cls, ru_tuple: agui.RunUsageStats):
        return cls(
            input_tokens=ru_tuple.input_tokens,
            output_tokens=ru_tuple.output_tokens,
            requests=ru_tuple.requests,
            tool_calls=ru_tuple.tool_calls,
        )


class AGUI_Run(pydantic.BaseModel):
    thread_id: pydantic.UUID4 = KW_ONLY
    run_id: pydantic.UUID4 = KW_ONLY

    parent_run_id: pydantic.UUID4 | None = KW_ONLY_NONE

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
        a_run: agui.Run,
        a_run_input: agui_core.RunAgentInput | None = None,
        a_run_meta: agui.RunMetadata = None,
        a_run_events: list[agui.RunEvent] = None,
        a_run_usage: agui.RunUsageStats | None = None,
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


AGUI_Runs = dict[pydantic.UUID4, AGUI_Run]


class AGUI_ThreadMetadata(pydantic.BaseModel):
    """Metadata for a thread

    Set all fields to 'None' to erase existing metadata.
    """

    name: str | None = KW_ONLY_NONE
    description: str | None = KW_ONLY_NONE

    @classmethod
    def from_thread_meta(
        cls,
        a_thread_meta: agui.ThreadMeta | None,
    ):
        if a_thread_meta is not None:
            return cls(
                name=a_thread_meta.name,
                description=a_thread_meta.description,
            )


class AGUI_NewThreadRequest(pydantic.BaseModel):
    metadata: AGUI_ThreadMetadata = KW_ONLY_NONE


# A '#RRGGBB' color, either case. Validated here rather than in the
# database: this is the boundary a bad value would arrive through, and a
# CHECK constraint could not report which field was wrong.
HEX_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}){1,2}$"

# Nothing stops a caller attaching a label a thousand times over, or
# filtering on a query string long enough to bloat the SQL. A ceiling
# well above any real use keeps both bounded.
MAX_THREAD_LABELS = 32


class AGUI_Label(pydantic.BaseModel):
    """A category which may be attached to threads.

    'usage_count' is present only for administrators: it spans every
    user's threads, so a name beside a volume would tell anyone else how
    much work exists that they cannot see. Omitted -- not zero, not null
    -- so a client cannot mistake "not allowed to know" for "unused" and
    offer a delete that is in fact destructive.
    """

    id: int = KW_ONLY
    name: str = KW_ONLY
    color: str = KW_ONLY
    usage_count: int | None = KW_ONLY_NONE

    @classmethod
    def from_label(cls, a_label: agui.Label, usage_count: int = None):
        return cls(
            id=a_label.id_,
            name=a_label.name,
            color=a_label.color,
            usage_count=usage_count,
        )


class AGUI_Labels(pydantic.BaseModel):
    labels: list[AGUI_Label]


class AGUI_NewLabelRequest(pydantic.BaseModel):
    name: str = pydantic.Field(kw_only=True, min_length=1, max_length=64)
    color: str | None = pydantic.Field(
        kw_only=True,
        default=None,
        pattern=HEX_COLOR_PATTERN,
    )


class AGUI_UpdateLabelRequest(pydantic.BaseModel):
    """Fields to change on a label; omitted ones are left alone."""

    name: str | None = pydantic.Field(
        kw_only=True,
        default=None,
        min_length=1,
        max_length=64,
    )
    color: str | None = pydantic.Field(
        kw_only=True,
        default=None,
        pattern=HEX_COLOR_PATTERN,
    )


class AGUI_SetThreadLabelsRequest(pydantic.BaseModel):
    """The complete set of labels a thread should carry.

    A replacement rather than a delta: the properties dialog knows the
    whole set, and a delta would need its own conflict story.
    """

    label_ids: list[int] = pydantic.Field(
        kw_only=True,
        max_length=MAX_THREAD_LABELS,
    )


class AGUI_Thread(pydantic.BaseModel):
    room_id: str = KW_ONLY
    thread_id: pydantic.UUID4 = KW_ONLY

    runs: AGUI_Runs | None = pydantic.Field(
        kw_only=True,
        default_factory=dict,
    )

    created: datetime.datetime | None = KW_ONLY_NONE
    metadata: AGUI_ThreadMetadata | None = KW_ONLY_NONE

    # Latest run activity in the thread (finish, or start while unfinished),
    # or None when it has no runs. Distinct from 'created' (the thread's
    # birth); lets clients mark threads with unseen activity.
    last_activity: pydantic.AwareDatetime | None = KW_ONLY_NONE

    # Whole labels rather than bare IDs: the client paints coloured
    # chips, and shipping IDs alone would force every listing to be
    # joined client-side against a separately-fetched catalogue -- with a
    # window in which a just-renamed label renders under its old name.
    # The integer IDs are still right there for cheap comparison.
    labels: list[AGUI_Label] = pydantic.Field(
        kw_only=True,
        default_factory=list,
    )

    @classmethod
    def from_thread(
        cls,
        a_thread: agui.Thread,
        a_thread_meta: AGUI_ThreadMetadata,
        a_thread_runs: AGUI_Runs = None,
        a_thread_last_activity: datetime.datetime | None = None,
        a_thread_labels: list[agui.Label] = None,
    ):
        return cls(
            room_id=a_thread.room_id,
            thread_id=a_thread.thread_id,
            created=a_thread.created,
            metadata=a_thread_meta,
            runs=a_thread_runs,
            last_activity=a_thread_last_activity,
            labels=[
                AGUI_Label.from_label(a_label)
                for a_label in a_thread_labels or ()
            ],
        )


class AGUI_Threads(pydantic.BaseModel):
    threads: list[AGUI_Thread]


class AGUI_ThreadPage(pydantic.BaseModel):
    """One page of the user's threads, spanning every room they may see.

    'total' counts every thread the user has across those rooms, not
    just the ones on this page, so a client can tell whether to keep
    paging without probing for a short page.
    """

    threads: list[AGUI_Thread]
    total: int = KW_ONLY
    limit: int = KW_ONLY
    offset: int = KW_ONLY


# ----------------------------------------------------------------------------
#   Room Authorization models
# ----------------------------------------------------------------------------


class ACLEntryUnchecked(pydantic.BaseModel):
    allow_deny: authz.AllowDeny = authz.AllowDeny.DENY
    everyone: bool = False
    authenticated: bool = False
    preferred_username: str | None = None
    email: str | None = None
    json_path: str | None = None


class ACLEntry(ACLEntryUnchecked):
    @pydantic.field_validator("json_path")
    @classmethod
    def _check_json_path(cls, value: str | None) -> str | None:
        return authz.validate_json_path(value)

    @pydantic.model_validator(mode="after")
    def _check_exactly_one_discriminator(self) -> ACLEntry:
        active = [
            name
            for name, is_set in (
                ("everyone", self.everyone),
                ("authenticated", self.authenticated),
                ("preferred_username", self.preferred_username is not None),
                ("email", self.email is not None),
                ("json_path", self.json_path is not None),
            )
            if is_set
        ]
        if len(active) != 1:
            raise authz.ExactlyOneDiscriminator(active)
        return self


class RoomPolicyUnchecked(pydantic.BaseModel):
    room_id: str
    default_allow_deny: authz.AllowDeny = authz.AllowDeny.DENY
    acl_entries: list[ACLEntryUnchecked] = pydantic.Field(default_factory=list)


class RoomPolicy(RoomPolicyUnchecked):
    acl_entries: list[ACLEntry] = pydantic.Field(default_factory=list)


RoomPolicyMap = dict[str, RoomPolicy | None]


class InstallationAuthorization(pydantic.BaseModel):
    admin_user_discriminators: list[str] = pydantic.Field(default_factory=list)
    room_policies: RoomPolicyMap = pydantic.Field(default_factory=dict)


# ----------------------------------------------------------------------------
#   'ask_with_rich_citations' tool models
# ----------------------------------------------------------------------------


class ChunkVisualization(pydantic.BaseModel):
    """Page images for a chunk, with chunk text highlighted"""

    source: RAGSource
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
