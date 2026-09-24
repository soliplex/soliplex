from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import pathlib
import re
import typing
import warnings
from collections import abc

from pydantic_ai import capabilities as ai_capabilities
from pydantic_ai import exceptions as ai_exceptions
from pydantic_ai import models as ai_models
from pydantic_ai import settings as ai_settings
from pydantic_ai.agent import abstract as ai_ag_abstract
from pydantic_ai.models import google as google_models
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import google as google_providers
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers
from pydantic_ai.providers import vllm as vllm_providers

from . import _utils
from . import exceptions
from . import interpolation as config_interp

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_default_dict_field = _utils._default_dict_field
_default_list_field = _utils._default_list_field
_env_embedded_field = config_interp.env_embedded_field
_no_interpolation_field = config_interp.no_interpolation_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_secret_whole_field = config_interp.secret_whole_field

HAS_V_NUMBER_SUFFIX = r".*/v\d+"
has_v_number_suffix = re.compile(HAS_V_NUMBER_SUFFIX)


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


class UnknownThinkingLevel(ValueError):
    def __init__(self, name, level, _config_path=None):
        self.name = name
        self.level = level
        self._config_path = _config_path
        super().__init__(
            f"Unknown thinking level in {name!r}: {level!r} "
            f"(configured in {_config_path}); "
            f"one of {list(THINKING_LEVELS)}"
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
    VLLM = "vllm"


#
#   How hard a model is asked to think, lowest first.  These are the
#   levels a client may offer; 'off' is Pydantic AI's 'thinking=False',
#   and the rest are its effort names verbatim.
#
#   The ladder is not universal.  Which rungs a model accepts is decided
#   by its chat template, which is shipped with the weights and is the
#   only authority on the matter:  Qwen3.8 takes 'xhigh', 'medium' and
#   'low' and rejects 'high'; gpt-oss takes 'low', 'medium' and 'high'.
#   A rung the template rejects fails the run, so what a room offers is
#   resolved per model rather than assumed.
#
class ThinkingLevelName(enum.StrEnum):
    OFF = "off"
    MINIMAL = "minimal"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


THINKING_OFF = ThinkingLevelName.OFF
THINKING_LEVELS = tuple(ThinkingLevelName)


THINKING_IN_MODEL_SETTINGS_DEPRECATION = """\
Setting 'thinking' in an agent's 'model_settings' is deprecated, and will
stop being honored in a future release (configured in {config_path}).
Use the 'thinking_default' agent configuration property instead, which a
client can also read and override per run.
"""


def as_thinking_level(level: str | None) -> ai_settings.ThinkingLevel | None:
    """Render one of 'THINKING_LEVELS' as Pydantic AI spells it.

    'off' is 'False' there -- a value, not an absence -- while 'None'
    stays None, meaning nothing is asserted and the model's own default
    applies.
    """
    if level is None:
        return None

    return False if level == THINKING_OFF else level


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
    model_name: str = _env_embedded_field(default=None)
    retries: int = 3

    system_prompt: dataclasses.InitVar[str] = None
    _system_prompt_text: str = _no_interpolation_field(default=None)
    _system_prompt_path: pathlib.Path = None

    provider_type: LLMProviderType = LLMProviderType.OLLAMA
    # installation config provides the default base URL
    provider_base_url: str = _env_embedded_field(default=None)

    # names a secret holding the API key
    provider_key: str = _secret_whole_field(default=None)

    model_settings: ai_settings.ModelSettings = None

    # How hard this agent's model thinks when a run asks for nothing
    # else.  One of 'THINKING_LEVELS', or None to assert nothing and
    # leave the model its own default.
    thinking_default: str = None

    # The levels this model's chat template accepts, for a model whose
    # capability Pydantic AI does not resolve -- a self-hosted one it
    # has no family for, or one it excludes because its ladder does not
    # match the usual names.  Declaring this says the model reasons,
    # and is the complete set a client may offer:  a level absent from
    # it is never sent, including 'off'.  Left unset, the model's
    # resolved profile decides, which is right for every model Pydantic
    # AI knows.
    thinking_levels: list[str] = None

    # The model's context window, in tokens. Pydantic AI already knows
    # it for hosted models; a local or OpenAI-compatible provider does
    # not report one, so a room served that way declares it here or
    # shows no context usage.
    context_window: int = None

    # Declares whether this agent's model accepts image input. Gates whether
    # RAG/analysis capabilities attach picture chunks to search results as
    # images (the capabilities run on this agent's model, not haiku.rag's).
    multimodal: bool = False

    _capability_configs: list[AgentCapabilityConfig] = _default_list_field()

    agui_feature_names: tuple[str] = ()

    # Set by `from_yaml` factory
    _installation_config: config_installation.InstallationConfig = (
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    # Use a config from the top-level InstallationConfig's 'agent_configs'
    # as a template.
    _template_id: str = None

    def __post_init__(self, system_prompt):
        if system_prompt is not None:
            self._system_prompt_text = system_prompt

        # A level nothing accepts fails the run it is sent on, and says
        # nothing about where it came from. Reject it at load instead.
        if self.thinking_default is not None:
            if self.thinking_default not in THINKING_LEVELS:
                raise UnknownThinkingLevel(
                    "thinking_default",
                    self.thinking_default,
                    self._config_path,
                )

        for level in self.thinking_levels or ():
            if level not in THINKING_LEVELS:
                raise UnknownThinkingLevel(
                    "thinking_levels",
                    level,
                    self._config_path,
                )

    @classmethod
    def _check_kind(cls, kind):
        if kind not in (None, cls.kind):
            raise AgentConfigKindMismatch(kind, cls.kind)

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
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
                if "thinking" in pm_settings:
                    warnings.warn(
                        THINKING_IN_MODEL_SETTINGS_DEPRECATION.format(
                            config_path=str(config_path),
                        ),
                        category=DeprecationWarning,
                        stacklevel=2,
                    )
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
            return system_prompt_file.read_text(encoding="utf-8")

        else:  # pragma: NO COVER
            pass

    @property
    def llm_model_name(self) -> str | None:
        return config_interp.resolve_field(self, "model_name")

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
            return config_interp.resolve_field(self, "provider_base_url")

    @property
    def llm_provider_kw(self) -> dict:
        provider_kw = {}
        base_url = self.llm_provider_base_url

        if base_url is not None:
            if not has_v_number_suffix.fullmatch(base_url):
                base_url = f"{base_url}/v1"

            provider_kw["base_url"] = base_url

        if self.provider_key is not None:
            provider_kw["api_key"] = config_interp.resolve_field(
                self, "provider_key"
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
            "model_name": self.model_name,  # not interpolated
            "retries": self.retries,
            "system_prompt": prompt,
            "model_settings": self.model_settings,
            "thinking_default": self.thinking_default,
            "thinking_levels": self.thinking_levels,
            "context_window": self.context_window,
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
    _installation_config: config_installation.InstallationConfig = (
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
        installation_config: config_installation.InstallationConfig,
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
            "agui_feature_names": self.agui_feature_names,
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
    installation_config: config_installation.InstallationConfig,
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


def _profile_kw(agent_config: AgentConfig, *, openai_compat: bool) -> dict:
    """Return the 'profile=' keyword for the model, or nothing.

    A partial profile is merged over Pydantic AI's own, so only what the
    configuration actually says is passed. 'context_window' left unset
    lets Pydantic AI fill it for a model it knows; set, it overrides.
    """
    profile = dict(_OPENAI_COMPAT_PROFILE) if openai_compat else {}

    if agent_config.context_window is not None:
        profile["context_window"] = agent_config.context_window

    if agent_config.thinking_levels:
        # Declaring the levels says the model reasons, and that has to
        # reach the profile to mean anything:  Pydantic AI discards a
        # thinking setting for a model whose profile does not claim
        # support, without an error, so a declaration that stopped at
        # the configuration would change nothing at all.
        profile["supports_thinking"] = True

    return {"profile": profile} if profile else {}


def get_context_window_from_config(
    *,
    agent_config: AgentConfig,
) -> int | None:
    """Return the model's context window, or None when nothing knows it.

    A declared window is the answer without building anything. Otherwise
    it is what the model's profile resolves -- pydantic-ai fills it for
    hosted models it recognises, and leaves it unset for a local one.

    None also covers a configuration the model cannot be built from: an
    agent template with no model name, or a provider whose key is not
    set. Both fail loudly the moment a run starts; listing the room is
    not that moment.
    """
    if agent_config.context_window is not None:
        return agent_config.context_window

    if agent_config.llm_model_name is None:
        return None

    try:
        model = get_model_from_config(agent_config=agent_config)
    except ai_exceptions.UserError:
        return None

    return model.context_window


@dataclasses.dataclass(frozen=True, kw_only=True)
class ThinkingSupport:
    """What a room may offer for how hard its model thinks."""

    levels: tuple[str, ...]
    """Offerable levels, lowest first; a subset of 'THINKING_LEVELS'.

    The complete set:  a level absent from it is one this model is not
    known to accept, and is never sent.  'off' is absent for a model
    that cannot stop reasoning.
    """

    default: str | None
    """What the room asks for when a run asks for nothing."""


def get_thinking_from_config(
    *,
    agent_config: AgentConfig,
) -> ThinkingSupport | None:
    """Return what this agent's model offers, or None for no control.

    None covers three cases that all mean the same thing to a client:
    a model that does not reason, one nothing can resolve a capability
    for, and a configuration no model can be built from.  In each, a
    level would be discarded on the way to the wire, so offering one
    would promise something that does not happen.

    A declared 'thinking_levels' answers without building anything:  it
    exists precisely for the models this resolution cannot serve.
    """
    if agent_config.thinking_levels:
        return ThinkingSupport(
            levels=tuple(agent_config.thinking_levels),
            default=agent_config.thinking_default,
        )

    if agent_config.llm_model_name is None:
        return None

    try:
        model = get_model_from_config(agent_config=agent_config)
    except ai_exceptions.UserError:
        return None

    profile = model.profile
    always_enabled = bool(profile.get("thinking_always_enabled", False))

    if not (profile.get("supports_thinking", False) or always_enabled):
        return None

    # 'minimal' is not a rung everywhere:  where it is missing Pydantic
    # AI quietly sends 'low' instead, so offering it would be a control
    # that does nothing.
    has_minimal = profile.get("openai_supports_minimal_reasoning_effort", True)

    levels = tuple(
        level
        for level in THINKING_LEVELS
        if not (level == THINKING_OFF and always_enabled)
        and not (level == "minimal" and not has_minimal)
    )

    return ThinkingSupport(
        levels=levels,
        default=agent_config.thinking_default,
    )


def get_model_from_config(
    *,
    agent_config: AgentConfig,
) -> ai_models.Model:
    provider_kw = agent_config.llm_provider_kw

    model_settings_kw = {}
    model_name = agent_config.llm_model_name

    if agent_config.model_settings:
        model_settings_kw["settings"] = ai_settings.ModelSettings(
            **agent_config.model_settings,
        )

    if agent_config.provider_type == LLMProviderType.GOOGLE:
        provider = google_providers.GoogleProvider(**provider_kw)
        return google_models.GoogleModel(
            model_name=model_name,
            provider=provider,
            **_profile_kw(agent_config, openai_compat=False),
            **model_settings_kw,
        )

    elif agent_config.provider_type == LLMProviderType.OLLAMA:
        provider = ollama_providers.OllamaProvider(
            **(provider_kw | {"api_key": "dummy"}),
        )
        return openai_models.OpenAIChatModel(
            model_name=model_name,
            provider=provider,
            **_profile_kw(agent_config, openai_compat=True),
            **model_settings_kw,
        )

    elif agent_config.provider_type == LLMProviderType.VLLM:
        provider = vllm_providers.VLLMProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=model_name,
            provider=provider,
            # No '_OPENAI_COMPAT_PROFILE' here: the vLLM provider's own
            # profile already sets that flag, and resolves the model
            # family from the served name -- which is the whole reason
            # to prefer it over 'openai' with a base URL.
            **_profile_kw(agent_config, openai_compat=False),
            **model_settings_kw,
        )

    else:
        provider = openai_providers.OpenAIProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=model_name,
            provider=provider,
            **_profile_kw(
                agent_config,
                openai_compat=bool(provider_kw.get("base_url")),
            ),
            **model_settings_kw,
        )
