import contextlib
import copy
import dataclasses
import functools
import pathlib
import typing
from unittest import mock

import pytest
import yaml
from pydantic_ai import settings as ai_settings

from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc
from soliplex.config import installation as config_installation

AGENT_ID = "testing-agent"
TEMPLATE_AGENT_ID = "testing-template"
BOGUS_TEMPLATE_AGENT_ID = "BOGUS"
SYSTEM_PROMPT = "You are a test"
MODEL_NAME = "test-model"
OTHER_MODEL_NAME = "test-model-other"
PROVIDER_BASE_URL = "https://provider.example.com/api"
OTHER_PROVIDER_BASE_URL = "https://other-provider.example.com/api"
OLLAMA_BASE_URL = "https://example.com:12345"
AGUI_FEATURE_NAME = "test-agui-feature"


BOGUS_AGENT_CONFIG_YAML = ""

W_KIND_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    kind="testing",
)

BARE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    system_prompt=SYSTEM_PROMPT,
)
BARE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: "{SYSTEM_PROMPT}"
"""

W_PROVIDER_KW_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    provider_type=config_agents.LLMProviderType.OPENAI,
    provider_base_url=OTHER_PROVIDER_BASE_URL,
    provider_key="secret:OTHER_PROVIDER_KEY",
)
W_PROVIDER_KW_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
provider_type: "openai"
provider_base_url: "{OTHER_PROVIDER_BASE_URL}"
provider_key: "secret:OTHER_PROVIDER_KEY"
"""

AGENT_RETRIES = 7
W_RETRIES_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    retries=AGENT_RETRIES,
)
W_RETRIES_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
retries: {AGENT_RETRIES}
"""

MODEL_SETTING_MAX_TOKENS = 1000
MODEL_SETTING_TEMPERATURE = 0.90
MODEL_SETTING_TOP_P = 0.70
MODEL_SETTING_TIMEOUT = 60
MODEL_SETTING_PARALLELL_TOOL_CALLS = True
MODEL_SETTING_SEED = 1234
MODEL_SETTING_FREQUENCY_PENALTY = 0.31
MODEL_SETTING_PRESENCE_PENALTY = 0.21
MODEL_SETTING_LOGIT_BIAS = {"waaa": 14}
MODEL_SETTING_STOP_SEQUENCE = "STOP"
MODEL_SETTING_EXTRA_HEADER_NAME = "test-header"
MODEL_SETTING_EXTRA_HEADER_VALUE = "test-header-value"
MODEL_SETTING_EXTRA_BODY_NAME = "test-body"
MODEL_SETTING_EXTRA_BODY_VALUE = "test-body-value"

W_MODEL_SETTINGS_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    provider_type="ollama",
    model_settings=ai_settings.ModelSettings(
        max_tokens=MODEL_SETTING_MAX_TOKENS,
        temperature=MODEL_SETTING_TEMPERATURE,
        top_p=MODEL_SETTING_TOP_P,
        timeout=MODEL_SETTING_TIMEOUT,
        parallel_tool_calls=MODEL_SETTING_PARALLELL_TOOL_CALLS,
        seed=MODEL_SETTING_SEED,
        frequency_penalty=MODEL_SETTING_FREQUENCY_PENALTY,
        presence_penalty=MODEL_SETTING_PRESENCE_PENALTY,
        logit_bias=MODEL_SETTING_LOGIT_BIAS,
        stop_sequences=[MODEL_SETTING_STOP_SEQUENCE],
        extra_headers={
            MODEL_SETTING_EXTRA_HEADER_NAME: MODEL_SETTING_EXTRA_HEADER_VALUE,
        },
        extra_body={
            MODEL_SETTING_EXTRA_BODY_NAME: MODEL_SETTING_EXTRA_BODY_VALUE,
        },
    ),
)
W_MODEL_SETTINGS_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
model_settings:
    max_tokens: {MODEL_SETTING_MAX_TOKENS}
    temperature: {MODEL_SETTING_TEMPERATURE}
    top_p: {MODEL_SETTING_TOP_P}
    timeout: {MODEL_SETTING_TIMEOUT}
    parallel_tool_calls: {str(MODEL_SETTING_PARALLELL_TOOL_CALLS).lower()}
    seed: {MODEL_SETTING_SEED}
    frequency_penalty: {MODEL_SETTING_FREQUENCY_PENALTY}
    presence_penalty: {MODEL_SETTING_PRESENCE_PENALTY}
    logit_bias: {MODEL_SETTING_LOGIT_BIAS}
    stop_sequences:
        - {MODEL_SETTING_STOP_SEQUENCE}
    extra_headers:
        {MODEL_SETTING_EXTRA_HEADER_NAME}: {MODEL_SETTING_EXTRA_HEADER_VALUE}
    extra_body:
        {MODEL_SETTING_EXTRA_BODY_NAME}: {MODEL_SETTING_EXTRA_BODY_VALUE}
"""


W_PROMPT_FILE_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    _system_prompt_path="./prompt.txt",
)
W_PROMPT_FILE_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: ./prompt.txt
"""

# 'model_name' not required heree:  supplied by template
W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=TEMPLATE_AGENT_ID,
    _system_prompt_path="./prompt.txt",
)
W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{TEMPLATE_AGENT_ID}"
system_prompt: ./prompt.txt
"""

W_PROMPT_FILE_W_BOGUS_TEMPLATE_ID_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{BOGUS_TEMPLATE_AGENT_ID}"
system_prompt: ./prompt.txt
"""

W_AGUI_FEATURE_NAMES_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    model_name=MODEL_NAME,
    system_prompt=SYSTEM_PROMPT,
    agui_feature_names=(AGUI_FEATURE_NAME,),
)
W_AGUI_FEATURE_NAMES_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
model_name: "{MODEL_NAME}"
system_prompt: "{SYSTEM_PROMPT}"
agui_feature_names:
  - "{AGUI_FEATURE_NAME}"
"""

FACTORY_NAME = "soliplex.config.agents.test_factory_wo_config"
WO_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=False,
)
WO_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: false
"""

W_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=True,
    extra_config={
        "foo": "Bar",
    },
)
W_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: true
extra_config:
  foo: "Bar"
"""

W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    factory_name=FACTORY_NAME,
    with_agent_config=False,
    agui_feature_names=(AGUI_FEATURE_NAME,),
)
W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
factory_name: "{FACTORY_NAME}"
with_agent_config: false
agui_feature_names:
  - "{AGUI_FEATURE_NAME}"
"""

W_BOGUS_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{BOGUS_TEMPLATE_AGENT_ID}"
"""

W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=TEMPLATE_AGENT_ID,
)
W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{TEMPLATE_AGENT_ID}"
"""

W_EXTRA_CONFIG_TEMPLATE_AGENT_ID = "testing-template-w-extra-config"
W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_KW = dict(
    id=AGENT_ID,
    _template_id=W_EXTRA_CONFIG_TEMPLATE_AGENT_ID,
    extra_config={
        "foo": "Bar",
    },
)
W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_YAML = f"""
id: "{AGENT_ID}"
template_id: "{W_EXTRA_CONFIG_TEMPLATE_AGENT_ID}"
extra_config:
  foo: "Bar"
"""


@pytest.mark.parametrize(
    "config_dict, expected",
    [
        ({}, {}),
        ({"template_id": BOGUS_TEMPLATE_AGENT_ID}, None),
        ({"other": "OTHER"}, {"other": "OTHER"}),
        (
            {"template_id": TEMPLATE_AGENT_ID, "other": "OTHER"},
            {
                "other": "OTHER",
                "key": "from_template",
                "_template_id": TEMPLATE_AGENT_ID,
            },
        ),
        (
            {"template_id": TEMPLATE_AGENT_ID, "key": "from_local"},
            {"key": "from_local", "_template_id": TEMPLATE_AGENT_ID},
        ),
        (
            {
                "template_id": TEMPLATE_AGENT_ID,
                "key": "from_local",
                "other": "OTHER",
            },
            {
                "other": "OTHER",
                "key": "from_local",
                "_template_id": TEMPLATE_AGENT_ID,
            },
        ),
    ],
)
def test__apply_agent_config_template(temp_dir, config_dict, expected):
    template_ac = mock.Mock(spec_set=["id", "as_yaml"])
    template_ac.id = TEMPLATE_AGENT_ID
    template_ac.as_yaml = {"key": "from_template"}
    i_config = mock.create_autospec(config_installation.InstallationConfig)
    i_config.agent_configs = [template_ac]
    config_path = temp_dir / "test.yaml"

    if expected is None:
        with pytest.raises(config_agents.InvalidAgentTemplateID):
            config_agents._apply_agent_config_template(
                config_dict,
                i_config,
                config_path,
            )

    else:
        found = config_agents._apply_agent_config_template(
            config_dict,
            i_config,
            config_path,
        )

        assert found == expected


@pytest.mark.parametrize(
    "kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_ctor(installation_config, kw):
    kw["_installation_config"] = installation_config

    found = config_agents.AgentConfig(**kw)

    assert found.model_name == kw["model_name"]


@pytest.mark.parametrize(
    "config_yaml, expectation",
    [
        (
            BOGUS_AGENT_CONFIG_YAML,
            pytest.raises(config_exc.FromYamlException),
        ),
        (
            BARE_AGENT_CONFIG_YAML,
            contextlib.nullcontext(BARE_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROVIDER_KW_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_PROVIDER_KW_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_RETRIES_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_RETRIES_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_MODEL_SETTINGS_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_MODEL_SETTINGS_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROMPT_FILE_AGENT_CONFIG_YAML,
            contextlib.nullcontext(W_PROMPT_FILE_AGENT_CONFIG_KW.copy()),
        ),
        (
            W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_YAML,
            contextlib.nullcontext(
                W_PROMPT_FILE_W_TEMPLATE_ID_AGENT_CONFIG_KW.copy()
            ),
        ),
        (
            W_PROMPT_FILE_W_BOGUS_TEMPLATE_ID_AGENT_CONFIG_YAML,
            pytest.raises(config_exc.FromYamlException),
        ),
        (
            W_AGUI_FEATURE_NAMES_AGENT_CONFIG_YAML,
            contextlib.nullcontext(
                W_AGUI_FEATURE_NAMES_AGENT_CONFIG_KW.copy()
            ),
        ),
    ],
)
def test_agentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expectation,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if config_dict is not None:
        template_id = config_dict.get("template_id")
    else:
        template_id = None

    if template_id not in (None, BOGUS_TEMPLATE_AGENT_ID):
        template_kw = {
            "model_name": OTHER_MODEL_NAME,
            "provider_base_url": OTHER_PROVIDER_BASE_URL,
        }
        installation_config.agent_configs = [
            config_agents.AgentConfig(id=template_id, **template_kw),
        ]
    else:
        template_kw = {}
        installation_config.agent_configs = []

    with expectation as expected:
        found = config_agents.AgentConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

    if isinstance(expected, dict):
        exp_agent_config = config_agents.AgentConfig(
            _installation_config=installation_config,
            _config_path=yaml_file,
            **(template_kw | expected),
        )

        assert found == exp_agent_config

        # See #180.
        assert found._installation_config is installation_config


@pytest.mark.parametrize("w_config_path", [False, True])
@pytest.mark.parametrize(
    "agent_config_kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
        W_MODEL_SETTINGS_AGENT_CONFIG_KW.copy(),
        W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_get_system_prompt(
    temp_dir,
    agent_config_kw,
    w_config_path,
):
    agent_config_kw = agent_config_kw.copy()

    if w_config_path:
        config_path = temp_dir / "prompt.txt"
        config_path.write_text(SYSTEM_PROMPT)

        agent_config_kw["_config_path"] = config_path

    agent_config = config_agents.AgentConfig(**agent_config_kw)

    if agent_config._system_prompt_text is not None:
        found = agent_config.get_system_prompt()
        assert found == agent_config._system_prompt_text
        return

    if agent_config._config_path:
        if agent_config._system_prompt_path is not None:
            expected = SYSTEM_PROMPT
        else:
            expected = None

        assert agent_config.get_system_prompt() == expected

    else:
        if agent_config._system_prompt_path is not None:
            with pytest.raises(config_exc.NoConfigPath):
                agent_config.get_system_prompt()

        else:
            assert agent_config.get_system_prompt() is None


@pytest.mark.parametrize(
    "provider_type, kw, expected",
    [
        (config_agents.LLMProviderType.OLLAMA, {}, OLLAMA_BASE_URL),
        (
            config_agents.LLMProviderType.OLLAMA,
            {"provider_base_url": PROVIDER_BASE_URL},
            PROVIDER_BASE_URL,
        ),
        (config_agents.LLMProviderType.OPENAI, {}, None),
        (
            config_agents.LLMProviderType.OPENAI,
            {"provider_base_url": PROVIDER_BASE_URL},
            PROVIDER_BASE_URL,
        ),
        (config_agents.LLMProviderType.GOOGLE, {}, None),
    ],
)
def test_agentconfig_llm_provider_base_url(
    installation_config,
    provider_type,
    kw,
    expected,
):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=provider_type,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_base_url

    assert found == expected


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_ollama_w_default_base_url(
    installation_config,
    has_pk,
):
    ic_environ = {"OLLAMA_BASE_URL": OLLAMA_BASE_URL}
    installation_config.get_environment = ic_environ.get

    kw = {}
    expected = {
        "base_url": f"{OLLAMA_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config_agents.LLMProviderType.OLLAMA,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_ollama_w_explicit_base_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {
        "base_url": f"{PROVIDER_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config_agents.LLMProviderType.OLLAMA,
        provider_base_url=PROVIDER_BASE_URL,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_openai_wo_provider_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {}

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config_agents.LLMProviderType.OPENAI,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_openai_w_provider_url(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {
        "base_url": f"{PROVIDER_BASE_URL}/v1",
    }

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config_agents.LLMProviderType.OPENAI,
        provider_base_url=PROVIDER_BASE_URL,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize("has_pk", [False, True])
def test_agentconfig_llm_provider_kw_google(
    installation_config,
    has_pk,
):
    kw = {}
    expected = {}

    if has_pk:
        kw["provider_key"] = "secret:SECRET_NAME"
        expected["api_key"] = installation_config.get_secret.return_value

    aconfig = config_agents.AgentConfig(
        id="test-agent",
        system_prompt="You are a test",
        provider_type=config_agents.LLMProviderType.GOOGLE,
        _installation_config=installation_config,
        **kw,
    )

    found = aconfig.llm_provider_kw

    assert found == expected

    if has_pk:
        installation_config.get_secret.assert_called_once_with(
            "secret:SECRET_NAME"
        )
    else:
        installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize(
    "agent_config_kw",
    [
        BARE_AGENT_CONFIG_KW.copy(),
        W_PROVIDER_KW_AGENT_CONFIG_KW.copy(),
        W_RETRIES_AGENT_CONFIG_KW.copy(),
        W_PROMPT_FILE_AGENT_CONFIG_KW.copy(),
    ],
)
def test_agentconfig_as_yaml(
    installation_config,
    agent_config_kw,
):
    agent_config_kw = copy.deepcopy(agent_config_kw)

    ic_environ = {
        "OLLAMA_BASE_URL": OLLAMA_BASE_URL,
    }
    installation_config.get_environment = ic_environ.get
    agent_config_kw["_installation_config"] = installation_config

    system_prompt = (
        agent_config_kw.get("system_prompt")
        or agent_config_kw.get("_system_prompt_text")
        or agent_config_kw.get("_system_prompt_path")
    )
    model_name = agent_config_kw.get("model_name") or MODEL_NAME
    model_settings = agent_config_kw.get("model_settings")
    expected = {
        "id": AGENT_ID,
        "system_prompt": system_prompt,
        "model_name": model_name,
        "model_settings": model_settings,
        "retries": agent_config_kw.get("retries", 3),
        "provider_type": agent_config_kw.get("provider_type", "ollama"),
    }

    expected["provider_base_url"] = agent_config_kw.get(
        "provider_base_url",
        OLLAMA_BASE_URL,
    )

    expected["provider_key"] = agent_config_kw.get("provider_key")

    aconfig = config_agents.AgentConfig(**agent_config_kw)

    found = aconfig.as_yaml

    assert found == expected

    installation_config.get_secret.assert_not_called()


@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_ctor(kw):
    found = config_agents.FactoryAgentConfig(**kw)

    assert found.id == AGENT_ID
    assert found.factory_name == kw["factory_name"]
    assert found.with_agent_config == kw["with_agent_config"]
    assert found.extra_config == kw.get("extra_config", {})


@pytest.mark.parametrize("w_existing", [False, True])
@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_factory(kw, w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_factory(ctx, agent_config=None):
        "This is a test"

    pyagent_config = config_agents.FactoryAgentConfig(**kw)

    if w_existing:
        pyagent_config._factory = existing

    _, factory_name = kw["factory_name"].rsplit(".", 1)
    patch = {factory_name: test_factory}

    with mock.patch.dict("soliplex.config.agents.__dict__", **patch):
        found = pyagent_config.factory

    if w_existing:
        assert found is existing

    else:
        if kw["with_agent_config"]:
            assert isinstance(found, functools.partial)
            assert found.func is test_factory
            assert found.keywords == {"agent_config": pyagent_config}
            assert found.__name__ == test_factory.__name__
            assert found.__doc__ == test_factory.__doc__
        else:
            assert found is test_factory


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_AGENT_CONFIG_YAML, None),
        (
            WO_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_YAML,
            W_AGUI_FEATURE_NAMES_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (W_BOGUS_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML, None),
        (
            W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
        (
            W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_YAML,
            W_TEMPLATE_ID_W_EXTRA_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        ),
    ],
)
def test_factoryagentconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    if config_dict is not None:
        template_id = config_dict.get("template_id")
    else:
        template_id = None

    if template_id not in (None, BOGUS_TEMPLATE_AGENT_ID):
        template_kw = {
            "factory_name": FACTORY_NAME,
            "with_agent_config": True,
        }
        installation_config.agent_configs = [
            config_agents.FactoryAgentConfig(id=template_id, **template_kw),
        ]
    else:
        template_kw = {}
        installation_config.agent_configs = []

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException):
            config_agents.FactoryAgentConfig.from_yaml(
                installation_config,
                yaml_file,
                config_dict,
            )
    else:
        expected = config_agents.FactoryAgentConfig(
            _installation_config=installation_config,
            _config_path=yaml_file,
            **(template_kw | expected_kw),
        )

        found = config_agents.FactoryAgentConfig.from_yaml(
            installation_config,
            yaml_file,
            config_dict,
        )

        assert found == expected

        # See #180.
        assert found._installation_config is installation_config


@pytest.mark.parametrize(
    "kw",
    [
        WO_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
        W_CONFIG_FACTORY_AGENT_CONFIG_KW.copy(),
    ],
)
def test_factoryagentconfig_as_yaml(
    installation_config,
    kw,
):
    kw = copy.deepcopy(kw)
    expected = copy.deepcopy(kw)

    if "extra_config" not in expected:
        expected["extra_config"] = {}

    aconfig = config_agents.FactoryAgentConfig(**kw)

    found = aconfig.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "agent_config, expected_kw",
    [
        (BARE_AGENT_CONFIG_KW.copy(), BARE_AGENT_CONFIG_KW),
        (W_KIND_AGENT_CONFIG_KW.copy(), W_KIND_AGENT_CONFIG_KW),
    ],
)
def test_extract_agent_configs(
    installation_config,
    temp_dir,
    patched_agent_configs,
    agent_config,
    expected_kw,
):
    @dataclasses.dataclass(kw_only=True)
    class TestAgentConfig:
        id: str
        model_name: str
        kind: typing.ClassVar[str] = "testing"
        _installation_config: config_installation.InstallationConfig = None
        _config_path: pathlib.Path = None

        @classmethod
        def from_yaml(cls, i_config, c_path, c_dict):
            return cls(
                _installation_config=i_config,
                _config_path=c_path,
                **c_dict,
            )

    # Register our extension agent config
    patched_agent_configs["testing"] = TestAgentConfig

    if agent_config.get("kind") == "testing":
        kw_no_kind = {k: v for k, v in expected_kw.items() if k != "kind"}
        expected = TestAgentConfig(
            _installation_config=installation_config,
            _config_path=temp_dir,
            **kw_no_kind,
        )
    else:
        expected = config_agents.AgentConfig(
            _installation_config=installation_config,
            _config_path=temp_dir,
            **expected_kw,
        )

    found = config_agents.extract_agent_config(
        installation_config,
        temp_dir,
        agent_config,
    )

    assert found == expected
