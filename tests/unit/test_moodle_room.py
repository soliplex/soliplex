"""Verify the Moodle Workplace room config loads correctly."""

import pathlib
from unittest import mock

import yaml

from soliplex import config

ROOM_CONFIG_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "example"
    / "rooms"
    / "moodle"
    / "room_config.yaml"
)


def test_moodle_room_config_loads():
    installation_config = mock.create_autospec(
        config.InstallationConfig
    )
    installation_config.get_environment.return_value = None

    # The room uses template_id: "default_chat", so we need
    # a matching agent config in the installation.
    template = config.AgentConfig(
        id="default_chat",
        model_name="gpt-oss:latest",
        system_prompt="template prompt",
        _installation_config=installation_config,
    )
    installation_config.agent_configs = [template]

    with ROOM_CONFIG_PATH.open() as f:
        config_dict = yaml.safe_load(f)

    room = config.RoomConfig.from_yaml(
        installation_config,
        ROOM_CONFIG_PATH,
        config_dict,
    )

    assert room.id == "moodle"
    assert room.name == "Moodle Workplace"
    assert room.allow_mcp is False
    assert "moodle" in room.mcp_client_toolset_configs

    mcp_cfg = room.mcp_client_toolset_configs["moodle"]
    assert isinstance(
        mcp_cfg, config.Stdio_MCP_ClientToolsetConfig
    )
    assert mcp_cfg.command == "python"
    assert mcp_cfg.args == ["-m", "moodle_mcp"]
    assert mcp_cfg.env == {
        "MOODLE_BASE_URL": "secret:MOODLE_BASE_URL",
        "MOODLE_API_TOKEN": "secret:MOODLE_API_TOKEN",
    }
