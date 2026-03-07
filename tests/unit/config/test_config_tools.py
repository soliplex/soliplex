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


def test_toolconfig_from_yaml_w_error(temp_dir, installation_config):
    tool_name = "soliplex.tools.test_tool"
    config_path = temp_dir / "thing_config.yaml"

    with pytest.raises(config_exc.FromYamlException) as exc_info:
        config_tools.ToolConfig.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict={
                "tool_name": tool_name,
                "allow_mcp": True,
                "nonesuch": "BOGUS",
            },
        )

    assert exc_info.value._config_path == config_path


@pytest.mark.parametrize(
    "w_feature_names, exp_feature_names",
    [
        (None, ()),
        (["foo"], ("foo",)),
    ],
)
def test_toolconfig_from_yaml(
    installation_config,
    temp_dir,
    w_feature_names,
    exp_feature_names,
):
    tool_name = "soliplex.tools.test_tool"
    config_path = temp_dir / "thing_config.yaml"

    expected = config_tools.ToolConfig(
        _installation_config=installation_config,
        _config_path=config_path,
        tool_name=tool_name,
        allow_mcp=True,
        agui_feature_names=exp_feature_names,
    )

    config_dict = {
        "tool_name": tool_name,
        "allow_mcp": True,
    }

    if w_feature_names is not None:
        config_dict["agui_feature_names"] = w_feature_names

    tool_config = config_tools.ToolConfig.from_yaml(
        installation_config=installation_config,
        config_path=config_path,
        config_dict=config_dict,
    )

    assert tool_config == expected


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
def test_toolconfig_tool(w_existing):
    def existing():  # pragma: NO COVER
        pass

    def test_tool(ctx, tool_config=None):
        "This is a test"

    if w_existing:
        tool_config = config_tools.ToolConfig(
            tool_name="no.such.animal.exists",
        )
        tool_config._tool = existing
    else:
        tool_config = config_tools.ToolConfig(
            tool_name="soliplex.tools.test_tool",
        )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
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
def test_toolconfig_tool_requires_w_conflict(test_tool):
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
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
def test_toolconfig_tool_description(test_tool):
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
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
def test_toolconfig_tool_requires(test_tool, expected):
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
        found = tool_config.tool_requires

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
def test_toolconfig_tool_with_config(test_tool, exp_wrapped):
    tool_config = config_tools.ToolConfig(
        tool_name="soliplex.tools.test_tool",
    )

    with mock.patch.dict("soliplex.tools.__dict__", test_tool=test_tool):
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
