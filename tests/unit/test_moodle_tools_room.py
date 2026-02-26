"""Verify the Moodle Workplace (Tool Calling) room config loads."""

import pathlib
from unittest import mock

import yaml

from soliplex import config

ROOM_CONFIG_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "example"
    / "rooms"
    / "moodle-tools"
    / "room_config.yaml"
)


def test_moodle_tools_room_config_loads():
    installation_config = mock.create_autospec(config.InstallationConfig)
    installation_config.get_environment.return_value = None
    installation_config.agent_configs = []

    with ROOM_CONFIG_PATH.open() as f:
        config_dict = yaml.safe_load(f)

    room = config.RoomConfig.from_yaml(
        installation_config,
        ROOM_CONFIG_PATH,
        config_dict,
    )

    assert room.id == "moodle-tools"
    assert room.name == "Moodle Workplace (Tool Calling)"
    assert room.allow_mcp is False
    assert room.mcp_client_toolset_configs == {}

    agent_cfg = room.agent_config
    assert isinstance(agent_cfg, config.FactoryAgentConfig)
    assert agent_cfg.factory_name == (
        "soliplex.moodle.agent.moodle_tools_agent_factory"
    )
    assert agent_cfg.with_agent_config is True
    assert agent_cfg.extra_config == {
        "moodle_base_url": "secret:MOODLE_BASE_URL",
        "moodle_api_token": "secret:MOODLE_API_TOKEN",
    }
