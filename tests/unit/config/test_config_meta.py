import contextlib
import copy
import warnings
from unittest import mock

import _test_features as agui_features
import _test_metaconfig
import pytest
import yaml

from soliplex import authz
from soliplex.config import _utils
from soliplex.config import exceptions as config_exc
from soliplex.config import meta as config_meta

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

SECRET_SOURCE_FUNC = lambda source: "SEEKRIT"  # noqa E731
W_SECRET_SOURCE_ICMETA_KW = BARE_ICMETA_KW | {
    "secret_sources": [
        config_meta.SecretSourceMeta(
            config_klass=_test_metaconfig.DummySecretSource,
            registered_func=SECRET_SOURCE_FUNC,
        ),
    ],
}
W_SECRET_SOURCE_ICMETA_YAML = """\
meta:
  secret_sources:
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
            registered_func=SECRET_SOURCE_FUNC,
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


def test_configmeta_from_yaml_w_importable_name():
    config_yaml = "_test_metaconfig.DummyConfigClass"

    with warnings.catch_warnings(record=True) as warned:
        meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is _test_metaconfig.DummyConfigClass
    assert meta.wrapper_klass is None
    assert meta.registered_func is None

    (warning,) = warned
    assert str(warning.message) == config_meta.CONFIG_META_DEPRECATED
    assert warning.category is DeprecationWarning


@pytest.mark.parametrize("w_regfunc", [False, True])
@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict(w_wrapper, w_regfunc):
    config_klass = mock.Mock()
    wrapper_klass = mock.Mock()
    registered_func = mock.Mock()

    config_yaml = {"config_klass": config_klass}

    if w_wrapper:
        config_yaml["wrapper_klass"] = wrapper_klass

    if w_regfunc:
        config_yaml["registered_func"] = registered_func

    with warnings.catch_warnings(record=True) as warned:
        meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is config_klass

    if w_wrapper:
        assert meta.wrapper_klass is wrapper_klass
    else:
        assert meta.wrapper_klass is None

    if w_regfunc:
        assert meta.registered_func is registered_func
    else:
        assert meta.registered_func is None

    (warning,) = warned
    assert str(warning.message) == config_meta.CONFIG_META_DEPRECATED
    assert warning.category is DeprecationWarning


@pytest.mark.parametrize("w_regfunc", [False, True])
@pytest.mark.parametrize("w_wrapper", [False, True])
def test_configmeta_from_yaml_w_dict_w_names(
    w_wrapper,
    w_regfunc,
):
    config_yaml = {"config_klass": "_test_metaconfig.DummyConfigClass"}

    if w_wrapper:
        config_yaml["wrapper_klass"] = "_test_metaconfig.DummyWrapperClass"

    if w_regfunc:
        config_yaml["registered_func"] = "_test_metaconfig.dummy_jsonpath_func"

    with warnings.catch_warnings(record=True) as warned:
        meta = config_meta.ConfigMeta.from_yaml(config_yaml)

    assert meta.config_klass is _test_metaconfig.DummyConfigClass

    if w_wrapper:
        assert meta.wrapper_klass is _test_metaconfig.DummyWrapperClass
    else:
        assert meta.wrapper_klass is None

    if w_regfunc:
        assert meta.registered_func is _test_metaconfig.dummy_jsonpath_func
    else:
        assert meta.registered_func is None

    (warning,) = warned
    assert str(warning.message) == config_meta.CONFIG_META_DEPRECATED
    assert warning.category is DeprecationWarning


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


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
        {"registered_func": "dummy.nonesuch_func"},
        {
            "wrapper_klass": "dummy.nonesuch_wrapper",
            "registered_func": "dummy.nonesuch_func",
        },
    ],
)
@pytest.mark.parametrize("w_bare_str", [False, True])
def test_toolconfigmeta_from_yaml(w_bare_str, w_depr_kw):
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"

    if w_bare_str:
        yaml_config = tool_config_klassname
    else:
        yaml_config = {
            "config_klass": tool_config_klassname,
        } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.ToolConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.tool_name == _test_metaconfig.DummyToolConfig.tool_name

    if not w_bare_str:
        assert len(warned) == len(w_depr_kw)

        messages = []
        for warning in warned:
            assert warning.category is DeprecationWarning
            messages.append(str(warning.message))

        for key in w_depr_kw:
            assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
        {"registered_func": "dummy.nonesuch_func"},
        {
            "wrapper_klass": "dummy.nonesuch_wrapper",
            "registered_func": "dummy.nonesuch_func",
        },
    ],
)
@pytest.mark.parametrize("w_bare_str", [False, True])
def test_mcp_toolsetconfigmeta_from_yaml(w_bare_str, w_depr_kw):
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"

    if w_bare_str:
        yaml_config = tool_config_klassname
    else:
        yaml_config = {
            "config_klass": tool_config_klassname,
        } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.MCP_ToolsetConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.kind == _test_metaconfig.DummyToolConfig.kind

    if not w_bare_str:
        assert len(warned) == len(w_depr_kw)

        messages = []
        for warning in warned:
            assert warning.category is DeprecationWarning
            messages.append(str(warning.message))

        for key in w_depr_kw:
            assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"registered_func": "dummy.nonesuch_func"},
    ],
)
def test_mcp_servertoolwrapperconfigmeta_from_yaml(w_depr_kw):
    tool_config_klassname = "_test_metaconfig.DummyToolConfig"
    wrapper_klassname = "_test_metaconfig.DummyMCPWrapper"

    yaml_config = {
        "config_klass": tool_config_klassname,
        "wrapper_klass": wrapper_klassname,
    } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.MCP_ServerToolWrapperConfigMeta.from_yaml(
            yaml_config,
        )

    assert found.config_klass is _test_metaconfig.DummyToolConfig
    assert found.wrapper_klass is _test_metaconfig.DummyMCPWrapper
    assert found.tool_name == _test_metaconfig.DummyToolConfig.tool_name

    assert len(warned) == len(w_depr_kw)

    messages = []
    for warning in warned:
        assert warning.category is DeprecationWarning
        messages.append(str(warning.message))

    for key in w_depr_kw:
        assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
        {"registered_func": "dummy.nonesuch_func"},
        {
            "wrapper_klass": "dummy.nonesuch_wrapper",
            "registered_func": "dummy.nonesuch_func",
        },
    ],
)
@pytest.mark.parametrize("w_bare_str", [False, True])
def test_skillconfigmeta_from_yaml(w_bare_str, w_depr_kw):
    skill_config_klassname = "_test_metaconfig.DummySkillConfig"

    if w_bare_str:
        yaml_config = skill_config_klassname
    else:
        yaml_config = {
            "config_klass": skill_config_klassname,
        } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.SkillConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummySkillConfig
    assert found.kind == _test_metaconfig.DummySkillConfig.kind

    if not w_bare_str:
        assert len(warned) == len(w_depr_kw)

        messages = []
        for warning in warned:
            assert warning.category is DeprecationWarning
            messages.append(str(warning.message))

        for key in w_depr_kw:
            assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
        {"registered_func": "dummy.nonesuch_func"},
        {
            "wrapper_klass": "dummy.nonesuch_wrapper",
            "registered_func": "dummy.nonesuch_func",
        },
    ],
)
@pytest.mark.parametrize("w_bare_str", [False, True])
def test_agentcapabilityconfigmeta_from_yaml(w_bare_str, w_depr_kw):
    capability_klassname = "_test_metaconfig.DummyAgentCapability"
    exp_cap_klass = _test_metaconfig.DummyAgentCapability

    if w_bare_str:
        yaml_config = capability_klassname
    else:
        yaml_config = {
            "config_klass": capability_klassname,
        } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.AgentCapabilityMeta.from_yaml(yaml_config)

    assert found.config_klass is exp_cap_klass
    assert found.capability_name == exp_cap_klass.__name__

    if not w_bare_str:
        assert len(warned) == len(w_depr_kw)

        messages = []
        for warning in warned:
            assert warning.category is DeprecationWarning
            messages.append(str(warning.message))

        for key in w_depr_kw:
            assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
        {"registered_func": "dummy.nonesuch_func"},
        {
            "wrapper_klass": "dummy.nonesuch_wrapper",
            "registered_func": "dummy.nonesuch_func",
        },
    ],
)
@pytest.mark.parametrize("w_bare_str", [False, True])
def test_agentconfigmeta_from_yaml(w_bare_str, w_depr_kw):
    agent_config_klassname = "_test_metaconfig.DummyAgentConfig"

    if w_bare_str:
        yaml_config = agent_config_klassname
    else:
        yaml_config = {
            "config_klass": agent_config_klassname,
        } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.AgentConfigMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummyAgentConfig
    assert found.kind == _test_metaconfig.DummyAgentConfig.kind

    if not w_bare_str:
        assert len(warned) == len(w_depr_kw)

        messages = []
        for warning in warned:
            assert warning.category is DeprecationWarning
            messages.append(str(warning.message))

        for key in w_depr_kw:
            assert any(key in message for message in messages)


@pytest.mark.parametrize(
    "w_depr_kw",
    [
        {},
        {"wrapper_klass": "dummy.nonesuch_wrapper"},
    ],
)
def test_secretsourcemeta_from_yaml(w_depr_kw):
    secret_source_klassname = "_test_metaconfig.DummySecretSource"
    registered_funcname = "_test_metaconfig.dummy_secret_getter"

    yaml_config = {
        "config_klass": secret_source_klassname,
        "registered_func": registered_funcname,
    } | w_depr_kw

    with warnings.catch_warnings(record=True) as warned:
        found = config_meta.SecretSourceMeta.from_yaml(yaml_config)

    assert found.config_klass is _test_metaconfig.DummySecretSource
    assert found.registered_func is _test_metaconfig.dummy_secret_getter
    assert found.kind == _test_metaconfig.DummySecretSource.kind

    assert len(warned) == len(w_depr_kw)

    messages = []
    for warning in warned:
        assert warning.category is DeprecationWarning
        messages.append(str(warning.message))

    for key in w_depr_kw:
        assert any(key in message for message in messages)


def test_jsonpathfunctionconfigmeta_from_yaml():
    meta = config_meta.JSONPathFunctionConfigMeta.from_yaml(
        {"name": "is_admin", "func": "_test_metaconfig.dummy_jsonpath_func"}
    )

    assert meta.name == "is_admin"
    assert meta.func is _test_metaconfig.dummy_jsonpath_func


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
    patched_skill_configs,
    patched_agent_capabilities,
    patched_agent_configs,
    patched_secret_getters,
    patched_secret_sources,
    patched_agui_features,
    patched_app_routers,
    patched_tool_configs,
    patched_mcp_toolset_configs,
    patched_mcp_tool_wrappers,
    patched_jsonpath_functions,
    config_yaml,
    expected_kw,
):
    patched_soliplex_config["test_secret_func"] = SECRET_SOURCE_FUNC
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
                ss_klass.kind: SECRET_SOURCE_FUNC
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
    patched_soliplex_config["test_secret_func"] = SECRET_SOURCE_FUNC

    expected = copy.deepcopy(BARE_ICMETA_KW)

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
