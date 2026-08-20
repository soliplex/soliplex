from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import importlib.metadata
import pathlib
import typing

import pydantic
from bubble_sandbox import config as bs_config
from bubble_sandbox import models as bs_models
from haiku.rag.capabilities import analysis as hr_analysis
from haiku.rag.capabilities import compaction as hr_compaction
from haiku.rag.capabilities import policy as hr_policy
from haiku.rag.capabilities import rag as hr_rag
from pydantic_ai import capabilities as ai_capabilities

from soliplex.capabilities import filesystem as cap_fs
from soliplex.config import agui as config_agui
from soliplex.skills import bwrap_sandbox

from . import _utils
from . import exceptions as config_exc
from . import rag as config_rag

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_default_dict_field = _utils._default_dict_field
_default_list_field = _utils._default_list_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none


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


class SkillKind(enum.StrEnum):
    FILESYSTEM = "filesystem"
    NATIVE = "native"
    ENTRYPOINT = "entrypoint"


CAPABILITY_ENTRY_POINT_GROUP = "soliplex.capabilities"


class UnknownCapabilityEntryPoint(KeyError):
    def __init__(self, *, name: str, available: typing.Sequence[str]):
        self.name = name
        self.available = available
        super().__init__(
            f"No capability entry point named {name!r} in group "
            f"'{CAPABILITY_ENTRY_POINT_GROUP}'; available: {list(available)}",
        )


def _load_capability_entry_point(name: str):
    """Resolve a `soliplex.capabilities` entry point to its module/object.

    The target exposes `create_capability(defer_loading=..., **params)` and,
    for stateful capabilities, module-level `STATE_NAMESPACE` / `STATE_TYPE`
    (and an optional `DESCRIPTION`).
    """
    entry_points = importlib.metadata.entry_points(
        group=CAPABILITY_ENTRY_POINT_GROUP,
    )
    for entry_point in entry_points:
        if entry_point.name == name:
            return entry_point.load()
    raise UnknownCapabilityEntryPoint(
        name=name,
        available=[ep.name for ep in entry_points],
    )


class SkillConfig(typing.Protocol):
    name: str
    description: str
    source: str | None
    state_type: None
    state_namespace: None
    agui_feature_names: tuple[str, ...]

    @property
    def capability(self) -> ai_capabilities.AbstractCapability: ...


@dataclasses.dataclass(kw_only=True)
class FilesystemSkillConfig:
    _capability: cap_fs.FilesystemCapability
    _validation_errors: list[str] = _default_list_field()

    kind: typing.ClassVar[str] = SkillKind.FILESYSTEM
    source: typing.ClassVar[SkillKind] = SkillKind.FILESYSTEM
    state_type: typing.ClassVar[None] = None
    state_namespace: typing.ClassVar[None] = None
    agui_feature_names: typing.ClassVar[tuple[str, ...]] = ()

    @classmethod
    def from_capability(cls, capability: cap_fs.FilesystemCapability):
        return cls(_capability=capability)

    @classmethod
    def from_path(cls, capability_path: pathlib.Path):
        capabilities, errors = cap_fs.discover_filesystem_capabilities(
            [capability_path]
        )
        if errors:
            placeholder = cap_fs.FilesystemCapability(
                id=capability_path.name,
                description=(
                    f"Invalid filesystem capability: {capability_path}"
                ),
                defer_loading=True,
                instructions="Invalid filesystem capability.",
                path=capability_path,
            )
            return cls(
                _capability=placeholder,
                _validation_errors=[str(error) for error in errors],
            )
        (capability,) = capabilities
        return cls.from_capability(capability)

    @property
    def capability(self) -> cap_fs.FilesystemCapability:
        return self._capability

    @property
    def name(self) -> str:
        assert self._capability.id is not None
        return self._capability.id

    @property
    def description(self) -> str:
        return self._capability.description or ""

    @property
    def path(self) -> pathlib.Path:
        return self._capability.path

    @property
    def errors(self) -> list[str]:
        return self._validation_errors

    @property
    def extra_parameters(self) -> dict[str, pathlib.Path]:
        return {"path": self.path}


@dataclasses.dataclass(kw_only=True)
class _HaikuRAGCapabilityConfig(
    config_rag._RAGConfigBase,
    config_rag._RAGDatabaseBase,
):
    capability_factory: typing.ClassVar[typing.Callable]
    capability_name: typing.ClassVar[str]
    description: typing.ClassVar[str]
    state_namespace: typing.ClassVar[str]
    state_type: typing.ClassVar[type[pydantic.BaseModel]]
    source: typing.ClassVar[SkillKind] = SkillKind.NATIVE

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict.pop("kind", None)

            rldb_override_path = config_dict.pop(
                "rag_lancedb_override_path",
                None,
            )
            if rldb_override_path is not None:
                config_dict["rag_lancedb_override_path"] = pathlib.Path(
                    rldb_override_path
                )

            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                cls.state_namespace,
                config_dict,
            ) from exc

    @property
    def name(self) -> str:
        return self.capability_name

    @property
    def capability(self) -> ai_capabilities.AbstractCapability:
        return type(self).capability_factory(
            db_path=self.rag_lancedb_path,
            config=self.haiku_rag_config,
            defer_loading=True,
        )

    @property
    def agui_feature_names(self) -> tuple[str, ...]:
        return (self.state_namespace,)

    @property
    def as_yaml(self) -> dict:
        result = {"kind": self.kind}
        if self.rag_lancedb_stem is not None:
            result["rag_lancedb_stem"] = self.rag_lancedb_stem
        else:
            result["rag_lancedb_override_path"] = str(
                self.rag_lancedb_override_path
            )
        return result

    @property
    def extra_parameters(self) -> dict[str, typing.Any]:
        return self.get_extra_parameters()


@dataclasses.dataclass(kw_only=True)
class HR_RAG_SkillConfig(_HaikuRAGCapabilityConfig):
    kind: typing.ClassVar[str] = "haiku.rag.skills.rag"
    capability_factory = hr_rag.create_capability
    capability_name = "rag"
    description = (
        "Search the haiku.rag knowledge base and cite evidence for grounded "
        "answers."
    )
    state_namespace = hr_rag.STATE_NAMESPACE
    state_type = hr_rag.RAGState


@dataclasses.dataclass(kw_only=True)
class HR_Analysis_SkillConfig(_HaikuRAGCapabilityConfig):
    kind: typing.ClassVar[str] = "haiku.rag.skills.analysis"
    capability_factory = hr_analysis.create_capability
    capability_name = "rag-analysis"
    description = (
        "Analyze the haiku.rag corpus with search and sandboxed Python code."
    )
    state_namespace = hr_analysis.STATE_NAMESPACE
    state_type = hr_analysis.AnalysisState


@dataclasses.dataclass(kw_only=True)
class _HaikuRAGEvidenceSkillConfig:
    """Base for haiku.rag's evidence capabilities.

    These take no configuration:  naming one is the whole switch. They are
    configured as skills rather than as agent capabilities so a room
    advertises them, along with the state a client can read.
    """

    kind: typing.ClassVar[str]
    capability_factory: typing.ClassVar[typing.Callable]
    capability_id: typing.ClassVar[str]
    name: typing.ClassVar[str]
    description: typing.ClassVar[str]
    source: typing.ClassVar[SkillKind] = SkillKind.NATIVE
    state_namespace: typing.ClassVar[str | None] = None
    state_type: typing.ClassVar[type[pydantic.BaseModel] | None] = None

    _installation_config: config_installation.InstallationConfig = None
    _config_path: pathlib.Path | None = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict.pop("kind", None)
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                cls.name,
                config_dict,
            ) from exc

    @property
    def capability(self) -> ai_capabilities.AbstractCapability:
        return type(self).capability_factory()

    @property
    def agui_feature_names(self) -> tuple[str, ...]:
        if self.state_namespace is None:
            return ()
        return (self.state_namespace,)

    @property
    def as_yaml(self) -> dict:
        return {"kind": self.kind}

    @property
    def extra_parameters(self) -> dict[str, typing.Any]:
        return {}


@dataclasses.dataclass(kw_only=True)
class HR_EvidenceCompaction_SkillConfig(_HaikuRAGEvidenceSkillConfig):
    kind: typing.ClassVar[str] = "haiku.rag.skills.evidence_compaction"
    capability_factory = hr_compaction.create_capability
    capability_id = hr_compaction.CAPABILITY_ID
    name = "rag-evidence-compaction"
    description = (
        "Replace earlier questions' evidence on each request with a capsule "
        "of what was cited."
    )


@dataclasses.dataclass(kw_only=True)
class HR_CitationPolicy_SkillConfig(_HaikuRAGEvidenceSkillConfig):
    kind: typing.ClassVar[str] = "haiku.rag.skills.citation_policy"
    capability_factory = hr_policy.create_capability
    capability_id = hr_policy.CAPABILITY_ID
    name = "rag-citation-policy"
    description = (
        "Require every answer to register the evidence that grounds it, or "
        "to declare that nothing does."
    )
    state_namespace = hr_policy.STATE_NAMESPACE
    state_type = hr_policy.CitationPolicyState


@dataclasses.dataclass(kw_only=True)
class BwrapSandboxSkillConfig:
    kind: typing.ClassVar[str] = bwrap_sandbox.CAPABILITY_NAME
    source: typing.ClassVar[SkillKind] = SkillKind.NATIVE
    name: typing.ClassVar[str] = bwrap_sandbox.CAPABILITY_NAME
    description: typing.ClassVar[str] = (
        bwrap_sandbox.CAPABILITY_DESCRIPTION.strip()
    )
    state_type: typing.ClassVar[None] = None
    state_namespace: typing.ClassVar[None] = None
    agui_feature_names: typing.ClassVar[tuple[str, ...]] = ()

    _installation_config: config_installation.InstallationConfig = None
    _config_path: pathlib.Path | None = None

    id: str | None = None
    default_environment: str = "bare"
    allowed_environments: bwrap_sandbox.AllowedEnvironments = None
    sandbox_config: bs_config.Config = None
    volumes: bs_models.VolumeMap = _default_dict_field()

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            config_dict.pop("kind", None)
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path
            config_dict["sandbox_config"] = bs_config.Config(
                config_file_path=config_path,
                **config_dict.pop("sandbox_config", {}),
            )
            config_dict["volumes"] = {
                key: bs_models.VolumeInfo(**value)
                for key, value in config_dict.pop("volumes", {}).items()
            }
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "bubble-sandbox",
                config_dict,
            ) from exc

    @property
    def capability(self) -> bwrap_sandbox.SandboxCapability:
        return bwrap_sandbox.create_bwrap_sandbox_capability(
            id=self.id,
            default_environment=self.default_environment,
            allowed_environments=self.allowed_environments,
            sandbox_config=self.sandbox_config,
            volumes=self.volumes,
            installation_config=self._installation_config,
        )

    @property
    def as_yaml(self) -> dict:
        result = {
            "kind": self.kind,
            "default_environment": self.default_environment,
        }
        if self.id is not None:
            result["id"] = self.id
        if self.allowed_environments is not None:
            result["allowed_environments"] = self.allowed_environments
        if self.sandbox_config is not None:
            config = self.sandbox_config
            result["sandbox_config"] = {
                "environments_pathname": config.environments_pathname,
                "execution_timeout_seconds": (
                    config.execution_timeout_seconds
                ),
                "max_output_chars": config.max_output_chars,
            }
        if self.volumes:
            result["volumes"] = {
                key: {
                    "host_path": str(value.host_path),
                    "writable": value.writable,
                }
                for key, value in self.volumes.items()
            }
        return result

    @property
    def extra_parameters(self) -> dict[str, typing.Any]:
        result = {"default_environment": self.default_environment}
        if self.allowed_environments is not None:
            result["allowed_environments"] = self.allowed_environments
        return result


@dataclasses.dataclass(kw_only=True)
class EntrypointCapabilityConfig:
    """A capability from a third-party `soliplex.capabilities` entry point.

    Mounted room-side via `{kind: entrypoint, name: <entry-point>, ...params}`.
    Extra keys are forwarded to the package's `create_capability`.
    """

    kind: typing.ClassVar[str] = "entrypoint"
    source: typing.ClassVar[SkillKind] = SkillKind.ENTRYPOINT

    _installation_config: config_installation.InstallationConfig = None
    _config_path: pathlib.Path | None = None

    name: str
    params: dict[str, typing.Any] = _default_dict_field()

    def __post_init__(self) -> None:
        # Register the capability's typed AG-UI state feature so the room can
        # synthesize default state (like the native-capability loop).
        namespace = self.state_namespace
        if namespace is not None:
            config_agui.AGUI_FEATURES_BY_NAME.setdefault(
                namespace,
                config_agui.AGUI_Feature(
                    name=namespace,
                    model_klass=self.state_type,
                    source=config_agui.AGUI_FeatureSource.SERVER,
                ),
            )

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        params = dict(config_dict)
        params.pop("kind", None)
        name = params.pop("name", None)
        try:
            return cls(
                name=name,
                params=params,
                _installation_config=installation_config,
                _config_path=config_path,
            )
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "entrypoint",
                config_dict,
            ) from exc

    @functools.cached_property
    def _module(self):
        return _load_capability_entry_point(self.name)

    @property
    def capability(self) -> ai_capabilities.AbstractCapability:
        return self._module.create_capability(
            defer_loading=True, **self.params
        )

    @property
    def description(self) -> str:
        return getattr(self._module, "DESCRIPTION", "") or ""

    @property
    def state_namespace(self) -> str | None:
        return getattr(self._module, "STATE_NAMESPACE", None)

    @property
    def state_type(self) -> type[pydantic.BaseModel] | None:
        return getattr(self._module, "STATE_TYPE", None)

    @property
    def agui_feature_names(self) -> tuple[str, ...]:
        namespace = self.state_namespace
        return (namespace,) if namespace is not None else ()

    @property
    def as_yaml(self) -> dict:
        return {"kind": self.kind, "name": self.name, **self.params}

    @property
    def extra_parameters(self) -> dict[str, typing.Any]:
        return dict(self.params)


for feature_name, model in (
    (hr_rag.STATE_NAMESPACE, hr_rag.RAGState),
    (hr_analysis.STATE_NAMESPACE, hr_analysis.AnalysisState),
    (hr_policy.STATE_NAMESPACE, hr_policy.CitationPolicyState),
):
    config_agui.AGUI_FEATURES_BY_NAME[feature_name] = config_agui.AGUI_Feature(
        name=feature_name,
        model_klass=model,
        source=config_agui.AGUI_FeatureSource.SERVER,
    )


SKILL_CONFIG_CLASSES_BY_KIND = {
    klass.kind: klass
    for klass in [
        HR_RAG_SkillConfig,
        HR_Analysis_SkillConfig,
        HR_EvidenceCompaction_SkillConfig,
        HR_CitationPolicy_SkillConfig,
        BwrapSandboxSkillConfig,
        EntrypointCapabilityConfig,
    ]
}

SkillConfigTypes = (
    FilesystemSkillConfig
    | HR_RAG_SkillConfig
    | HR_Analysis_SkillConfig
    | BwrapSandboxSkillConfig
    | EntrypointCapabilityConfig
)
SkillConfigMap = dict[str, SkillConfigTypes]


def extract_skill_configs(
    installation_config: config_installation.InstallationConfig,
    config_path: pathlib.Path,
    config_dict: dict,
) -> SkillConfigMap:
    skill_configs = {}
    for config in config_dict.pop("skill_configs", ()):
        kind = config.get("kind")
        try:
            config_class = SKILL_CONFIG_CLASSES_BY_KIND[kind]
        except KeyError:
            raise InvalidSkillKind(
                invalid_skill_kind=kind,
                available_skill_kinds=SKILL_CONFIG_CLASSES_BY_KIND.keys(),
                _config_path=config_path,
            ) from None
        skill_config = config_class.from_yaml(
            installation_config,
            config_path,
            config,
        )
        skill_configs[skill_config.name] = skill_config
    return skill_configs


@dataclasses.dataclass(kw_only=True)
class RoomSkillsConfig:
    """Select native capabilities for a room."""

    installation_skill_names: list[str] = _default_list_field()
    _skill_configs: SkillConfigMap = _default_dict_field()
    _installation_config: config_installation.InstallationConfig = (
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @staticmethod
    def _check_installation_skills(
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ) -> None:
        requested = set(config_dict.get("installation_skill_names", ()))
        available = set(installation_config.skill_configs)
        if missing := requested - available:
            raise MissingSkillNames(
                _config_path=config_path,
                missing_skill_names=missing,
                available_skill_names=available,
            )

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            cls._check_installation_skills(
                installation_config,
                config_path,
                config_dict,
            )
            config_dict["_skill_configs"] = extract_skill_configs(
                installation_config,
                config_path,
                config_dict,
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
    def as_yaml(self) -> dict:
        result = {}
        if self.installation_skill_names:
            result["installation_skill_names"] = self.installation_skill_names
        if self._skill_configs:
            result["skill_configs"] = [
                config.as_yaml for config in self._skill_configs.values()
            ]
        return result

    @property
    def skill_configs(self) -> SkillConfigMap:
        installation_configs = self._installation_config.skill_configs
        return {
            name: installation_configs[name]
            for name in self.installation_skill_names
        } | self._skill_configs

    @property
    def capabilities(self) -> list[ai_capabilities.AbstractCapability]:
        return [config.capability for config in self.skill_configs.values()]

    @property
    def rag_db_paths(self) -> dict[str, str]:
        paths = {}
        for config in self.skill_configs.values():
            if isinstance(config, _HaikuRAGCapabilityConfig):
                capability = config.capability
                assert capability.id is not None
                paths[capability.id] = str(config.rag_lancedb_path)
        return paths

    @property
    def has_sandbox(self) -> bool:
        return any(
            isinstance(config, BwrapSandboxSkillConfig)
            for config in self.skill_configs.values()
        )
