from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing
import warnings

from soliplex import authz

from . import _utils
from . import agents as config_agents
from . import agui as config_agui
from . import exceptions as config_exc
from . import secrets as config_secrets
from . import skills as config_skills
from . import tools as config_tools

_no_repr = _utils._no_repr
_no_repr_no_compare = _utils._no_repr_no_compare
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_no_repr_no_compare_dict = _utils._no_repr_no_compare_dict
_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field


CONFIG_META_DEPRECATED = """\
The 'ConfigMeta' class is deprecated; use one of the specialized meta-config
types instead.  Support for the form will be removed after 'v0.76'.
"""

FROM_YAML_KEY_DEPRECATED = """\
The '{field}' key passed to '{klass}.from_yaml' is deprecated,
and will be removed after 'v0.76'.
"""


class WrapperForUnknownToolConfig(ValueError):
    def __init__(self, tool_config_klass, wrapper_klass):
        self.tool_config_klass = tool_config_klass
        self.wrapper_klass = wrapper_klass

        tck_dotted = _utils._dotted_name(tool_config_klass)
        wk_dotted = _utils._dotted_name(wrapper_klass)

        super().__init__(
            f"Wrapper class '{wk_dotted}' cannot be "
            f"registered for unregistered tool config class '{tck_dotted}'"
        )


@dataclasses.dataclass(kw_only=True)
class ConfigMeta:
    """(Deprecated) Registered config class

    This class was used for widely different types, and is now
    deprecated in favor of the more specific meta config types below.

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
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):

        warnings.warn(
            CONFIG_META_DEPRECATED,
            DeprecationWarning,
            stacklevel=2,
        )

        if isinstance(yaml_config, _utils.DottedName):
            config_klass = _utils._from_dotted_name(yaml_config)
            return cls(config_klass=config_klass)
        else:
            config_klass = yaml_config["config_klass"]

            if isinstance(config_klass, _utils.DottedName):
                config_klass = _utils._from_dotted_name(config_klass)

            wrapper_klass = yaml_config.get("wrapper_klass")

            if isinstance(wrapper_klass, _utils.DottedName):
                wrapper_klass = _utils._from_dotted_name(wrapper_klass)

            registered_func = yaml_config.get("registered_func")

            if isinstance(registered_func, _utils.DottedName):
                registered_func = _utils._from_dotted_name(registered_func)

            return cls(
                config_klass=config_klass,
                wrapper_klass=wrapper_klass,
                registered_func=registered_func,
            )


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
    def from_yaml(cls, yaml_config: dict):
        model_klass = yaml_config["model_klass"]
        yaml_config["model_klass"] = _utils._from_dotted_name(model_klass)
        return cls(**yaml_config)


@dataclasses.dataclass(kw_only=True)
class _ConfigKlassOnlyMeta:
    """Base for config meta classes which take only 'config_klass'"""

    config_klass: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):

        if isinstance(yaml_config, _utils.DottedName):
            config_klass = _utils._from_dotted_name(yaml_config)
        else:
            config_klass = _utils._from_dotted_name(
                yaml_config["config_klass"]
            )

            for field in ("wrapper_klass", "registered_func"):
                if field in yaml_config:
                    msg = FROM_YAML_KEY_DEPRECATED.format(
                        klass=cls.__name__,
                        field=field,
                    )
                    warnings.warn(
                        msg,
                        DeprecationWarning,
                        stacklevel=2,
                    )

        return cls(config_klass=config_klass)


@dataclasses.dataclass(kw_only=True)
class ToolConfigMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering tool config classes.

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    @property
    def tool_name(self) -> _utils.DottedName:
        return self.config_klass.tool_name


@dataclasses.dataclass(kw_only=True)
class MCP_ToolsetConfigMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering MCP toolset config classes.

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class MCP_ServerToolWrapperConfigMeta:
    """Meta-config class for registering wrapper classes for MCP server tools

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        a class or factory used to wrap instances of 'config_klass'

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    config_klass: typing.Any
    wrapper_klass: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):
        config_klass = _utils._from_dotted_name(yaml_config["config_klass"])
        wrapper_klass = _utils._from_dotted_name(yaml_config["wrapper_klass"])

        if "registered_func" in yaml_config:
            msg = FROM_YAML_KEY_DEPRECATED.format(
                klass=cls.__name__,
                field="registered_func",
            )
            warnings.warn(
                msg,
                DeprecationWarning,
                stacklevel=2,
            )

        return cls(
            config_klass=config_klass,
            wrapper_klass=wrapper_klass,
        )

    @property
    def tool_name(self) -> _utils.DottedName:
        return self.config_klass.tool_name


@dataclasses.dataclass(kw_only=True)
class SkillConfigMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering skill config classes

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class AgentCapabilityMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering agent capability classes

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    @property
    def capability_name(self) -> _utils.DottedName:
        return self.config_klass.__name__


@dataclasses.dataclass(kw_only=True)
class AgentConfigMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering agent config classes

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.

    'registered_func'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class SecretSourceMeta:
    """Meta-config class for registering secret source classes

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'registered_func'
        a callable taking an instance of 'config_klass' and returning
        a resolved secret, or raising a 'soliplex_secrets.SecretError'
        on a miss.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    'wrapper_klass'
        No-op fossil from 'ConfigMeta'; can only be passed to 'from_yaml',
        where it is ignored with a deprecation warning.
    """

    config_klass: typing.Any
    registered_func: typing.Any = None

    @classmethod
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):
        config_klass = _utils._from_dotted_name(yaml_config["config_klass"])
        registered_func = _utils._from_dotted_name(
            yaml_config["registered_func"],
        )

        if "wrapper_klass" in yaml_config:
            msg = FROM_YAML_KEY_DEPRECATED.format(
                klass=cls.__name__,
                field="wrapper_klass",
            )
            warnings.warn(
                msg,
                DeprecationWarning,
                stacklevel=2,
            )

        return cls(
            config_klass=config_klass,
            registered_func=registered_func,
        )

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class JSONPathFunctionConfigMeta:
    """Registered JSONPath filter function

    'name'
        the name by which the function is invoked inside a JSONPath
        filter expression.

    'func'
        dotted name of a callable implementing the filter function. It
        is registered into 'authz.the_jsonpath_environment' and must
        conform to python-jsonpath's filter-function protocol.
    """

    name: str
    func: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: dict):
        func = yaml_config["func"]
        yaml_config["func"] = _utils._from_dotted_name(func)
        return cls(**yaml_config)


@dataclasses.dataclass(kw_only=True)
class InstallationConfigMeta:
    """Configuration for pluggable components

    'agui_features'
        a list consisting of `AGUI_FeatureConfigMeta' mappings, defining the
        AG-UI features supported by the installation.

    'tool_configs'
        a list consisting of strings (importable dotted names of tool
        config classes) or `ToolConfigMeta' mappings, defining the types
        of tools which can be configured.

    'mcp_toolset_configs'
        a list consisting of strings (importable dotted names of MCP client
        toolset config classes) or `MCP_ToolsetConfigMeta' mappings, defining
        the types of MCP client toolsets which can be configured.

    'mcp_server_tool_wrappers"
        a list consisting of `MCP_ServerToolWrapperConfigMeta'
        mappings, defining
        the types of MCP server tool wrappers which can be configured.

    'skill_configs'
        a list consisting of strings (importable dotted names of skill
        config classes) or `SkillConfigMeta' mappings, defining the types
        of skills which can be configured.

    'agent_capability_types'
        a list consisting of strings (importable dotted names of agent
        capability classes) or `AgentCapabilityMeta' mappings,
        defining additional capability types with which agents can be
        configured.

    'agent_configs'
        a list consisting of strings (importable dotted names of agent
        config classes) or `AgentConfigMeta' mappings, defining the
        types of agents which can be configured.

    'secret_sources'
        a list consisting of  strings (importable dotted names of secret
        source classes) or `SecretSourceMeta' mappings, defining the
        tyeps of secret sources which can be configured.

    'jsonpath_functions'
        a list consisting of `JSONPathFunctionConfigMeta' mappings,
        defining named filter functions registered into the shared
        'authz.the_jsonpath_environment' for use in room ACL queries.

    After loading, adds the configured classes to the registry mappings
    'TOOL_CONFIG_CLASSES_BY_TOOL_NAME' and
    'MCP_TOOLSET_CONFIG_CLASSES_BY_KIND'.
    """

    agui_features: list[str | AGUI_FeatureConfigMeta] = ()
    tool_configs: list[str | ToolConfigMeta] = ()
    mcp_toolset_configs: list[str | MCP_ToolsetConfigMeta] = ()
    mcp_server_tool_wrappers: list[MCP_ServerToolWrapperConfigMeta] = ()
    skill_configs: list[str | SkillConfigMeta] = ()
    agent_capability_types: list[str | AgentCapabilityMeta] = ()
    agent_configs: list[str | AgentConfigMeta] = ()
    secret_sources: list[str | SecretSourceMeta] = ()
    jsonpath_functions: list[JSONPathFunctionConfigMeta] = ()

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
                ToolConfigMeta.from_yaml(tc_yaml)
                for tc_yaml in config_dict.get("tool_configs", ())
            ]

            config_dict["mcp_toolset_configs"] = [
                MCP_ToolsetConfigMeta.from_yaml(mcp_tc_yaml)
                for mcp_tc_yaml in config_dict.get("mcp_toolset_configs", ())
            ]

            config_dict["mcp_server_tool_wrappers"] = [
                MCP_ServerToolWrapperConfigMeta.from_yaml(mcp_tc_yaml)
                for mcp_tc_yaml in config_dict.get(
                    "mcp_server_tool_wrappers",
                    (),
                )
            ]

            config_dict["skill_configs"] = [
                SkillConfigMeta.from_yaml(sc_yaml)
                for sc_yaml in config_dict.get("skill_configs", ())
            ]

            config_dict["agent_capability_types"] = [
                AgentCapabilityMeta.from_yaml(ac_yaml)
                for ac_yaml in config_dict.get("agent_capability_types", ())
            ]

            config_dict["agent_configs"] = [
                AgentConfigMeta.from_yaml(ac_yaml)
                for ac_yaml in config_dict.get("agent_configs", ())
            ]

            config_dict["secret_sources"] = [
                SecretSourceMeta.from_yaml(ss_yaml)
                for ss_yaml in config_dict.get("secret_sources", ())
            ]

            config_dict["jsonpath_functions"] = [
                JSONPathFunctionConfigMeta.from_yaml(jf_yaml)
                for jf_yaml in config_dict.get("jsonpath_functions", ())
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
        tc_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        for tc_meta in self.tool_configs:
            tc_registry[tc_meta.tool_name] = tc_meta.config_klass

        self.mcp_toolset_configs = list(self.mcp_toolset_configs)
        mtc_registry = config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        for mtc_meta in self.mcp_toolset_configs:
            mtc_registry[mtc_meta.kind] = mtc_meta.config_klass

        self.mcp_server_tool_wrappers = list(self.mcp_server_tool_wrappers)
        mstw_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        for mstw_meta in self.mcp_server_tool_wrappers:
            if mstw_meta.tool_name not in tc_registry:
                raise WrapperForUnknownToolConfig(
                    tool_config_klass=mstw_meta.config_klass,
                    wrapper_klass=mstw_meta.wrapper_klass,
                )
            mstw_registry[mstw_meta.tool_name] = mstw_meta.wrapper_klass

        self.skill_configs = list(self.skill_configs)
        sc_registry = config_skills.SKILL_CONFIG_CLASSES_BY_KIND
        for sc_meta in self.skill_configs:
            sc_registry[sc_meta.kind] = sc_meta.config_klass

        self.agent_capability_types = list(self.agent_capability_types)
        act_registry = config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME
        for act_meta in self.agent_capability_types:
            act_registry[act_meta.capability_name] = act_meta.config_klass

        self.agent_configs = list(self.agent_configs)
        ac_registry = config_agents.AGENT_CONFIG_CLASSES_BY_KIND
        for ac_meta in self.agent_configs:
            ac_registry[ac_meta.kind] = ac_meta.config_klass

        self.secret_sources = list(self.secret_sources)
        sg_registry = config_secrets.SECRET_GETTERS_BY_KIND
        ss_registry = config_secrets.SourceClassesByKind
        for ss_meta in self.secret_sources:
            sg_registry[ss_meta.kind] = ss_meta.registered_func
            ss_registry[ss_meta.kind] = ss_meta.config_klass

        self.jsonpath_functions = list(self.jsonpath_functions)
        for jf_meta in self.jsonpath_functions:
            authz.register_jsonpath_function(jf_meta.name, jf_meta.func)

    @property
    def as_yaml(self) -> dict:
        agui_feature_registry = config_agui.AGUI_FEATURES_BY_NAME
        agui_feature_entries = [
            {
                "name": feature.name,
                "model_klass": _utils._dotted_name(feature.model_klass),
                "source": str(feature.source),
            }
            for feature in agui_feature_registry.values()
        ]

        tc_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        tool_config_entries = [
            _utils._dotted_name(klass) for klass in tc_registry.values()
        ]

        mcptc_registry = config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        mcp_toolset_config_entries = [
            _utils._dotted_name(klass) for klass in mcptc_registry.values()
        ]

        mcptw_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        mcp_server_tool_wrapper_entries = [
            {
                "config_klass": _utils._dotted_name(
                    tc_registry[tool_name],
                ),
                "wrapper_klass": _utils._dotted_name(wrapper_klass),
            }
            for tool_name, wrapper_klass in mcptw_registry.items()
        ]

        sc_registry = config_skills.SKILL_CONFIG_CLASSES_BY_KIND
        skill_config_entries = [
            _utils._dotted_name(klass) for klass in sc_registry.values()
        ]

        cap_registry = config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME.values()
        capability_type_entries = [
            _utils._dotted_name(klass) for klass in cap_registry
        ]

        ac_registry = config_agents.AGENT_CONFIG_CLASSES_BY_KIND
        agent_config_entries = [
            _utils._dotted_name(klass) for klass in ac_registry.values()
        ]

        ss_registry = config_secrets.SourceClassesByKind
        sg_registry = config_secrets.SECRET_GETTERS_BY_KIND
        secret_source_entries = [
            {
                "config_klass": _utils._dotted_name(
                    ss_registry[kind],
                ),
                "registered_func": _utils._dotted_name(r_func),
            }
            for kind, r_func in sg_registry.items()
        ]

        jsonpath_function_registry = authz.registered_jsonpath_functions()
        jsonpath_function_entries = [
            {"name": name, "func": _utils._dotted_name(func)}
            for name, func in jsonpath_function_registry.items()
        ]

        return {
            "agui_features": agui_feature_entries,
            "tool_configs": tool_config_entries,
            "mcp_toolset_configs": mcp_toolset_config_entries,
            "mcp_server_tool_wrappers": mcp_server_tool_wrapper_entries,
            "skill_configs": skill_config_entries,
            "agent_capability_types": capability_type_entries,
            "agent_configs": agent_config_entries,
            "secret_sources": secret_source_entries,
            "jsonpath_functions": jsonpath_function_entries,
        }
