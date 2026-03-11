from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import pathlib
import typing
import warnings

import pydantic
from haiku.rag import config as hr_config
from haiku.rag.skills import rag as hr_skills_rag
from haiku.rag.skills import rlm as hr_skills_rlm
from haiku.skills import agent as hs_agent
from haiku.skills import discovery as hs_discovery
from haiku.skills import models as hs_models
from pydantic_ai import models as ai_models

from soliplex import agents
from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils
from . import agents as config_agents
from . import exceptions as config_exc
from . import rag as config_rag

_default_list_field = _utils._default_list_field
_default_dict_field = _utils._default_dict_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none


# ============================================================================
#   Skill configuration types
# ============================================================================


class OnlyOneOfModelNameAgentConfig(ValueError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Pass only one of 'model_name' and 'agent_config' "
            f"(configured in {_config_path})"
        )


class OnlyOneOfToolNamesRagFeatures(ValueError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Pass only one of 'tool_names' and 'rag_features' "
            f"(configured in {_config_path})"
        )


class Invalid_RAG_Feature(ValueError):
    def __init__(
        self,
        *,
        rag_feature: str,
        suggestion: str,
        _config_path: pathlib.Path,
    ):
        self.rag_feature = rag_feature
        self.suggestion = suggestion
        self._config_path = _config_path
        super().__init__(
            f"Invalid RAG feature '{rag_feature}'; "
            f"{suggestion}; "
            f"(configured in {_config_path})"
        )


class InvalidSkillKind(KeyError):
    def __init__(
        self,
        *,
        invalid_skill_kind: str,
        available_skill_kinds: typing.Sequence[str],
        _config_path: pathlib.Path,
    ):
        self.invalid_skill_kind = invalid_skill_kind
        self.available_skill_kinds = available_skill_kinds
        self._config_path = _config_path
        super().__init__(
            f"Skill kind '{invalid_skill_kind}' unknown; "
            f"available kinds: {list(available_skill_kinds)}; "
            f"(configured in {_config_path})",
        )


class MissingSkillNames(KeyError):
    def __init__(
        self,
        _config_path: pathlib.Path,
        missing_skill_names: typing.Sequence[str],
        available_skill_names: typing.Sequence[str],
    ):
        self.missing_skill_names = missing_skill_names
        self.available_skill_names = available_skill_names
        self._config_path = _config_path
        super().__init__(
            f"Required skills {list(missing_skill_names)} not found "
            f"in available skills: {list(available_skill_names)} "
            f"(configured in {_config_path})",
        )


SkillKind = hs_models.SkillSource
SkillStateType = type[pydantic.BaseModel] | None


@dataclasses.dataclass(kw_only=True)
class _SkillConfigModelBase:
    """Base for configuration for an agent skill."""

    model_name: str | None = None
    agent_config: config_agents.AgentConfig | None = None

    _config_path: pathlib.Path | None = None

    def __post_init__(self):
        if self.model_name is not None and self.agent_config is not None:
            raise OnlyOneOfModelNameAgentConfig(
                _config_path=self._config_path,
            )

    @property
    def model_or_name(self) -> ai_models.Model | str | None:
        if self.agent_config is not None:
            return agents.get_model_from_config(
                agent_config=self.agent_config,
            )
        if self.model_name is not None:
            return self.model_name

        return None


class _SkillPropertiesFromMetadata(typing.Protocol):
    @property
    def skill_metadata(self) -> hs_models.SkillMetadata:
        return self._skill_metadata

    @property
    def name(self) -> str:
        return self._skill_metadata.name

    @property
    def description(self) -> str:
        return self._skill_metadata.description

    @property
    def license(self) -> str | None:
        return self._skill_metadata.license

    @property
    def compatibility(self) -> str | None:
        return self._skill_metadata.compatibility

    @property
    def allowed_tools(self) -> str:
        return self._skill_metadata.allowed_tools

    @property
    def metadata(self) -> dict:
        return self._skill_metadata.metadata


@dataclasses.dataclass(kw_only=True)
class _DiscoveredSkillConfigBase(
    _SkillConfigModelBase,
    _SkillPropertiesFromMetadata,
):
    """Configuration for an agent skill discovered by the installation"""

    kind: typing.ClassVar[hs_models.SkillSource]  # quasi- @abstractproperty

    _skill_metadata: hs_models.SkillMetadata
    state_namespace: str | None = None
    state_type: SkillStateType = None

    @property
    def source(self) -> hs_models.SkillSource | None:
        return self.kind

    @classmethod
    def from_skill(cls, skill: hs_models.Skill):
        return cls(
            _skill_metadata=skill.metadata,
            state_type=skill.state_type,
            state_namespace=skill.state_namespace,
        )

    @property
    def agui_feature_names(self) -> tuple[str]:
        if self.state_namespace is not None:
            return (self.state_namespace,)
        else:
            return ()

    @property
    def skill(self) -> hs_models.Skill:
        return hs_models.Skill(
            source=self.kind,
            metadata=self._skill_metadata,
            state_type=self.state_type,
            state_namespace=self.state_namespace,
            model=self.model_or_name,
        )


@dataclasses.dataclass(kw_only=True)
class FilesystemSkillConfig(_DiscoveredSkillConfigBase):
    """Configuration for an agent skill loaded from a filesystem directory"""

    kind: typing.ClassVar[hs_models.SkillSource] = SkillKind.FILESYSTEM

    _skill_path: pathlib.Path
    _validation_errors: list[str] = _default_list_field()

    @classmethod
    def from_skill(cls, skill: hs_models.Skill):
        return cls(
            _skill_metadata=skill.metadata,
            _skill_path=skill.path,
            state_type=skill.state_type,
            state_namespace=skill.state_namespace,
        )

    @classmethod
    def from_path(cls, skill_path: pathlib.Path):
        """Parse a skill from its 'SKILLS.md', capturing validation errors

        Used in CLI's '--list-skills', where we want to display those
        errors.

        'skill_path' must be the path for a single filesystem skill.
        """
        skills, validation_errors = hs_discovery.discover_from_paths(
            [skill_path],
        )
        if validation_errors:
            skill_metadata = hs_models.SkillMetadata(
                name=skill_path.name,
                description=f"Invalid filesystem skill: {skill_path}",
            )
            return cls(
                _skill_path=skill_path,
                _skill_metadata=skill_metadata,
                _validation_errors=[str(ve) for ve in validation_errors],
            )
        else:
            (skill,) = skills
            result = cls.from_skill(skill)
            result._skill_path = skill_path
            return result

    @property
    def path(self) -> pathlib.Path | None:
        return self._skill_path

    @property
    def errors(self) -> list[str]:
        return self._validation_errors

    @property
    def skill(self) -> hs_models.Skill:
        return hs_models.Skill(
            source=self.kind,
            metadata=self._skill_metadata,
            path=self._skill_path,
            state_type=self.state_type,
            state_namespace=self.state_namespace,
            model=self.model_or_name,
        )


@dataclasses.dataclass(kw_only=True)
class EntrypointSkillConfig(_DiscoveredSkillConfigBase):
    """Configuration for an agent skill loaded from an entrypoint"""

    kind: typing.ClassVar[hs_models.SkillSource] = SkillKind.ENTRYPOINT


@dataclasses.dataclass(kw_only=True)
class _HR_SkillConfigBase(
    config_rag._RAGConfigBase,
    _SkillPropertiesFromMetadata,
):
    """Base class for 'haiku-rag' skll configs"""

    source: typing.ClassVar[hs_models.SkillSource] = SkillKind.ENTRYPOINT

    _haiku_rag_config: hr_config.AppConfig = None

    @property
    def _skill_metadata(self) -> hs_models.SkillMetadata:
        return self._hr_skill_module.skill_metadata()

    @property
    def state_namespace(self) -> str:
        return self._hr_skill_module.STATE_NAMESPACE

    @property
    def state_type(self) -> type[pydantic.BaseModel]:
        return self._hr_skill_module.STATE_TYPE

    @property
    def agui_feature_names(self):
        return [self.state_namespace]

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            _kind = config_dict.pop("kind", None)
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                cls._hr_skill_module.STATE_NAMESPACE,
                config_dict,
            ) from exc

    @property
    def skill(self) -> hs_models.Skill:
        return self._hr_skill_module.create_skill(
            db_path=self.rag_lancedb_path,
            config=self.haiku_rag_config,
        )


class HR_RAG_Tools(enum.StrEnum):
    SEARCH = "search"
    LIST_DOCUMENTS = "list_documents"
    GET_DOCUMENT = "get_document"
    ASK = "ask"
    RESEARCH = "research"


DEFAULT_RAG_TOOLS = [
    HR_RAG_Tools.SEARCH,
    HR_RAG_Tools.LIST_DOCUMENTS,
    HR_RAG_Tools.GET_DOCUMENT,
    HR_RAG_Tools.ASK,
]


RAG_FEATURE_NAMES_TO_TOOLS: dict[str | None, list[HR_RAG_Tools]] = {
    "search": [HR_RAG_Tools.SEARCH],
    "documents": [
        HR_RAG_Tools.LIST_DOCUMENTS,
        HR_RAG_Tools.GET_DOCUMENT,
    ],
    "qa": [HR_RAG_Tools.ASK],
}

USE_HR_SKILLS_RLM = "Use 'haiku.rag.skills.rlm' skill instead"

REMOVED_HR_RAG_FEATURES = {
    "analysis": USE_HR_SKILLS_RLM,
}


def _rag_feature_to_tools(
    rag_feature: str | None,
    _config_path: pathlib.Path,
) -> list[HR_RAG_Tools]:
    """Map legacy 'rag_features' entry to tools names"""
    suggestion = REMOVED_HR_RAG_FEATURES.get(rag_feature)

    if suggestion is not None:
        raise Invalid_RAG_Feature(
            rag_feature=rag_feature,
            _config_path=_config_path,
            suggestion=suggestion,
        )

    try:
        return RAG_FEATURE_NAMES_TO_TOOLS[rag_feature]
    except KeyError:
        raise Invalid_RAG_Feature(
            rag_feature=rag_feature,
            _config_path=_config_path,
            suggestion=(
                f"Available features: {list(RAG_FEATURE_NAMES_TO_TOOLS)}"
            ),
        ) from None


def _default_rag_tools() -> list[HR_RAG_Tools]:
    return DEFAULT_RAG_TOOLS[:]


@dataclasses.dataclass(kw_only=True)
class HR_RAG_SkillConfig(_HR_SkillConfigBase):
    """Configuration for an agent skill from 'haiku.rag.skills.rag"""

    kind: typing.ClassVar[hs_models.SkillSource] = "haiku.rag.skills.rag"
    _hr_skill_module = hr_skills_rag

    _tool_names: list[HR_RAG_Tools] = dataclasses.field(
        default_factory=_default_rag_tools,
    )

    @property
    def tool_names(self):
        return self._tool_names

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        tool_names = config_dict.pop("tool_names", None)
        rag_features = config_dict.pop("rag_features", None)

        if tool_names is not None and rag_features is not None:
            raise OnlyOneOfToolNamesRagFeatures(
                _config_path=config_path,
            )

        if tool_names is not None:
            rag_tools = [HR_RAG_Tools(tool_name) for tool_name in tool_names]

        elif rag_features is not None:
            warnings.warn(
                "'rag_features' is deprecated. Use 'tool_names'",
                DeprecationWarning,
                stacklevel=2,
            )
            rag_tools = sum(
                (
                    _rag_feature_to_tools(rag_feature, config_path)
                    for rag_feature in rag_features
                ),
                [],
            )
        else:
            rag_tools = DEFAULT_RAG_TOOLS

        config_dict["_tool_names"] = rag_tools

        return super().from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )

    @property
    def skill(self) -> hs_models.Skill:
        skill = super().skill
        skill.tools = [
            tool for tool in skill.tools if tool.__name__ in self.tool_names
        ]
        return skill


@dataclasses.dataclass(kw_only=True)
class HR_RLM_SkillConfig(_HR_SkillConfigBase):
    """Configuration for an agent skill from 'haiku.rag.skills.rlm"""

    kind: typing.ClassVar[hs_models.SkillSource] = "haiku.rag.skills.rlm"
    _hr_skill_module = hr_skills_rlm


SKILL_CONFIG_CLASSES_BY_KIND = {
    klass.kind: klass
    for klass in [
        FilesystemSkillConfig,
        EntrypointSkillConfig,
        HR_RAG_SkillConfig,
        HR_RLM_SkillConfig,
    ]
}

SkillConfigTypes = (
    FilesystemSkillConfig
    | EntrypointSkillConfig
    | HR_RAG_SkillConfig
    | HR_RLM_SkillConfig
)
SkillConfigMap = dict[str, SkillConfigTypes]
SkillMap = dict[str, hs_models.Skill]


def extract_skill_configs(
    installation_config: InstallationConfig,  # noqa F821 cycles
    config_path: pathlib.Path,
    config_dict: dict,
):
    skill_configs = {}

    for s_config in config_dict.pop("skill_configs", ()):
        kind = s_config.get("kind")
        try:
            sc_klass = SKILL_CONFIG_CLASSES_BY_KIND[kind]
        except KeyError:
            raise InvalidSkillKind(
                invalid_skill_kind=kind,
                available_skill_kinds=SKILL_CONFIG_CLASSES_BY_KIND.keys(),
                _config_path=config_path,
            ) from None

        skill_config = sc_klass.from_yaml(
            installation_config,
            config_path,
            s_config,
        )
        skill_configs[skill_config.name] = skill_config

    return skill_configs


@dataclasses.dataclass(kw_only=True)
class RoomSkillsConfig(_SkillConfigModelBase):
    """Configure skills in a room"""

    #
    # Use skills defined in the installation, identified by name
    #
    installation_skill_names: list[str] = _default_list_field()

    # Set by `from_yaml` factory
    _skill_configs: SkillConfigMap = _default_dict_field()
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @staticmethod
    def _check_skill_configs(
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        config_skill_names = set(
            config_dict.get("installation_skill_names", ())
        )
        installation_skill_names = set(installation_config.skill_configs)
        missing_skill_names = config_skill_names - installation_skill_names

        if missing_skill_names:
            raise MissingSkillNames(
                _config_path=config_path,
                missing_skill_names=missing_skill_names,
                available_skill_names=installation_skill_names,
            )

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            cls._check_skill_configs(
                installation_config,
                config_path,
                config_dict,
            )

            config_dict["_skill_configs"] = extract_skill_configs(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            return cls(**config_dict)

        except config_exc.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "room_skills",
                config_dict,
            ) from exc

    @property
    def skill_configs(self) -> SkillConfigMap:
        ic_skill_configs = self._installation_config.skill_configs
        return {
            skill_name: ic_skill_configs[skill_name]
            for skill_name in self.installation_skill_names
        } | (self._skill_configs)

    @property
    def skills(self) -> SkillMap:
        return {
            name: skill_config.skill
            for name, skill_config in self.skill_configs.items()
        }

    @property
    def skill_toolset(self) -> hs_agent.SkillToolset:
        skill_map = self.skills
        return hs_agent.SkillToolset(
            skills=skill_map.values(),
            skill_model=self.model_or_name,
        )
