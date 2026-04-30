from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib

from . import _utils
from . import agents as config_agents
from . import tools as config_tools

_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_default_dict_field = _utils._default_dict_field

# ============================================================================
#   Completions endpoint-related configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
class CompletionConfig:
    """Configuration for a completion endpoint."""

    #
    # Required metadata
    #
    id: str
    agent_config: config_agents.AgentConfig

    name: str = None

    #
    # Tool options
    #
    tool_configs: config_tools.ToolConfigMap = _default_dict_field()
    mcp_client_toolset_configs: config_tools.MCP_ClientToolsetConfigMap = (
        _default_dict_field()
    )

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycles
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        config_dict["_installation_config"] = installation_config
        config_dict["_config_path"] = config_path

        completion_id = config_dict["id"]

        if "name" not in config_dict:
            config_dict["name"] = completion_id

        agent_config_yaml = config_dict.pop("agent")
        agent_config_yaml["id"] = f"completion-{completion_id}"

        config_dict["agent_config"] = config_agents.extract_agent_config(
            installation_config,
            config_path,
            agent_config_yaml,
        )

        config_dict["tool_configs"] = config_tools.extract_tool_configs(
            installation_config,
            config_path,
            config_dict,
        )

        config_dict["mcp_client_toolset_configs"] = (
            config_tools.extract_mcp_client_toolset_configs(
                installation_config,
                config_path,
                config_dict,
            )
        )

        return cls(**config_dict)


CompletionConfigMap = dict[str, CompletionConfig]
