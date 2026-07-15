"""Round-trip tests for the config ``as_yaml`` serializers.

Each test loads a real example configuration, dumps it back to YAML via the
``as_yaml`` serializer, reloads the dumped copy, and asserts that the second
load serializes identically to the first.  This exercises the ``from_yaml``
<-> ``as_yaml`` round trip end-to-end against on-disk example files.

The dump is written to a scratch directory in a different location than the
source, so the round trip also proves that ``as_yaml`` emits location-
independent (resolved) paths that survive a reload from elsewhere.
"""

import os
import pathlib
from unittest import mock

import pytest
import yaml

from soliplex.config import installation as config_installation
from soliplex.config import rooms as config_rooms

MINIMAL_CONFIG = pathlib.Path("example/minimal.yaml")
OLLAMA_BASE_URL = "http://ollama.example.com:11434"


@pytest.fixture(scope="module")
def os_env_with_ollama_base_url():
    with mock.patch.dict(os.environ, clear=True) as patched:
        patched["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
        yield patched


def _minimal_room_ids():
    with mock.patch.dict(os.environ, clear=True) as patched:
        patched["OLLAMA_BASE_URL"] = OLLAMA_BASE_URL
        installation = config_installation.load_installation(MINIMAL_CONFIG)
        return sorted(installation.room_configs)


@pytest.fixture(scope="module")
def minimal_installation(os_env_with_ollama_base_url):
    return config_installation.load_installation(MINIMAL_CONFIG)


def test_installation_config_roundtrips(tmp_path):
    original = config_installation.load_installation(MINIMAL_CONFIG)
    dumped_path = tmp_path / "installation.yaml"
    dumped_path.write_text(yaml.safe_dump(original.as_yaml))

    reloaded = config_installation.load_installation(dumped_path)

    assert reloaded.as_yaml == original.as_yaml


@pytest.mark.parametrize("room_id", _minimal_room_ids())
def test_room_config_roundtrips(
    tmp_path,
    minimal_installation,
    room_id,
):
    original = minimal_installation.room_configs[room_id]
    dumped_path = tmp_path / "room_config.yaml"
    dumped_path.write_text(yaml.safe_dump(original.as_yaml))

    reloaded = config_rooms.RoomConfig.from_yaml(
        minimal_installation,
        dumped_path,
        yaml.safe_load(dumped_path.read_text()),
    )

    assert reloaded.as_yaml == original.as_yaml
