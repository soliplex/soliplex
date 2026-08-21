from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing

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


class ExtraneousKeys(TypeError):
    def __init__(self, allowed_keys, extra_keys):
        self.extra_keys = extra_keys
        allowed_key_repr = ", ".join(f"'{key}'" for key in allowed_keys)
        extra_key_repr = ", ".join(f"'{key}'" for key in extra_keys)
        super().__init__(
            f"Only {allowed_key_repr} allowed (passed {extra_key_repr})"
        )


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


class GetterForUnknownSecretSource(ValueError):
    def __init__(self, kind, func):
        self.kind = kind
        self.func = func

        func_dotted = _utils._dotted_name(func)

        super().__init__(
            f"Getter '{func_dotted}' cannot be registered "
            f"for unregistered secret source kind '{kind}'"
        )


@dataclasses.dataclass(kw_only=True, frozen=True)
class ClearMetaRegistry:
    """Marker used to signal that a config registry is to be cleared

    If passed, it is only sensible as the first in a list of meta configs.
    """

    MARKER: typing.ClassVar[str] = "$$CLEAR$$"


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


AllowedKeys = typing.ClassVar[frozenset[str]]


@dataclasses.dataclass(kw_only=True)
class _ConfigKlassOnlyMeta:
    """Base for config meta classes which take only 'config_klass'

    Derived classes may declare ignored, deprecated keys by overriding
    '_ALLOWED_KEYS'.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset({"config_klass"})
    config_klass: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):

        if isinstance(yaml_config, _utils.DottedName):
            config_klass = _utils._from_dotted_name(yaml_config)
        else:
            extraneous_keys = set(yaml_config) - cls._ALLOWED_KEYS

            if extraneous_keys:
                raise ExtraneousKeys(cls._ALLOWED_KEYS, extraneous_keys)

            config_klass = _utils._from_dotted_name(
                yaml_config["config_klass"]
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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.

    'registered_func'
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.

    'registered_func'
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

    config_klass: typing.Any
    wrapper_klass: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: _utils.DottedName | dict):
        config_klass = _utils._from_dotted_name(yaml_config["config_klass"])
        wrapper_klass = _utils._from_dotted_name(yaml_config["wrapper_klass"])

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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.

    'registered_func'
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.

    'registered_func'
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

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
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.

    'registered_func'
        No-op fossil from 'ConfigMeta'; accepted by 'from_yaml' (see
        '_ALLOWED_KEYS') and otherwise ignored.
    """

    _ALLOWED_KEYS: AllowedKeys = frozenset(
        {
            "config_klass",
            "wrapper_klass",
            "registered_func",
        }
    )

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class SecretSourceMeta(_ConfigKlassOnlyMeta):
    """Meta-config class for registering secret source classes.

    'config_klass'
        a class or factory: returned value must have a 'from_yaml' method
        compatible with the category for which it is used.

        If passed as a string to 'from_yaml', it is resolved via
        '_utils._from_dotted_name'.

    The getter which resolves a secret from an instance of 'config_klass'
    is registered separately, via 'SecretGetterConfigMeta'. A YAML entry
    may still carry 'registered_func' alongside 'config_klass' as
    shorthand: 'InstallationConfigMeta.from_yaml' desugars it into an
    entry here plus one in 'secret_getters'.
    """

    @property
    def kind(self) -> str:
        return self.config_klass.kind


@dataclasses.dataclass(kw_only=True)
class SecretGetterConfigMeta:
    """Registered secret getter function

    'kind'
        the secret source kind whose sources the function resolves. Its
        source config class must already be registered, via
        'meta.secret_sources'.

    'func'
        dotted name of a callable taking an instance of the source config
        class registered for 'kind', returning the resolved secret, or
        raising a 'soliplex.secrets.SecretError' subclass on a miss.
    """

    kind: str
    func: typing.Any

    @classmethod
    def from_yaml(cls, yaml_config: dict):
        func = yaml_config["func"]
        yaml_config["func"] = _utils._from_dotted_name(func)
        return cls(**yaml_config)


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
        a list consisting of strings (importable dotted names of secret
        source classes) or `SecretSourceMeta' mappings, defining the
        types of secret sources which can be configured.

        As shorthand, an entry may carry 'registered_func' alongside
        'config_klass'; it is desugared into this list plus an implicit
        'secret_getters' entry for the same kind.

    'secret_getters'
        a list consisting of `SecretGetterConfigMeta' mappings, defining
        the functions which resolve secrets from the sources configured
        for a given kind. Applied after 'secret_sources': a getter whose
        kind has no registered source class raises
        'GetterForUnknownSecretSource'.

    'jsonpath_functions'
        a list consisting of `JSONPathFunctionConfigMeta' mappings,
        defining named filter functions registered into the shared
        'authz.the_jsonpath_environment' for use in room ACL queries.

    After loading, adds the configured entries to the global registries
    each subsection feeds: 'AGUI_FEATURES_BY_NAME',
    'TOOL_CONFIG_CLASSES_BY_TOOL_NAME',
    'MCP_TOOLSET_CONFIG_CLASSES_BY_KIND',
    'MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME',
    'SKILL_CONFIG_CLASSES_BY_KIND', 'AGENT_CAPABILITY_CLASSES_BY_NAME',
    'AGENT_CONFIG_CLASSES_BY_KIND', 'SourceClassesByKind',
    'SECRET_GETTERS_BY_KIND', and the shared JSONPath environment's
    function extensions.

    A '$$CLEAR$$' marker in a subsection empties that subsection's
    registry first. Two subsections cascade, because the dependent
    registry cannot outlive the one it keys off: clearing 'tool_configs'
    also clears 'mcp_server_tool_wrappers', and clearing 'secret_sources'
    also clears 'secret_getters'.
    """

    agui_features: list[str | AGUI_FeatureConfigMeta | ClearMetaRegistry] = ()
    tool_configs: list[str | ToolConfigMeta | ClearMetaRegistry] = ()
    mcp_toolset_configs: list[
        str | MCP_ToolsetConfigMeta | ClearMetaRegistry
    ] = ()
    mcp_server_tool_wrappers: list[
        MCP_ServerToolWrapperConfigMeta | ClearMetaRegistry
    ] = ()
    skill_configs: list[str | SkillConfigMeta | ClearMetaRegistry] = ()
    agent_capability_types: list[
        str | AgentCapabilityMeta | ClearMetaRegistry
    ] = ()
    agent_configs: list[str | AgentConfigMeta | ClearMetaRegistry] = ()
    secret_sources: list[str | SecretSourceMeta | ClearMetaRegistry] = ()
    secret_getters: list[SecretGetterConfigMeta | ClearMetaRegistry] = ()
    jsonpath_functions: list[
        JSONPathFunctionConfigMeta | ClearMetaRegistry
    ] = ()

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @staticmethod
    def _partition_cmrs(
        entries: list[str | dict],
        *,
        config_klass: typing.Any,
    ):
        """Partition a list of YAML config entries into two groups

        - Those having 'ClearMetaRegistry.MARKER' as their string value;
        - Those which don't.

        If the first group is non-empty, prepend the returned list with
        a 'ClearMetaRegistry' instance, signalling the processor that it
        should clear the registry (or registries) it populates before adding
        config based on the remaining entries.
        """
        has_clear = any(entry == ClearMetaRegistry.MARKER for entry in entries)
        clear_pfx = [ClearMetaRegistry()] if has_clear else []

        return clear_pfx + [
            config_klass.from_yaml(entry)
            for entry in entries
            if entry != ClearMetaRegistry.MARKER
        ]

    @staticmethod
    def _desugar_secret_sources(
        source_entries: list[str | dict],
        getter_entries: list[str | dict],
    ) -> tuple[list, list]:
        """Split combined secret source entries into the two subsections.

        A 'secret_sources' entry carrying 'registered_func' alongside
        'config_klass' is shorthand for registering the source class and
        its getter together. Strip that key, and **prepend** an equivalent
        'secret_getters' entry, so an explicitly configured getter for the
        same kind still wins ('__post_init__' is last-write-wins).

        Both lists are returned unpartitioned, so that a 'ClearMetaRegistry'
        marker written by the user is still hoisted ahead of the desugared
        entries.
        """
        desugared = []
        sources = []

        for entry in source_entries:
            if isinstance(entry, dict) and "registered_func" in entry:
                entry = dict(entry)
                registered_func = entry.pop("registered_func")
                config_klass = _utils._from_dotted_name(
                    entry["config_klass"],
                )
                desugared.append(
                    {"kind": config_klass.kind, "func": registered_func},
                )

            sources.append(entry)

        return sources, desugared + list(getter_entries)

    @staticmethod
    def _strip_clear(entries: tuple | list) -> tuple[list, bool]:
        """Convert entries to a list.

        If any CMR are present, strip them, returning 'stripped, True'

        Otherwise, return  'converted_list, False'
        """
        stripped = [
            entry
            for entry in entries
            if not isinstance(entry, ClearMetaRegistry)
        ]
        clear = len(stripped) < len(entries)
        return stripped, clear

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config_dict: dict | None):
        if config_dict is None:
            config_dict = {}

        config_dict["_config_path"] = config_path

        try:
            config_dict["agui_features"] = cls._partition_cmrs(
                config_dict.get("agui_features", ()),
                config_klass=AGUI_FeatureConfigMeta,
            )

            config_dict["tool_configs"] = cls._partition_cmrs(
                config_dict.get("tool_configs", ()),
                config_klass=ToolConfigMeta,
            )

            config_dict["mcp_toolset_configs"] = cls._partition_cmrs(
                config_dict.get("mcp_toolset_configs", ()),
                config_klass=MCP_ToolsetConfigMeta,
            )

            config_dict["mcp_server_tool_wrappers"] = cls._partition_cmrs(
                config_dict.get("mcp_server_tool_wrappers", ()),
                config_klass=MCP_ServerToolWrapperConfigMeta,
            )

            config_dict["skill_configs"] = cls._partition_cmrs(
                config_dict.get("skill_configs", ()),
                config_klass=SkillConfigMeta,
            )

            config_dict["agent_capability_types"] = cls._partition_cmrs(
                config_dict.get("agent_capability_types", ()),
                config_klass=AgentCapabilityMeta,
            )

            config_dict["agent_configs"] = cls._partition_cmrs(
                config_dict.get("agent_configs", ()),
                config_klass=AgentConfigMeta,
            )

            secret_sources, secret_getters = cls._desugar_secret_sources(
                config_dict.get("secret_sources", ()),
                config_dict.get("secret_getters", ()),
            )

            config_dict["secret_sources"] = cls._partition_cmrs(
                secret_sources,
                config_klass=SecretSourceMeta,
            )

            config_dict["secret_getters"] = cls._partition_cmrs(
                secret_getters,
                config_klass=SecretGetterConfigMeta,
            )

            config_dict["jsonpath_functions"] = cls._partition_cmrs(
                config_dict.get("jsonpath_functions", ()),
                config_klass=JSONPathFunctionConfigMeta,
            )

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
        af_registry = config_agui.AGUI_FEATURES_BY_NAME
        tc_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        mtc_registry = config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        mstw_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        sc_registry = config_skills.SKILL_CONFIG_CLASSES_BY_KIND
        act_registry = config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME
        ac_registry = config_agents.AGENT_CONFIG_CLASSES_BY_KIND
        sg_registry = config_secrets.SECRET_GETTERS_BY_KIND
        ss_registry = config_secrets.SourceClassesByKind
        jf_registry = authz.the_jsonpath_environment.function_extensions

        self.agui_features, af_clear = self._strip_clear(self.agui_features)

        if af_clear:
            af_registry.clear()

        for af_meta in self.agui_features:
            af_registry[af_meta.name] = config_agui.AGUI_Feature(
                name=af_meta.name,
                model_klass=af_meta.model_klass,
                source=af_meta.source,
            )

        self.tool_configs, tc_clear = self._strip_clear(self.tool_configs)

        if tc_clear:
            tc_registry.clear()
            mstw_registry.clear()  # no wrappers without tools

        for tc_meta in self.tool_configs:
            tc_registry[tc_meta.tool_name] = tc_meta.config_klass

        self.mcp_toolset_configs, mtc_clear = self._strip_clear(
            self.mcp_toolset_configs,
        )

        if mtc_clear:
            mtc_registry.clear()

        for mtc_meta in self.mcp_toolset_configs:
            mtc_registry[mtc_meta.kind] = mtc_meta.config_klass

        self.mcp_server_tool_wrappers, mstw_clear = self._strip_clear(
            self.mcp_server_tool_wrappers,
        )

        if mstw_clear:
            mstw_registry.clear()

        for mstw_meta in self.mcp_server_tool_wrappers:
            if mstw_meta.tool_name not in tc_registry:
                raise WrapperForUnknownToolConfig(
                    tool_config_klass=mstw_meta.config_klass,
                    wrapper_klass=mstw_meta.wrapper_klass,
                )
            mstw_registry[mstw_meta.tool_name] = mstw_meta.wrapper_klass

        self.skill_configs, sc_clear = self._strip_clear(self.skill_configs)

        if sc_clear:
            sc_registry.clear()

        for sc_meta in self.skill_configs:
            sc_registry[sc_meta.kind] = sc_meta.config_klass

        self.agent_capability_types, act_clear = self._strip_clear(
            self.agent_capability_types,
        )
        if act_clear:
            act_registry.clear()

        for act_meta in self.agent_capability_types:
            act_registry[act_meta.capability_name] = act_meta.config_klass

        self.agent_configs, ac_clear = self._strip_clear(self.agent_configs)

        if ac_clear:
            ac_registry.clear()

        for ac_meta in self.agent_configs:
            ac_registry[ac_meta.kind] = ac_meta.config_klass

        self.secret_sources, ss_clear = self._strip_clear(self.secret_sources)

        if ss_clear:
            ss_registry.clear()
            sg_registry.clear()  # no getters without sources

        for ss_meta in self.secret_sources:
            ss_registry[ss_meta.kind] = ss_meta.config_klass

        self.secret_getters, sg_clear = self._strip_clear(self.secret_getters)

        if sg_clear:
            sg_registry.clear()

        for sg_meta in self.secret_getters:
            if sg_meta.kind not in ss_registry:
                raise GetterForUnknownSecretSource(
                    kind=sg_meta.kind,
                    func=sg_meta.func,
                )
            sg_registry[sg_meta.kind] = sg_meta.func

        self.jsonpath_functions, jf_clear = self._strip_clear(
            self.jsonpath_functions,
        )

        if jf_clear:
            jf_registered = (
                set(jf_registry) - authz.BUILTIN_JSONPATH_FUNCTION_NAMES
            )
            for jf_key in jf_registered:
                del jf_registry[jf_key]

        for jf_meta in self.jsonpath_functions:
            authz.register_jsonpath_function(jf_meta.name, jf_meta.func)

    @property
    def as_yaml(self) -> dict:
        first_clear = [ClearMetaRegistry.MARKER]
        agui_feature_registry = config_agui.AGUI_FEATURES_BY_NAME
        agui_feature_entries = first_clear + [
            {
                "name": feature.name,
                "model_klass": _utils._dotted_name(feature.model_klass),
                "source": str(feature.source),
            }
            for feature in agui_feature_registry.values()
        ]

        tc_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        tool_config_entries = first_clear + [
            _utils._dotted_name(klass) for klass in tc_registry.values()
        ]

        mcptc_registry = config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        mcp_toolset_config_entries = first_clear + [
            _utils._dotted_name(klass) for klass in mcptc_registry.values()
        ]

        mcptw_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        mcp_server_tool_wrapper_entries = first_clear + [
            {
                "config_klass": _utils._dotted_name(
                    tc_registry[tool_name],
                ),
                "wrapper_klass": _utils._dotted_name(wrapper_klass),
            }
            for tool_name, wrapper_klass in mcptw_registry.items()
        ]

        sc_registry = config_skills.SKILL_CONFIG_CLASSES_BY_KIND
        skill_config_entries = first_clear + [
            _utils._dotted_name(klass) for klass in sc_registry.values()
        ]

        cap_registry = config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME.values()
        capability_type_entries = first_clear + [
            _utils._dotted_name(klass) for klass in cap_registry
        ]

        ac_registry = config_agents.AGENT_CONFIG_CLASSES_BY_KIND
        agent_config_entries = first_clear + [
            _utils._dotted_name(klass) for klass in ac_registry.values()
        ]

        ss_registry = config_secrets.SourceClassesByKind
        secret_source_entries = first_clear + [
            _utils._dotted_name(klass) for klass in ss_registry.values()
        ]

        sg_registry = config_secrets.SECRET_GETTERS_BY_KIND
        secret_getter_entries = first_clear + [
            {"kind": kind, "func": _utils._dotted_name(func)}
            for kind, func in sg_registry.items()
        ]

        jsonpath_function_registry = authz.registered_jsonpath_functions()
        jsonpath_function_entries = first_clear + [
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
            "secret_getters": secret_getter_entries,
            "jsonpath_functions": jsonpath_function_entries,
        }
