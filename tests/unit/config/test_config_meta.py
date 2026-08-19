import contextlib
import copy
import dataclasses

import _test_features as agui_features
import _test_metaconfig
import pytest
import yaml

from soliplex import authz
from soliplex.config import _utils
from soliplex.config import agents as config_agents
from soliplex.config import agui as config_agui
from soliplex.config import exceptions as config_exc
from soliplex.config import meta as config_meta
from soliplex.config import secrets as config_secrets
from soliplex.config import skills as config_skills
from soliplex.config import tools as config_tools

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
    "agent_capability_types": [],
    "agent_configs": [],
    "secret_sources": [],
    "jsonpath_functions": [],
}
BARE_ICMETA_YAML = """\
meta:
"""

AGUI_FEATURE_NAME_FOR_META = "test-agui-feature-for-meta"
W_AGUI_FEATURES_ICMETA_KW = BARE_ICMETA_KW | {
    "agui_features": [
        config_meta.AGUI_FeatureConfigMeta(
            name=AGUI_FEATURE_NAME_FOR_META,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
}
W_AGUI_FEATURES_ICMETA_YAML = f"""\
meta:
  agui_features:
      - name: "{AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "_test_features.EmptyFeatureModel"
        source: "server"
"""

W_AGUI_FEATURES_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "agui_features": [
        config_meta.ClearMetaRegistry(),
        config_meta.AGUI_FeatureConfigMeta(
            name=AGUI_FEATURE_NAME_FOR_META,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
}
W_AGUI_FEATURES_W_CLEAR_ICMETA_YAML = f"""\
meta:
  agui_features:
      - "{config_meta.ClearMetaRegistry.MARKER}"
      - name: "{AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "_test_features.EmptyFeatureModel"
        source: "server"
"""


W_TOOL_CONFIGS_ICMETA_KW = BARE_ICMETA_KW | {
    "tool_configs": [
        config_meta.ToolConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
        ),
    ],
    "mcp_server_tool_wrappers": [
        config_meta.MCP_ServerToolWrapperConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
            wrapper_klass=_test_metaconfig.DummyMCPWrapper,
        ),
    ],
}
W_TOOL_CONFIGS_ICMETA_YAML = """\
meta:
  tool_configs:
    - "_test_metaconfig.DummyToolConfig"
  mcp_server_tool_wrappers:
    - config_klass: "_test_metaconfig.DummyToolConfig"
      wrapper_klass: "_test_metaconfig.DummyMCPWrapper"
"""

W_TOOL_CONFIGS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "tool_configs": [
        config_meta.ClearMetaRegistry(),
        config_meta.ToolConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
        ),
    ],
}
W_TOOL_CONFIGS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  tool_configs:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - "_test_metaconfig.DummyToolConfig"
"""

W_TOOL_WRAPPERS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "mcp_server_tool_wrappers": [
        config_meta.ClearMetaRegistry(),
        config_meta.MCP_ServerToolWrapperConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
            wrapper_klass=_test_metaconfig.DummyMCPWrapper,
        ),
    ],
}
W_TOOL_WRAPPERS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  mcp_server_tool_wrappers:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - config_klass: "_test_metaconfig.DummyToolConfig"
      wrapper_klass: "_test_metaconfig.DummyMCPWrapper"
"""

W_TOOL_CONFIGS_W_WRAPPERS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "tool_configs": [
        config_meta.ClearMetaRegistry(),
        config_meta.ToolConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
        ),
    ],
    "mcp_server_tool_wrappers": [
        config_meta.ClearMetaRegistry(),
        config_meta.MCP_ServerToolWrapperConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
            wrapper_klass=_test_metaconfig.DummyMCPWrapper,
        ),
    ],
}
W_TOOL_CONFIGS_W_WRAPPERS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  tool_configs:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - "_test_metaconfig.DummyToolConfig"
  mcp_server_tool_wrappers:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - config_klass: "_test_metaconfig.DummyToolConfig"
      wrapper_klass: "_test_metaconfig.DummyMCPWrapper"
"""


W_MCP_TOOLSET_CONFIGS_ICMETA_KW = BARE_ICMETA_KW | {
    "mcp_toolset_configs": [
        config_meta.MCP_ToolsetConfigMeta(
            config_klass=_test_metaconfig.DummyMCP_ToolsetConfig,
        )
    ],
}
W_MCP_TOOLSET_CONFIGS_ICMETA_YAML = """\
meta:
  mcp_toolset_configs:
    - "_test_metaconfig.DummyMCP_ToolsetConfig"
"""


W_MCP_TOOLSET_CONFIGS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "mcp_toolset_configs": [
        config_meta.ClearMetaRegistry(),
        config_meta.MCP_ToolsetConfigMeta(
            config_klass=_test_metaconfig.DummyMCP_ToolsetConfig,
        ),
    ],
}
W_MCP_TOOLSET_CONFIGS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  mcp_toolset_configs:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - "_test_metaconfig.DummyMCP_ToolsetConfig"
"""


W_SKILL_CONFIGS_ICMETA_KW = BARE_ICMETA_KW | {
    "skill_configs": [
        config_meta.SkillConfigMeta(
            config_klass=_test_metaconfig.DummySkillConfig,
        ),
    ],
}
W_SKILL_CONFIGS_ICMETA_YAML = """\
meta:
  skill_configs:
    - "_test_metaconfig.DummySkillConfig"
"""

W_SKILL_CONFIGS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "skill_configs": [
        config_meta.ClearMetaRegistry(),
        config_meta.SkillConfigMeta(
            config_klass=_test_metaconfig.DummySkillConfig,
        ),
    ],
}
W_SKILL_CONFIGS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  skill_configs:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - "_test_metaconfig.DummySkillConfig"
"""


W_AGENT_CAPABILITY_ICMETA_KW = BARE_ICMETA_KW | {
    "agent_capability_types": [
        config_meta.AgentCapabilityMeta(
            config_klass=_test_metaconfig.DummyAgentCapability
        ),
    ],
}
W_AGENT_CAPABILITY_ICMETA_YAML = """\
meta:
  agent_capability_types:
      - "_test_metaconfig.DummyAgentCapability"
"""

W_AGENT_CAPABILITY_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "agent_capability_types": [
        config_meta.ClearMetaRegistry(),
        config_meta.AgentCapabilityMeta(
            config_klass=_test_metaconfig.DummyAgentCapability
        ),
    ],
}
W_AGENT_CAPABILITY_W_CLEAR_ICMETA_YAML = f"""\
meta:
  agent_capability_types:
      - "{config_meta.ClearMetaRegistry.MARKER}"
      - "_test_metaconfig.DummyAgentCapability"
"""


W_AGENT_CONFIGS_ICMETA_KW = BARE_ICMETA_KW | {
    "agent_configs": [
        config_meta.AgentConfigMeta(
            config_klass=_test_metaconfig.DummyAgentConfig,
        ),
    ],
}
W_AGENT_CONFIGS_ICMETA_YAML = """\
meta:
  agent_configs:
      - "_test_metaconfig.DummyAgentConfig"
"""

W_AGENT_CONFIGS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "agent_configs": [
        config_meta.ClearMetaRegistry(),
        config_meta.AgentConfigMeta(
            config_klass=_test_metaconfig.DummyAgentConfig,
        ),
    ],
}
W_AGENT_CONFIGS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  agent_configs:
      - "{config_meta.ClearMetaRegistry.MARKER}"
      - "_test_metaconfig.DummyAgentConfig"
"""


def secret_source_func(source):  # pragma: NO COVER (registered, not called)
    return "SEEKRIT"


W_SECRET_SOURCE_ICMETA_KW = BARE_ICMETA_KW | {
    "secret_sources": [
        config_meta.SecretSourceMeta(
            config_klass=_test_metaconfig.DummySecretSource,
            registered_func=secret_source_func,
        ),
    ],
}
W_SECRET_SOURCE_ICMETA_YAML = """\
meta:
  secret_sources:
    - "config_klass": "_test_metaconfig.DummySecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""

W_SECRET_SOURCE_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "secret_sources": [
        config_meta.ClearMetaRegistry(),
        config_meta.SecretSourceMeta(
            config_klass=_test_metaconfig.DummySecretSource,
            registered_func=secret_source_func,
        ),
    ],
}
W_SECRET_SOURCE_W_CLEAR_ICMETA_YAML = f"""\
meta:
  secret_sources:
    - "{config_meta.ClearMetaRegistry.MARKER}"
    - "config_klass": "_test_metaconfig.DummySecretSource"
      "registered_func": "soliplex.config.test_secret_func"
"""


JSONPATH_FUNCTION_NAME = "faux_filter"
W_JSONPATH_FUNCTIONS_ICMETA_KW = BARE_ICMETA_KW | {
    "jsonpath_functions": [
        config_meta.JSONPathFunctionConfigMeta(
            name=JSONPATH_FUNCTION_NAME,
            func=_test_metaconfig.dummy_jsonpath_func,
        ),
    ],
}
W_JSONPATH_FUNCTIONS_ICMETA_YAML = f"""\
meta:
  jsonpath_functions:
      - name: "{JSONPATH_FUNCTION_NAME}"
        func: "_test_metaconfig.dummy_jsonpath_func"
"""

W_JSONPATH_FUNCTIONS_W_CLEAR_ICMETA_KW = BARE_ICMETA_KW | {
    "jsonpath_functions": [
        config_meta.ClearMetaRegistry(),
        config_meta.JSONPathFunctionConfigMeta(
            name=JSONPATH_FUNCTION_NAME,
            func=_test_metaconfig.dummy_jsonpath_func,
        ),
    ],
}
W_JSONPATH_FUNCTIONS_W_CLEAR_ICMETA_YAML = f"""\
meta:
  jsonpath_functions:
      - "{config_meta.ClearMetaRegistry.MARKER}"
      - name: "{JSONPATH_FUNCTION_NAME}"
        func: "_test_metaconfig.dummy_jsonpath_func"
"""


FULL_ICMETA_KW = {
    "agui_features": [
        config_meta.AGUI_FeatureConfigMeta(
            name=AGUI_FEATURE_NAME_FOR_META,
            model_klass=agui_features.EmptyFeatureModel,
            source="server",
        ),
    ],
    "tool_configs": [
        config_meta.ToolConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
        ),
    ],
    "mcp_toolset_configs": [
        config_meta.MCP_ToolsetConfigMeta(
            config_klass=_test_metaconfig.DummyMCP_ToolsetConfig,
        ),
    ],
    "mcp_server_tool_wrappers": [
        config_meta.MCP_ServerToolWrapperConfigMeta(
            config_klass=_test_metaconfig.DummyToolConfig,
            wrapper_klass=_test_metaconfig.DummyMCPWrapper,
        ),
    ],
    "skill_configs": [
        config_meta.SkillConfigMeta(
            config_klass=_test_metaconfig.DummySkillConfig,
        ),
    ],
    "agent_capability_types": [
        config_meta.AgentCapabilityMeta(
            config_klass=_test_metaconfig.DummyAgentCapability,
        ),
    ],
    "agent_configs": [
        config_meta.AgentConfigMeta(
            config_klass=_test_metaconfig.DummyAgentConfig,
        ),
    ],
    "secret_sources": [
        config_meta.SecretSourceMeta(
            config_klass=_test_metaconfig.DummySecretSource,
            registered_func=secret_source_func,
        ),
    ],
    "jsonpath_functions": [
        config_meta.JSONPathFunctionConfigMeta(
            name=JSONPATH_FUNCTION_NAME,
            func=_test_metaconfig.dummy_jsonpath_func,
        ),
    ],
}
FULL_ICMETA_YAML = f"""\
meta:
  agui_features:
      - name: "{AGUI_FEATURE_NAME_FOR_META}"
        model_klass: "_test_features.EmptyFeatureModel"
        source: "server"
  tool_configs:
    - "_test_metaconfig.DummyToolConfig"
  mcp_toolset_configs:
      - "_test_metaconfig.DummyMCP_ToolsetConfig"
  mcp_server_tool_wrappers:
    - config_klass: "_test_metaconfig.DummyToolConfig"
      wrapper_klass: "_test_metaconfig.DummyMCPWrapper"
  skill_configs:
      - "_test_metaconfig.DummySkillConfig"
  agent_capability_types:
      - "_test_metaconfig.DummyAgentCapability"
  agent_configs:
      - "_test_metaconfig.DummyAgentConfig"
  secret_sources:
    - "config_klass": "_test_metaconfig.DummySecretSource"
      "registered_func": "soliplex.config.test_secret_func"
  jsonpath_functions:
      - name: "{JSONPATH_FUNCTION_NAME}"
        func: "_test_metaconfig.dummy_jsonpath_func"
"""

NoRaise = contextlib.nullcontext()


@pytest.mark.parametrize(
    "w_source_kw, exp_source",
    [
        ({}, "either"),
        ({"source": "either"}, "either"),
        ({"source": "server"}, "server"),
        ({"source": "client"}, "client"),
    ],
)
def test_agui_featureconfigmeta_from_yaml(w_source_kw, exp_source):

    meta = config_meta.AGUI_FeatureConfigMeta.from_yaml(
        {
            "name": "my_feature",
            "model_klass": "_test_metaconfig.DummyModelClass",
        }
        | w_source_kw
    )

    assert meta.name == "my_feature"
    assert meta.model_klass is _test_metaconfig.DummyModelClass
    assert meta.source == exp_source


@pytest.mark.parametrize("w_bare_str", [False, True])
def test_toolconfigmeta_from_yaml(w_bare_str):
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"

    if w_bare_str:
        yaml_config = tool_config_klassname
    else:
        yaml_config = {"config_klass": tool_config_klassname}

    found = config_meta.ToolConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.tool_name == _test_metaconfig.DummyToolConfig.tool_name


@pytest.mark.parametrize("w_bare_str", [False, True])
def test_mcp_toolsetconfigmeta_from_yaml(w_bare_str):
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"

    if w_bare_str:
        yaml_config = tool_config_klassname
    else:
        yaml_config = {
            "config_klass": tool_config_klassname,
        }

    found = config_meta.MCP_ToolsetConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.kind == _test_metaconfig.DummyToolConfig.kind


def test_mcp_servertoolwrapperconfigmeta_from_yaml():
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"
    wrapper_klassname = "_test_metaconfig.DummyMCPWrapper"

    yaml_config = {
        "config_klass": tool_config_klassname,
        "wrapper_klass": wrapper_klassname,
    }

    found = config_meta.MCP_ServerToolWrapperConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.wrapper_klass is _test_metaconfig.DummyMCPWrapper
    assert found.tool_name == _test_metaconfig.DummyToolConfig.tool_name


@pytest.mark.parametrize("w_bare_str", [False, True])
def test_skillconfigmeta_from_yaml(w_bare_str):
    skill_config_klassname = "_test_metaconfig.DummySkillConfig"

    if w_bare_str:
        yaml_config = skill_config_klassname
    else:
        yaml_config = {
            "config_klass": skill_config_klassname,
        }

    found = config_meta.SkillConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummySkillConfig
    assert found.kind == _test_metaconfig.DummySkillConfig.kind


@pytest.mark.parametrize("w_bare_str", [False, True])
def test_agentcapabilityconfigmeta_from_yaml(w_bare_str):
    capability_klassname = "_test_metaconfig.DummyAgentCapability"
    exp_cap_klass = _test_metaconfig.DummyAgentCapability

    if w_bare_str:
        yaml_config = capability_klassname
    else:
        yaml_config = {"config_klass": capability_klassname}

    found = config_meta.AgentCapabilityMeta.from_yaml(yaml_config)

    assert found.config_klass is exp_cap_klass
    assert found.capability_name == exp_cap_klass.__name__


@pytest.mark.parametrize("w_bare_str", [False, True])
def test_agentconfigmeta_from_yaml(w_bare_str):
    agent_config_klassname = "_test_metaconfig.DummyAgentConfig"

    if w_bare_str:
        yaml_config = agent_config_klassname
    else:
        yaml_config = {"config_klass": agent_config_klassname}

    found = config_meta.AgentConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyAgentConfig
    assert found.kind == _test_metaconfig.DummyAgentConfig.kind


def test_secretsourcemeta_from_yaml():
    secret_source_klassname = "_test_metaconfig.DummySecretSource"
    registered_funcname = "_test_metaconfig.dummy_secret_getter"

    yaml_config = {
        "config_klass": secret_source_klassname,
        "registered_func": registered_funcname,
    }

    found = config_meta.SecretSourceMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummySecretSource
    assert found.registered_func is _test_metaconfig.dummy_secret_getter
    assert found.kind == _test_metaconfig.DummySecretSource.kind


def test_jsonpathfunctionconfigmeta_from_yaml():
    meta = config_meta.JSONPathFunctionConfigMeta.from_yaml(
        {"name": "is_admin", "func": "_test_metaconfig.dummy_jsonpath_func"}
    )

    assert meta.name == "is_admin"
    assert meta.func is _test_metaconfig.dummy_jsonpath_func


@dataclasses.dataclass(frozen=True)
class _TestConfig:
    @classmethod
    def from_yaml(cls, entry):
        return cls()


@pytest.mark.parametrize(
    "w_entries, exp_entries",
    [
        ([], []),
        (
            [
                config_meta.ClearMetaRegistry.MARKER,
            ],
            [
                config_meta.ClearMetaRegistry(),
            ],
        ),
        (
            [
                config_meta.ClearMetaRegistry.MARKER,
                config_meta.ClearMetaRegistry.MARKER,
            ],
            [
                config_meta.ClearMetaRegistry(),
            ],
        ),
        (
            [
                config_meta.ClearMetaRegistry.MARKER,
                {},
            ],
            [
                config_meta.ClearMetaRegistry(),
                _TestConfig(),
            ],
        ),
        (
            [
                {},
                config_meta.ClearMetaRegistry.MARKER,
            ],
            [
                config_meta.ClearMetaRegistry(),
                _TestConfig(),
            ],
        ),
        (
            [
                config_meta.ClearMetaRegistry.MARKER,
                {},
                config_meta.ClearMetaRegistry.MARKER,
            ],
            [
                config_meta.ClearMetaRegistry(),
                _TestConfig(),
            ],
        ),
    ],
)
def test_installationconfigmeta__partition_cmrs(w_entries, exp_entries):

    found = config_meta.InstallationConfigMeta._partition_cmrs(
        w_entries,
        config_klass=_TestConfig,
    )

    assert found == exp_entries


@pytest.mark.parametrize(
    "w_entries, exp_entries, exp_clear",
    [
        ([], [], False),
        (
            [config_meta.ClearMetaRegistry()],
            [],
            True,
        ),
        (
            [config_meta.ClearMetaRegistry(), config_meta.ClearMetaRegistry()],
            [],
            True,
        ),
        (
            [config_meta.ClearMetaRegistry(), {}],
            [{}],
            True,
        ),
        (
            [{}],
            [{}],
            False,
        ),
        (
            [{}, config_meta.ClearMetaRegistry()],
            [{}],
            True,
        ),
        (
            [
                config_meta.ClearMetaRegistry(),
                {},
                config_meta.ClearMetaRegistry(),
            ],
            [{}],
            True,
        ),
    ],
)
def test_installationconfigmeta__strip_clear(
    w_entries, exp_entries, exp_clear
):

    found = config_meta.InstallationConfigMeta._strip_clear(w_entries)

    entries, clear = found
    assert entries == exp_entries
    assert clear == exp_clear


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BOGUS_ICMETA_YAML, None),
        (BARE_ICMETA_YAML, BARE_ICMETA_KW),
        (W_AGUI_FEATURES_ICMETA_YAML, W_AGUI_FEATURES_ICMETA_KW),
        (W_TOOL_CONFIGS_ICMETA_YAML, W_TOOL_CONFIGS_ICMETA_KW),
        (W_MCP_TOOLSET_CONFIGS_ICMETA_YAML, W_MCP_TOOLSET_CONFIGS_ICMETA_KW),
        (W_SKILL_CONFIGS_ICMETA_YAML, W_SKILL_CONFIGS_ICMETA_KW),
        (W_AGENT_CAPABILITY_ICMETA_YAML, W_AGENT_CAPABILITY_ICMETA_KW),
        (W_AGENT_CONFIGS_ICMETA_YAML, W_AGENT_CONFIGS_ICMETA_KW),
        (
            W_SECRET_SOURCE_ICMETA_YAML,
            W_SECRET_SOURCE_ICMETA_KW,
        ),
        (
            W_JSONPATH_FUNCTIONS_ICMETA_YAML,
            W_JSONPATH_FUNCTIONS_ICMETA_KW,
        ),
        (FULL_ICMETA_YAML, FULL_ICMETA_KW),
    ],
)
def test_installationconfigmeta_from_yaml(
    temp_dir,
    patched_soliplex_config,
    patched_agui_features,
    patched_tool_configs,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    patched_skill_configs,
    patched_agent_capabilities,
    patched_agent_configs,
    patched_secret_getters,
    patched_secret_sources,
    patched_jsonpath_functions,
    patched_app_routers,
    config_yaml,
    expected_kw,
):
    patched_soliplex_config["test_secret_func"] = secret_source_func
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_dict_meta = copy.deepcopy(config_dict["meta"])

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

        # ICMeta c'tor loads defaults
        patched_app_routers.clear()

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
                tool_config_klass = _utils._from_dotted_name(
                    meta_kw["config_klass"]
                )
                wrapper_klassname = meta_kw["wrapper_klass"]
                assert (
                    patched_mcp_tool_wrappers[tool_config_klass.tool_name]
                    == mcptcp_by_class_name[wrapper_klassname]
                )

        if config_dict_meta and "skill_configs" in config_dict_meta:
            scs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_skill_configs.values()
            }
            for klass_name in config_dict_meta["skill_configs"]:
                assert (
                    scs_by_class_name[klass_name].kind in patched_skill_configs
                )

        if config_dict_meta and "agent_capability_types" in config_dict_meta:
            acts_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass.__name__
                for klass in patched_agent_capabilities.values()
            }
            for klass_name in config_dict_meta["agent_capability_types"]:
                short_name = acts_by_class_name[klass_name]
                assert short_name in patched_agent_capabilities

        if config_dict_meta and "agent_configs" in config_dict_meta:
            acs_by_class_name = {
                f"{klass.__module__}.{klass.__name__}": klass
                for klass in patched_agent_configs.values()
            }
            for klass_name in config_dict_meta["agent_configs"]:
                kind = acs_by_class_name[klass_name].kind
                assert kind in patched_agent_configs

        if config_dict_meta and "secret_sources" in config_dict_meta:
            ss_klass = _test_metaconfig.DummySecretSource
            assert patched_secret_getters == {
                ss_klass.kind: secret_source_func
            }
            assert patched_secret_sources == {ss_klass.kind: ss_klass}

        if config_dict_meta and "jsonpath_functions" in config_dict_meta:
            assert authz.registered_jsonpath_functions() == {
                JSONPATH_FUNCTION_NAME: _test_metaconfig.dummy_jsonpath_func
            }
            assert (
                patched_jsonpath_functions[JSONPATH_FUNCTION_NAME]
                is _test_metaconfig.dummy_jsonpath_func
            )


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        pytest.param(
            W_AGUI_FEATURES_W_CLEAR_ICMETA_YAML,
            W_AGUI_FEATURES_W_CLEAR_ICMETA_KW,
            id="agui_features",
        ),
        pytest.param(
            W_TOOL_CONFIGS_W_CLEAR_ICMETA_YAML,
            W_TOOL_CONFIGS_W_CLEAR_ICMETA_KW,
            id="tool_configs_only",
        ),
        pytest.param(
            W_TOOL_WRAPPERS_W_CLEAR_ICMETA_YAML,
            W_TOOL_WRAPPERS_W_CLEAR_ICMETA_KW,
            id="tool_wrappers_only",
        ),
        pytest.param(
            W_TOOL_CONFIGS_W_WRAPPERS_W_CLEAR_ICMETA_YAML,
            W_TOOL_CONFIGS_W_WRAPPERS_W_CLEAR_ICMETA_KW,
            id="tool_configs and wrappers",
        ),
        pytest.param(
            W_MCP_TOOLSET_CONFIGS_W_CLEAR_ICMETA_YAML,
            W_MCP_TOOLSET_CONFIGS_W_CLEAR_ICMETA_KW,
            id="MCP toolsets",
        ),
        pytest.param(
            W_SKILL_CONFIGS_W_CLEAR_ICMETA_YAML,
            W_SKILL_CONFIGS_W_CLEAR_ICMETA_KW,
            id="skills",
        ),
        pytest.param(
            W_AGENT_CAPABILITY_W_CLEAR_ICMETA_YAML,
            W_AGENT_CAPABILITY_W_CLEAR_ICMETA_KW,
            id="agent_capabilities",
        ),
        pytest.param(
            W_AGENT_CONFIGS_W_CLEAR_ICMETA_YAML,
            W_AGENT_CONFIGS_W_CLEAR_ICMETA_KW,
            id="agents",
        ),
        pytest.param(
            W_SECRET_SOURCE_W_CLEAR_ICMETA_YAML,
            W_SECRET_SOURCE_W_CLEAR_ICMETA_KW,
            id="secret sources",
        ),
        pytest.param(
            W_JSONPATH_FUNCTIONS_W_CLEAR_ICMETA_YAML,
            W_JSONPATH_FUNCTIONS_W_CLEAR_ICMETA_KW,
            id="jsonpath functions",
        ),
    ],
)
def test_installationconfigmeta_from_yaml_w_clear(
    temp_dir,
    patched_soliplex_config,
    patched_agui_features,
    patched_tool_configs,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    patched_skill_configs,
    patched_agent_capabilities,
    patched_agent_configs,
    patched_secret_getters,
    patched_secret_sources,
    patched_jsonpath_functions,
    patched_app_routers,
    config_yaml,
    expected_kw,
):
    patched_soliplex_config["test_secret_func"] = secret_source_func
    expected_kw = copy.deepcopy(expected_kw)

    yaml_file = temp_dir / "config.yaml"
    yaml_file.write_text(config_yaml)

    with yaml_file.open() as fp:
        config_dict = yaml.safe_load(fp)

    config_dict_meta = copy.deepcopy(config_dict["meta"])

    if "mcp_server_tool_wrappers" in config_dict_meta:
        # Cannot register wrappers for unknown tool configs
        patched_tool_configs["_test_metaconfig.dummy_tool"] = object()

    expected = config_meta.InstallationConfigMeta(
        _config_path=yaml_file,
        **expected_kw,
    )

    # ICMeta c'tor loads defaults
    patched_app_routers.clear()

    if "agui_features" in config_dict_meta:
        patched_agui_features.clear()
        patched_agui_features["before"] = object()

    if "tool_configs" in config_dict_meta:
        patched_tool_configs.clear()
        patched_tool_configs["before"] = object()

        # TC clear must clear wrappers
        patched_mcp_tool_wrappers.clear()
        patched_mcp_tool_wrappers["before"] = object()

    if "mcp_toolset_configs" in config_dict_meta:
        patched_mcp_toolset_configs.clear()
        patched_mcp_toolset_configs["before"] = object()

    if "mcp_server_tool_wrappers" in config_dict_meta:
        patched_mcp_tool_wrappers.clear()
        patched_mcp_tool_wrappers["before"] = object()

    if "skill_configs" in config_dict_meta:
        patched_skill_configs.clear()
        patched_skill_configs["before"] = object()

    if "agent_capability_types" in config_dict_meta:
        patched_agent_capabilities.clear()
        patched_agent_capabilities["before"] = object()

    if "agent_configs" in config_dict_meta:
        patched_agent_configs.clear()
        patched_agent_configs["before"] = object()

    if "secret_sources" in config_dict_meta:
        patched_secret_sources.clear()
        patched_secret_sources["before"] = object()
        patched_secret_getters.clear()
        patched_secret_getters["before"] = object()

    if "jsonpath_functions" in config_dict_meta:
        patched_jsonpath_functions.clear()
        patched_jsonpath_functions["before"] = object()

    ic_meta = config_meta.InstallationConfigMeta.from_yaml(
        yaml_file,
        config_dict_meta.copy() if config_dict_meta is not None else None,
    )

    assert ic_meta == expected

    if "agui_features" in config_dict_meta:
        assert "before" not in patched_agui_features

        for (af_name, af_found), af_expected in zip(
            patched_agui_features.items(),
            config_dict_meta["agui_features"][1:],  # skip clear
            strict=True,
        ):
            assert af_name == af_expected["name"]
            assert af_found.name == af_expected["name"]
            assert af_found.model_klass == af_expected["model_klass"]
            assert af_found.source == af_expected["source"]

    if "tool_configs" in config_dict_meta:
        assert "before" not in patched_tool_configs
        assert "before" not in patched_mcp_tool_wrappers

        tcs_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass
            for klass in patched_tool_configs.values()
        }
        for klass_name in config_dict_meta["tool_configs"]:
            if klass_name != config_meta.ClearMetaRegistry.MARKER:
                assert (
                    tcs_by_class_name[klass_name].tool_name
                    in patched_tool_configs
                )

    if "mcp_toolset_configs" in config_dict_meta:
        assert "before" not in patched_mcp_toolset_configs

        mtscs_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass
            for klass in patched_mcp_toolset_configs.values()
        }
        for klass_name in config_dict_meta["mcp_toolset_configs"]:
            if klass_name != config_meta.ClearMetaRegistry.MARKER:
                assert (
                    mtscs_by_class_name[klass_name].kind
                    in patched_mcp_toolset_configs
                )

    if "mcp_server_tool_wrappers" in config_dict_meta:
        assert "before" not in patched_mcp_tool_wrappers

        mcptcp_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass
            for klass in patched_mcp_tool_wrappers.values()
        }
        for meta_kw in config_dict_meta["mcp_server_tool_wrappers"]:
            if meta_kw != config_meta.ClearMetaRegistry.MARKER:
                tool_config_klass = _utils._from_dotted_name(
                    meta_kw["config_klass"]
                )
                wrapper_klassname = meta_kw["wrapper_klass"]
                assert (
                    patched_mcp_tool_wrappers[tool_config_klass.tool_name]
                    == mcptcp_by_class_name[wrapper_klassname]
                )

    if "skill_configs" in config_dict_meta:
        assert "before" not in patched_skill_configs

        scs_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass
            for klass in patched_skill_configs.values()
        }
        for klass_name in config_dict_meta["skill_configs"]:
            if klass_name != config_meta.ClearMetaRegistry.MARKER:
                assert (
                    scs_by_class_name[klass_name].kind in patched_skill_configs
                )

    if "agent_capability_types" in config_dict_meta:
        assert "before" not in patched_agent_capabilities

        acts_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass.__name__
            for klass in patched_agent_capabilities.values()
        }
        for klass_name in config_dict_meta["agent_capability_types"]:
            if klass_name != config_meta.ClearMetaRegistry.MARKER:
                short_name = acts_by_class_name[klass_name]
                assert short_name in patched_agent_capabilities

    if "agent_configs" in config_dict_meta:
        assert "before" not in patched_agent_configs

        acs_by_class_name = {
            f"{klass.__module__}.{klass.__name__}": klass
            for klass in patched_agent_configs.values()
        }
        for klass_name in config_dict_meta["agent_configs"]:
            if klass_name != config_meta.ClearMetaRegistry.MARKER:
                kind = acs_by_class_name[klass_name].kind
                assert kind in patched_agent_configs

    if "secret_sources" in config_dict_meta:
        assert "before" not in patched_secret_getters
        assert "before" not in patched_secret_sources

        ss_klass = _test_metaconfig.DummySecretSource
        assert patched_secret_getters == {ss_klass.kind: secret_source_func}
        assert patched_secret_sources == {ss_klass.kind: ss_klass}

    if "jsonpath_functions" in config_dict_meta:
        assert "before" not in patched_jsonpath_functions

        assert authz.registered_jsonpath_functions() == {
            JSONPATH_FUNCTION_NAME: _test_metaconfig.dummy_jsonpath_func
        }
        assert (
            patched_jsonpath_functions[JSONPATH_FUNCTION_NAME]
            is _test_metaconfig.dummy_jsonpath_func
        )


@pytest.mark.parametrize("w_jsonpath", [False, True])
@pytest.mark.parametrize("w_secret_reg", [False, True])
@pytest.mark.parametrize("w_agent", [False, True])
@pytest.mark.parametrize("w_capability", [False, True])
@pytest.mark.parametrize("w_skills", [False, True])
@pytest.mark.parametrize("w_mcp_toolsets", [False, True])
@pytest.mark.parametrize("w_tools", [False, True])
def test_installationconfigmeta_as_yaml(
    patched_soliplex_config,
    patched_agent_configs,
    patched_agent_capabilities,
    patched_skill_configs,
    patched_secret_getters,
    patched_secret_sources,
    patched_agui_features,
    patched_app_routers,
    patched_tool_configs,
    patched_mcp_tool_wrappers,
    patched_mcp_toolset_configs,
    patched_jsonpath_functions,
    w_tools,
    w_mcp_toolsets,
    w_skills,
    w_capability,
    w_agent,
    w_secret_reg,
    w_jsonpath,
):
    patched_soliplex_config["test_secret_func"] = secret_source_func

    first_clear = config_meta.ClearMetaRegistry.MARKER
    expected = {key: [first_clear] for key in BARE_ICMETA_KW}

    if w_tools:
        klass = _test_metaconfig.DummyToolConfig
        patched_tool_configs[klass.tool_name] = klass
        expected["tool_configs"].append(
            "_test_metaconfig.DummyToolConfig",
        )
        wrapper_klass = _test_metaconfig.DummyMCPWrapper
        patched_mcp_tool_wrappers[klass.tool_name] = wrapper_klass
        expected["mcp_server_tool_wrappers"].append(
            {
                "config_klass": "_test_metaconfig.DummyToolConfig",
                "wrapper_klass": "_test_metaconfig.DummyMCPWrapper",
            }
        )

    if w_mcp_toolsets:
        klass = _test_metaconfig.DummyMCP_ToolsetConfig
        patched_mcp_toolset_configs[klass.kind] = klass
        expected["mcp_toolset_configs"].append(
            "_test_metaconfig.DummyMCP_ToolsetConfig",
        )

    if w_skills:
        klass = _test_metaconfig.DummySkillConfig
        patched_skill_configs[klass.kind] = klass
        expected["skill_configs"].append(
            "_test_metaconfig.DummySkillConfig",
        )

    if w_capability:
        klass = _test_metaconfig.DummyAgentCapability
        patched_agent_capabilities[klass.__name__] = klass
        expected["agent_capability_types"].append(
            "_test_metaconfig.DummyAgentCapability",
        )

    if w_agent:
        klass = _test_metaconfig.DummyAgentConfig
        patched_agent_configs[klass.kind] = klass
        expected["agent_configs"].append(
            "_test_metaconfig.DummyAgentConfig",
        )

    if w_secret_reg:
        klass = _test_metaconfig.DummySecretSource
        registered_func = _test_metaconfig.dummy_secret_getter
        patched_secret_getters[klass.kind] = registered_func
        patched_secret_sources[klass.kind] = klass

        expected["secret_sources"].append(
            {
                "config_klass": "_test_metaconfig.DummySecretSource",
                "registered_func": "_test_metaconfig.dummy_secret_getter",
            }
        )

    if w_jsonpath:
        authz.register_jsonpath_function(
            JSONPATH_FUNCTION_NAME, _test_metaconfig.dummy_jsonpath_func
        )
        expected["jsonpath_functions"].append(
            {
                "name": JSONPATH_FUNCTION_NAME,
                "func": "_test_metaconfig.dummy_jsonpath_func",
            }
        )

    icmeta = config_meta.InstallationConfigMeta()

    found = icmeta.as_yaml

    assert found == expected


def test_installationconfigmeta_as_yaml_wo_secret_source_clear(
    patched_secret_sources,
    patched_secret_getters,
):
    # Every import-time kind is registered in both registries, so nothing
    # was suppressed and 'as_yaml' must not ask a reload to clear them.
    for kind in config_secrets.DEFAULT_SECRET_SOURCE_KINDS:
        patched_secret_sources[kind] = _test_metaconfig.DummySecretSource
        patched_secret_getters[kind] = _test_metaconfig.dummy_secret_getter

    found = config_meta.InstallationConfigMeta().as_yaml["secret_sources"]

    assert config_meta.ClearMetaRegistry.MARKER not in found
    assert len(found) == len(config_secrets.DEFAULT_SECRET_SOURCE_KINDS)


def _registry_snapshot():
    """Copy every registry 'InstallationConfigMeta' writes into."""
    return {
        "agui_features": dict(config_agui.AGUI_FEATURES_BY_NAME),
        "tool_configs": dict(
            config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME,
        ),
        "mcp_toolset_configs": dict(
            config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND,
        ),
        "mcp_tool_wrappers": dict(
            config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME,
        ),
        "skill_configs": dict(config_skills.SKILL_CONFIG_CLASSES_BY_KIND),
        "agent_capabilities": dict(
            config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME,
        ),
        "agent_configs": dict(config_agents.AGENT_CONFIG_CLASSES_BY_KIND),
        "secret_getters": dict(config_secrets.SECRET_GETTERS_BY_KIND),
        "jsonpath_functions": dict(authz.registered_jsonpath_functions()),
    }


def _clear_registries():
    """Empty every registry 'InstallationConfigMeta' writes into.

    Registration is purely additive, so without this a dump that dropped
    a whole category would still appear to round-trip: the entries from
    the first load would still be sitting in the registry. Clearing
    between the dump and the reload is what makes the assertion mean
    "'as_yaml' emitted everything needed to rebuild the registries".
    """
    config_agui.AGUI_FEATURES_BY_NAME.clear()
    config_tools.TOOL_CONFIG_CLASSES_BY_TOOL_NAME.clear()
    config_tools.MCP_TOOLSET_CONFIG_CLASSES_BY_KIND.clear()
    config_tools.MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME.clear()
    config_skills.SKILL_CONFIG_CLASSES_BY_KIND.clear()
    config_agents.AGENT_CAPABILITY_CLASSES_BY_NAME.clear()
    config_agents.AGENT_CONFIG_CLASSES_BY_KIND.clear()
    config_secrets.SECRET_GETTERS_BY_KIND.clear()
    config_secrets.SourceClassesByKind.clear()

    # Drop only the config-supplied filters, leaving the RFC 9535
    # built-ins the environment needs.
    function_extensions = authz.the_jsonpath_environment.function_extensions
    for name in authz.registered_jsonpath_functions():
        del function_extensions[name]


def _round_trip_icmeta_registries(config_path, config_dict):
    """Round-trip a metaconfig, snapshotting the registries each time.

    Unlike every other config class, the state under test here is the
    *global registries*, not the instance fields: 'as_yaml' deliberately
    dumps the software-level registry contents rather than the (possibly
    empty) 'meta:' stanza it was loaded from. That asymmetry is correct
    under the "same application state" criterion, so what has to hold is
    that reloading a dump into empty registries rebuilds them exactly --
    and that a second cycle changes nothing further.

    'from_yaml' mutates the mapping it is handed, hence the copies.
    """
    klass = config_meta.InstallationConfigMeta

    original = klass.from_yaml(config_path, copy.deepcopy(config_dict))
    after_load = _registry_snapshot()
    dumped = copy.deepcopy(original.as_yaml)

    _clear_registries()
    reloaded = klass.from_yaml(config_path, dumped)
    after_first = _registry_snapshot()
    dumped_again = copy.deepcopy(reloaded.as_yaml)

    _clear_registries()
    klass.from_yaml(config_path, dumped_again)
    after_second = _registry_snapshot()

    return after_load, after_first, after_second


@pytest.mark.parametrize(
    "config_yaml",
    [
        BARE_ICMETA_YAML,
        # YAML which does not clear the registries
        W_AGUI_FEATURES_ICMETA_YAML,
        W_TOOL_CONFIGS_ICMETA_YAML,
        W_MCP_TOOLSET_CONFIGS_ICMETA_YAML,
        W_SKILL_CONFIGS_ICMETA_YAML,
        W_AGENT_CAPABILITY_ICMETA_YAML,
        W_AGENT_CONFIGS_ICMETA_YAML,
        W_SECRET_SOURCE_ICMETA_YAML,
        W_JSONPATH_FUNCTIONS_ICMETA_YAML,
        FULL_ICMETA_YAML,
        # YAML which already clears the registries
        W_AGUI_FEATURES_W_CLEAR_ICMETA_YAML,
        W_TOOL_CONFIGS_W_CLEAR_ICMETA_YAML,
        W_MCP_TOOLSET_CONFIGS_W_CLEAR_ICMETA_YAML,
        W_SKILL_CONFIGS_W_CLEAR_ICMETA_YAML,
        W_AGENT_CAPABILITY_W_CLEAR_ICMETA_YAML,
        W_AGENT_CONFIGS_W_CLEAR_ICMETA_YAML,
        W_SECRET_SOURCE_W_CLEAR_ICMETA_YAML,
        W_JSONPATH_FUNCTIONS_W_CLEAR_ICMETA_YAML,
    ],
)
def test_installationconfigmeta_as_yaml_round_trips_registries(
    patched_soliplex_config,
    patched_agui_features,
    patched_tool_configs,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    patched_skill_configs,
    patched_agent_capabilities,
    patched_agent_configs,
    patched_secret_getters,
    patched_secret_sources,
    patched_jsonpath_functions,
    temp_dir,
    config_yaml,
):
    # The dumped dotted name for the getter is not the one the YAML was
    # written with -- 'as_yaml' renders it from the function's own
    # '__module__' / '__name__', so 'soliplex.config.test_secret_func'
    # comes back as 'test_config_meta.secret_source_func'. Both resolve
    # to the same object, which is exactly the "same application state,
    # not identical mapping" criterion.
    patched_soliplex_config["test_secret_func"] = secret_source_func
    config_dict = yaml.safe_load(config_yaml)["meta"]

    after_load, after_first, after_second = _round_trip_icmeta_registries(
        temp_dir / "installation.yaml",
        config_dict,
    )

    assert after_first == after_load
    assert after_second == after_first


def test_installationconfigmeta_postinit_registers_tool_configs(
    patched_tool_configs,
):
    tc_klass = _test_metaconfig.DummyToolConfig
    tc_meta = config_meta.ToolConfigMeta(config_klass=tc_klass)

    config_meta.InstallationConfigMeta(tool_configs=[tc_meta])

    assert patched_tool_configs[tc_klass.tool_name] is tc_klass


def test_installationconfigmeta_postinit_registers_mcp_toolset_configs(
    patched_mcp_toolset_configs,
):
    mtc_klass = _test_metaconfig.DummyMCP_ToolsetConfig
    mtc_meta = config_meta.MCP_ToolsetConfigMeta(config_klass=mtc_klass)

    config_meta.InstallationConfigMeta(mcp_toolset_configs=[mtc_meta])

    assert patched_mcp_toolset_configs[mtc_klass.kind] is mtc_klass


@pytest.mark.parametrize(
    "w_tc_registered, expectation",
    [
        (False, pytest.raises(config_meta.WrapperForUnknownToolConfig)),
        (True, contextlib.nullcontext()),
    ],
)
def test_installationconfigmeta_postinit_registers_mcp_tool_wrappers(
    patched_tool_configs,
    patched_mcp_tool_wrappers,
    w_tc_registered,
    expectation,
):
    cfg_klass = _test_metaconfig.DummyToolConfig
    if w_tc_registered:
        patched_tool_configs[cfg_klass.tool_name] = cfg_klass

    wrp_klass = _test_metaconfig.DummyMCPWrapper
    mstw_meta = config_meta.MCP_ServerToolWrapperConfigMeta(
        config_klass=cfg_klass,
        wrapper_klass=wrp_klass,
    )

    with expectation as expected:
        config_meta.InstallationConfigMeta(
            mcp_server_tool_wrappers=[mstw_meta],
        )

    if not isinstance(expected, pytest.ExceptionInfo):
        assert patched_mcp_tool_wrappers[cfg_klass.tool_name] is wrp_klass


def test_installationconfigmeta_postinit_registers_skill_configs(
    patched_skill_configs,
):
    sc_klass = _test_metaconfig.DummySkillConfig
    sc_meta = config_meta.SkillConfigMeta(config_klass=sc_klass)

    config_meta.InstallationConfigMeta(skill_configs=[sc_meta])

    assert patched_skill_configs[sc_klass.kind] is sc_klass


def test_installationconfigmeta_postinit_registers_agent_capabilities(
    patched_agent_capabilities,
):
    cap_klass = _test_metaconfig.DummyAgentCapability
    ac_meta = config_meta.AgentCapabilityMeta(config_klass=cap_klass)

    config_meta.InstallationConfigMeta(agent_capability_types=[ac_meta])

    assert patched_agent_capabilities[cap_klass.__name__] is cap_klass


def test_installationconfigmeta_postinit_registers_agent_configs(
    patched_agent_configs,
):
    ac_klass = _test_metaconfig.DummyAgentConfig
    ac_meta = config_meta.AgentConfigMeta(config_klass=ac_klass)

    config_meta.InstallationConfigMeta(agent_configs=[ac_meta])

    assert patched_agent_configs[ac_klass.kind] is ac_klass


def test_installationconfigmeta_postinit_registers_secret_sources(
    patched_secret_getters,
    patched_secret_sources,
):
    ss_klass = _test_metaconfig.DummySecretSource
    ss_getter = _test_metaconfig.dummy_secret_getter
    ss_meta = config_meta.SecretSourceMeta(
        config_klass=ss_klass,
        registered_func=ss_getter,
    )

    config_meta.InstallationConfigMeta(secret_sources=[ss_meta])

    assert patched_secret_getters[ss_klass.kind] is ss_getter
    assert patched_secret_sources[ss_klass.kind] is ss_klass


def test_installationconfigmeta_postinit_registers_jsonpath_functions(
    patched_jsonpath_functions,
):
    jp_func = _test_metaconfig.dummy_jsonpath_func
    jf_meta = config_meta.JSONPathFunctionConfigMeta(
        name=JSONPATH_FUNCTION_NAME,
        func=jp_func,
    )

    config_meta.InstallationConfigMeta(jsonpath_functions=[jf_meta])

    env = authz.the_jsonpath_environment
    assert env.function_extensions[JSONPATH_FUNCTION_NAME] is jp_func
