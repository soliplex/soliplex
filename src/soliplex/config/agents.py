from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import pathlib
import typing
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
        if _config_path is not None:
            super().__init__(
                f"Unknown capability name: {name} "
                f"(configured in {_config_path})"
            )
        else:
            super().__init__(f"Unknown capability name: {name}")


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

        config_dict = (
            template_config.as_yaml
            | config_dict
            | {"_template_id": template_id}
        )

    return config_dict


@dataclasses.dataclass(kw_only=True)
class AgentCapabilityConfig:
    name: str
    kwargs: dict[str, typing.Any] = _default_dict_field()

    _config_path: pathlib.Path = None

    @property
    def as_capability(self) -> ai_capabilities.AbstractCapability:
        try:
            cap_klass = AGENT_CAPABILITY_CLASSES_BY_NAME[self.name]
        except KeyError:
            raise UnknownCapability(self.name) from None

        return cap_klass(**self.kwargs)


def extract_capability_config(
    cap_config: str | dict[str, typing.Any],
    _config_path: pathlib.Path,
) -> AgentCapabilityConfig:
    if isinstance(cap_config, str):
        name = cap_config
        kwargs = {}
    else:
        ((name, kwargs),) = cap_config.items()

    if name not in AGENT_CAPABILITY_CLASSES_BY_NAME:
        raise UnknownCapability(name, _config_path)

    return AgentCapabilityConfig(
        name=name,
        kwargs=kwargs,
        _config_path=_config_path,
    )


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
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
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
                    extract_capability_config(cap, config_path)
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
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
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
    agent_kind = config_dict.get("kind")

    if agent_kind is not None:  # kind is a typing.ClassVar
        config_dict = {
            key: value for key, value in config_dict.items() if key != "kind"
        }

    ac_class = AGENT_CONFIG_CLASSES_BY_KIND.get(agent_kind, AgentConfig)

    return ac_class.from_yaml(
        installation_config,
        config_path,
        config_dict,
    )


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
            **model_settings_kw,
        )

    else:
        provider = openai_providers.OpenAIProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=agent_config.model_name,
            provider=provider,
            **model_settings_kw,
        )
