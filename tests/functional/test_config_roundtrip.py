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


AGUI_SSE_DELIVERY_BLOCK = {
    "strategy": "bounded",
    "max_deltas": 8,
    "max_bytes": 256,
    "max_ms": 250,
}


def test_installation_config_roundtrips_w_agui_sse_delivery(
    tmp_path,
    os_env_with_ollama_base_url,
):
    original = config_installation.load_installation(MINIMAL_CONFIG)
    dumped = original.as_yaml | {"agui_sse_delivery": AGUI_SSE_DELIVERY_BLOCK}
    dumped_path = tmp_path / "installation.yaml"
    dumped_path.write_text(yaml.safe_dump(dumped))

    reloaded = config_installation.load_installation(dumped_path)

    assert reloaded.as_yaml == dumped
    for room_config in reloaded.room_configs.values():
        assert "agui_sse_delivery" not in room_config.as_yaml
        assert room_config.effective_agui_sse_delivery == (
            reloaded.agui_sse_delivery
        )


@pytest.mark.parametrize("room_id", _minimal_room_ids())
def test_room_config_roundtrips_w_agui_sse_delivery(
    tmp_path,
    minimal_installation,
    room_id,
):
    original = minimal_installation.room_configs[room_id]
    dumped = original.as_yaml | {"agui_sse_delivery": {"strategy": "message"}}
    dumped_path = tmp_path / "room_config.yaml"
    dumped_path.write_text(yaml.safe_dump(dumped))

    reloaded = config_rooms.RoomConfig.from_yaml(
        minimal_installation,
        dumped_path,
        yaml.safe_load(dumped_path.read_text()),
    )

    assert reloaded.as_yaml == dumped
    assert reloaded.effective_agui_sse_delivery.as_yaml == {
        "strategy": "message",
    }
