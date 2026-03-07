import contextlib
import copy
import dataclasses
import typing
from unittest import mock

import pytest
import yaml

from soliplex import config
from soliplex import secrets
from soliplex.agui import features as agui_features
from soliplex.config import agui as config_agui
from soliplex.config import tools as config_tools
from tests.unit.config import test_config_agui as test_agui

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

W_AGUI_FEATURES_ICMETA_KW = {
    "agui_features": [
        config.AGUI_FeatureConfigMeta(
            name=test_agui.AGUI_FEATURE_NAME,
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
      - name: "{test_agui.AGUI_FEATURE_NAME}"
        model_klass: "soliplex.agui.features.EmptyFeatureModel"
        source: "server"
"""


W_TOOL_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [
        config.ConfigMeta(config_klass=FauxToolConfig),
    ],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [
        config.ConfigMeta(
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
        config.ConfigMeta(
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
        config.ConfigMeta(config_klass=config.HR_RAG_SkillConfig),
    ],
    "mcp_server_tool_wrappers": [],
    "agent_configs": [],
    "secret_sources": [],
}
W_SKILL_CONFIGS_ICMETA_YAML = """\
meta:
  skill_configs:
    - "soliplex.config.HR_RAG_SkillConfig"
"""


W_AGENT_CONFIGS_ICMETA_KW = {
    "agui_features": [],
    "tool_configs": [],
    "mcp_toolset_configs": [],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [],
    "agent_configs": [
        config.ConfigMeta(config_klass=config.AgentConfig),
        config.ConfigMeta(config_klass=config.FactoryAgentConfig),
    ],
    "secret_sources": [],
}
W_AGENT_CONFIGS_ICMETA_YAML = """\
meta:
  agent_configs:
      - "soliplex.config.AgentConfig"
      - "soliplex.config.FactoryAgentConfig"
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
        config.ConfigMeta(
            config_klass=config.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
W_SECRET_SOURCE_ICMETA_YAML = """\
meta:
  secret_sources:
    - "config_klass": "soliplex.config.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


FULL_ICMETA_KW = {
    "agui_features": [
        config.AGUI_FeatureConfigMeta(
            name=test_agui.AGUI_FEATURE_NAME,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
    "tool_configs": [],
    "mcp_toolset_configs": [
        config.ConfigMeta(
            config_klass=config_tools.Stdio_MCP_ClientToolsetConfig
        ),
        config.ConfigMeta(
            config_klass=config_tools.HTTP_MCP_ClientToolsetConfig
        ),
    ],
    "mcp_server_tool_wrappers": [],
    "skill_configs": [
        config.ConfigMeta(config_klass=config.HR_RAG_SkillConfig),
        config.ConfigMeta(config_klass=config.HR_RLM_SkillConfig),
    ],
    "agent_configs": [
        config.ConfigMeta(config_klass=config.AgentConfig),
        config.ConfigMeta(config_klass=config.FactoryAgentConfig),
    ],
    "secret_sources": [
        config.ConfigMeta(
            config_klass=config.EnvVarSecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
FULL_ICMETA_YAML = f"""\
meta:
  agui_features:
      - name: "{test_agui.AGUI_FEATURE_NAME}"
        model_klass: "soliplex.agui.features.EmptyFeatureModel"
        source: "server"
  mcp_toolset_configs:
      - "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig"
      - "soliplex.config.tools.HTTP_MCP_ClientToolsetConfig"
  skill_configs:
      - "soliplex.config.HR_RAG_SkillConfig"
      - "soliplex.config.HR_RLM_SkillConfig"
  agent_configs:
      - "soliplex.config.AgentConfig"
      - "soliplex.config.FactoryAgentConfig"
  secret_sources:
    - "config_klass": "soliplex.config.EnvVarSecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


@mock.patch("importlib.import_module")
def test_configmeta_from_yaml_w_dotted_name(im):
    config_yaml = "somemodule.SomeClass"

    faux_module = im.return_value = mock.Mock()

    meta = config.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is faux_module.SomeClass


@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict(w_wrapper):
    config_klass = mock.Mock()
    wrapper_klass = mock.Mock()

    config_yaml = {"config_klass": config_klass}

    if w_wrapper:
        config_yaml["wrapper_klass"] = wrapper_klass

    meta = config.ConfigMeta.from_yaml(config_yaml)

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
        meta = config.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None


def test_configmeta_dottedname():
    config_klass = mock.create_autospec(
        type,
        __module__="some.module",
        __name__="some_config",
    )
    meta = config.ConfigMeta(config_klass=config_klass)

    assert meta.dotted_name == "some.module.some_config"


@pytest.fixture
def patched_soliplex_config_agui():
    with mock.patch.dict(config_agui.__dict__) as patched:
        patched["AGUI_FEATURES_BY_NAME"] = {}

        yield patched


@pytest.fixture
def patched_soliplex_config_tools():
    with mock.patch.dict(config_tools.__dict__) as patched:
        patched["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"] = {}
        patched["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"] = {}
        patched["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"] = {}
        yield patched


@pytest.fixture
def patched_soliplex_config():
    with mock.patch.dict(config.__dict__) as patched:
        patched["test_secret_func"] = SECRET_SOURCE_FUNC
        patched["SKILL_CONFIG_CLASSES_BY_KIND"] = {}
        patched["AGENT_CONFIG_CLASSES_BY_KIND"] = {}
        patched["SECRET_GETTERS_BY_KIND"] = {}

        yield patched


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
    patched_soliplex_config_agui,
    patched_soliplex_config_tools,
    config_yaml,
    expected_kw,
):
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_meta = config_dict["meta"]

    if expected_kw is None:
        with pytest.raises(config.FromYamlException) as exc:
            config.InstallationConfigMeta.from_yaml(
                yaml_file,
                config_meta,
            )
        assert exc.value._config_path == yaml_file

    else:
        expected = config.InstallationConfigMeta(
            _config_path=yaml_file,
            **expected_kw,
        )

        ic_meta = config.InstallationConfigMeta.from_yaml(
            yaml_file,
            config_meta.copy() if config_meta is not None else None,
        )

        assert ic_meta == expected

        PSC = patched_soliplex_config
        PSCA = patched_soliplex_config_agui
        PSCT = patched_soliplex_config_tools

        if config_meta and "agui_features" in config_meta:
            agui_registry = PSCA["AGUI_FEATURES_BY_NAME"]
            for (af_name, af_found), af_expected in zip(
                agui_registry.items(),
                config_meta["agui_features"],
                strict=True,
            ):
                assert af_name == af_expected["name"]
                assert af_found.name == af_expected["name"]
                assert af_found.model_klass == af_expected["model_klass"]
                assert af_found.source == af_expected["source"]

        if config_meta and "tool_configs" in config_meta:
            tool_registry = PSCT["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"]
            tcs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in tool_registry.values()
            }
            for klass_name in config_meta["tool_configs"]:
                assert tcs_by_class_name[klass_name].tool_name in tool_registry

        if config_meta and "mcp_toolset_configs" in config_meta:
            mcp_toolset_registry = PSCT["MCP_TOOLSET_CONFIG_CLASSES_BY_KIND"]
            tcs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in mcp_toolset_registry.values()
            }
            for klass_name in config_meta["mcp_toolset_configs"]:
                assert (
                    tcs_by_class_name[klass_name].kind in mcp_toolset_registry
                )

        if config_meta and "mcp_server_tool_wrappers" in config_meta:
            wrapper_registry = PSCT["MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"]
            mcptcp_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in wrapper_registry.values()
            }
            for meta_kw in config_meta["mcp_server_tool_wrappers"]:
                wrapper_klass_name = meta_kw["wrapper_klass"]
                assert (
                    wrapper_registry["faux"]
                    == mcptcp_by_class_name[wrapper_klass_name]
                )

        if config_meta and "agent_configs" in config_meta:
            agent_registry = PSC["AGENT_CONFIG_CLASSES_BY_KIND"]
            acs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in agent_registry.values()
            }
            for klass_name in config_meta["agent_configs"]:
                kind = acs_by_class_name[klass_name].kind
                assert kind in agent_registry

        if config_meta and "secret_sources" in config_meta:
            ss_registry = PSC["SECRET_GETTERS_BY_KIND"]
            assert ss_registry == {
                config.EnvVarSecretSource.kind: SECRET_SOURCE_FUNC
            }


@pytest.mark.parametrize("w_secret_reg", [False, True])
@pytest.mark.parametrize("w_agent", [False, True])
@pytest.mark.parametrize("w_skills", [False, True])
@pytest.mark.parametrize("w_mcp_toolsets", [False, True])
@pytest.mark.parametrize("w_tools", [False, True])
def test_installationconfigmeta_as_yaml(
    patched_soliplex_config,
    patched_soliplex_config_agui,
    patched_soliplex_config_tools,
    w_tools,
    w_mcp_toolsets,
    w_skills,
    w_agent,
    w_secret_reg,
):
    icmeta_kw = {}
    expected_dict = copy.deepcopy(BARE_ICMETA_KW)
    icmeta_kw = icmeta_kw.copy()

    if w_tools:
        klass = FauxToolConfig
        tool_registry = config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME
        tool_registry[klass.tool_name] = klass
        expected_dict["tool_configs"].append(
            "test_config_meta.FauxToolConfig",
        )
        wrapper_klass = config_tools.NoArgsMCPWrapper
        wrapper_registry = config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME
        wrapper_registry[klass.tool_name] = wrapper_klass
        expected_dict["mcp_server_tool_wrappers"].append(
            {
                "config_klass": "test_config_meta.FauxToolConfig",
                "wrapper_klass": "soliplex.config.tools.NoArgsMCPWrapper",
            }
        )

    if w_mcp_toolsets:
        klass = config_tools.Stdio_MCP_ClientToolsetConfig
        mcpts_registry = config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND
        mcpts_registry[klass.kind] = klass
        expected_dict["mcp_toolset_configs"].append(
            "soliplex.config.tools.Stdio_MCP_ClientToolsetConfig",
        )

    if w_skills:
        klass = config.HR_RAG_SkillConfig
        skill_registry = config.SKILL_CONFIG_CLASSES_BY_KIND
        skill_registry[klass.kind] = klass
        expected_dict["skill_configs"].append(
            "soliplex.config.HR_RAG_SkillConfig",
        )

    if w_agent:
        klass = config.AgentConfig
        agent_registry = config.AGENT_CONFIG_CLASSES_BY_KIND
        agent_registry[klass.kind] = klass
        expected_dict["agent_configs"].append(
            "soliplex.config.AgentConfig",
        )

    if w_secret_reg:
        klass = config.EnvVarSecretSource
        registered_func = secrets.get_env_var_secret
        secret_registry = config.SECRET_GETTERS_BY_KIND
        secret_registry[klass.kind] = registered_func
        expected_dict["secret_sources"].append(
            {
                "config_klass": "soliplex.config.EnvVarSecretSource",
                "registered_func": "soliplex.secrets.get_env_var_secret",
            }
        )

    icmeta = config.InstallationConfigMeta(**icmeta_kw)

    found = icmeta.as_yaml

    assert found == expected_dict


def test_installationconfigmeta_postinit_registers_tool_configs(
    patched_soliplex_config_tools,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config_tools.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    tc_meta = config.ConfigMeta(config_klass=_DummyToolConfig)
    config.InstallationConfigMeta(tool_configs=[tc_meta])

    tcs = patched_soliplex_config_tools["TOOL_CONFIG_CLASSES_BY_TOOL_NAME"]
    assert tcs[_DummyToolConfig.tool_name] is _DummyToolConfig


def test_installationconfigmeta_postinit_registers_mcp_tool_wrappers(
    patched_soliplex_config_tools,
):
    @dataclasses.dataclass(kw_only=True)
    class _DummyToolConfig(config_tools.ToolConfig):
        tool_name: str = "tests.unit.test_config.dummy_tool"

    @dataclasses.dataclass(kw_only=True)
    class _DummyWrapper:
        func: typing.Any
        tool_config: config_tools.ToolConfig

    mstw_meta = config.ConfigMeta(
        config_klass=_DummyToolConfig,
        wrapper_klass=_DummyWrapper,
    )
    config.InstallationConfigMeta(mcp_server_tool_wrappers=[mstw_meta])

    wrappers = patched_soliplex_config_tools[
        "MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME"
    ]
    assert wrappers[_DummyToolConfig.tool_name] is _DummyWrapper
