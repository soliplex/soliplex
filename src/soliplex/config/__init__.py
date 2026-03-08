from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import importlib
import itertools
import os
import pathlib
import sys
import typing

import dotenv
import logfire
import yaml
from haiku.rag import config as hr_config
from haiku.skills import discovery as hs_discovery
from haiku.skills import models as hs_models

from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils
from . import agents as config_agents
from . import agui as config_agui
from . import authsystem as config_authsystem
from . import exceptions as config_exc

# from . import quizzes as config_quizzes
# from . import rag as config_rag
from . import rooms as config_rooms
from . import secrets as config_secrets
from . import skills as config_skills
from . import tools as config_tools

FILE_PREFIX = "file:"

SYNC_MEMORY_ENGINE_URL = "sqlite://"
ASYNC_MEMORY_ENGINE_URL = "sqlite+aiosqlite://"

FromYamlException = config_exc.FromYamlException

_dotted_name = _utils._dotted_name
_no_repr = _utils._no_repr
_no_repr_no_compare = _utils._no_repr_no_compare
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_no_repr_no_compare_dict = _utils._no_repr_no_compare_dict
_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field


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
    agent_config: config_agents.AgentConfig

    name: str = None

    #
    # Tool options
    #
    tool_configs: config_tools.ToolConfigMap = _default_dict_field()
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap = (
        _default_dict_field()
    )

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = _no_repr_no_compare_none()
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        config_dict["_installation_config"] = installation_config
        config_dict["_config_path"] = config_path

        completion_id = config_dict["id"]

        if "name" not in config_dict:
            config_dict["name"] = completion_id

        agent_config_yaml = config_dict.pop("agent")
        agent_config_yaml["id"] = f"completion-{completion_id}"

        config_dict["agent_config"] = config_agents.extract_agent_config(
            installation_config,
            config_path,
            agent_config_yaml,
        )

        config_dict["tool_configs"] = config_tools.extract_tool_configs(
            installation_config,
            config_path,
            config_dict,
        )

        config_dict["mcp_client_toolset_configs"] = (
            config_tools.extract_mcp_client_toolset_configs(
                installation_config,
                config_path,
                config_dict,
            )
        )

        return cls(**config_dict)


# ============================================================================
#   Logfire configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
class LogfireInstrumentPydanticAI:
    include_binary_content: bool = True
    include_content: bool = True

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict | None,
    ):
        try:
            return cls(
                _config_path=config_path,
                **config_dict,
            )
        except Exception as exc:
            raise FromYamlException(
                config_path,
                "logfire_instrument_pydantic_ai",
                config_dict,
            ) from exc

    @property
    def instrument_pydantic_ai_kwargs(self) -> dict[str, typing.Any]:
        return {
            "include_binary_content": self.include_binary_content,
            "include_content": self.include_content,
        }

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return self.instrument_pydantic_ai_kwargs


@dataclasses.dataclass(kw_only=True)
class LogfireInstrumentFastAPI:
    capture_headers: bool = False
    excluded_urls: list[str] = None
    record_send_receive: bool = False
    extra_spans: bool = False

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict | None,
    ):
        try:
            return cls(
                _config_path=config_path,
                **config_dict,
            )
        except Exception as exc:
            raise FromYamlException(
                config_path,
                "logfire_instrument_fast_api",
                config_dict,
            ) from exc

    @property
    def instrument_fast_api_kwargs(self) -> dict[str, typing.Any]:
        return {
            "capture_headers": self.capture_headers,
            "excluded_urls": self.excluded_urls,
            "record_send_receive": self.record_send_receive,
            "extra_spans": self.extra_spans,
        }

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return self.instrument_fast_api_kwargs


@dataclasses.dataclass(kw_only=True)
class LogfireConfig:
    send_to_logfire: bool | None = None
    token: str  # "secret:LOGFIRE_TOKEN" or similar
    service_name: str = "env:LOGFIRE_SERVICE_NAME"
    service_version: str = "env:LOGFIRE_SERVICE_VERSION"
    environment: str = "env:LOGFIRE_ENVIRONMENT"
    config_dir: pathlib.Path | str = "env:LOGFIRE_CONFIG_DIR"
    data_dir: pathlib.Path | str = "env:LOGFIRE_DATA_DIR"
    min_level: int | logfire.LevelName = "env:LOGFIRE_MIN_LEVEL"
    inspect_arguments: bool = None
    add_baggage_to_attributes: bool = True
    distributed_tracing: bool = None
    base_url: str = None
    scrubbing_patterns: list[str] = None

    instrument_pydantic_ai: LogfireInstrumentPydanticAI = None
    instrument_fast_api: LogfireInstrumentFastAPI = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = _no_repr_no_compare_none()
    _config_path: pathlib.Path = None

    @property
    def logfire_config_kwargs(self) -> dict[str, typing.Any]:
        """Return a mapping to be passed as kwargs to 'logfire.config()'

        Resolve values prefixed with 'env:' using the installation
        configuration environment.
        """

        def maybe_getenv(key):
            if key.startswith("env:"):
                return self._installation_config.get_environment(key[4:])
            else:
                return key

        kwargs = {
            "token": self._installation_config.get_secret(self.token),
            "service_name": maybe_getenv(self.service_name),
            "service_version": maybe_getenv(self.service_version),
            "environment": maybe_getenv(self.environment),
            "config_dir": maybe_getenv(self.config_dir),
            "data_dir": maybe_getenv(self.data_dir),
            "min_level": maybe_getenv(self.min_level),
            "add_baggage_to_attributes": self.add_baggage_to_attributes,
        }
        if self.send_to_logfire is not None:
            kwargs["send_to_logfire"] = self.send_to_logfire

        if self.inspect_arguments is not None:
            kwargs["inspect_arguments"] = self.inspect_arguments

        if self.distributed_tracing is not None:
            kwargs["distributed_tracing"] = self.distributed_tracing

        if self.base_url is not None:
            kwargs["advanced"] = {
                "base_url": maybe_getenv(self.base_url),
            }

        if self.scrubbing_patterns is not None:
            kwargs["scrubbing"] = {
                "extra_patterns": self.scrubbing_patterns,
            }

        return kwargs

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        result = {
            "token": self.token,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "config_dir": self.config_dir,
            "data_dir": self.data_dir,
            "min_level": self.min_level,
            "add_baggage_to_attributes": self.add_baggage_to_attributes,
        }

        if self.send_to_logfire is not None:
            result["send_to_logfire"] = self.send_to_logfire

        if self.inspect_arguments is not None:
            result["inspect_arguments"] = self.inspect_arguments

        if self.distributed_tracing is not None:
            result["distributed_tracing"] = self.distributed_tracing

        if self.base_url is not None:
            result["base_url"] = self.base_url

        if self.scrubbing_patterns is not None:
            result["scrubbing_patterns"] = self.scrubbing_patterns

        if self.instrument_pydantic_ai is not None:
            result["instrument_pydantic_ai"] = (
                self.instrument_pydantic_ai.as_yaml
            )

        if self.instrument_fast_api is not None:
            result["instrument_fast_api"] = self.instrument_fast_api.as_yaml

        return result

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            ipydai = config_dict.pop("instrument_pydantic_ai", None)

            if ipydai is not None:
                ipydai = LogfireInstrumentPydanticAI.from_yaml(
                    config_path,
                    ipydai,
                )
                config_dict["instrument_pydantic_ai"] = ipydai

            ifapi = config_dict.pop("instrument_fast_api", None)

            if ifapi is not None:
                ifapi = LogfireInstrumentFastAPI.from_yaml(
                    config_path,
                    ifapi,
                )
                config_dict["instrument_fast_api"] = ifapi

            return cls(
                _installation_config=installation_config,
                _config_path=config_path,
                **config_dict,
            )

        except FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise FromYamlException(
                config_path,
                "logfire_config",
                config_dict,
            ) from exc


# ============================================================================
#   Installation configuration types
# ============================================================================


def _check_is_dict(config_yaml):
    if not isinstance(config_yaml, dict):
        raise config_exc.NotADict(config_yaml)

    return config_yaml


def _load_config_yaml(config_path: pathlib.Path) -> dict:
    """Load a YAML config file"""
    if not config_path.is_file():
        raise config_exc.NoSuchConfig(config_path)

    try:
        with config_path.open() as stream:
            config_yaml = _check_is_dict(
                yaml.load(stream, yaml.Loader),
            )

    except Exception as exc:
        raise FromYamlException(config_path, None, {}) from exc

    return config_yaml


def _find_configs_yaml(
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

    except config_exc.NoSuchConfig:
        for sub in sorted(to_search.glob("*")):
            # See #233
            if sub.name.startswith("."):
                continue

            if sub.is_dir():
                sub_config = sub / filename_yaml
                try:
                    yield sub_config, _load_config_yaml(sub_config)
                except config_exc.NoSuchConfig:
                    continue
            else:  # pragma: NO COVER
                pass


_find_room_configs = functools.partial(
    _find_configs_yaml,
    filename_yaml="room_config.yaml",
)

_find_completion_configs = functools.partial(
    _find_configs_yaml,
    filename_yaml="completion_config.yaml",
)


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
    if env_value is not None:
        return env_value

    if env_name in dotenv_env:
        return dotenv_env[env_name]

    try:
        return os.environ[env_name]
    except KeyError:
        raise MissingEnvVar(env_name) from None


def _from_dotted_name(dotted_name: str):
    module_name, target = dotted_name.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, target)


@dataclasses.dataclass(kw_only=True)
class AGUI_FeatureConfigMeta:
    """Registered config class

    'model_klass'
        dotted name of a a class or factory returning an 'agui.AGUI_Feature'
        when passed the feature name and an instance of this class.

    'source':
        (optional) one of "client", "server", or "either" (defaults to
        "either).
    """

    name: str
    model_klass: typing.Any
    source: config_agui.AGUI_FeatureSource = "either"

    @classmethod
    def from_yaml(cls, yaml_config: str | dict):
        model_klass = yaml_config["model_klass"]
        yaml_config["model_klass"] = _from_dotted_name(model_klass)
        return cls(**yaml_config)


@dataclasses.dataclass(kw_only=True)
class ConfigMeta:
    """Registered config class

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

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

    'skill_configs'
        a list consisting of strings (importable dotted names of skill
        config classes) or `ConfigMeta' mappings, defining the types
        of skills which can be configured.

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
    'MCP_TOOLSET_CONFIG_CLASSES_BY_KIND'.
    """

    agui_features: list[str | AGUI_FeatureConfigMeta] = ()
    tool_configs: list[str | ConfigMeta] = ()
    mcp_toolset_configs: list[str | ConfigMeta] = ()
    mcp_server_tool_wrappers: list[ConfigMeta] = ()
    skill_configs: list[str | ConfigMeta] = ()
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

            config_dict["skill_configs"] = [
                ConfigMeta.from_yaml(sc_yaml)
                for sc_yaml in config_dict.get("skill_configs", ())
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

        except FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise FromYamlException(
                config_path,
                "icmeta",
                config_dict,
            ) from exc

    def __post_init__(self):
        self.agui_features = list(self.agui_features)
        feature_registry = config_agui.AGUI_FEATURES_BY_NAME
        for af_meta in self.agui_features:
            feature_registry[af_meta.name] = config_agui.AGUI_Feature(
                name=af_meta.name,
                model_klass=af_meta.model_klass,
                source=af_meta.source,
            )

        self.tool_configs = list(self.tool_configs)
        for tc_meta in self.tool_configs:
            klass = tc_meta.config_klass
            config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME[klass.tool_name] = (
                klass
            )

        self.mcp_toolset_configs = list(self.mcp_toolset_configs)
        for mtc_meta in self.mcp_toolset_configs:
            klass = mtc_meta.config_klass
            config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND[klass.kind] = klass

        self.mcp_server_tool_wrappers = list(self.mcp_server_tool_wrappers)
        for mstw_meta in self.mcp_server_tool_wrappers:
            config_klass = mstw_meta.config_klass
            tool_name = config_klass.tool_name
            wrapper_klass = mstw_meta.wrapper_klass
            config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME[tool_name] = (
                wrapper_klass
            )

        self.skill_configs = list(self.skill_configs)
        for sc_meta in self.skill_configs:
            klass = sc_meta.config_klass
            config_skills.SKILL_CONFIG_CLASSES_BY_KIND[klass.kind] = klass

        self.agent_configs = list(self.agent_configs)
        for ac_meta in self.agent_configs:
            klass = ac_meta.config_klass
            config_agents.AGENT_CONFIG_CLASSES_BY_KIND[klass.kind] = klass

        self.secret_sources = list(self.secret_sources)
        ss_registry = config_secrets.SECRET_GETTERS_BY_KIND
        for ss_meta in self.secret_sources:
            config_klass = ss_meta.config_klass
            registered_func = ss_meta.registered_func
            ss_registry[config_klass.kind] = registered_func

    @property
    def as_yaml(self) -> dict:
        agui_feature_registry = config_agui.AGUI_FEATURES_BY_NAME
        agui_feature_entries = [
            {
                "name": feature.name,
                "model_klass": _dotted_name(feature.model_klass),
                "source": str(feature.source),
            }
            for feature in agui_feature_registry.values()
        ]

        tool_config_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        tool_config_entries = [
            _dotted_name(klass) for klass in tool_config_registry.values()
        ]

        mcp_toolset_config_registry = (
            config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        )
        mcp_toolset_config_entries = [
            _dotted_name(klass)
            for klass in mcp_toolset_config_registry.values()
        ]

        mcp_tool_wrapper_registry = (
            config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        )
        mcp_server_tool_wrapper_entries = [
            {
                "config_klass": _dotted_name(
                    tool_config_registry[tool_name],
                ),
                "wrapper_klass": _dotted_name(wrapper_klass),
            }
            for tool_name, wrapper_klass in mcp_tool_wrapper_registry.items()
        ]

        skill_config_registry = config_skills.SKILL_CONFIG_CLASSES_BY_KIND
        skill_config_entries = [
            _dotted_name(klass) for klass in skill_config_registry.values()
        ]

        agent_config_registry = config_agents.AGENT_CONFIG_CLASSES_BY_KIND
        agent_config_entries = [
            _dotted_name(klass) for klass in agent_config_registry.values()
        ]

        secret_source_registry = config_secrets.SourceClassesByKind
        secret_getter_registry = config_secrets.SECRET_GETTERS_BY_KIND
        secret_source_entries = [
            {
                "config_klass": _dotted_name(
                    secret_source_registry[kind],
                ),
                "registered_func": _dotted_name(r_func),
            }
            for kind, r_func in secret_getter_registry.items()
        ]

        return {
            "agui_features": agui_feature_entries,
            "tool_configs": tool_config_entries,
            "mcp_toolset_configs": mcp_toolset_config_entries,
            "mcp_server_tool_wrappers": mcp_server_tool_wrapper_entries,
            "skill_configs": skill_config_entries,
            "agent_configs": agent_config_entries,
            "secret_sources": secret_source_entries,
        }


def _load_filesystem_skill_configs(i_config) -> config_skills.SkillConfigMap:
    fs_skill_configs = {}

    fs_skills, validation_errors = hs_discovery.discover_from_paths(
        i_config.filesystem_skills_paths,
    )
    for fs_skill in fs_skills:
        skill_config = config_skills.FilesystemSkillConfig.from_skill(fs_skill)

        if skill_config.name not in fs_skill_configs:
            fs_skill_configs[skill_config.name] = skill_config

    for validation_error in validation_errors:
        skill_path = validation_error.path
        skill_name = skill_path.name
        message = str(validation_error)
        skill_metadata = hs_models.SkillMetadata(
            name=skill_name,
            description=f"Invalid filesystem skill: {skill_path}",
        )
        fs_skill_configs[skill_name] = config_skills.FilesystemSkillConfig(
            _skill_metadata=skill_metadata,
            _skill_path=skill_path,
            _validation_errors=[message],
        )

    return fs_skill_configs


def _load_entrypoint_skill_configs() -> config_skills.SkillConfigMap:
    ep_skill_configs = {}

    for skill in hs_discovery.discover_from_entrypoints():
        feature_name = skill.state_namespace
        feature_registry = config_agui.AGUI_FEATURES_BY_NAME

        if feature_name is not None and feature_name not in feature_registry:
            feature_registry[feature_name] = config_agui.AGUI_Feature(
                name=feature_name,
                model_klass=skill.state_type,
                source=config_agui.AGUI_FeatureSource.SERVER,
            )

        skill_config = config_skills.EntrypointSkillConfig.from_skill(skill)

        if skill_config.name not in ep_skill_configs:
            ep_skill_configs[skill_config.name] = skill_config

    return ep_skill_configs


class EnvironmentSourceType(enum.StrEnum):
    CONFIG_YAML = "config-yaml"
    DOT_ENV = "dot-env"
    OS_ENV = "os-environment"


@dataclasses.dataclass
class EnvironmentSource:
    source_type: EnvironmentSourceType
    value: str | None


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
    def agui_features(self) -> list[config_agui.AGUI_Feature]:
        return [
            feature for feature in config_agui.AGUI_FEATURES_BY_NAME.values()
        ]

    #
    # Variables loaded via 'dotenv' library
    #
    disable_dotenv: bool = False

    _from_dotenv: dict[str, str] = None

    @staticmethod
    def _load_dotenv(from_path: pathlib.Path) -> dict[str, str] | None:
        if from_path.is_file():
            with from_path.open() as stream:
                return dotenv.dotenv_values(stream=stream)

    @property
    def from_dotenv(self) -> dict[str, str]:
        if self.disable_dotenv:
            return {}

        if self._from_dotenv is None:
            for from_path in [
                self._config_path.parent / ".env",
                pathlib.Path.cwd() / ".env",
            ]:
                values = self._load_dotenv(from_path)

                if values is not None:
                    self._from_dotenv = values
                    break

        return self._from_dotenv or {}

    #
    # Secrets name values looked up from env vars or other sources.
    #
    secrets: list[config_secrets.SecretConfig] = _default_list_field()
    _secrets_map: dict[str, config_secrets.SecretConfig] = None

    @property
    def secrets_map(self) -> dict[str, config_secrets.SecretConfig]:
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
        secret_name = config_secrets.strip_secret_prefix(secret_name)
        return self._resolve_secret(secret_name)

    def interpolate_secrets(self, value):
        """Replace 'secret:<secret_name>' markers w/ secret value

        The marker pattern may appear zero or more times.
        """

        def resolved_tokens(value):
            tokens = config_secrets.SECRET_RE.split(value)

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

    # Values from installation config file.
    _environment_from_config: dict[str, str] = _no_repr_no_compare_dict()

    environment: dict[str, typing.Any] = _default_dict_field()

    def get_environment_sources(self, key) -> list[EnvironmentSource]:
        """Return sources available for an environment key

        First in the list will be the source whose value is used.
        """
        EST = EnvironmentSourceType
        ES = EnvironmentSource

        result = []

        from_config = self._environment_from_config.get(key)

        if from_config is not None:
            result.append(ES(EST.CONFIG_YAML, from_config))

        if self._from_dotenv is not None:
            from_dotenv = self._from_dotenv.get(key)

            if from_dotenv is not None:
                result.append(ES(EST.DOT_ENV, from_dotenv))
            else:  # pragma: NO COVER
                pass

        from_osenv = os.getenv(key)

        if from_osenv is not None:
            result.append(ES(EST.OS_ENV, from_osenv))

        return result

    def get_environment(self, key, default=None):
        """Find the configured value for a given quasi-envvar"""
        return self.environment.get(key, default)

    def resolve_environment(self):
        resolved = {}
        failed = []
        excs = []

        for key, value in self.environment.items():
            try:
                resolved[key] = resolve_environment_entry(
                    key,
                    value,
                    self.from_dotenv,
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
    agent_configs: list[config_agents.AgentConfigTypes] = _default_list_field()
    _agent_configs_map: config_agents.AgentConfigMap = None

    @property
    def agent_configs_map(self) -> config_agents.AgentConfigMap:
        if self._agent_configs_map is None:
            self._agent_configs_map = {
                agent_config.id: agent_config
                for agent_config in self.agent_configs
            }

        return self._agent_configs_map

    # Path(s) to filesystm AI skills:  each item must be a single
    # directory containing matching the spec:
    # https://agentskills.io/specification
    #
    # or a directory whose subdirectories match that spec.
    #
    # Defaults to one path: './skills' (set in '__post_init__').
    #
    filesystem_skills_paths: list[pathlib.Path] = None

    _available_filesystem_skill_configs: config_skills.SkillConfigMap = None
    _available_entrypoint_skill_configs: config_skills.SkillConfigMap = None
    _skill_configs: config_skills.SkillConfigMap = None

    @property
    def available_filesystem_skill_configs(
        self,
    ) -> config_skills.SkillConfigMap:
        if self._available_filesystem_skill_configs is None:
            self._available_filesystem_skill_configs = (
                _load_filesystem_skill_configs(self)
            )

        return self._available_filesystem_skill_configs.copy()

    @property
    def available_entrypoint_skill_configs(
        self,
    ) -> config_skills.SkillConfigMap:
        if self._available_entrypoint_skill_configs is None:
            self._available_entrypoint_skill_configs = (
                _load_entrypoint_skill_configs()  # no 'self' needed
            )

        return self._available_entrypoint_skill_configs.copy()

    @property
    def skill_configs(self) -> config_skills.SkillConfigMap:
        if self._skill_configs is not None:
            return self._skill_configs.copy()
        else:
            return {}

    #
    # Path(s) to OIDC Authentication System configs
    #
    # Defaults to one path: './oidc' (set in '__post_init__')
    #
    oidc_paths: list[pathlib.Path | None] = None

    _oidc_auth_system_configs: list[config_authsystem.OIDCAuthSystemConfig] = (
        None
    )

    #
    # Path(s) to room configs:  each item can be either a single
    # room config (a directory containing its own 'room_config.yaml' file),
    # or a directory containing such room configs.
    #
    # Defaults to one path: './rooms' (set in '__post_init__'), which is
    # normally a "container" directory for room config directories.
    #
    room_paths: list[pathlib.Path] = None

    _room_configs: config_rooms.RoomConfigMap = None

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
    # Console logging configuration
    #
    _logging_config_file: pathlib.Path = None

    @property
    def logging_config_file(self) -> pathlib.Path | None:
        """Return the path to our logging config file"""
        if self._logging_config_file is None:
            return None

        return self._config_path.parent / self._logging_config_file

    @property
    def logging_config(self) -> dict[str, typing.Any] | None:
        """Return a mapping for use in configuring the 'logging' module

        If no file is configured, return None.
        """
        config_file = self.logging_config_file

        if config_file is not None:
            return _load_config_yaml(config_file)

    # Map logging extra keys to request header keys.  E.g., if there is
    # a request header, 'X-Request-ID', we can make it availalable as a
    # logging extra, 'request_id', via:
    #
    # logging_headers_map:
    #   request_id: "X-Request-ID'
    _logging_headers_map: dict[str, str] = None

    @property
    def logging_headers_map(self) -> dict[str, str]:
        result = {}

        if self._logging_headers_map is not None:
            result |= self._logging_headers_map

        return result

    # Map logging extra keys to OIDC claims.  E.g., if there is
    # an OIDC clam, 'foo_user_id', we can make it availalable as a
    # logging extra, 'user_id', via:
    #
    # logging_claims_map:
    #   user_id: "foo_user_id'
    _logging_claims_map: dict[str, str] = None

    @property
    def logging_claims_map(self) -> dict[str, str]:
        result = {}

        if self._logging_claims_map is not None:
            result |= self._logging_claims_map

        return result

    #
    # Logfire configuration
    #
    logfire_config: LogfireConfig = None

    #
    # DB-URI secret handling
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
    _authorization_dburi_sync: str = None
    _authorization_dburi_async: str = None

    @property
    def authorization_dburi_sync(self):
        return self._dburi_w_secret(
            self._authorization_dburi_sync,
            SYNC_MEMORY_ENGINE_URL,
        )

    @property
    def authorization_dburi_async(self):
        return self._dburi_w_secret(
            self._authorization_dburi_async,
            ASYNC_MEMORY_ENGINE_URL,
        )

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config_dict: dict):
        try:
            config_dict["_config_path"] = config_path

            meta = config_dict.get("meta")
            config_dict["meta"] = InstallationConfigMeta.from_yaml(
                config_path,
                meta,
            )

            secret_configs = [
                config_secrets.SecretConfig.from_yaml(
                    config_path,
                    secret_config,
                )
                for secret_config in config_dict.pop("secrets", ())
            ]
            config_dict["secrets"] = secret_configs

            environment = config_dict.get("environment", {})

            if isinstance(environment, list):
                environment = [
                    {"name": entry} if isinstance(entry, str) else entry
                    for entry in environment
                ]

                environment = {
                    entry["name"]: entry.get("value") for entry in environment
                }

            # Preserve values as read for later introspection.
            config_dict["_environment_from_config"] = environment
            config_dict["environment"] = environment

            hr_config_file = config_dict.pop(
                "haiku_rag_config_file",
                "./haiku.rag.yaml",
            )
            config_dict["_haiku_rag_config_file"] = (
                config_path.parent / hr_config_file
            )

            agent_configs = [
                config_agents.extract_agent_config(
                    None,
                    config_path,
                    a_config,
                )
                for a_config in config_dict.get("agent_configs", ())
            ]
            config_dict["agent_configs"] = agent_configs

            skill_configs = config_dict.pop("skill_configs", None)
            if skill_configs is not None:
                config_dict["_skill_configs"] = skill_configs

            logging_config_file = config_dict.pop("logging_config_file", None)

            if logging_config_file is not None:
                config_dict["_logging_config_file"] = pathlib.Path(
                    logging_config_file
                )

            logging_headers_map = config_dict.pop("logging_headers_map", None)

            if logging_headers_map is not None:
                config_dict["_logging_headers_map"] = logging_headers_map

            logging_claims_map = config_dict.pop("logging_claims_map", None)

            if logging_claims_map is not None:
                config_dict["_logging_claims_map"] = logging_claims_map

            logfire_cfg = config_dict.pop("logfire_config", None)

            if logfire_cfg is not None:
                logfire_cfg = LogfireConfig.from_yaml(
                    None,
                    config_path,
                    logfire_cfg,
                )

            config_dict["logfire_config"] = logfire_cfg

            tp_dburi = config_dict.pop("thread_persistence_dburi", {})
            config_dict["_thread_persistence_dburi_sync"] = tp_dburi.get(
                "sync"
            )
            config_dict["_thread_persistence_dburi_async"] = tp_dburi.get(
                "async"
            )

            ra_dburi = config_dict.pop("authorization_dburi", {})
            config_dict["_authorization_dburi_sync"] = ra_dburi.get("sync")
            config_dict["_authorization_dburi_async"] = ra_dburi.get("async")

            return cls(**config_dict)

        except FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise FromYamlException(
                config_path,
                "installation",
                config_dict,
            ) from exc

    def __post_init__(self):
        if self.meta is None:
            self.meta = InstallationConfigMeta(tool_configs=[])

        replaced_secrets = []
        for secret in self.secrets:
            replaced_sources = [
                dataclasses.replace(
                    source,
                    _installation_config=self,
                )
                for source in secret.sources
            ]
            replaced_secrets.append(
                dataclasses.replace(
                    secret,
                    sources=replaced_sources,
                    _installation_config=self,
                )
            )
        self.secrets = replaced_secrets

        self.agent_configs = [
            dataclasses.replace(
                agent_config,
                _installation_config=self,
            )
            for agent_config in self.agent_configs
        ]

        if self.logfire_config is not None:
            self.logfire_config = dataclasses.replace(
                self.logfire_config,
                _installation_config=self,
            )

        if self.oidc_paths is None:
            self.oidc_paths = ["./oidc"]

        if self.room_paths is None:
            self.room_paths = ["./rooms"]

        if self.completion_paths is None:
            self.completion_paths = ["./completions"]

        if self.quizzes_paths is None:
            self.quizzes_paths = ["./quizzes"]

        if self.filesystem_skills_paths is None:
            self.filesystem_skills_paths = ["./skills"]

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

            self.filesystem_skills_paths = [
                parent_dir / skills_path
                for skills_path in self.filesystem_skills_paths
                if skills_path is not None
            ]

        # Resolve skills after resolving paths
        if self._skill_configs is not None:
            available_fs = self.available_filesystem_skill_configs
            available_ep = self.available_entrypoint_skill_configs

            fs_skills = {}

            if isinstance(self._skill_configs, list):
                for skill_config_dict in self._skill_configs:
                    if (
                        skill_config_dict["kind"]
                        == config_skills.SkillKind.FILESYSTEM
                    ):
                        skill_name = skill_config_dict["skill_name"]
                        fs_skills[skill_name] = available_fs[skill_name]

                ep_skills = {}
                for skill_config_dict in self._skill_configs:
                    if (
                        skill_config_dict["kind"]
                        == config_skills.SkillKind.ENTRYPOINT
                    ):
                        skill_name = skill_config_dict["skill_name"]
                        ep_skills[skill_name] = available_ep[skill_name]

                self._skill_configs = ep_skills | fs_skills

    @property
    def as_yaml(self) -> dict:
        result = {
            "id": self.id,
            "meta": self.meta.as_yaml,
            "secrets": [secret.as_yaml for secret in self.secrets],
            # Dump the resolved version, not the original config
            "environment": self.environment,
            "haiku_rag_config_file": str(self._haiku_rag_config_file),
            "agent_configs": [ac.as_yaml for ac in self.agent_configs],
            "filesystem_skills_paths": [
                str(path) for path in self.filesystem_skills_paths
            ],
            "logging_config_file": str(self._logging_config_file),
            "oidc_paths": [str(path) for path in self.oidc_paths],
            "room_paths": [str(path) for path in self.room_paths],
            "completion_paths": [str(path) for path in self.completion_paths],
            "quizzes_paths": [str(path) for path in self.quizzes_paths],
        }

        if self.logfire_config is not None:
            result["logfire_config"] = self.logfire_config.as_yaml

        return result

    def _load_oidc_auth_system_configs(
        self,
    ) -> list[config_authsystem.OIDCAuthSystemConfig]:
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
                oas_config = config_authsystem.OIDCAuthSystemConfig.from_yaml(
                    self,
                    oidc_config,
                    auth_system_yaml,
                )
                oas_configs.append(oas_config)

        return oas_configs

    @property
    def oidc_auth_system_configs(
        self,
    ) -> list[config_authsystem.OIDCAuthSystemConfig]:
        if self._oidc_auth_system_configs is None:
            self._oidc_auth_system_configs = (
                self._load_oidc_auth_system_configs()
            )

        return self._oidc_auth_system_configs

    def _load_room_configs(self) -> config_rooms.RoomConfigMap:
        room_configs = {}

        for room_path in self.room_paths:
            for config_path, config_yaml in _find_room_configs(room_path):
                # XXX  order of 'room_paths' controls first-past-the-post
                #      for any conflict on room ID.
                config_id = config_yaml["id"]
                if config_id not in room_configs:
                    room_configs[config_id] = (
                        config_rooms.RoomConfig.from_yaml(
                            self,
                            config_path,
                            config_yaml,
                        )
                    )

        return room_configs

    @property
    def room_configs(self) -> config_rooms.RoomConfigMap:
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
        self._available_filesystem_configs = _load_filesystem_skill_configs(
            self
        )
        self._available_entrypoint_configs = _load_entrypoint_skill_configs()
        self._oidc_auth_system_configs = self._load_oidc_auth_system_configs()
        self._room_configs = self._load_room_configs()
        self._completion_configs = self._load_completion_configs()


def load_installation(config_path: pathlib.Path) -> InstallationConfig:
    config_path = config_path.resolve()

    if config_path.is_dir():
        config_path = config_path / "installation.yaml"

    config_yaml = _load_config_yaml(config_path)

    return InstallationConfig.from_yaml(config_path, config_yaml)
