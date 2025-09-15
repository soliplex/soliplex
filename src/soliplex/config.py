import dataclasses
import enum
import functools
import importlib
import inspect
import json
import os
import pathlib
import random
import typing
from collections import abc

import yaml

from soliplex import util

#=============================================================================
#   Exceptions raised during YAML config processing
#=============================================================================

class FromYamlException(ValueError):
    def __init__(self, config_path):
        self.config_path = config_path
        super().__init__(f"Error in YAML configuration: {config_path}")


class NoConfigPath(ValueError):
    def __init__(self):
        super().__init__("No '_config_path' set")


class NoSuchConfig(ValueError):
    def __init__(self, config_path):
        self.config_path = config_path
        super().__init__(f"Config path is not a YAML file: {config_path}")


class NotADict(ValueError):
    def __init__(self, found):
        self.found = found
        super().__init__(f"YAML did not parse as a dict: {found}")


class ToolRequirementConflict(ValueError):
    def __init__(self, tool_name):
        self.tool_name = tool_name
        super().__init__(
            f"Tool {tool_name} requires both context and tool config"
        )


class NoProviderKeyInEnvironment(ValueError):
    def __init__(self, envvar):
        self.envvar = envvar
        super().__init__(f"No API key in environment: {envvar}")


class RagDbExactlyOneOfStemOrOverride(TypeError):
    _config_path = None
    def __init__(self):
        super().__init__(
            "Configure exactly one of 'rag_lancedb_stem' or "
            "'rag_lancedb_override_path'"
        )


class RCQExactlyOneOfStemOrOverride(TypeError):
    def __init__(self):
        super().__init__(
            "Configure exactly one of '_question_file_stem' or "
            "'_question_file_override_path'"
        )


#=============================================================================
#   OIDC Authentication system configuration types
#=============================================================================

WELL_KNOWN_OPENID_CONFIGURATION = ".well-known/openid-configuration"


@dataclasses.dataclass
class OIDCAuthSystemConfig:
    id: str
    title: str

    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str = None
    client_secret: str = "" # "env:{JOSCE_CLIENT_SECRET}"
    oidc_client_pem_path: pathlib.Path = None

    # Set in 'from_yaml' below
    _config_path: pathlib.Path | None = None

    @classmethod
    def from_yaml(
        cls, config_path: pathlib.Path, config: dict[str, typing.Any],
    ):
        config["_config_path"] = config_path

        client_secret = config.pop("client_secret", "")
        config["client_secret"] =  util.interpolate_env_vars(client_secret)

        oidc_client_pem_path = config.pop("oidc_client_pem_path", None)
        if oidc_client_pem_path is not None:
            config["oidc_client_pem_path"] = (
                config_path.parent / oidc_client_pem_path
            )

        return cls(**config)

    @property
    def server_metadata_url(self):
        return f"{self.server_url}/{WELL_KNOWN_OPENID_CONFIGURATION}"

    @property
    def oauth_client_kwargs(self) -> dict:
        client_kwargs = {}

        if self.scope is not None:
            client_kwargs["scope"] = self.scope

        if self.oidc_client_pem_path is not None:
            client_kwargs["verify"] = str(self.oidc_client_pem_path)

        return {
            "name": self.id,
            "server_metadata_url": self.server_metadata_url,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "client_kwargs": client_kwargs,
            # added by the auth setup
            #"authorize_state": main.SESSION_SECRET_KEY,
        }


@dataclasses.dataclass
class AvailableOIDCAuthSystemConfigs:
    systems: list[OIDCAuthSystemConfig] = dataclasses.field(
        default_factory=list,
    )


#=============================================================================
#   Tool configuration types
#=============================================================================

class ToolRequires(enum.StrEnum):
    FASTAPI_CONTEXT = "fastapi_context"
    TOOL_CONFIG = "tool_config"
    BARE = "bare"


@dataclasses.dataclass
class ToolConfig:
    kind: str
    tool_name: str

    allow_mcp: bool = False

    _tool: abc.Callable[..., typing.Any] = None

    @property
    def tool_id(self):
        _, tool_id = self.tool_name.rsplit(".", 1)
        return tool_id

    @property
    def tool(self):
        if self._tool is None:
            module_name, tool_id = self.tool_name.rsplit(".", 1)
            module = importlib.import_module(module_name)
            self._tool = getattr(module, tool_id)

        return self._tool

    @property
    def tool_description(self) -> str:
        return inspect.getdoc(self.tool)

    @property
    def tool_requires(self) -> ToolRequires | None:
        tool_params = inspect.signature(self.tool).parameters

        if "ctx" in tool_params and "tool_config" in tool_params:
            raise ToolRequirementConflict(self.tool_name)

        if "ctx" in tool_params:
            return ToolRequires.FASTAPI_CONTEXT
        elif "tool_config" in tool_params:
            return ToolRequires.TOOL_CONFIG
        else:
            return ToolRequires.BARE

    @property
    def tool_with_config(self) -> abc.Callable[..., typing.Any]:
        if self.tool_requires == ToolRequires.TOOL_CONFIG:
            tool_func_sig = inspect.signature(self.tool)
            wo_tc_sig = tool_func_sig.replace(
                parameters=[
                    param for param in tool_func_sig.parameters.values()
                    if param.name != "tool_config"
                ]
            )
            tool_w_config = functools.update_wrapper(
                functools.partial(self.tool, tool_config=self),
                self.tool,
            )
            tool_w_config.__signature__  = wo_tc_sig

            return tool_w_config
        else:
            return self.tool


@dataclasses.dataclass
class SearchDocumentsToolConfig(ToolConfig):
    kind: str = "search_documents"
    tool_name: str = "soliplex.tools.search_documents"

    # Set in '__post_init__' below
    _rag_lancedb_path: pathlib.Path = None

    # One of these two options must be specfied
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    expand_context_radius: int = 2
    search_documents_limit: int = 5
    return_citations: bool = False

    # Set in 'from_yaml' below
    _config_path: pathlib.Path | None = None

    @classmethod
    def from_yaml(
        cls, config_path: pathlib.Path, config: dict[str, typing.Any],
    ):
        try:
            instance = cls(**config)
        except RagDbExactlyOneOfStemOrOverride as exc:
            raise FromYamlException(config_path) from exc

        instance._config_path = config_path
        return instance

    def __post_init__(self):
        exclusive_required = [
            self.rag_lancedb_stem,
            self.rag_lancedb_override_path,
        ]
        passed = list(filter(None, exclusive_required))

        if len(list(passed)) != 1:
            raise RagDbExactlyOneOfStemOrOverride()

    @property
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the room's RAG rag_lancedb_path database"""
        if self.rag_lancedb_override_path is not None:
            rsop = self.rag_lancedb_override_path

            if self._config_path is not None:
                rsop = (self._config_path.parent / rsop).resolve()
            else:
                rsop = pathlib.Path(rsop).resolve()

            return rsop
        else:
            db_rag_dir = pathlib.Path(os.environ["RAG_LANCE_DB_PATH"])
            rspdb = (db_rag_dir / f"{self.rag_lancedb_stem}.lancedb").resolve()

            return rspdb


TOOL_CONFIG_CLASSES_BY_TOOL_NAME = {
    klass.tool_name: klass
    for klass in [
        SearchDocumentsToolConfig,
    ]
}

def extract_tool_configs(config_path: pathlib.Path, config: dict):
    tool_configs = {}

    for t_config in config.pop("tools", ()):
        tool_name = t_config.pop("tool_name")
        tc_class = TOOL_CONFIG_CLASSES_BY_TOOL_NAME.get(tool_name)

        if tc_class is None:
            _, kind = tool_name.rsplit(".", 1)
            tool_config = ToolConfig(
                kind=kind, tool_name=tool_name, **t_config,
            )
            tool_configs[kind] = tool_config
        else:
            tool_config = tc_class.from_yaml(config_path, t_config)
            tool_configs[tool_config.kind] = tool_config

    return tool_configs


@dataclasses.dataclass
class Stdio_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which runs as a subprocess"""
    command: str
    args: list[str] = dataclasses.field(
        default_factory=list,
    )

    env: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None


@dataclasses.dataclass
class HTTP_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which makes calls over streaming HTTP"""
    url: str
    headers: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict,
    )

    query_params: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None


MCP_CONFIG_CLASSES_BY_TYPE = {
    "stdio": Stdio_MCP_ClientToolsetConfig,
    "http": HTTP_MCP_ClientToolsetConfig,
}

def extract_mcp_client_toolset_configs(
    config_path: pathlib.Path, config: dict,
):
    mcp_client_toolset_configs = {}

    for mcp_name, mcp_client_toolset_config in config.pop(
        "mcp_client_toolsets", {}
    ).items():
        type_ = mcp_client_toolset_config.pop("type")
        mcp_config_klass = MCP_CONFIG_CLASSES_BY_TYPE[type_]
        mcp_client_toolset_configs[mcp_name] = mcp_config_klass(
            **mcp_client_toolset_config,
        )

    return mcp_client_toolset_configs


#=============================================================================
#   Agent-related configuration types
#=============================================================================

class LLMProviderType(enum.StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"


@dataclasses.dataclass
class AgentConfig:
    #
    # Agent-specific options
    #
    id: str  # set as 'room-{room_id}' or 'completion-{completion_id}'
    model_name: str = None

    system_prompt: dataclasses.InitVar[str] = None
    _system_prompt_text: str = None
    _system_prompt_path: pathlib.Path = None

    provider_type: LLMProviderType = LLMProviderType.OLLAMA
    provider_base_url: str = None  # defaults to OLLAMA_BASE_URL envvar
    provider_key_envvar: str = None  # envvar name containing API key

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    def __post_init__(self, system_prompt):
        if self.model_name is None:
            self.model_name = os.getenv("DEFAULT_AGENT_MODEL")

        if system_prompt is not None:
            self._system_prompt_text = system_prompt

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        if "system_prompt" in config:
            system_prompt = config.pop("system_prompt")

            if system_prompt.startswith("./"):
                config["_system_prompt_path"] = system_prompt
            else:
                config["system_prompt"] = system_prompt

        return cls(**config)

    def get_system_prompt(self) -> str | None:
        if self._system_prompt_text is not None:
            return self._system_prompt_text

        if self._system_prompt_path is not None:
            if self._config_path is None:
                raise NoConfigPath()

            system_prompt_file = (
                self._config_path.parent / self._system_prompt_path
            )
            return system_prompt_file.read_text()

        else:  # pragma: NO COVER
            pass

    @property
    def llm_provider_kw(self) -> dict:
        if self.provider_base_url is None:
            provider_base_url = os.environ["OLLAMA_BASE_URL"]
        else:
            provider_base_url = self.provider_base_url

        provider_kw = {
            "base_url": f"{provider_base_url}/v1",
        }

        if self.provider_key_envvar is not None:
            provider_key = os.getenv(self.provider_key_envvar)

            if provider_key is None:
                raise NoProviderKeyInEnvironment(self.provider_key_envvar)

            provider_kw["api_key"] = provider_key

        return provider_kw


#=============================================================================
#   Quiz-related configuration types
#=============================================================================

class QuizQuestionType(enum.StrEnum):
    QA = "qa"
    FILL_BLANK = "fill-blank"
    MULTIPLE_CHOICE = "multiple-choice"


@dataclasses.dataclass
class QuizQuestionMetadata:
    type: QuizQuestionType
    uuid: str
    options: list[str] = dataclasses.field(
        default_factory=list,
    )


@dataclasses.dataclass
class QuizQuestion:
    inputs: str
    expected_output: str
    metadata: QuizQuestionMetadata


@dataclasses.dataclass
class QuizConfig:

    id: str
    question_file: dataclasses.InitVar[str] = None
    _question_file_stem: str = None
    _question_file_path_override: str = None
    _questions_map: dict[str, QuizQuestion] = None

    title: str = "Quiz"
    randomize: bool = False
    max_questions: int = None

    def __post_init__(self, question_file):
        if question_file is not None:
            if "/" in question_file:
                self._question_file_path_override = question_file
            else:
                if question_file.endswith(".json"):
                    question_file = question_file[:-len(".json")]

                self._question_file_stem = question_file
        if (
            self._question_file_stem is None and
            self._question_file_path_override is None
        ) or (
            self._question_file_stem is not None and
            self._question_file_path_override is not None
        ):
            raise RCQExactlyOneOfStemOrOverride()

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        try:
            return cls(**config)
        except RCQExactlyOneOfStemOrOverride as exc:
            raise FromYamlException(config_path) from exc

    @property
    def question_file_path(self) -> pathlib.Path:
        if self._question_file_path_override is not None:
            return pathlib.Path(self._question_file_path_override)
        else:
            installation_path = pathlib.Path(os.environ["INSTALLATION_PATH"])
            quizzes_path = installation_path / "quizzes"
            return quizzes_path / f"{self._question_file_stem}.json"

    @staticmethod
    def _make_question(question: dict) -> QuizQuestion:

        metadata = QuizQuestionMetadata(
            uuid=question["metadata"]["uuid"],
            type = question["metadata"]["type"],
            options = question["metadata"].get("options", []),
        )
        return QuizQuestion(
            inputs=question["inputs"],
            expected_output=question["expected_output"],
            metadata=metadata,
        )

    def _load_questions_file(self) -> dict[str, QuizQuestion]:
        quiz_json = json.loads(self.question_file_path.read_text())
        return {
            q_dict["metadata"]["uuid"]: self._make_question(q_dict)
                for q_dict in quiz_json["cases"]
        }

    def get_questions(self) -> list[QuizQuestion]:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        questions = list(self._questions_map.values())

        if self.randomize:
            random.shuffle(questions)

        if self.max_questions is not None:
            questions = questions[:self.max_questions]

        return questions

    def get_question(self, uuid: str) -> QuizQuestion:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        return self._questions_map[uuid]


#=============================================================================
#   Room-related configuration types
#=============================================================================

@dataclasses.dataclass
class RoomConfig:
    """Configuration for a chat room."""

    #
    # Required room metadata
    #
    id: str
    name: str
    description: str
    agent_config: AgentConfig

    #
    # Room UI options
    #
    _order: str = None   # defaults to 'id'
    welcome_message: str = None
    suggestions: list[str] = dataclasses.field(
        default_factory=list,
    )
    enable_attachments: bool = False

    #
    # Tool options
    #
    tool_configs: dict[str, ToolConfig] = dataclasses.field(
        default_factory=dict,
    )
    mcp_client_toolset_configs: dict[
        str, Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
    ] = dataclasses.field(default_factory=dict)

    #
    # MCP options
    #
    allow_mcp: bool = False

    #
    # Quiz-specific options
    #
    quizzes: list[QuizConfig] = dataclasses.field(
        default_factory=list,
    )
    _quiz_map: dict[str, QuizConfig] = None

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    logo_image: dataclasses.InitVar[str] = None
    _logo_image: str = None

    def __post_init__(self, logo_image: str | None):
        if logo_image is not None:
            self._logo_image = logo_image

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        room_id = config["id"]
        agent_config_yaml = config.pop("agent")
        agent_config_yaml["id"] = f"room-{room_id}"

        config["agent_config"] = AgentConfig.from_yaml(
            config_path,
            agent_config_yaml,
        )

        config["tool_configs"] = extract_tool_configs(config_path, config)

        config["mcp_client_toolset_configs"] = (
            extract_mcp_client_toolset_configs(config_path, config)
        )

        quizzes_config_yaml = config.pop("quizzes", None)
        if quizzes_config_yaml is not None:
            config["quizzes"] = [
                QuizConfig.from_yaml(config_path, quiz_config_yaml)
                for quiz_config_yaml in quizzes_config_yaml
            ]

        logo_image = config.pop("logo_image", None)
        config["_logo_image"] = logo_image

        return cls(**config)

    @property
    def sort_key(self):
        if self._order is not None:
            return self._order

        return self.id

    @property
    def quiz_map(self) -> dict[str, QuizConfig]:
        if self._quiz_map is None:
            self._quiz_map = {
                quiz.id: quiz for quiz in self.quizzes
            }

        return self._quiz_map

    def get_logo_image(self) -> pathlib.Path | None:
        if self._logo_image is not None:
            if self._config_path is None:
                raise NoConfigPath()

            return self._config_path.parent / self._logo_image


#=============================================================================
#   Completions endpoint-related configuration types
#=============================================================================

@dataclasses.dataclass
class CompletionsConfig:
    """Configuration for a completions endpoint."""

    #
    # Required metadata
    #
    id: str
    agent_config: AgentConfig

    name: str = None

    #
    # Tool options
    #
    tool_configs: dict[str, ToolConfig] = dataclasses.field(
        default_factory=dict,
    )
    mcp_client_toolset_configs: dict[
        str, Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
    ] = dataclasses.field(default_factory=dict)

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        completions_id = config["id"]

        if "name" not in config:
            config["name"] = completions_id

        agent_config_yaml = config.pop("agent")
        agent_config_yaml["id"] = f"completions-{completions_id}"

        config["agent_config"] = AgentConfig.from_yaml(
            config_path,
            agent_config_yaml,
        )

        config["tool_configs"] = extract_tool_configs(config_path, config)

        config["mcp_client_toolset_configs"] = (
            extract_mcp_client_toolset_configs(config_path, config)
        )

        return cls(**config)


#=============================================================================
#   Installation configuration types
#=============================================================================

def _check_is_dict(config_yaml):
    if not isinstance(config_yaml, dict):
        raise NotADict(config_yaml)

    return config_yaml

def _load_config_yaml(config_path: pathlib.Path) -> dict:
    """Load a YAML config file"""
    if not config_path.is_file():
        raise NoSuchConfig(config_path)

    try:
        with config_path.open() as stream:
            config_yaml = _check_is_dict(
                yaml.load(stream, yaml.Loader),
            )

    except Exception as exc:
        raise FromYamlException(config_path) from exc

    return config_yaml


def _find_configs(
    to_search: pathlib.Path, filename_yaml: str,
) -> typing.Sequence[tuple[pathlib.Path, dict]]:
    """Yield a sequence of YAML configs found under 'to_search'

    Yielded values are tuples, '(config_path, config_yaml)', suitable for
    passing to a config class's 'from_yaml'.

    If 'to_search' has its own copy of 'filename_yaml', just yield the one
    config parsed from it.

    Otherwise, itterate over immediate subdirectories, yielding configs
    parsed from any which have copies of 'filename_yaml'
    """
    config_file = to_search / filename_yaml

    try:
        yield config_file, _load_config_yaml(config_file)

    except NoSuchConfig:

        for sub in sorted(to_search.glob("*")):
            if sub.is_dir():
                sub_config = sub / filename_yaml
                try:
                    yield sub_config, _load_config_yaml(sub_config)
                except NoSuchConfig:
                    continue
            else:   # pragma: NO COVER
                pass


_find_room_configs = functools.partial(
    _find_configs, filename_yaml="room_config.yaml",
)

_find_completions_configs = functools.partial(
    _find_configs, filename_yaml="completions_config.yaml",
)


@dataclasses.dataclass
class InstallationConfig:
    """Configuration for a set of rooms, completions, etc."""
    #
    # Required metadata
    #
    id: str

    #
    # Secrets name values looked up from env vars or other sources.
    #
    secrets: list[str] = dataclasses.field(
        default_factory=list,
    )
    #
    # Map values similar to 'os.environ'.
    #
    environment: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )

    #
    # Path(s) to OIDC Authentication System configs
    #
    # Defaults to one path: './oidc' (set in '__post_init__')
    #
    oidc_paths: list[pathlib.Path] = None

    _oidc_auth_system_configs: list[OIDCAuthSystemConfig] = None

    #
    # Path(s) to room configs:  each item can be either a single
    # room config (a directory containing its own 'room_config.yaml' file),
    # or a directory containing such room configs.
    #
    # Defaults to one path: './rooms' (set in '__post_init__'), which is
    # normally a "container" directory for room config directories.
    #
    room_paths: list[pathlib.Path] = None

    _room_configs: dict[str, RoomConfig] = None

    #
    # Path(s) to completions configs:  each item can be either a single
    # completion config (a directory containing its own
    # 'completions_config.yaml' file), or a directory containing such
    # completions configs.
    #
    # Defaults to one path: './completions' (set in '__post_init__'), which is
    # normally a "container" directory for completions config directories.
    #
    completions_paths: list[pathlib.Path] = None

    _completions_configs: dict[str, CompletionsConfig] = None

    #
    # Path(s) to quiz data:  each item must be a single directory containing
    # one or more '*.json' files, each holding question data for a single quiz.
    #
    # Defaults to one path: './quizzes' (set in '__post_init__').
    #
    quizzes_paths: list[pathlib.Path] = None

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path

        environment = config.get("environment")

        if isinstance(environment, list):
            config["environment"] = {
                item["name"]: item["value"]
                for item in environment
            }

        return cls(**config)

    def __post_init__(self):
        if self.oidc_paths is None:
            self.oidc_paths = ["./oidc"]

        if self.room_paths is None:
            self.room_paths = ["./rooms"]

        if self.completions_paths is None:
            self.completions_paths = ["./completions"]

        if self.quizzes_paths is None:
            self.quizzes_paths = ["./quizzes"]

        if self._config_path is not None:

            parent_dir = self._config_path.parent

            self.oidc_paths = [
                parent_dir / oidc_path
                for oidc_path in self.oidc_paths
            ]

            self.room_paths = [
                parent_dir / room_path
                for room_path in self.room_paths
            ]

            self.completions_paths = [
                parent_dir / completions_path
                for completions_path in self.completions_paths
            ]

            self.quizzes_paths = [
                parent_dir / quizzes_path
                for quizzes_path in self.quizzes_paths
            ]

    def _load_oidc_auth_system_configs(self) -> list[OIDCAuthSystemConfig]:
        oas_configs = []

        for oidc_path in self.oidc_paths:
            oidc_config = oidc_path / "config.yaml"
            config_yaml = _load_config_yaml(oidc_config)

            oidc_client_pem_path = config_yaml.get("oidc_client_pem_path")
            if oidc_client_pem_path is not None:
                oidc_client_pem_path = (
                    oidc_config / oidc_client_pem_path
                )

            for auth_system_yaml in config_yaml["auth_systems"]:
                if "oidc_client_pem_path" not in auth_system_yaml:
                    auth_system_yaml["oidc_client_pem_path"] = (
                        oidc_client_pem_path
                    )
                oas_config = OIDCAuthSystemConfig.from_yaml(
                    oidc_config, auth_system_yaml,
                )
                oas_configs.append(oas_config)

        return oas_configs

    @property
    def oidc_auth_system_configs(self) -> list[OIDCAuthSystemConfig]:
        if self._oidc_auth_system_configs is None:
            self._oidc_auth_system_configs = (
                self._load_oidc_auth_system_configs()
            )

        return self._oidc_auth_system_configs

    def _load_room_configs(self) -> dict[str, RoomConfig]:
        room_configs = {}

        for room_path in self.room_paths:
            for config_path, config_yaml in _find_room_configs(room_path):
                # XXX  order of 'room_paths' controls first-past-the-post
                #      for any conflict on room ID.
                config_id = config_yaml["id"]
                if config_id not in room_configs:
                    room_configs[config_id] = RoomConfig.from_yaml(
                        config_path, config_yaml,
                    )

        return room_configs

    @property
    def room_configs(self) -> dict[str, RoomConfig]:
        if self._room_configs is None:
            self._room_configs = self._load_room_configs()

        return self._room_configs.copy()

    def _load_completions_configs(self) -> dict[str, RoomConfig]:
        completions_configs = {}

        for completions_path in self.completions_paths:
            for config_path, config_yaml in _find_completions_configs(
                completions_path
            ):
                # XXX  order of 'completions_paths' controls
                #      first-past-the-post for any conflict on completions ID.
                config_id = config_yaml["id"]
                if config_id not in completions_configs:
                    completions_configs[config_id] = (
                        CompletionsConfig.from_yaml(config_path, config_yaml)
                    )

        return completions_configs

    @property
    def completions_configs(self) -> dict[str, RoomConfig]:
        if self._completions_configs is None:
            self._completions_configs = self._load_completions_configs()

        return self._completions_configs.copy()

    def reload_configurations(self):
        """Load all dependent configuration sets"""
        self._oidc_auth_system_configs = (
            self._load_oidc_auth_system_configs()
        )
        self._room_configs = self._load_room_configs()
        self._completions_configs = self._load_completions_configs()


def load_installation(config_path: pathlib.Path) -> InstallationConfig:
    config_path = config_path.resolve()

    if config_path.is_dir():
        config_path = config_path / "installation.yaml"

    config_yaml = _load_config_yaml(config_path)

    return InstallationConfig.from_yaml(config_path, config_yaml)
