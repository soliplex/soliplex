import contextlib
import copy
import dataclasses
import typing
from unittest import mock

import pytest
import yaml

from soliplex import secrets
from soliplex.agui import features as agui_features
from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc
from soliplex.config import meta as config_meta
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

NoRaise = contextlib.nullcontext()


class FauxToolConfig:
    tool_name = "faux"


BOGUS_ICMETA_YAML = """\
meta:
    tool_configs:
"""
BARE_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "skill_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
BARE_ICMETA_YAML = """\
meta:
"""

AGUI_FEATURE_NAME_FOR_META = "test-agui-feature-for-meta"
W_AGUI_FEATURES_ICMETA_KW = {
    "agui_features": [
        config_meta.AGUI_FeatureConfigMeta(
            name=AGUI_FEATURE_NAME_FOR_META,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "skill_configs": [],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_AGUI_FEATURES_ICMETA_YAML = f"""\
meta:
  agui_features:
      - name: "{AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "soliplex.agui.features.EmptyFeatureModel"
        source: "server"
"""


W_TOOL_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [
        config_meta.ConfigMeta(config_klass=FauxToolConfig),
    ],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [
        config_meta.ConfigMeta(
            config_klass=FauxToolConfig,
            wrapper_klass=config_tools.NoArgsMCPWrapper,
        ),
    ],
    "skill_configs": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_TOOL_CONFIGS_ICMETA_YAML = """\
meta:
  tool_configs:
    - "test_config_meta.FauxToolConfig"
  mcp_server_tool_wrappers:
    - config_klass: "test_config_meta.FauxToolConfig"
      wrapper_klass: "soliplex.config.tools.NoArgsMCPWrapper"
"""


W_MCP_TOOLSET_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [
        config_meta.ConfigMeta(
            config_klass=config_tools.Stdio_MCP_ClientToolsetConfig,
        )
    ],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_MCP_TOOLSET_CONFIGS_ICMETA_YAML = """\
meta:
  mcp_toolset_configs:
    - "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig"
"""


W_SKILL_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "skill_configs": [
        config_meta.ConfigMeta(config_klass=config_skills.HR_RAG_SkillConfig),
    ],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_SKILL_CONFIGS_ICMETA_YAML = """\
meta:
  skill_configs:
    - "soliplex.config.skills.HR_RAG_SkillConfig"
"""


W_AGENT_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [],
    "agent_configs": [
        config_meta.ConfigMeta(config_klass=config_agents.AgentConfig),
        config_meta.ConfigMeta(config_klass=config_agents.FactoryAgentConfig),
    ],
    "secret_sources": [],
}
W_AGENT_CONFIGS_ICMETA_YAML = """\
meta:
  agent_configs:
      - "soliplex.config.agents.AgentConfig"
      - "soliplex.config.agents.FactoryAgentConfig"
"""

SECRET_SOURCE_FUNC = lambda source: "SEEKRIT"  # noqa E731
W_SECRET_SOURCE_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [],
    "agent_configs": [],
    "secret_sources": [
        config_meta.ConfigMeta(
            config_klass=config_secrets.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
W_SECRET_SOURCE_ICMETA_YAML = """\
meta:
  secret_sources:
    - "config_klass": "soliplex.config.secrets.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


FULL_ICMETA_KW = {
    "agui_features": [
        config_meta.AGUI_FeatureConfigMeta(
            name=AGUI_FEATURE_NAME_FOR_META,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
    "tool_configs": [],
    "mcp_toolset_configs": [
        config_meta.ConfigMeta(
            config_klass=config_tools.Stdio_MCP_ClientToolsetConfig
        ),
        config_meta.ConfigMeta(
            config_klass=config_tools.HTTP_MCP_ClientToolsetConfig
        ),
    ],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [
        config_meta.ConfigMeta(config_klass=config_skills.HR_RAG_SkillConfig),
        config_meta.ConfigMeta(config_klass=config_skills.HR_RLM_SkillConfig),
    ],
    "agent_configs": [
        config_meta.ConfigMeta(config_klass=config_agents.AgentConfig),
        config_meta.ConfigMeta(config_klass=config_agents.FactoryAgentConfig),
    ],
    "secret_sources": [
        config_meta.ConfigMeta(
            config_klass=config_secrets.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
FULL_ICMETA_YAML = f"""\
meta:
  agui_features:
      - name: "{AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "soliplex.agui.features.EmptyFeatureModel"
        source: "server"
  mcp_toolset_configs:
      - "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig"
      - "soliplex.config.tools.HTTP_MCP_ClientToolsetConfig"
  skill_configs:
      - "soliplex.config.skills.HR_RAG_SkillConfig"
      - "soliplex.config.skills.HR_RLM_SkillConfig"
  agent_configs:
      - "soliplex.config.agents.AgentConfig"
      - "soliplex.config.agents.FactoryAgentConfig"
  secret_sources:
    - "config_klass": "soliplex.config.secrets.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


@mock.patch("importlib.import_module")
def test_configmeta_from_yaml_w_importable_name(im):
    config_yaml = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is faux_module.SomeClass


@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict(w_wrapper):
    config_klass = mock.Mock()
    wrapper_klass = mock.Mock()

    config_yaml = {"config_klass": config_klass}

    if w_wrapper:
        config_yaml["wrapper_klass"] = wrapper_klass

    meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None


@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict_w_names(w_wrapper):
    dummy_module = mock.Mock()
    config_klass = dummy_module.ConfigClass = mock.Mock()
    wrapper_klass = dummy_module.WrapperClass = mock.Mock()

    config_yaml = {"config_klass": "dummy.ConfigClass"}

    if w_wrapper:
        config_yaml["wrapper_klass"] = "dummy.WrapperClass"

    with mock.patch.dict("sys.modules", dummy=dummy_module):
        meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_ICMETA_YAML, None),
        (BARE_ICMETA_YAML, BARE_ICMETA_KW),
        (W_AGUI_FEATURES_ICMETA_YAML, W_AGUI_FEATURES_ICMETA_KW),
        (W_TOOL_CONFIGS_ICMETA_YAML, W_TOOL_CONFIGS_ICMETA_KW),
        (W_MCP_TOOLSET_CONFIGS_ICMETA_YAML, W_MCP_TOOLSET_CONFIGS_ICMETA_KW),
        (W_SKILL_CONFIGS_ICMETA_YAML, W_SKILL_CONFIGS_ICMETA_KW),
        (W_AGENT_CONFIGS_ICMETA_YAML, W_AGENT_CONFIGS_ICMETA_KW),
        (
            W_SECRET_SOURCE_ICMETA_YAML,
            W_SECRET_SOURCE_ICMETA_KW,
        ),
        (FULL_ICMETA_YAML, FULL_ICMETA_KW),
    ],
)
def test_installationconfigmeta_from_yaml(
    temp_dir,
    patched_soliplex_config,
    patched_skill_configs,
    patched_agent_configs,
    patched_secret_getters,
    patched_agui_features,
    patched_tool_configs,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    config_yaml,
    expected_kw,
):
    patched_soliplex_config["test_secret_func"] = SECRET_SOURCE_FUNC
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_dict_meta = config_dict["meta"]

    if expected_kw is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_meta.InstallationConfigMeta.from_yaml(
                yaml_file,
                config_dict_meta,
            )
        assert exc.value._config_path == yaml_file

    else:
        expected = config_meta.InstallationConfigMeta(
            _config_path=yaml_file,
            **expected_kw,
        )

        ic_meta = config_meta.InstallationConfigMeta.from_yaml(
            yaml_file,
            config_dict_meta.copy() if config_dict_meta is not None else None,
        )

        assert ic_meta == expected

        if config_dict_meta and "agui_features" in config_dict_meta:
            for (af_name, af_found), af_expected in zip(
                patched_agui_features.items(),
                config_dict_meta["agui_features"],
                strict=True,
            ):
                assert af_name == af_expected["name"]
                assert af_found.name == af_expected["name"]
                assert af_found.model_klass == af_expected["model_klass"]
                assert af_found.source == af_expected["source"]

        if config_dict_meta and "tool_configs" in config_dict_meta:
            tcs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_tool_configs.values()
            }
            for klass_name in config_dict_meta["tool_configs"]:
                assert (
                    tcs_by_class_name[klass_name].tool_name
                    in patched_tool_configs
                )

        if config_dict_meta and "mcp_toolset_configs" in config_dict_meta:
            mtscs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_mcp_toolset_configs.values()
            }
            for klass_name in config_dict_meta["mcp_toolset_configs"]:
                assert (
                    mtscs_by_class_name[klass_name].kind
                    in patched_mcp_toolset_configs
                )

        if config_dict_meta and "mcp_server_tool_wrappers" in config_dict_meta:
            mcptcp_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_mcp_tool_wrappers.values()
            }
            for meta_kw in config_dict_meta["mcp_server_tool_wrappers"]:
                wrapper_klass_name = meta_kw["wrapper_klass"]
                assert (
                    patched_mcp_tool_wrappers["faux"]
                    == mcptcp_by_class_name[wrapper_klass_name]
                )

        if config_dict_meta and "agent_configs" in config_dict_meta:
            acs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_agent_configs.values()
            }
            for klass_name in config_dict_meta["agent_configs"]:
                kind = acs_by_class_name[klass_name].kind
                assert kind in patched_agent_configs

        if config_dict_meta and "secret_sources" in config_dict_meta:
            assert patched_secret_getters == {
                config_secrets.EnvVarSecretSource.kind: SECRET_SOURCE_FUNC
            }


@pytest.mark.parametrize("w_secret_reg", [False, True])
@pytest.mark.parametrize("w_agent", [False, True])
@pytest.mark.parametrize("w_skills", [False, True])
@pytest.mark.parametrize("w_mcp_toolsets", [False, True])
@pytest.mark.parametrize("w_tools", [False, True])
def test_installationconfigmeta_as_yaml(
    patched_soliplex_config,
    patched_agent_configs,
    patched_skill_configs,
    patched_secret_getters,
    patched_agui_features,
    patched_tool_configs,
    patched_mcp_tool_wrappers,
    patched_mcp_toolset_configs,
    w_tools,
    w_mcp_toolsets,
    w_skills,
    w_agent,
    w_secret_reg,
):
    patched_soliplex_config["test_secret_func"] = SECRET_SOURCE_FUNC

    icmeta_kw = {}
    expected_dict = copy.deepcopy(BARE_ICMETA_KW)
    icmeta_kw = icmeta_kw.copy()

    if w_tools:
        klass = FauxToolConfig
        patched_tool_configs[klass.tool_name] = klass
        expected_dict["tool_configs"].append(
            "test_config_meta.FauxToolConfig",
        )
        wrapper_klass = config_tools.NoArgsMCPWrapper
        patched_mcp_tool_wrappers[klass.tool_name] = wrapper_klass
        expected_dict["mcp_server_tool_wrappers"].append(
            {
                "config_klass": "test_config_meta.FauxToolConfig",
                "wrapper_klass": "soliplex.config.tools.NoArgsMCPWrapper",
            }
        )

    if w_mcp_toolsets:
        klass = config_tools.Stdio_MCP_ClientToolsetConfig
        patched_mcp_toolset_configs[klass.kind] = klass
        expected_dict["mcp_toolset_configs"].append(
            "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig",
        )

    if w_skills:
        klass = config_skills.HR_RAG_SkillConfig
        patched_skill_configs[klass.kind] = klass
        expected_dict["skill_configs"].append(
            "soliplex.config.skills.HR_RAG_SkillConfig",
        )

    if w_agent:
        klass = config_agents.AgentConfig
        patched_agent_configs[klass.kind] = klass
        expected_dict["agent_configs"].append(
            "soliplex.config.agents.AgentConfig",
        )

    if w_secret_reg:
        klass = config_secrets.EnvVarSecretSource
        registered_func = secrets.get_env_var_secret
        patched_secret_getters[klass.kind] = registered_func
        expected_dict["secret_sources"].append(
            {
                "config_klass": "soliplex.config.secrets.EnvVarSecretSource",
                "registered_func": "soliplex.secrets.get_env_var_secret",
            }
        )

    icmeta = config_meta.InstallationConfigMeta(**icmeta_kw)

    found = icmeta.as_yaml

    assert found == expected_dict


def test_installationconfigmeta_postinit_registers_tool_configs(
    patched_tool_configs,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config_tools.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    tc_meta = config_meta.ConfigMeta(config_klass=_DummyToolConfig)
    config_meta.InstallationConfigMeta(tool_configs=[tc_meta])

    assert patched_tool_configs[_DummyToolConfig.tool_name] is _DummyToolConfig


def test_installationconfigmeta_postinit_registers_mcp_tool_wrappers(
    patched_mcp_tool_wrappers,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config_tools.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    @dataclasses.dataclass(kw_only=True)
    class _DummyWrapper:
        func: typing.Any
        tool_config: config_tools.ToolConfig

    mstw_meta = config_meta.ConfigMeta(
        config_klass=_DummyToolConfig,
        wrapper_klass=_DummyWrapper,
    )
    config_meta.InstallationConfigMeta(mcp_server_tool_wrappers=[mstw_meta])

    assert (
        patched_mcp_tool_wrappers[_DummyToolConfig.tool_name] is _DummyWrapper
    )
