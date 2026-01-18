from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import importlib
import inspect
import itertools
import json
import os
import pathlib
import random
import re
import ssl
import sys
import typing
import warnings
from collections import abc
from urllib import parse as url_parse

import dotenv
import yaml
from haiku.rag import config as hr_config
from pydantic_ai import settings as ai_settings
from pydantic_ai.agent import abstract as ai_ag_abstract

from soliplex.agui import features

FILE_PREFIX = "file:"

SECRET_PREFIX = "secret:"
SECRET_PATTERN = rf"{SECRET_PREFIX}(?P<secret_name>\w+)"
SECRET_RE = re.compile(SECRET_PATTERN)

SYNC_MEMORY_ENGINE_URL = "sqlite://"
ASYNC_MEMORY_ENGINE_URL = "sqlite+aiosqlite://"

# ============================================================================
#   Exceptions raised during YAML config processing
# ============================================================================


class FromYamlException(ValueError):
    def __init__(self, _config_path, kind: str, config: dict):
        self._config_path = _config_path
        self.kind = kind
        self.config = config

        if config is not None and "_installation_config" in config:
            elide_ic = {"_installation_config": "<elided>"}
            tb_config = config | elide_ic
        else:
            tb_config = config

        super().__init__(
            f"Error in YAML configuration: {_config_path}; "
            f"Kind: {kind}; "
            f"Config: {tb_config}; "
        )


class NoConfigPath(ValueError):
    def __init__(self):
        super().__init__("No '_config_path' set")


class NoSuchConfig(ValueError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(f"Config path is not a YAML file: {_config_path}")


class NotADict(ValueError):
    def __init__(self, found):
        self.found = found
        super().__init__(f"YAML did not parse as a dict: {found}")


class ToolRequirementConflict(ValueError):
    def __init__(self, tool_name, _config_path):
        self.tool_name = tool_name
        self._config_path = _config_path
        super().__init__(
            f"Tool {tool_name} requires both context and tool config "
            f"(configured in {_config_path}"
        )


class RagDbExactlyOneOfStemOrOverride(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure exactly one of 'rag_lancedb_stem' or "
            f"'rag_lancedb_override_path' "
            f"(configured in {_config_path})"
        )


class RagDbFileNotFound(ValueError):
    def __init__(self, rag_db_filename, _config_path):
        self.rag_db_filename = rag_db_filename
        self._config_path = _config_path
        super().__init__(
            f"RAG DB file not found: {rag_db_filename} "
            f"(configured in {_config_path})"
        )


class InvalidAgentTemplateID(KeyError):
    def __init__(self, template_id, _config_path):
        self.template_id = template_id
        self._config_path = _config_path
        super().__init__(
            f"Template agent not found: {template_id} "
            f"(configured in {_config_path})"
        )


class QCExactlyOneOfStemOrOverride(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure exactly one of '_question_file_stem' or "
            f"'_question_file_override_path' "
            f"(configured in {_config_path})"
        )


class QuestionFileNotFoundWithStem(ValueError):
    def __init__(self, stem, quizzes_paths, _config_path):
        self.stem = stem
        self.quizzes_paths = quizzes_paths
        self._config_path = _config_path
        super().__init__(
            f"'{stem}.json' file not found on paths: "
            f"{','.join([str(qp) for qp in quizzes_paths])} "
            f"(configured in {_config_path})"
        )


class QuestionFileNotFoundWithOverride(ValueError):
    def __init__(self, override, _config_path):
        self.override = override
        self._config_path = _config_path
        super().__init__(
            f"'{override}' file not found (configured in {_config_path})"
        )


class NotASecret(ValueError):
    def __init__(self, config_str):
        self.config_str = config_str
        super().__init__(
            f"Config '{config_str}' must be prefixed with 'secret:'"
        )


class MissingEnvVar(ValueError):
    def __init__(self, env_var):
        self.env_var = env_var
        super().__init__(
            f"Environment variable '{env_var}' cannot be resolved"
        )


class MissingEnvVars(ExceptionGroup, ValueError):
    def __init__(self, env_vars, excs):
        self.env_vars = env_vars
        super().__init__(
            f"Environment variables cannot be resolved: {env_vars}",
            excs,
        )


def _dotted_name(type_or_func) -> str:
    return f"{type_or_func.__module__}.{type_or_func.__name__}"


def _no_repr(**kw):
    return dataclasses.field(repr=False, **kw)


def _no_repr_none(**kw):
    return _no_repr(default=None, **kw)


# ============================================================================
#   OIDC Authentication system configuration types
# ============================================================================

WELL_KNOWN_OPENID_CONFIGURATION = ".well-known/openid-configuration"


@dataclasses.dataclass(kw_only=True)
class OIDCAuthSystemConfig:
    id: str
    title: str

    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str = None
    client_secret: str = ""  # "env:{JOSCE_CLIENT_SECRET}"
    oidc_client_pem_path: pathlib.Path = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        oidc_client_pem_path = config.pop("oidc_client_pem_path", None)
        if oidc_client_pem_path is not None:
            config["oidc_client_pem_path"] = (
                config_path.parent / oidc_client_pem_path
            )

        try:
            return cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "oidc", config) from exc

    @property
    def server_metadata_url(self):
        return f"{self.server_url}/{WELL_KNOWN_OPENID_CONFIGURATION}"

    @property
    def oauth_client_kwargs(self) -> dict:
        client_kwargs = {}

        if self.scope is not None:
            client_kwargs["scope"] = self.scope

        if self.oidc_client_pem_path is not None:
            client_kwargs["verify"] = ssl.create_default_context(
                cafile=self.oidc_client_pem_path
            )

        try:
            client_secret = self._installation_config.get_secret(
                self.client_secret
            )
        except Exception:
            client_secret = self.client_secret

        return {
            "name": self.id,
            "server_metadata_url": self.server_metadata_url,
            "client_id": self.client_id,
            "client_secret": client_secret,
            "client_kwargs": client_kwargs,
            # added by the auth setup
            # "authorize_state": main.SESSION_SECRET_KEY,
        }


@dataclasses.dataclass(kw_only=True)
class AvailableOIDCAuthSystemConfigs:
    systems: list[OIDCAuthSystemConfig] = dataclasses.field(
        default_factory=list,
    )


# ============================================================================
#   Tool configuration types
# ============================================================================


class ToolRequires(enum.StrEnum):
    FASTAPI_CONTEXT = "fastapi_context"
    TOOL_CONFIG = "tool_config"
    BARE = "bare"


@dataclasses.dataclass(kw_only=True)
class ToolConfig:
    tool_name: str
    agui_feature_names: tuple[str] = ()

    allow_mcp: bool = False

    _tool: abc.Callable[..., typing.Any] = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        try:
            return cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "toolconfig", config) from exc

    @property
    def kind(self):
        _, kind = self.tool_name.rsplit(".", 1)
        return kind

    @property
    def tool_id(self):
        return self.kind

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
            raise ToolRequirementConflict(self.tool_name, self._config_path)

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
                    param
                    for param in tool_func_sig.parameters.values()
                    if param.name != "tool_config"
                ]
            )
            tool_w_config = functools.update_wrapper(
                functools.partial(self.tool, tool_config=self),
                self.tool,
            )
            tool_w_config.__signature__ = wo_tc_sig

            return tool_w_config
        else:
            return self.tool

    def get_extra_parameters(self) -> dict:
        return {}


@dataclasses.dataclass(kw_only=True)
class _RAGToolBase:
    # Set in '__post_init__' below
    _rag_lancedb_path: pathlib.Path = None

    # One of these two options must be specified
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    # Normally set via subclass 'from_yaml'
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    def __post_init__(self):
        exclusive_required = [
            self.rag_lancedb_stem,
            self.rag_lancedb_override_path,
        ]
        passed = list(filter(None, exclusive_required))

        if len(list(passed)) != 1:
            raise RagDbExactlyOneOfStemOrOverride(self._config_path)

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        """Populate a haiku-rag config object w/ room-level overrides

        Use installation's 'haiku_rag_config' as a base.  If the room
        directory holds a 'haiku.rag.yaml' file, load it's mapping, and
        treat it as overrides.
        """
        if self._config_path is None:
            raise NoConfigPath()

        base_config = self._installation_config.haiku_rag_config

        hr_config_file = self._config_path.parent / "haiku.rag.yaml"

        if hr_config_file.is_file():
            base_config_yaml = base_config.model_dump()
            room_config_yaml = hr_config.load_yaml_config(hr_config_file)

            return hr_config.AppConfig.model_validate(
                base_config_yaml | room_config_yaml
            )
        else:
            return base_config

    @property
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the room's RAG rag_lancedb_path database"""
        if self.rag_lancedb_override_path is not None:
            rsop = self.rag_lancedb_override_path

            if self._config_path is not None:
                rsop = (self._config_path.parent / rsop).resolve()
            else:
                rsop = pathlib.Path(rsop).resolve()

            if not rsop.is_dir():
                raise RagDbFileNotFound(rsop, self._config_path)

            return rsop
        else:
            db_rag_dir = pathlib.Path(
                self._installation_config.get_environment(
                    "RAG_LANCE_DB_PATH",
                )
            )
            rspdb = (db_rag_dir / f"{self.rag_lancedb_stem}.lancedb").resolve()

            if not rspdb.is_dir():
                raise RagDbFileNotFound(rspdb, self._config_path)

            return rspdb

    def get_extra_parameters(self) -> dict:
        try:
            rag_lancedb_path = self.rag_lancedb_path
        except RagDbFileNotFound as exc:
            rag_lancedb_path = f"MISSING: {exc.rag_db_filename}"

        return {
            "rag_lancedb_path": rag_lancedb_path,
        }


@dataclasses.dataclass(kw_only=True)
class SearchDocumentsToolConfig(ToolConfig, _RAGToolBase):
    kind: str = "search_documents"
    tool_name: str = "soliplex.tools.search_documents"

    search_documents_limit: int = 5

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            instance = cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "sdtc", config) from exc

        return instance

    def get_extra_parameters(self) -> dict:
        local = {
            "search_documents_limit": self.search_documents_limit,
        }
        return (
            super().get_extra_parameters()
            | _RAGToolBase.get_extra_parameters(self)
            | local
        )


@dataclasses.dataclass(kw_only=True)
class RAGResearchToolConfig(ToolConfig, _RAGToolBase):
    kind: str = "research_report"
    tool_name: str = "soliplex.tools.research_report"

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            instance = cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "rrtc", config) from exc

        return instance

    def get_extra_parameters(self) -> dict:
        return (
            super().get_extra_parameters()
            | _RAGToolBase.get_extra_parameters(self)
        )


@dataclasses.dataclass(kw_only=True)
class AskWithRichCitationsToolConfig(ToolConfig, _RAGToolBase):
    kind: str = "ask_with_rich_citations"
    tool_name: str = "soliplex.tools.ask_with_rich_citations"
    agui_feature_names: typing.ClassVar[tuple[str]] = (
        "filter_documents",
        "ask_history",
    )

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            instance = cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "awrctc", config) from exc

        return instance

    def get_extra_parameters(self) -> dict:
        return (
            super().get_extra_parameters()
            | _RAGToolBase.get_extra_parameters(self)
        )


TOOL_CONFIG_CLASSES_BY_TOOL_NAME = {
    klass.tool_name: klass
    for klass in [
        SearchDocumentsToolConfig,
        RAGResearchToolConfig,
        AskWithRichCitationsToolConfig,
    ]
}


ToolConfigMap = dict[str, ToolConfig]


def extract_tool_configs(
    installation_config: InstallationConfig,
    config_path: pathlib.Path,
    config: dict,
) -> ToolConfigMap:
    tool_configs = {}

    for t_config in config.pop("tools", ()):
        tool_name = t_config.get("tool_name")
        tc_class = TOOL_CONFIG_CLASSES_BY_TOOL_NAME.get(tool_name, ToolConfig)

        tool_config = tc_class.from_yaml(
            installation_config,
            config_path,
            t_config,
        )
        tool_configs[tool_config.kind] = tool_config

    return tool_configs


@dataclasses.dataclass(kw_only=True)
class Stdio_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which runs as a subprocess"""

    kind: typing.ClassVar[str] = "stdio"
    command: str
    args: list[str] = dataclasses.field(
        default_factory=list,
    )

    env: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            return cls(**config)
        except Exception as exc:
            raise FromYamlException(
                config_path,
                "stdio_mcptc",
                config,
            ) from exc

    @property
    def toolset_params(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        env_map = {
            key: self._installation_config.get_secret(value)
            for (key, value) in self.env.items()
        }
        return {
            "command": self.command,
            "args": self.args,
            "env": env_map,
            "allowed_tools": self.allowed_tools,
        }


@dataclasses.dataclass(kw_only=True)
class HTTP_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which makes calls over streaming HTTP"""

    kind: typing.ClassVar[str] = "http"
    url: str
    headers: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict,
    )

    query_params: dict[str, str] = dataclasses.field(
        default_factory=dict,
    )
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict[str, typing.Any],
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            return cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "http_mcptc", config) from exc

    @property
    def toolset_params(self) -> dict:
        return {
            "url": self.url,
            "headers": self.headers,
            "query_params": self.query_params,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        url = self.url

        headers = {
            key: self._installation_config.interpolate_secrets(value)
            for (key, value) in self.headers.items()
        }

        if self.query_params:
            qp = {
                key: self._installation_config.get_secret(value)
                for (key, value) in self.query_params.items()
            }
            qs = url_parse.urlencode(qp)
            url = f"{url}?{qs}"

        return {
            "url": url,
            "headers": headers,
            "allowed_tools": self.allowed_tools,
        }


MCP_TOOLSET_CONFIG_CLASSES_BY_KIND = {
    "stdio": Stdio_MCP_ClientToolsetConfig,
    "http": HTTP_MCP_ClientToolsetConfig,
}


def extract_mcp_client_toolset_configs(
    installation_config: InstallationConfig,
    config_path: pathlib.Path,
    config: dict,
):
    mcp_client_toolset_configs = {}

    for mcp_name, mcp_client_toolset_config in config.pop(
        "mcp_client_toolsets", {}
    ).items():
        kind = mcp_client_toolset_config.pop("kind")
        mcp_config_klass = MCP_TOOLSET_CONFIG_CLASSES_BY_KIND[kind]
        mcp_client_toolset_configs[mcp_name] = mcp_config_klass.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config=mcp_client_toolset_config,
        )

    return mcp_client_toolset_configs


MCP_ClientToolsetConfig = (
    Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
)

MCP_ClientToolsetConfigMap = dict[str, MCP_ClientToolsetConfig]


@dataclasses.dataclass(kw_only=True)
class NoArgsMCPWrapper:
    func: abc.Callable[..., typing.Any]
    tool_config: ToolConfig

    def __call__(self):
        return self.func(tool_config=self.tool_config)


@dataclasses.dataclass(kw_only=True)
class WithQueryMCPWrapper:
    func: abc.Callable[..., typing.Any]
    tool_config: ToolConfig

    def __call__(self, query):
        return self.func(query, tool_config=self.tool_config)


MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME = {
    SearchDocumentsToolConfig.tool_name: WithQueryMCPWrapper,
}


# ============================================================================
#   Agent-related configuration types
# ============================================================================


class LLMProviderType(enum.StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GOOGLE = "google"


@dataclasses.dataclass(kw_only=True)
class AgentConfig:
    #
    # Agent-specific options
    #
    id: str  # set as 'room-{room_id}' or 'completion-{completion_id}'
    kind: typing.ClassVar[str] = "default"
    model_name: str = None
    retries: int = 3

    system_prompt: dataclasses.InitVar[str] = None
    _system_prompt_text: str = None
    _system_prompt_path: pathlib.Path = None

    provider_type: LLMProviderType = LLMProviderType.OLLAMA
    provider_base_url: str = None  # installation config provides default
    provider_key: str = None  # secret containing API key

    model_settings: ai_settings.ModelSettings = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    # Use a config from the top-level InstallationConfig's 'agent_configs'
    # as a template.
    _template_id: str = None

    def __post_init__(self, system_prompt):
        if self.model_name is None:
            if self._installation_config is not None:
                self.model_name = self._installation_config.get_environment(
                    "DEFAULT_AGENT_MODEL",
                )

        if system_prompt is not None:
            self._system_prompt_text = system_prompt

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            if "template_id" in config:
                template_id = config.pop("template_id")

                # Cannot use 'agent_configs_map' because we might still be
                # initalizing the IC.
                ic_agent_configs_map = {
                    agent_config.id: agent_config
                    for agent_config in installation_config.agent_configs
                }

                if template_id not in ic_agent_configs_map:
                    raise InvalidAgentTemplateID(  # noqa: TRY301
                        template_id,
                        config_path,
                    )

                template_config = ic_agent_configs_map[template_id]

                config = (
                    template_config.as_yaml
                    | config
                    | {"_template_id": template_id}
                )

            if "model_name" not in config:
                msg = (
                    f"Missing 'model_name' in agent configuration "
                    f"(configured in {config_path})"
                )
                warnings.warn(msg, DeprecationWarning)  # noqa B028

            if "system_prompt" in config:
                system_prompt = config.pop("system_prompt")

                if system_prompt.startswith("./"):
                    config["_system_prompt_path"] = system_prompt
                else:
                    config["system_prompt"] = system_prompt

            if config.get("model_settings") is not None:
                pm_settings = config.pop("model_settings")
                config["model_settings"] = ai_settings.ModelSettings(
                    **pm_settings
                )

            return cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "agent", config) from exc

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
    def llm_provider_base_url(self) -> str | None:
        if (
            self.provider_type == LLMProviderType.OLLAMA
            and self.provider_base_url is None
        ):
            ic = self._installation_config
            return ic.get_environment("OLLAMA_BASE_URL")
        else:
            return self.provider_base_url

    @property
    def llm_provider_kw(self) -> dict:
        provider_kw = {}
        base_url = self.llm_provider_base_url

        if base_url is not None:
            provider_kw["base_url"] = f"{base_url}/v1"

        if self.provider_key is not None:
            provider_kw["api_key"] = self._installation_config.get_secret(
                self.provider_key
            )

        return provider_kw

    @property
    def as_yaml(self) -> dict:
        prompt = (
            self._system_prompt_path
            if self._system_prompt_text is None
            else self._system_prompt_text
        )
        if self.provider_base_url is None:
            provider_base_url = self._installation_config.get_environment(
                "OLLAMA_BASE_URL"
            )
        else:
            provider_base_url = self.provider_base_url

        return {
            "id": self.id,
            "model_name": self.model_name,
            "retries": self.retries,
            "system_prompt": prompt,
            "model_settings": self.model_settings,
            "provider_type": str(self.provider_type),
            "provider_base_url": provider_base_url,
            "provider_key": self.provider_key,  # "secret:SECRET_NAME"
        }


AgentFactory = abc.Callable[[], ai_ag_abstract.AbstractAgent]


@dataclasses.dataclass(kw_only=True)
class FactoryAgentConfig:
    id: str
    factory_name: str  # dotted name for import
    kind: typing.ClassVar[str] = "factory"
    with_agent_config: bool = False
    extra_config: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict,
    )

    _factory: AgentFactory = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @property
    def factory(self) -> AgentFactory:
        if self._factory is None:
            module_name, factory_id = self.factory_name.rsplit(".", 1)
            module = importlib.import_module(module_name)
            factory = getattr(module, factory_id)

            if self.with_agent_config:
                self._factory = functools.update_wrapper(
                    functools.partial(factory, agent_config=self),
                    factory,
                )
            else:
                self._factory = factory

        return self._factory

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            return cls(**config_dict)

        except Exception as exc:
            raise FromYamlException(
                config_path,
                "python_agent",
                config_dict,
            ) from exc

    @property
    def as_yaml(self) -> dict:
        return {
            "id": self.id,
            "factory_name": self.factory_name,
            "with_agent_config": self.with_agent_config,
            "extra_config": self.extra_config,
        }


AGENT_CONFIG_CLASSES_BY_KIND = {
    klass.kind: klass
    for klass in [
        AgentConfig,
        FactoryAgentConfig,
    ]
}

AgentConfigMap = dict[str, AgentConfig | FactoryAgentConfig]


def extract_agent_config(
    installation_config: InstallationConfig,
    config_path: pathlib.Path,
    config: dict,
) -> AgentConfig:  # or subclass
    agent_kind = config.get("kind")

    if agent_kind is not None:  # kind is a typing.ClassVar
        config = {key: value for key, value in config.items() if key != "kind"}

    ac_class = AGENT_CONFIG_CLASSES_BY_KIND.get(agent_kind, AgentConfig)

    return ac_class.from_yaml(
        installation_config,
        config_path,
        config,
    )


# ============================================================================
#   Quiz-related configuration types
# ============================================================================


class QuizQuestionType(enum.StrEnum):
    QA = "qa"
    FILL_BLANK = "fill-blank"
    MULTIPLE_CHOICE = "multiple-choice"


@dataclasses.dataclass(kw_only=True)
class QuizQuestionMetadata:
    type: QuizQuestionType
    uuid: str
    options: list[str] = dataclasses.field(
        default_factory=list,
    )


@dataclasses.dataclass(kw_only=True)
class QuizQuestion:
    inputs: str
    expected_output: str
    metadata: QuizQuestionMetadata


@dataclasses.dataclass(kw_only=True)
class QuizConfig:
    id: str
    question_file: dataclasses.InitVar[str] = None
    _question_file_stem: str = None
    _question_file_path_override: str = None
    _questions_map: dict[str, QuizQuestion] = None

    title: str = "Quiz"
    randomize: bool = False
    max_questions: int = None

    judge_agent: AgentConfig | None = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            ja_config = config.pop("judge_agent", None)
            if ja_config is not None:
                config["judge_agent"] = extract_agent_config(
                    installation_config,
                    config_path,
                    ja_config,
                )

            return cls(**config)
        except Exception as exc:
            raise FromYamlException(config_path, "quiz", config) from exc

    def __post_init__(self, question_file):
        if question_file is not None:
            if "/" in question_file:
                self._question_file_path_override = question_file
            else:
                if question_file.endswith(".json"):
                    question_file = question_file[: -len(".json")]

                self._question_file_stem = question_file
        if (
            self._question_file_stem is None
            and self._question_file_path_override is None
        ) or (
            self._question_file_stem is not None
            and self._question_file_path_override is not None
        ):
            raise QCExactlyOneOfStemOrOverride(self._config_path)

        if self.judge_agent is None:
            kwargs = {
                "id": f"quiz-{self.id}-judge",
                "model_name": "gpt-oss:20b",
            }
            if self._installation_config is not None:
                i_config = self._installation_config
                kwargs["provider_base_url"] = i_config.get_environment(
                    "OLLAMA_BASE_URL",
                )
            self.judge_agent = AgentConfig(**kwargs)

    @property
    def question_file_path(self) -> pathlib.Path:
        if self._question_file_path_override is not None:
            return pathlib.Path(self._question_file_path_override)
        else:
            for quizzes_path in self._installation_config.quizzes_paths:
                qf_path = quizzes_path / f"{self._question_file_stem}.json"

                if qf_path.is_file():
                    return qf_path

    @staticmethod
    def _make_question(question: dict) -> QuizQuestion:
        metadata = QuizQuestionMetadata(
            uuid=question["metadata"]["uuid"],
            type=question["metadata"]["type"],
            options=question["metadata"].get("options", []),
        )
        return QuizQuestion(
            inputs=question["inputs"],
            expected_output=question["expected_output"],
            metadata=metadata,
        )

    def _load_questions_file(self) -> dict[str, QuizQuestion]:
        question_file = self.question_file_path

        if question_file is None:
            raise QuestionFileNotFoundWithStem(
                self._question_file_stem,
                self._installation_config.quizzes_paths,
                self._config_path,
            )

        if not question_file.is_file():
            raise QuestionFileNotFoundWithOverride(
                self._question_file_path_override,
                self._config_path,
            )

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
            questions = questions[: self.max_questions]

        return questions

    def get_question(self, uuid: str) -> QuizQuestion:
        if self._questions_map is None:
            self._questions_map = self._load_questions_file()

        return self._questions_map[uuid]


# ============================================================================
#   Room-related configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
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
    _order: str = None  # defaults to 'id'
    welcome_message: str = None
    suggestions: list[str] = dataclasses.field(
        default_factory=list,
    )
    enable_attachments: bool = False

    #
    # Tool options
    #
    tool_configs: ToolConfigMap = dataclasses.field(default_factory=dict)
    mcp_client_toolset_configs: MCP_ClientToolsetConfigMap = dataclasses.field(
        default_factory=dict
    )

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
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    logo_image: dataclasses.InitVar[str] = None
    _logo_image: str = None

    def __post_init__(self, logo_image: str | None):
        if logo_image is not None:
            self._logo_image = logo_image

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        try:
            config["_installation_config"] = installation_config
            config["_config_path"] = config_path

            room_id = config["id"]
            agent_config_yaml = config.pop("agent")
            agent_config_yaml["id"] = f"room-{room_id}"

            config["agent_config"] = extract_agent_config(
                installation_config,
                config_path,
                agent_config_yaml,
            )

            config["tool_configs"] = extract_tool_configs(
                installation_config,
                config_path,
                config,
            )

            config["mcp_client_toolset_configs"] = (
                extract_mcp_client_toolset_configs(
                    installation_config,
                    config_path,
                    config,
                )
            )

            quizzes_config_yaml = config.pop("quizzes", None)
            if quizzes_config_yaml is not None:
                config["quizzes"] = [
                    QuizConfig.from_yaml(
                        installation_config,
                        config_path,
                        quiz_config_yaml,
                    )
                    for quiz_config_yaml in quizzes_config_yaml
                ]

            logo_image = config.pop("logo_image", None)
            config["_logo_image"] = logo_image

            return cls(**config)

        except Exception as exc:
            raise FromYamlException(config_path, "room", config) from exc

    @property
    def sort_key(self):
        if self._order is not None:
            return self._order

        return self.id

    @property
    def agui_feature_names(self) -> tuple[str]:
        tool_configs = self.tool_configs.values()
        return sum(
            (tool_config.agui_feature_names for tool_config in tool_configs),
            start=(),
        )

    @property
    def quiz_map(self) -> dict[str, QuizConfig]:
        if self._quiz_map is None:
            self._quiz_map = {quiz.id: quiz for quiz in self.quizzes}

        return self._quiz_map

    def get_logo_image(self) -> pathlib.Path | None:
        if self._logo_image is not None:
            if self._config_path is None:
                raise NoConfigPath()

            return self._config_path.parent / self._logo_image


# ============================================================================
#   Completions endpoint-related configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
class CompletionConfig:
    """Configuration for a completion endpoint."""

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
    _installation_config: InstallationConfig = _no_repr_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config: dict,
    ):
        config["_installation_config"] = installation_config
        config["_config_path"] = config_path

        completion_id = config["id"]

        if "name" not in config:
            config["name"] = completion_id

        agent_config_yaml = config.pop("agent")
        agent_config_yaml["id"] = f"completion-{completion_id}"

        config["agent_config"] = extract_agent_config(
            installation_config,
            config_path,
            agent_config_yaml,
        )

        config["tool_configs"] = extract_tool_configs(
            installation_config,
            config_path,
            config,
        )

        config["mcp_client_toolset_configs"] = (
            extract_mcp_client_toolset_configs(
                installation_config,
                config_path,
                config,
            )
        )

        return cls(**config)


# ============================================================================
#   Secrets configuration types
# ============================================================================

SECRET_GETTERS_BY_KIND = {}


class _BaseSecretSource:
    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        config["_config_path"] = config_path
        return cls(**config)

    @property
    def as_yaml(self) -> dict:
        return {
            "kind": self.kind,
            "secret_name": self.secret_name,
            **self.extra_arguments,
        }


@dataclasses.dataclass(kw_only=True)
class EnvVarSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "env_var"
    secret_name: str
    env_var_name: str | None = None
    _config_path: pathlib.Path = None

    def __post_init__(self):
        if self.env_var_name is None:
            self.env_var_name = self.secret_name

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"env_var_name": self.env_var_name}


@dataclasses.dataclass(kw_only=True)
class FilePathSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "file_path"
    secret_name: str
    file_path: str
    _config_path: pathlib.Path = None

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"file_path": self.file_path}


@dataclasses.dataclass(kw_only=True)
class SubprocessSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "subprocess"
    secret_name: str
    command: str
    args: list[str] | tuple[str] = ()
    _config_path: pathlib.Path = None

    @property
    def command_line(self) -> str:
        listed = [self.command, *self.args]
        return " ".join(listed)

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"command_line": self.command_line}

    @property
    def as_yaml(self) -> dict:
        return {
            "kind": self.kind,
            "secret_name": self.secret_name,
            "command": self.command,
            "args": list(self.args),
        }


@dataclasses.dataclass(kw_only=True)
class RandomCharsSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "random_chars"
    secret_name: str
    n_chars: int = 32
    _config_path: pathlib.Path = None

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"n_chars": self.n_chars}


SecretSource = (
    EnvVarSecretSource
    | FilePathSecretSource
    | SubprocessSecretSource
    | RandomCharsSecretSource
)


SecretSources = list[SecretSource]


SourceClassesByKind = {
    klass.kind: klass
    for klass in [
        EnvVarSecretSource,
        FilePathSecretSource,
        SubprocessSecretSource,
        RandomCharsSecretSource,
    ]
}


@dataclasses.dataclass(kw_only=True)
class SecretConfig:
    secret_name: str
    sources: SecretSources = None

    # Set in 'from_yaml' below
    _config_path: pathlib.Path = None
    _resolved: str = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = [EnvVarSecretSource(secret_name=self.secret_name)]

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict | str):
        if isinstance(config, str):
            config = {
                "secret_name": config,
                "sources": [
                    {"kind": "env_var", "env_var_name": config},
                ],
            }

        config["_config_path"] = config_path
        source_configs = config.pop("sources", None)

        sources = []

        for source_config in source_configs:
            source_config["secret_name"] = config["secret_name"]
            source_kind = source_config.pop("kind")
            source_klass = SourceClassesByKind[source_kind]
            source_inst = source_klass.from_yaml(config_path, source_config)
            sources.append(source_inst)

        config["sources"] = sources

        return cls(**config)

    @property
    def as_yaml(self) -> dict:
        return {
            "secret_name": self.secret_name,
            "sources": [source.as_yaml for source in self.sources],
        }

    @property
    def resolved(self) -> str | None:
        return self._resolved


# ============================================================================
#   AGUI feature configuration types
# ============================================================================


class AGUI_FeatureSource(enum.StrEnum):
    CLIENT = "client"
    SERVER = "server"
    EITHER = "either"


@dataclasses.dataclass(kw_only=True)
class AGUI_Feature:
    """Registration of schema and semantics defining a Soliplex AGUI feature

    Features define a contract between the Soliplex client and the Soliplex
    server, describing the schema of a portion of the AG-UI protocol's
    'state' mapping.
    """

    name: str
    """Key within the AG-UI state in which the feature's data is stored"""

    model_klass: type
    """Pydantic model class defining schema for the feature's data"""

    source: AGUI_FeatureSource = AGUI_FeatureSource.EITHER
    """Parties allowed to write to the feature's data in the AG-UI 'state'"""

    @property
    def description(self) -> str:
        return self.model_klass.model_json_schema()["description"]

    @property
    def as_yaml(self):
        return {
            "name": self.name,
            "description": self.description,
            "source": str(self.source),
        }

    @property
    def json_schema(self):
        return self.model_klass.model_json_schema()


AGUI_FEATURES_BY_NAME = {
    agui_feature.name: agui_feature
    for agui_feature in [
        AGUI_Feature(
            name=features.FILTER_DOCUMENTS_FEATURE,
            model_klass=features.FilterDocuments,
            source=AGUI_FeatureSource.CLIENT,
        ),
        AGUI_Feature(
            name=features.ASK_HISTORY_FEATURE,
            model_klass=features.AskedAndAnswered,
            source=AGUI_FeatureSource.SERVER,
        ),
        AGUI_Feature(
            name=features.HAIKU_CHAT_FEATURE,
            model_klass=features.hr_chat_state.ChatSessionState,
            source=AGUI_FeatureSource.SERVER,
        ),
    ]
}

# ============================================================================
#   Installation configuration types
# ============================================================================


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
        raise FromYamlException(config_path, None, {}) from exc

    return config_yaml


def _find_configs(
    to_search: pathlib.Path,
    filename_yaml: str,
) -> typing.Sequence[tuple[pathlib.Path, dict]]:
    """Yield a sequence of YAML configs found under 'to_search'

    Yielded values are tuples, '(config_path, config_yaml)', suitable for
    passing to a config class's 'from_yaml'.

    If 'to_search' has its own copy of 'filename_yaml', just yield the one
    config parsed from it.

    Otherwise, iterate over immediate subdirectories, yielding configs
    parsed from any which have copies of 'filename_yaml'
    """
    config_file = to_search / filename_yaml

    try:
        yield config_file, _load_config_yaml(config_file)

    except NoSuchConfig:
        for sub in sorted(to_search.glob("*")):
            # See #233
            if sub.name.startswith("."):
                continue

            if sub.is_dir():
                sub_config = sub / filename_yaml
                try:
                    yield sub_config, _load_config_yaml(sub_config)
                except NoSuchConfig:
                    continue
            else:  # pragma: NO COVER
                pass


_find_room_configs = functools.partial(
    _find_configs,
    filename_yaml="room_config.yaml",
)

_find_completion_configs = functools.partial(
    _find_configs,
    filename_yaml="completion_config.yaml",
)


def strip_secret_prefix(config_str: str) -> str:
    if not config_str.startswith(SECRET_PREFIX):
        raise NotASecret(config_str)

    return config_str[len(SECRET_PREFIX) :]


def resolve_file_prefix(
    config_value: typing.Any,
    config_path: pathlib.Path,
) -> str:
    if isinstance(config_value, str):
        if config_value.startswith(FILE_PREFIX):
            file_part = config_value[len(FILE_PREFIX) :]
            config_value = config_path.parent / file_part
            config_value = str(config_value.resolve())

    return config_value


def resolve_environment_entry(
    env_name: str,
    env_value: str,
    dotenv_env: dict[str, str],
) -> dict:
    if env_name in dotenv_env:
        return dotenv_env[env_name]

    if env_value is None:
        try:
            return os.environ[env_name]
        except KeyError:
            raise MissingEnvVar(env_name) from None

    return env_value


def _from_dotted_name(dotted_name: str):
    module_name, target = dotted_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, target)


@dataclasses.dataclass(kw_only=True)
class AGUI_FeatureConfigMeta:
    """Registered config class

    'model_klass'
        dotted name of a a class or factory returning an 'AGUI_Feature'
        when passed the feature name and an instance of this class.

    'source':
        (optional) one of "client", "server", or "either" (defaults to
        "either).
    """

    name: str
    model_klass: typing.Any
    source: AGUI_FeatureSource = "either"

    @classmethod
    def from_yaml(cls, yaml_config: str | dict):
        model_klass = yaml_config["model_klass"]
        yaml_config["model_klass"] = _from_dotted_name(model_klass)
        return cls(**yaml_config)


@dataclasses.dataclass(kw_only=True)
class ConfigMeta:
    """Registered config class

    'config_klass'
        a class or factory: must have a 'from_yaml' method compatible
        with 'extract_tool_configs' / 'extract_mcp_client_toolset_configs'
        usage above.

    'wrapper_klass'
        a class or factory used to wrap instances of 'config_klass'

    'registered_func'
        a callable taking an instance of 'config_klass' (return type
        unspecified), but it should be the same type for all 'config_klass'
        classes registered for a given set.
    """

    config_klass: typing.Any
    wrapper_klass: typing.Any = None
    registered_func: typing.Any = None

    @classmethod
    def from_yaml(cls, yaml_config: str | dict):
        if isinstance(yaml_config, str):
            config_klass = _from_dotted_name(yaml_config)
            return cls(config_klass=config_klass)
        else:
            config_klass = yaml_config["config_klass"]

            if isinstance(config_klass, str):
                config_klass = _from_dotted_name(config_klass)

            wrapper_klass = yaml_config.get("wrapper_klass")

            if isinstance(wrapper_klass, str):
                wrapper_klass = _from_dotted_name(wrapper_klass)

            registered_func = yaml_config.get("registered_func")

            if isinstance(registered_func, str):
                registered_func = _from_dotted_name(registered_func)

            return cls(
                config_klass=config_klass,
                wrapper_klass=wrapper_klass,
                registered_func=registered_func,
            )

    @property
    def dotted_name(self):
        klass = self.config_klass
        return f"{klass.__module__}.{klass.__name__}"


@dataclasses.dataclass(kw_only=True)
class InstallationConfigMeta:
    """Configuration for pluggable components

    'agui_features'
        a list consisting of `AGUI_FeatureConfigMeta' mappings, defining the
        AG-UI features supported by the installation.

    'tool_configs'
        a list consisting of strings (importable dotted names of tool
        config classes) or `ConfigMeta' mappings, defining the types
        of tools which can be configured.

    'mcp_toolset_configs'
        a list consisting of strings (importable dotted names of MCP client
        toolset config classes) or `ConfigMeta' mappings, defining the types
        of MCP client toolsets which can be configured.

    'mcp_server_tool_wrappers"
        a list consisting of strings (importable dotted names of MCP
        server tool wrapper classes) or `ConfigMeta' mappings, defining
        the types of MCP server tool wrappers which can be configured.

    'agent_configs'
        a list consisting of strings (importable dotted names of agent
        config classes) or `ConfigMeta' mappings, defining the
        types of agents which can be configured.

    'secret_sources'
        a list consisting of  strings (importable dotted names of secret
        source classes) or `ConfigMeta' mappings, defining the
        tyeps of secret sources which can be configured.

    After loading, adds the configured classes to the registry mappings
    'TOOL_CONFIG_CLASSES_BY_TOOL_NAME' and
    'MCP_TOOLSET_CONFIG_CLASSES_BY_TYPE'.
    """

    agui_features: list[str | AGUI_FeatureConfigMeta] = ()
    tool_configs: list[str | ConfigMeta] = ()
    mcp_toolset_configs: list[str | ConfigMeta] = ()
    mcp_server_tool_wrappers: list[ConfigMeta] = ()
    agent_configs: list[str | ConfigMeta] = ()
    secret_sources: list[str | ConfigMeta] = ()

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config_dict: dict | None):
        if config_dict is None:
            config_dict = {}

        config_dict["_config_path"] = config_path

        try:
            config_dict["agui_features"] = [
                AGUI_FeatureConfigMeta.from_yaml(af_yaml)
                for af_yaml in config_dict.get("agui_features", ())
            ]

            config_dict["tool_configs"] = [
                ConfigMeta.from_yaml(tc_yaml)
                for tc_yaml in config_dict.get("tool_configs", ())
            ]

            config_dict["mcp_toolset_configs"] = [
                ConfigMeta.from_yaml(mcp_tc_yaml)
                for mcp_tc_yaml in config_dict.get("mcp_toolset_configs", ())
            ]

            config_dict["mcp_server_tool_wrappers"] = [
                ConfigMeta.from_yaml(mcp_tc_yaml)
                for mcp_tc_yaml in config_dict.get(
                    "mcp_server_tool_wrappers",
                    (),
                )
            ]

            config_dict["agent_configs"] = [
                ConfigMeta.from_yaml(ac_yaml)
                for ac_yaml in config_dict.get("agent_configs", ())
            ]

            config_dict["secret_sources"] = [
                ConfigMeta.from_yaml(ss_yaml)
                for ss_yaml in config_dict.get("secret_sources", ())
            ]

            return cls(**config_dict)

        except Exception as exc:
            raise FromYamlException(
                config_path,
                "icmeta",
                config_dict,
            ) from exc

    def __post_init__(self):
        self.agui_features = list(self.agui_features)
        for af_meta in self.agui_features:
            klass = af_meta.model_klass
            AGUI_FEATURES_BY_NAME[af_meta.name] = klass

        self.tool_configs = list(self.tool_configs)
        for tc_meta in self.tool_configs:
            klass = tc_meta.config_klass
            TOOL_CONFIG_CLASSES_BY_TOOL_NAME[klass.tool_name] = klass

        self.mcp_toolset_configs = list(self.mcp_toolset_configs)
        for mtc_meta in self.mcp_toolset_configs:
            klass = mtc_meta.config_klass
            MCP_TOOLSET_CONFIG_CLASSES_BY_KIND[klass.kind] = klass

        self.mcp_server_tool_wrappers = list(self.mcp_server_tool_wrappers)
        for mstw_meta in self.mcp_server_tool_wrappers:
            config_klass = mstw_meta.config_klass
            tool_name = config_klass.tool_name
            wrapper_klass = mstw_meta.wrapper_klass
            MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME[tool_name] = wrapper_klass

        self.agent_configs = list(self.agent_configs)
        for ac_meta in self.agent_configs:
            klass = ac_meta.config_klass
            AGENT_CONFIG_CLASSES_BY_KIND[klass.kind] = klass

        self.secret_sources = list(self.secret_sources)
        for ss_meta in self.secret_sources:
            config_klass = ss_meta.config_klass
            registered_func = ss_meta.registered_func
            SECRET_GETTERS_BY_KIND[config_klass.kind] = registered_func

    @property
    def as_yaml(self) -> dict:
        agui_feature_entries = [
            {
                "name": feature.name,
                "model_klass": _dotted_name(feature.model_klass),
                "source": str(feature.source),
            }
            for feature in AGUI_FEATURES_BY_NAME.values()
        ]
        tool_config_entries = [
            _dotted_name(klass)
            for klass in TOOL_CONFIG_CLASSES_BY_TOOL_NAME.values()
        ]
        mcp_toolset_config_entries = [
            _dotted_name(klass)
            for klass in MCP_TOOLSET_CONFIG_CLASSES_BY_KIND.values()
        ]
        mcptcw_items = MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME.items()
        mcp_server_tool_wrapper_entries = [
            {
                "config_klass": _dotted_name(
                    TOOL_CONFIG_CLASSES_BY_TOOL_NAME[tool_name],
                ),
                "wrapper_klass": _dotted_name(wrapper_klass),
            }
            for tool_name, wrapper_klass in mcptcw_items
        ]
        agent_config_entries = [
            _dotted_name(klass)
            for klass in AGENT_CONFIG_CLASSES_BY_KIND.values()
        ]
        secret_source_entries = [
            {
                "config_klass": _dotted_name(SourceClassesByKind[kind]),
                "registered_func": _dotted_name(r_func),
            }
            for kind, r_func in SECRET_GETTERS_BY_KIND.items()
        ]
        return {
            "agui_features": agui_feature_entries,
            "tool_configs": tool_config_entries,
            "mcp_toolset_configs": mcp_toolset_config_entries,
            "mcp_server_tool_wrappers": mcp_server_tool_wrapper_entries,
            "agent_configs": agent_config_entries,
            "secret_sources": secret_source_entries,
        }


@dataclasses.dataclass(kw_only=True)
class InstallationConfig:
    """Configuration for a set of rooms, completion, etc."""

    #
    # Required metadata
    #
    id: str

    meta: InstallationConfigMeta = None

    #
    # AG-UI features defined via metaconfig / defaults
    #
    @property
    def agui_features(self) -> list[AGUI_Feature]:
        return [feature for feature in AGUI_FEATURES_BY_NAME.values()]

    #
    # Secrets name values looked up from env vars or other sources.
    #
    secrets: list[SecretConfig] = dataclasses.field(
        default_factory=list,
    )
    _secrets_map: dict[str, SecretConfig] = None

    @property
    def secrets_map(self) -> dict[str, SecretConfig]:
        if self._secrets_map is None:
            self._secrets_map = {
                secret_config.secret_name: secret_config
                for secret_config in self.secrets
            }

        return self._secrets_map

    def _resolve_secret(self, secret_name):
        from soliplex import secrets as secrets_module  # avoid cycle

        try:
            secret_config = self.secrets_map[secret_name]
        except KeyError:
            raise secrets_module.UnknownSecret(secret_name) from None

        return secrets_module.get_secret(secret_config)

    def get_secret(self, secret_name) -> str:
        """Return the value for a given secret."""
        secret_name = strip_secret_prefix(secret_name)
        return self._resolve_secret(secret_name)

    def interpolate_secrets(self, value):
        """Replace 'secret:<secret_name>' markers w/ secret value

        The marker pattern may appear zero or more times.
        """

        def resolved_tokens(value):
            tokens = SECRET_RE.split(value)

            if sys.version_info >= (3, 13):  # noqa: UP036
                batch = itertools.batched(tokens, 2, strict=False)
            else:  # pragma: NO COVER
                batch = itertools.batched(tokens, 2)  # noqa: B911

            for two_or_one in batch:
                yield two_or_one[0]

                if len(two_or_one) == 2:
                    yield self._resolve_secret(two_or_one[1])

        return "".join(resolved_tokens(value))

    #
    # Map values similar to 'os.environ'.
    #
    environment: dict[str, typing.Any] = dataclasses.field(
        default_factory=dict,
    )

    def get_environment(self, key, default=None):
        """Find the configured value for a given quasi-envvar"""
        return self.environment.get(key, default)

    def resolve_environment(self):
        dotenv_file = self._config_path.parent / ".env"

        if dotenv_file.is_file():
            with dotenv_file.open() as stream:
                dotenv_env = dotenv.dotenv_values(stream=stream)
        else:
            dotenv_env = {}

        resolved = {}
        failed = []
        excs = []

        for key, value in self.environment.items():
            try:
                resolved[key] = resolve_environment_entry(
                    key,
                    value,
                    dotenv_env,
                )
            except MissingEnvVar as exc:
                excs.append(exc)
                failed.append(exc.env_var)

        if excs:
            raise MissingEnvVars(",".join(failed), excs)  # noqa: TRY301

        self.environment = {
            key: resolve_file_prefix(value, self._config_path)
            for key, value in resolved.items()
        }

    #
    # Global haiku-rag configuration
    #
    _haiku_rag_config_file: pathlib.Path = None

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        """Populate a haiku-rag config object from our environment"""
        config_yaml = hr_config.load_yaml_config(self._haiku_rag_config_file)
        config = hr_config.AppConfig.model_validate(config_yaml)
        ollama_base_url = self.get_environment("OLLAMA_BASE_URL")
        if ollama_base_url is not None:
            config.providers.ollama.base_url = ollama_base_url
        return config

    #
    # Agent configurations not bound to a room or completion.
    #
    agent_configs: list[AgentConfig] = dataclasses.field(
        default_factory=list,
    )
    _agent_configs_map: AgentConfigMap = None

    @property
    def agent_configs_map(self) -> AgentConfigMap:
        if self._agent_configs_map is None:
            self._agent_configs_map = {
                agent_config.id: agent_config
                for agent_config in self.agent_configs
            }

        return self._agent_configs_map

    #
    # Path(s) to OIDC Authentication System configs
    #
    # Defaults to one path: './oidc' (set in '__post_init__')
    #
    oidc_paths: list[pathlib.Path | None] = None

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
    # Path(s) to completion configs:  each item can be either a single
    # completion config (a directory containing its own
    # 'completion_config.yaml' file), or a directory containing such
    # completion configs.
    #
    # Defaults to one path: './completion' (set in '__post_init__'), which is
    # normally a "container" directory for completion config directories.
    #
    completion_paths: list[pathlib.Path] = None

    _completion_configs: dict[str, CompletionConfig] = None

    #
    # Path(s) to quiz data:  each item must be a single directory containing
    # one or more '*.json' files, each holding question data for a single quiz.
    #
    # Defaults to one path: './quizzes' (set in '__post_init__').
    #
    quizzes_paths: list[pathlib.Path] = None

    #
    #   DB-URI secret handling
    #
    def _dburi_w_secret(self, dburi: str | None, default: str) -> str:
        if dburi is None:
            return default

        return self.interpolate_secrets(dburi)

    #
    # Thread persistence DB-URI
    #
    _thread_persistence_dburi_sync: str = None
    _thread_persistence_dburi_async: str = None

    @property
    def thread_persistence_dburi_sync(self):
        return self._dburi_w_secret(
            self._thread_persistence_dburi_sync,
            SYNC_MEMORY_ENGINE_URL,
        )

    @property
    def thread_persistence_dburi_async(self):
        return self._dburi_w_secret(
            self._thread_persistence_dburi_async,
            ASYNC_MEMORY_ENGINE_URL,
        )

    #
    # Room authorization DB-URI
    #
    _room_authz_dburi_sync: str = None
    _room_authz_dburi_async: str = None

    @property
    def room_authz_dburi_sync(self):
        return self._dburi_w_secret(
            self._room_authz_dburi_sync,
            SYNC_MEMORY_ENGINE_URL,
        )

    @property
    def room_authz_dburi_async(self):
        return self._dburi_w_secret(
            self._room_authz_dburi_async,
            ASYNC_MEMORY_ENGINE_URL,
        )

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict):
        try:
            config["_config_path"] = config_path

            meta = config.get("meta")
            config["meta"] = InstallationConfigMeta.from_yaml(
                config_path,
                meta,
            )

            secret_configs = [
                SecretConfig.from_yaml(config_path, secret_config)
                for secret_config in config.pop("secrets", ())
            ]
            config["secrets"] = secret_configs

            environment = config.get("environment", {})

            if isinstance(environment, list):
                environment = [
                    {"name": entry} if isinstance(entry, str) else entry
                    for entry in environment
                ]

                environment = {
                    entry["name"]: entry.get("value") for entry in environment
                }

            config["environment"] = environment

            hr_config_file = config.pop(
                "haiku_rag_config_file",
                "./haiku.rag.yaml",
            )
            config["_haiku_rag_config_file"] = (
                config_path.parent / hr_config_file
            )

            agent_configs = [
                extract_agent_config(
                    None,
                    config_path,
                    a_config,
                )
                for a_config in config.get("agent_configs", ())
            ]
            config["agent_configs"] = agent_configs

            tp_dburi = config.pop("thread_persistence_dburi", {})
            config["_thread_persistence_dburi_sync"] = tp_dburi.get("sync")
            config["_thread_persistence_dburi_async"] = tp_dburi.get("async")

            ra_dburi = config.pop("room_authz_dburi", {})
            config["_room_authz_dburi_sync"] = ra_dburi.get("sync")
            config["_room_authz_dburi_async"] = ra_dburi.get("async")

            return cls(**config)

        except FromYamlException:  # pragma: NO COVER
            raise
        except Exception as exc:
            raise FromYamlException(
                config_path,
                "installation",
                config,
            ) from exc

    def __post_init__(self):
        if self.meta is None:
            self.meta = InstallationConfigMeta(tool_configs=[])

        self.agent_configs = [
            dataclasses.replace(
                agent_config,
                _installation_config=self,
            )
            for agent_config in self.agent_configs
        ]

        if self.oidc_paths is None:
            self.oidc_paths = ["./oidc"]

        if self.room_paths is None:
            self.room_paths = ["./rooms"]

        if self.completion_paths is None:
            self.completion_paths = ["./completions"]

        if self.quizzes_paths is None:
            self.quizzes_paths = ["./quizzes"]

        if self._config_path is not None:
            parent_dir = self._config_path.parent

            self.oidc_paths = [
                parent_dir / oidc_path
                for oidc_path in self.oidc_paths
                if oidc_path is not None
            ]

            self.room_paths = [
                parent_dir / room_path
                for room_path in self.room_paths
                if room_path is not None
            ]

            self.completion_paths = [
                parent_dir / completion_path
                for completion_path in self.completion_paths
                if completion_path is not None
            ]

            self.quizzes_paths = [
                parent_dir / quizzes_path
                for quizzes_path in self.quizzes_paths
                if quizzes_path is not None
            ]

    @property
    def as_yaml(self) -> dict:
        return {
            "id": self.id,
            "meta": self.meta.as_yaml,
            "secrets": [secret.as_yaml for secret in self.secrets],
            "environment": self.environment,
            "haiku_rag_config_file": str(self._haiku_rag_config_file),
            "agent_configs": [ac.as_yaml for ac in self.agent_configs],
            "oidc_paths": [str(path) for path in self.oidc_paths],
            "room_paths": [str(path) for path in self.room_paths],
            "completion_paths": [str(path) for path in self.completion_paths],
            "quizzes_paths": [str(path) for path in self.quizzes_paths],
        }

    def _load_oidc_auth_system_configs(self) -> list[OIDCAuthSystemConfig]:
        oas_configs = []

        for oidc_path in self.oidc_paths:
            oidc_config = oidc_path / "config.yaml"
            config_yaml = _load_config_yaml(oidc_config)

            oidc_client_pem_path = config_yaml.get("oidc_client_pem_path")
            if oidc_client_pem_path is not None:
                oidc_client_pem_path = oidc_path / oidc_client_pem_path

            for auth_system_yaml in config_yaml["auth_systems"]:
                if "oidc_client_pem_path" not in auth_system_yaml:
                    auth_system_yaml["oidc_client_pem_path"] = (
                        oidc_client_pem_path
                    )
                oas_config = OIDCAuthSystemConfig.from_yaml(
                    self,
                    oidc_config,
                    auth_system_yaml,
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
                        self,
                        config_path,
                        config_yaml,
                    )

        return room_configs

    @property
    def room_configs(self) -> dict[str, RoomConfig]:
        if self._room_configs is None:
            self._room_configs = self._load_room_configs()

        return self._room_configs.copy()

    def _load_completion_configs(self) -> dict[str, CompletionConfig]:
        completion_configs = {}

        for completion_path in self.completion_paths:
            for config_path, config_yaml in _find_completion_configs(
                completion_path
            ):
                # XXX  order of 'completion_paths' controls
                #      first-past-the-post for any conflict on completion ID.
                config_id = config_yaml["id"]
                if config_id not in completion_configs:
                    completion_configs[config_id] = CompletionConfig.from_yaml(
                        self,
                        config_path,
                        config_yaml,
                    )

        return completion_configs

    @property
    def completion_configs(self) -> dict[str, CompletionConfig]:
        if self._completion_configs is None:
            self._completion_configs = self._load_completion_configs()

        return self._completion_configs.copy()

    def reload_configurations(self):
        """Load all dependent configuration sets"""
        self._oidc_auth_system_configs = self._load_oidc_auth_system_configs()
        self._room_configs = self._load_room_configs()
        self._completion_configs = self._load_completion_configs()


def load_installation(config_path: pathlib.Path) -> InstallationConfig:
    config_path = config_path.resolve()

    if config_path.is_dir():
        config_path = config_path / "installation.yaml"

    config_yaml = _load_config_yaml(config_path)

    return InstallationConfig.from_yaml(config_path, config_yaml)
