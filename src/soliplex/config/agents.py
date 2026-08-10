from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import pathlib
import typing
import warnings
from collections import abc

from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import models as ai_models
from pydantic_ai import settings as ai_settings
from pydantic_ai.agent import abstract as ai_ag_abstract
from pydantic_ai.models import google as google_models
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import google as google_providers
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers

from . import _utils
from . import exceptions

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_dict_field = _utils._default_dict_field
_default_list_field = _utils._default_list_field


#
#   Copy the pydantic_ai capability registry as defaults, so that we
#   can extend via meta-config.
#
AGENT_CAPABILITY_CLASSES_BY_NAME = ai_capabilities.CAPABILITY_TYPES.copy()

# ============================================================================
#   Agent-related configuration types
# ============================================================================


class InvalidAgentTemplateID(KeyError):
    def __init__(self, template_id, _config_path):
        self.template_id = template_id
        self._config_path = _config_path
        super().__init__(
            f"Template agent not found: {template_id} "
            f"(configured in {_config_path})"
        )


class UnknownCapability(KeyError):
    def __init__(self, name, _config_path=None):
        self.name = name
        self._config_path = _config_path

        super().__init__(
            f"Unknown capability name: {name} (configured in {_config_path})"
        )


class UnknownAgentConfigKind(KeyError):
    def __init__(self, kind, _config_path=None):
        self.kind = kind
        self._config_path = _config_path
        super().__init__(
            f"Unknown agent config kind: {kind} (configured in {_config_path})"
        )


class AgentConfigKindMismatch(ValueError):
    def __init__(self, found_kind, expected_kind):
        self.found_kind = found_kind
        self.expected_kind = expected_kind
        super().__init__(
            "Agent config kind mismatch: "
            f"found '{found_kind}', expected '{expected_kind}'"
        )


class LLMProviderType(enum.StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    GOOGLE = "google"


def _apply_agent_config_template(
    config_dict,
    installation_config,
    config_path,
):
    template_id = config_dict.pop("template_id", None)

    if template_id is not None:
        # Cannot use 'agent_configs_map' because we might still be
        # initalizing the IC.
        ic_agent_configs_map = {
            agent_config.id: agent_config
            for agent_config in installation_config.agent_configs
        }

        if template_id not in ic_agent_configs_map:
            raise InvalidAgentTemplateID(template_id, config_path)

        template_config = ic_agent_configs_map[template_id]
        tc_yaml_no_kind = {
            key: value
            for key, value in template_config.as_yaml.items()
            if key != "kind"
        }

        config_dict = (
            tc_yaml_no_kind | config_dict | {"_template_id": template_id}
        )

    return config_dict


ACC_BBB_NO_NAME_KEY_DEPRECATED = """\
AgentCapabilityConfig.from_yaml: '{<name>: <kwargs>}' form is deprecated;
use '{"name": <name>, "kwargs": <kwargs>}' instead.
"""


@dataclasses.dataclass(kw_only=True)
class AgentCapabilityConfig:
    name: str
    kwargs: dict[str, typing.Any] = _default_dict_field()

    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict_or_str: str | dict,
    ):
        if isinstance(config_dict_or_str, str):
            name = config_dict_or_str
            config_dict = {"name": name}
        else:
            if "name" not in config_dict_or_str:  # BBB deprecated
                warnings.warn(
                    ACC_BBB_NO_NAME_KEY_DEPRECATED,
                    DeprecationWarning,
                    stacklevel=2,
                )
                ((name, kwargs),) = config_dict_or_str.items()
                config_dict = {"name": name, "kwargs": kwargs}
            else:
                name = config_dict_or_str["name"]
                config_dict = config_dict_or_str

        if name not in AGENT_CAPABILITY_CLASSES_BY_NAME:
            raise UnknownCapability(name, config_path)

        return cls(**config_dict, _config_path=config_path)

    @property
    def as_yaml(self) -> dict:
        return {"name": self.name, "kwargs": self.kwargs}

    @property
    def as_capability(self) -> ai_capabilities.AbstractCapability:
        try:
            cap_klass = AGENT_CAPABILITY_CLASSES_BY_NAME[self.name]
        except KeyError:
            raise UnknownCapability(self.name, self._config_path) from None

        return cap_klass(**self.kwargs)


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

    # Declares whether this agent's model accepts image input. Gates whether
    # RAG/analysis capabilities attach picture chunks to search results as
    # images (the capabilities run on this agent's model, not haiku.rag's).
    multimodal: bool = False

    _capability_configs: list[AgentCapabilityConfig] = _default_list_field()

    agui_feature_names: tuple[str] = ()

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    # Use a config from the top-level InstallationConfig's 'agent_configs'
    # as a template.
    _template_id: str = None

    def __post_init__(self, system_prompt):
        if system_prompt is not None:
            self._system_prompt_text = system_prompt

    @classmethod
    def _check_kind(cls, kind):
        if kind not in (None, cls.kind):
            raise AgentConfigKindMismatch(kind, cls.kind)

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            kind = config_dict.pop("kind", None)
            cls._check_kind(kind)

            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            config_dict = _apply_agent_config_template(
                config_dict,
                installation_config,
                config_path,
            )

            system_prompt = config_dict.pop("system_prompt", None)
            if system_prompt is not None:
                if system_prompt.startswith("./"):
                    config_dict["_system_prompt_path"] = system_prompt
                else:
                    config_dict["system_prompt"] = system_prompt

            pm_settings = config_dict.pop("model_settings", None)
            if pm_settings is not None:
                config_dict["model_settings"] = ai_settings.ModelSettings(
                    **pm_settings
                )

            capabilities = config_dict.pop("capabilities", None)
            if capabilities is not None:
                config_dict["_capability_configs"] = [
                    AgentCapabilityConfig.from_yaml(config_path, cap)
                    for cap in capabilities
                ]

            agui_feature_names = config_dict.pop("agui_feature_names", ())
            config_dict["agui_feature_names"] = tuple(agui_feature_names)

            return cls(**config_dict)
        except Exception as exc:
            raise exceptions.FromYamlException(
                config_path,
                "agent",
                config_dict,
            ) from exc

    def get_system_prompt(self) -> str | None:
        if self._system_prompt_text is not None:
            return self._system_prompt_text

        if self._system_prompt_path is not None:
            if self._config_path is None:
                raise exceptions.NoConfigPath()

            system_prompt_file = (
                self._config_path.parent / self._system_prompt_path
            )
            return system_prompt_file.read_text()

        else:  # pragma: NO COVER
            pass

    @property
    def llm_provider_base_url(self) -> str | None:
        ic = self._installation_config

        if ic is None:
            return self.provider_base_url

        if (
            self.provider_type == LLMProviderType.OLLAMA
            and self.provider_base_url is None
        ):
            return ic.get_environment("OLLAMA_BASE_URL")
        else:
            return ic.interpolate_environment(self.provider_base_url)

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
    def capabilities(self) -> list[ai_capabilities.AbstractCapability]:
        return [acc.as_capability for acc in self._capability_configs]

    @property
    def as_yaml(self) -> dict:
        prompt = (
            self._system_prompt_path
            if self._system_prompt_text is None
            else self._system_prompt_text
        )
        capabilities = {}

        for cap_cfg in self._capability_configs:
            cap_list = capabilities.setdefault("capabilities", [])
            cap_list.append(cap_cfg.as_yaml)

        return {
            "id": self.id,
            "kind": self.kind,
            "model_name": self.model_name,
            "retries": self.retries,
            "system_prompt": prompt,
            "model_settings": self.model_settings,
            "multimodal": self.multimodal,
            "provider_type": str(self.provider_type),
            "provider_base_url": self.provider_base_url,
            "provider_key": self.provider_key,  # "secret:SECRET_NAME"
            "agui_feature_names": self.agui_feature_names,
        } | capabilities


AgentFactory = abc.Callable[[], ai_ag_abstract.AbstractAgent]


@dataclasses.dataclass(kw_only=True)
class FactoryAgentConfig:
    id: str
    factory_name: _utils.DottedName
    kind: typing.ClassVar[str] = "factory"
    with_agent_config: bool = False
    extra_config: dict[str, typing.Any] = _default_dict_field()

    agui_feature_names: tuple[str] = ()

    _factory: AgentFactory = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    # Use a config from the top-level InstallationConfig's 'agent_configs'
    # as a template.
    _template_id: str = None

    @property
    def factory(self) -> AgentFactory:
        if self._factory is None:
            factory = _utils._from_dotted_name(self.factory_name)

            if self.with_agent_config:
                self._factory = functools.update_wrapper(
                    functools.partial(factory, agent_config=self),
                    factory,
                )
            else:
                self._factory = factory

        return self._factory

    @classmethod
    def _check_kind(cls, kind):
        if kind not in (None, cls.kind):
            raise AgentConfigKindMismatch(kind, cls.kind)

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            kind = config_dict.pop("kind", None)
            cls._check_kind(kind)

            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            config_dict = _apply_agent_config_template(
                config_dict,
                installation_config,
                config_path,
            )

            agui_feature_names = config_dict.pop("agui_feature_names", ())
            config_dict["agui_feature_names"] = tuple(agui_feature_names)

            return cls(**config_dict)

        except Exception as exc:
            raise exceptions.FromYamlException(
                config_path,
                "python_agent",
                config_dict,
            ) from exc

    @property
    def as_yaml(self) -> dict:
        return {
            "kind": self.kind,
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

AgentConfigTypes = AgentConfig | FactoryAgentConfig

AgentConfigMap = dict[str, AgentConfigTypes]


def extract_agent_config(
    installation_config: InstallationConfig,  # noqa F821 cycle
    config_path: pathlib.Path,
    config_dict: dict,
) -> AgentConfig:  # or subclass

    # YAML not required to specify 'kind'
    agent_kind = config_dict.get("kind", AgentConfig.kind)

    try:
        ac_class = AGENT_CONFIG_CLASSES_BY_KIND[agent_kind]
    except KeyError:
        raise UnknownAgentConfigKind(
            agent_kind,
            config_path,
        ) from None

    return ac_class.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )


# Strict OpenAI-compatible backends (some vLLM chat templates, e.g. Qwen's)
# reject more than one leading system message. The agent prompt and each
# capability's instructions map to one system message apiece, so have
# pydantic-ai merge them for any endpoint that is not api.openai.com.
_OPENAI_COMPAT_PROFILE = {
    "openai_chat_supports_multiple_system_messages": False,
}


def get_model_from_config(
    *,
    agent_config: AgentConfig,
) -> ai_models.Model:
    provider_kw = agent_config.llm_provider_kw

    model_settings_kw = {}

    if agent_config.model_settings:
        model_settings_kw["settings"] = ai_settings.ModelSettings(
            **agent_config.model_settings,
        )

    if agent_config.provider_type == LLMProviderType.GOOGLE:
        provider = google_providers.GoogleProvider(**provider_kw)
        return google_models.GoogleModel(
            model_name=agent_config.model_name,
            provider=provider,
            **model_settings_kw,
        )

    elif agent_config.provider_type == LLMProviderType.OLLAMA:
        provider_kw["api_key"] = "dummy"
        provider = ollama_providers.OllamaProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=agent_config.model_name,
            provider=provider,
            profile=_OPENAI_COMPAT_PROFILE,
            **model_settings_kw,
        )

    else:
        profile_kw = (
            {"profile": _OPENAI_COMPAT_PROFILE}
            if provider_kw.get("base_url")
            else {}
        )
        provider = openai_providers.OpenAIProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=agent_config.model_name,
            provider=provider,
            **profile_kw,
            **model_settings_kw,
        )
