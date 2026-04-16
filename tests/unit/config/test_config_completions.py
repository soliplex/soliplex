import dataclasses

import pytest
import yaml

from soliplex.config import agents as config_agents
from soliplex.config import completions as config_completions
from soliplex.config import tools as config_tools
from tests.unit.config import test_config_agents as test_agents
from tests.unit.config import test_config_tools as test_tools

COMPLETION_ID = "test-completion"
COMPLETION_NAME = "Test Completions"

BARE_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "agent_config": config_agents.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        model_name=test_agents.MODEL_NAME,
        system_prompt=test_agents.SYSTEM_PROMPT,
    ),
}
BARE_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
agent:
    model_name: "{test_agents.MODEL_NAME}"
    system_prompt: "{test_agents.SYSTEM_PROMPT}"
"""

FULL_COMPLETION_CONFIG_KW = {
    "id": COMPLETION_ID,
    "name": COMPLETION_NAME,
    "agent_config": config_agents.AgentConfig(
        id=f"completion-{COMPLETION_ID}",
        model_name=test_agents.MODEL_NAME,
        system_prompt=test_agents.SYSTEM_PROMPT,
    ),
    "tool_configs": {
        "get_current_datetime": config_tools.ToolConfig(
            tool_name="soliplex.tools.get_current_datetime",
        ),
    },
    "mcp_client_toolset_configs": {
        "stdio_test": config_tools.Stdio_MCP_ClientToolsetConfig(
            command="cat",
            args=[
                "-",
            ],
            env={
                "foo": "bar",
            },
        ),
        "http_test": config_tools.HTTP_MCP_ClientToolsetConfig(
            url=test_tools.HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=test_tools.HTTP_MCP_QUERY_PARAMS,
        ),
        "sse_test": config_tools.SSE_MCP_ClientToolsetConfig(
            url=test_tools.HTTP_MCP_URL,
            headers={
                "Authorization": "Bearer secret:BEARER_TOKEN",
            },
            query_params=test_tools.HTTP_MCP_QUERY_PARAMS,
        ),
    },
}
FULL_COMPLETION_CONFIG_YAML = f"""\
id: "{COMPLETION_ID}"
name: "{COMPLETION_NAME}"
agent:
    model_name: "{test_agents.MODEL_NAME}"
    system_prompt: "{test_agents.SYSTEM_PROMPT}"
tools:
    - tool_name: "soliplex.tools.get_current_datetime"
mcp_client_toolsets:
    stdio_test:
      kind: "stdio"
      command: "cat"
      args:
        - "-"
      env:
        foo: "bar"
    http_test:
      kind: "http"
      url: "{test_tools.HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {test_tools.HTTP_MCP_QP_KEY}: "{test_tools.HTTP_MCP_QP_VALUE}"
    sse_test:
      kind: "sse"
      url: "{test_tools.HTTP_MCP_URL}"
      headers:
        Authorization: "Bearer secret:BEARER_TOKEN"
      query_params:
        {test_tools.HTTP_MCP_QP_KEY}: "{test_tools.HTTP_MCP_QP_VALUE}"
"""


@pytest.mark.parametrize(
    "config_yaml, expected_kw",
    [
        (BARE_COMPLETION_CONFIG_YAML, BARE_COMPLETION_CONFIG_KW),
        (FULL_COMPLETION_CONFIG_YAML, FULL_COMPLETION_CONFIG_KW),
    ],
)
def test_completionconfig_from_yaml(
    installation_config,
    temp_dir,
    config_yaml,
    expected_kw,
):
    if "name" not in expected_kw:
        expected_kw = expected_kw.copy()
        expected_kw["name"] = expected_kw["id"]

    expected = config_completions.CompletionConfig(**expected_kw)

    yaml_file = temp_dir / "test.yaml"
    yaml_file.write_text(config_yaml)
    expected = dataclasses.replace(
        expected,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )
    expected.agent_config = dataclasses.replace(
        expected.agent_config,
        _installation_config=installation_config,
        _config_path=yaml_file,
    )

    if len(expected_kw.get("tool_configs", {})) > 0:
        for tool_config in expected_kw["tool_configs"].values():
            tool_config._installation_config = installation_config
            tool_config._config_path = yaml_file

    if len(expected_kw.get("mcp_client_toolset_configs", {})) > 0:
        for mcts_config in expected_kw["mcp_client_toolset_configs"].values():
            mcts_config._installation_config = installation_config
            mcts_config._config_path = yaml_file

    with yaml_file.open() as stream:
        config_dict = yaml.safe_load(stream)

    found = config_completions.CompletionConfig.from_yaml(
        installation_config,
        yaml_file,
        config_dict,
    )

    assert found == expected
