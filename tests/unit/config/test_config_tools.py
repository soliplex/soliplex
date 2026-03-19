import copy
import dataclasses
import functools
import inspect
from unittest import mock
from urllib import parse as url_parse

import pytest
import yaml

from soliplex.config import exceptions as config_exc
from soliplex.config import tools as config_tools

BEARER_TOKEN = "FACEDACE"
HTTP_MCP_AUTH_HEADER = {"Authorization": "Bearer secret:BEARER_TOKEN"}
HTTP_MCP_URL = "https://example.com/services/baz/mcp"
HTTP_MCP_QP_KEY = "frob"
HTTP_MCP_QP_VALUE = "secret:BAZQUYTH"
HTTP_MCP_QUERY_PARAMS = {HTTP_MCP_QP_KEY: HTTP_MCP_QP_VALUE}


async def _ai_tools_prepare(_ctx, tool_def):  # pragma: NO COVER
    return tool_def


async def _ai_tools_args_validator(_ctx, _tool_params):  # pragma: NO COVER
    pass


class _AI_Tools_SchemaGenerator:
    pass


class _AI_Tools_FunctionSchema:
    pass


AITP_MAX_RETRIES = 7
AITP_NAME = "test_aitool_params_name"
AITP_DESC = "test aitool_params description"
AITP_DOCSTRING_FORMAT = "sphinx"
AITP_META_KEY = "foo"
AITP_META_VALUE = "bar"
AITP_TIMEOUT = 3.1415
AITP_PREPARE_NAME = "test_prepare"
AITP_ARGS_VALIDATOR_NAME = "test_args_validator"
AITP_SCHEMA_GENERATOR_NAME = "TestSchemaGeneratorKlass"
AITP_FUNCTION_SCHEMA_NAME = "TestFunctionSchemaKlass"

# This one raises
BOGUS_AI_TOOL_PARAMS_YAML = ""

BARE_AI_TOOL_PARAMS_KW = {
    "takes_ctx": False,
}
BARE_AI_TOOL_PARAMS_YAML = """
    takes_ctx: false
"""

FULL_AI_TOOL_PARAMS_KW = {
    "takes_ctx": True,
    "max_retries": AITP_MAX_RETRIES,
    "name": AITP_NAME,
    "description": AITP_DESC,
    "docstring_format": AITP_DOCSTRING_FORMAT,
    "require_parameter_descriptions": True,
    "strict": True,
    "sequential": True,
    "requires_approval": True,
    "metadata": {
        AITP_META_KEY: AITP_META_VALUE,
    },
    "timeout": AITP_TIMEOUT,
    "_prepare": f"soliplex.tools.{AITP_PREPARE_NAME}",
    "_args_validator": f"soliplex.tools.{AITP_ARGS_VALIDATOR_NAME}",
    "_schema_generator": f"soliplex.tools.{AITP_SCHEMA_GENERATOR_NAME}",
    "_function_schema": f"soliplex.tools.{AITP_FUNCTION_SCHEMA_NAME}",
}
FULL_AI_TOOL_PARAMS_YAML = f"""
    takes_ctx: true
    max_retries: {AITP_MAX_RETRIES}
    name: "{AITP_NAME}"
    description: "{AITP_DESC}"
    docstring_format: "{AITP_DOCSTRING_FORMAT}"
    require_parameter_descriptions: true
    strict: true
    sequential: true
    requires_approval: true
    metadata:
        {AITP_META_KEY}: "{AITP_META_VALUE}"
    timeout: {AITP_TIMEOUT}
    prepare: "soliplex.tools.{AITP_PREPARE_NAME}"
    args_validator: "soliplex.tools.{AITP_ARGS_VALIDATOR_NAME}"
    schema_generator: "soliplex.tools.{AITP_SCHEMA_GENERATOR_NAME}"
    function_schema: "soliplex.tools.{AITP_FUNCTION_SCHEMA_NAME}"
"""

TOOL_NAME = "test-tool-name"
TOOL_AGUI_FEATURE_NAME = "test-tool-agui-feature-name"
TOOL_AITP_KWARGS = {"takes_ctx": True}

# This one raises
EMPTY_TOOL_CONFIG_PARAMS_YAML = ""

BOGUS_TOOL_CONFIG_PARAMS_YAML = """
    tool_name: tool_name
    allow_mcp: True
    nonesuch: "BOGUS"
"""

BARE_TOOL_CONFIG_PARAMS_KW = {
    "tool_name": TOOL_NAME,
    "allow_mcp": True,
}
BARE_TOOL_CONFIG_PARAMS_YAML = f"""
    tool_name: {TOOL_NAME}
    allow_mcp: true
"""

W_AGUI_FEATURE_NAME_TOOL_CONFIG_PARAMS_KW = {
    "tool_name": TOOL_NAME,
    "allow_mcp": True,
    "agui_feature_names": (TOOL_AGUI_FEATURE_NAME,),
}
W_AGUI_FEATURE_NAME_TOOL_CONFIG_PARAMS_YAML = f"""
    tool_name: {TOOL_NAME}
    allow_mcp: true
    agui_feature_names:
      - {TOOL_AGUI_FEATURE_NAME}
"""

W_AI_TOOL_PARAMS_TOOL_CONFIG_PARAMS_KW = {
    "tool_name": TOOL_NAME,
    "allow_mcp": True,
    "_ai_tool_params": config_tools.AIToolParams(**TOOL_AITP_KWARGS),
}
W_AI_TOOL_PARAMS_TOOL_CONFIG_PARAMS_YAML = f"""
    tool_name: {TOOL_NAME}
    allow_mcp: true
    ai_tool_params:
        takes_ctx: true
"""


# This one raises
BOGUS_SDTC_CONFIG_YAML = """
    #rag_lancedb_stem: "rag"
    #rag_lancedb_override_path: "/path/to/rag.lancedb"
"""

W_STEM_SDTC_CONFIG_KW = {
    "rag_lancedb_stem": "rag",
    "search_documents_limit": 7,
    "allow_mcp": True,
}
W_STEM_SDTC_CONFIG_YAML = """
    rag_lancedb_stem: "rag"
    search_documents_limit: 7
    allow_mcp: true
"""


W_OVERRIDE_SDTC_CONFIG_KW = {
    "rag_lancedb_override_path": "/path/to/rag.lancedb",
}
W_OVERRIDE_SDTC_CONFIG_YAML = """
    rag_lancedb_override_path: "/path/to/rag.lancedb"
"""

# This one raises
BOGUS_STDIO_MCTC_CONFIG_YAML = ""

BARE_STDIO_MCTC_CONFIG_KW = {
    "command": "cat",
}
BARE_STDIO_MCTC_CONFIG_YAML = """
    command: "cat"
"""

FULL_STDIO_MCTC_CONFIG_KW = {
    "command": "cat",
    "args": [
        "-a",
    ],
    "env": {"FOO": "BAR"},
    "allowed_tools": [
        "some_tool",
    ],
}
FULL_STDIO_MCTC_CONFIG_YAML = """
    command: "cat"
    args:
       - "-a"
    env:
        FOO: "BAR"
    allowed_tools:
      - "some_tool"
"""

# This one raises
BOGUS_HTTP_MCTC_CONFIG_YAML = ""

BARE_HTTP_MCTC_CONFIG_KW = {
    "url": "https://example.com/api",
}
BARE_HTTP_MCTC_CONFIG_YAML = """
    url: "https://example.com/api"
"""

FULL_HTTP_MCTC_CONFIG_KW = {
    "url": "https://example.com/api",
    "headers": {
        "Authorization": "Bearer DEADBEEF",
    },
    "query_params": {
        "foo": "bar",
    },
    "allowed_tools": [
        "some_tool",
    ],
}
FULL_HTTP_MCTC_CONFIG_YAML = """
    url: "https://example.com/api"
    headers:
        Authorization: "Bearer DEADBEEF"
    query_params:
        foo: "bar"
    allowed_tools:
      - "some_tool"
"""


@pytest.fixture
def patched_soliplex_tools():
    to_patch = {
        AITP_PREPARE_NAME: _ai_tools_prepare,
        AITP_ARGS_VALIDATOR_NAME: _ai_tools_args_validator,
        AITP_SCHEMA_GENERATOR_NAME: _AI_Tools_SchemaGenerator,
        AITP_FUNCTION_SCHEMA_NAME: _AI_Tools_FunctionSchema,
    }
    with mock.patch.dict("soliplex.tools.__dict__", **to_patch) as patched:
        yield patched


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_AI_TOOL_PARAMS_YAML, None),
        (BARE_AI_TOOL_PARAMS_YAML, BARE_AI_TOOL_PARAMS_KW),
        (FULL_AI_TOOL_PARAMS_YAML, FULL_AI_TOOL_PARAMS_KW),
    ],
)
def test_aitp_from_yaml(
    temp_dir,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_tools.AIToolParams.from_yaml(
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        aitp = config_tools.AIToolParams.from_yaml(
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config_tools.AIToolParams(
            _config_path=config_path,
            **exp_config,
        )
        assert aitp == expected


@pytest.mark.parametrize(
    "ctor_kwargs",
    [
        BARE_AI_TOOL_PARAMS_KW,
        FULL_AI_TOOL_PARAMS_KW,
    ],
)
def test_aitp_as_yaml(ctor_kwargs):
    expected = copy.deepcopy(ctor_kwargs)

    _prepare = expected.pop("_prepare", None)
    if _prepare is not None:
        expected["prepare"] = _prepare

    _args_validator = expected.pop("_args_validator", None)
    if _args_validator is not None:
        expected["args_validator"] = _args_validator

    _schema_generator = expected.pop("_schema_generator", None)
    if _schema_generator is not None:
        expected["schema_generator"] = _schema_generator

    _function_schema = expected.pop("_function_schema", None)
    if _function_schema is not None:
        expected["function_schema"] = _function_schema

    aitp = config_tools.AIToolParams(**ctor_kwargs)

    found = aitp.as_yaml

    assert found == expected


@pytest.mark.parametrize(
    "ctor_kwargs",
    [
        BARE_AI_TOOL_PARAMS_KW,
        FULL_AI_TOOL_PARAMS_KW,
    ],
)
def test_aitp_as_aitool_ctor_kwargs(patched_soliplex_tools, ctor_kwargs):
    expected = copy.deepcopy(ctor_kwargs)

    _prepare = expected.pop("_prepare", None)
    if _prepare is not None:
        expected["prepare"] = _ai_tools_prepare

    _args_validator = expected.pop("_args_validator", None)
    if _args_validator is not None:
        expected["args_validator"] = _ai_tools_args_validator

    _schema_generator = expected.pop("_schema_generator", None)
    if _schema_generator is not None:
        expected["schema_generator"] = _AI_Tools_SchemaGenerator

    _function_schema = expected.pop("_function_schema", None)
    if _function_schema is not None:
        expected["function_schema"] = _AI_Tools_FunctionSchema

    aitp = config_tools.AIToolParams(**ctor_kwargs)

    found = aitp.as_aitool_ctor_kwargs

    assert found == expected


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (EMPTY_TOOL_CONFIG_PARAMS_YAML, None),
        (BOGUS_TOOL_CONFIG_PARAMS_YAML, None),
        (BARE_TOOL_CONFIG_PARAMS_YAML, BARE_TOOL_CONFIG_PARAMS_KW),
        (
            W_AGUI_FEATURE_NAME_TOOL_CONFIG_PARAMS_YAML,
            W_AGUI_FEATURE_NAME_TOOL_CONFIG_PARAMS_KW,
        ),
        (
            W_AI_TOOL_PARAMS_TOOL_CONFIG_PARAMS_YAML,
            W_AI_TOOL_PARAMS_TOOL_CONFIG_PARAMS_KW,
        ),
    ],
)
def test_toolconfig_from_yaml(
    temp_dir,
    installation_config,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_tools.ToolConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        found = config_tools.ToolConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )

        aitp = exp_config.pop("_ai_tool_params", None)
        if aitp is not None:
            exp_config["_ai_tool_params"] = dataclasses.replace(
                aitp,
                _config_path=config_path,
            )

        expected = config_tools.ToolConfig(
            _config_path=config_path,
            **exp_config,
        )
        assert found == expected


def test_toolconfig_kind():
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.kind == "test_tool"


def test_toolconfig_tool_id():
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.tool_id == "test_tool"


@pytest.mark.parametrize("w_existing", [False, True])
def test_toolconfig_tool(patched_soliplex_tools, w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_tool(ctx, tool_config=None):
        "This is a test"

    patched_soliplex_tools["test_tool"] = test_tool

    if w_existing:
        tool_config = config_tools.ToolConfig(
            tool_name="no.such.animal.exists",
        )
        tool_config._tool = existing
    else:
        tool_config = config_tools.ToolConfig(
            tool_name="soliplex.tools.test_tool",
        )

    found = tool_config.tool

    if w_existing:
        assert found is existing

    else:
        assert found is test_tool


def TEST_TOOL_W_CTX_WO_PARAM_WO_TC(
    ctx,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_WO_TC(
    ctx,
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_WO_PARAM_W_TC(
    ctx,
    tool_config: config_tools.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_W_CTX_W_PARAM_W_TC(
    ctx,
    query: str,
    tool_config: config_tools.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_WO_TC() -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_WO_TC(
    query: str,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_WO_PARAM_W_TC(
    tool_config: config_tools.ToolConfig,
) -> str:
    "This is a test"


def TEST_TOOL_WO_CTX_W_PARAM_W_TC(
    query: str,
    tool_config: config_tools.ToolConfig,
) -> str:
    "This is a test"


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_W_TC,
        TEST_TOOL_W_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_requires_w_conflict(
    patched_soliplex_tools, test_tool
):
    patched_soliplex_tools["test_tool"] = test_tool

    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with pytest.raises(config_tools.ToolRequirementConflict):
        _ = tool_config.tool_requires


@pytest.mark.parametrize(
    "test_tool",
    [
        TEST_TOOL_W_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_W_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_W_PARAM_WO_TC,
        TEST_TOOL_WO_CTX_WO_PARAM_W_TC,
        TEST_TOOL_WO_CTX_W_PARAM_W_TC,
    ],
)
def test_toolconfig_tool_description(patched_soliplex_tools, test_tool):
    patched_soliplex_tools["test_tool"] = test_tool

    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    found = tool_config.tool_description

    assert found == test_tool.__doc__.strip()


@pytest.mark.parametrize(
    "test_tool, expected",
    [
        (
            TEST_TOOL_W_CTX_WO_PARAM_WO_TC,
            config_tools.ToolRequires.FASTAPI_CONTEXT,
        ),
        (
            TEST_TOOL_W_CTX_W_PARAM_WO_TC,
            config_tools.ToolRequires.FASTAPI_CONTEXT,
        ),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, config_tools.ToolRequires.BARE),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, config_tools.ToolRequires.BARE),
        (
            TEST_TOOL_WO_CTX_WO_PARAM_W_TC,
            config_tools.ToolRequires.TOOL_CONFIG,
        ),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, config_tools.ToolRequires.TOOL_CONFIG),
    ],
)
def test_toolconfig_tool_requires(patched_soliplex_tools, test_tool, expected):
    patched_soliplex_tools["test_tool"] = test_tool

    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    found = tool_config.tool_requires

    assert found == expected


@pytest.mark.parametrize(
    "ctor_kwargs, expected",
    [
        (BARE_TOOL_CONFIG_PARAMS_KW, {}),
        (W_AI_TOOL_PARAMS_TOOL_CONFIG_PARAMS_KW, TOOL_AITP_KWARGS),
    ],
)
def test_toolconfig_ai_tool_params(ctor_kwargs, expected):
    tool_config = config_tools.ToolConfig(**ctor_kwargs)

    found = tool_config.ai_tool_params

    assert found == expected


@pytest.mark.parametrize(
    "test_tool, exp_wrapped",
    [
        (TEST_TOOL_W_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_W_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_W_PARAM_WO_TC, False),
        (TEST_TOOL_WO_CTX_WO_PARAM_W_TC, True),
        (TEST_TOOL_WO_CTX_W_PARAM_W_TC, True),
    ],
)
def test_toolconfig_tool_with_config(
    patched_soliplex_tools,
    test_tool,
    exp_wrapped,
):
    patched_soliplex_tools["test_tool"] = test_tool

    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    found = tool_config.tool_with_config

    if exp_wrapped:
        assert isinstance(found, functools.partial)
        assert found.func is test_tool
        assert found.keywords == {"tool_config": tool_config}
        assert found.__name__ == test_tool.__name__
        assert found.__doc__ == test_tool.__doc__

        exp_signature = inspect.signature(test_tool)
        for param in found.__signature__.parameters:
            assert param in exp_signature.parameters

    else:
        assert found is test_tool


def test_toolconfig_get_extra_parameters():
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    assert tool_config.get_extra_parameters() == {}


def test_sdtc_ctor(installation_config, temp_dir):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

    from_stem = db_rag_path / "stem.lancedb"
    from_stem.mkdir()

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    config_path = temp_dir / "rooms" / "test" / "room_config.yaml"

    sdt_config = config_tools.SearchDocumentsToolConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        rag_lancedb_stem="stem",
    )

    assert sdt_config._installation_config is installation_config
    assert sdt_config._config_path == config_path

    found = sdt_config.rag_lancedb_path
    assert found.resolve() == from_stem.resolve()

    expected_ep = {
        "rag_lancedb_path": from_stem.resolve(),
        "search_documents_limit": 5,
    }

    assert sdt_config.get_extra_parameters() == expected_ep


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_SDTC_CONFIG_YAML, None),
        (W_STEM_SDTC_CONFIG_YAML, W_STEM_SDTC_CONFIG_KW),
        (W_OVERRIDE_SDTC_CONFIG_YAML, W_OVERRIDE_SDTC_CONFIG_KW),
    ],
)
def test_sdtc_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    db_rag_dir = temp_dir / "db" / "rag"
    db_rag_dir.mkdir(parents=True)

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_dir)}
    installation_config.get_environment = ic_environ.get

    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_tools.SearchDocumentsToolConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        sdt_config = config_tools.SearchDocumentsToolConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config_tools.SearchDocumentsToolConfig(
            _installation_config=installation_config,
            _config_path=config_path,
            **exp_config,
        )
        assert sdt_config == expected


@pytest.mark.parametrize(
    "stem, override, which",
    [
        ("testing", None, "stem"),
        (None, "./override", "override"),
    ],
)
def test_sdtc_get_extra_parameters_w_missing_file(
    installation_config,
    temp_dir,
    stem,
    override,
    which,
):
    db_rag_path = temp_dir / "db" / "rag"
    db_rag_path.mkdir(parents=True)

    if which == "stem":
        exp_filename = db_rag_path / f"{stem}.lancedb"
    else:
        exp_filename = temp_dir / override

    ic_environ = {"RAG_LANCE_DB_PATH": str(db_rag_path)}
    installation_config.get_environment = ic_environ.get

    kw = {
        "_installation_config": installation_config,
        "_config_path": temp_dir / "room_config.yaml",
    }

    if stem is not None:
        kw["rag_lancedb_stem"] = stem

    if override is not None:
        kw["rag_lancedb_override_path"] = override

    sdt_config = config_tools.SearchDocumentsToolConfig(**kw)

    ep = sdt_config.get_extra_parameters()

    assert ep["rag_lancedb_path"] == f"MISSING: {exp_filename.resolve()}"


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_STDIO_MCTC_CONFIG_YAML, None),
        (BARE_STDIO_MCTC_CONFIG_YAML, BARE_STDIO_MCTC_CONFIG_KW),
        (FULL_STDIO_MCTC_CONFIG_YAML, FULL_STDIO_MCTC_CONFIG_KW),
    ],
)
def test_stdio_mctc_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_tools.Stdio_MCP_ClientToolsetConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        stdio_mctc = config_tools.Stdio_MCP_ClientToolsetConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config_tools.Stdio_MCP_ClientToolsetConfig(
            _installation_config=installation_config,
            _config_path=config_path,
            **exp_config,
        )
        assert stdio_mctc == expected


@pytest.mark.parametrize("w_env", [{}, {"foo": "bar"}])
def test_stdio_mctc_toolset_params(w_env):
    stdio_mctc = config_tools.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
    )

    found = stdio_mctc.toolset_params

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["env"] == stdio_mctc.env
    assert found["allowed_tools"] == stdio_mctc.allowed_tools


@pytest.mark.parametrize("w_env", [{}, {"FOO_KEY": "secret:FOO_KEY"}])
def test_stdio_mctc_tool_kwargs(installation_config, w_env):
    stdio_mctc = config_tools.Stdio_MCP_ClientToolsetConfig(
        command="cat",
        args=["-"],
        env=w_env,
        _installation_config=installation_config,
    )

    found = stdio_mctc.tool_kwargs

    assert found["command"] == stdio_mctc.command
    assert found["args"] == stdio_mctc.args
    assert found["allowed_tools"] == stdio_mctc.allowed_tools

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["env"].items(),
        w_env.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.get_secret.return_value
        assert (
            mock.call(cfg_value)
            in installation_config.get_secret.call_args_list
        )


@pytest.mark.parametrize(
    "config_yaml, exp_config",
    [
        (BOGUS_HTTP_MCTC_CONFIG_YAML, None),
        (BARE_HTTP_MCTC_CONFIG_YAML, BARE_HTTP_MCTC_CONFIG_KW),
        (FULL_HTTP_MCTC_CONFIG_YAML, FULL_HTTP_MCTC_CONFIG_KW),
    ],
)
def test_http_mctc_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    exp_config,
):
    config_dir = temp_dir / "rooms" / "test_room"
    config_dir.mkdir(parents=True)

    config_path = config_dir / "room_config.yaml"
    config_path.write_text(config_yaml)

    with config_path.open() as stream:
        config_dict = yaml.safe_load(stream)

    if exp_config is None:
        with pytest.raises(config_exc.FromYamlException) as exc:
            config_tools.HTTP_MCP_ClientToolsetConfig.from_yaml(
                installation_config=installation_config,
                config_path=config_path,
                config_dict=config_dict,
            )

        assert exc.value._config_path == config_path

    else:
        http_mctc = config_tools.HTTP_MCP_ClientToolsetConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=config_dict,
        )
        expected = config_tools.HTTP_MCP_ClientToolsetConfig(
            _installation_config=installation_config,
            _config_path=config_path,
            **exp_config,
        )
        assert http_mctc == expected


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_toolset_params(w_query_params, w_headers):
    http_mctc = config_tools.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
    )

    found = http_mctc.toolset_params

    assert found["url"] == http_mctc.url
    assert found["query_params"] == http_mctc.query_params
    assert found["headers"] == http_mctc.headers
    assert found["allowed_tools"] == http_mctc.allowed_tools


@pytest.mark.parametrize("w_headers", [{}, HTTP_MCP_AUTH_HEADER])
@pytest.mark.parametrize("w_query_params", [{}, HTTP_MCP_QUERY_PARAMS])
def test_http_mctc_tool_kwargs(
    installation_config,
    w_query_params,
    w_headers,
):
    installation_config.get_secret.return_value = "<secret>"
    installation_config.interpolate_secrets.return_value = "<interp>"

    http_mctc = config_tools.HTTP_MCP_ClientToolsetConfig(
        url=HTTP_MCP_URL,
        headers=w_headers,
        query_params=w_query_params,
        _installation_config=installation_config,
    )

    found = http_mctc.tool_kwargs

    assert found["allowed_tools"] == http_mctc.allowed_tools

    if w_query_params:
        base, qs = found["url"].split("?")
        assert base == http_mctc.url

        qp_dict = dict(url_parse.parse_qsl(qs))

        for (f_key, f_val), (cfg_key, cfg_value) in zip(
            qp_dict.items(),
            w_query_params.items(),
            strict=True,
        ):
            assert f_key == cfg_key
            assert f_val == installation_config.get_secret.return_value
            assert (
                mock.call(cfg_value)
                in installation_config.get_secret.call_args_list
            )

    else:
        assert found["url"] == http_mctc.url

    for (f_key, f_val), (cfg_key, cfg_value) in zip(
        found["headers"].items(),
        w_headers.items(),
        strict=True,
    ):
        assert f_key == cfg_key
        assert f_val is installation_config.interpolate_secrets.return_value
        assert (
            mock.call(cfg_value)
            in installation_config.interpolate_secrets.call_args_list
        )


def test_noargsmcpwrapper_call():
    func = mock.Mock(spec_set=())
    tool_config = mock.create_autospec(config_tools.ToolConfig)

    wrapper = config_tools.NoArgsMCPWrapper(func=func, tool_config=tool_config)

    found = wrapper()

    assert found is func.return_value
    func.assert_called_once_with(tool_config=tool_config)


def test_withquerymcpwrapper_call():
    func = mock.Mock(spec_set=())
    tool_config = mock.create_autospec(config_tools.ToolConfig)

    wrapper = config_tools.WithQueryMCPWrapper(
        func=func, tool_config=tool_config
    )

    found = wrapper(query="text")

    assert found is func.return_value
    func.assert_called_once_with("text", tool_config=tool_config)
