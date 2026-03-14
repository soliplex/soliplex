from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import pathlib
import typing
from collections import abc

from pydantic_ai import settings as ai_settings
from pydantic_ai.agent import abstract as ai_ag_abstract

from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils
from . import exceptions

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_dict_field = _utils._default_dict_field

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

            if "system_prompt" in config_dict:
                system_prompt = config_dict.pop("system_prompt")

                if system_prompt.startswith("./"):
                    config_dict["_system_prompt_path"] = system_prompt
                else:
                    config_dict["system_prompt"] = system_prompt

            if config_dict.get("model_settings") is not None:
                pm_settings = config_dict.pop("model_settings")
                config_dict["model_settings"] = ai_settings.ModelSettings(
                    **pm_settings
                )

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
