from __future__ import annotations  # forward refs in typing decls

import dataclasses
import importlib
import pathlib
import typing

from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils
from . import agents as config_agents
from . import agui as config_agui
from . import exceptions as config_exc

# from . import quizzes as config_quizzes
# from . import rag as config_rag
from . import secrets as config_secrets
from . import skills as config_skills
from . import tools as config_tools

_dotted_name = _utils._dotted_name
_no_repr = _utils._no_repr
_no_repr_no_compare = _utils._no_repr_no_compare
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_no_repr_no_compare_dict = _utils._no_repr_no_compare_dict
_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field


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

        except config_exc.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise config_exc.FromYamlException(
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
