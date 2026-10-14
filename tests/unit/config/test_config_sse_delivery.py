import pathlib

import pytest

from soliplex.config import sse_delivery as config_sse_delivery

CONFIG_PATH = pathlib.Path("/path/to/config.yaml")

MESSAGE = config_sse_delivery.AGUI_SSEDeliveryStrategy.MESSAGE
BOUNDED = config_sse_delivery.AGUI_SSEDeliveryStrategy.BOUNDED

BOUNDED_YAML = {
    "strategy": "bounded",
    "max_deltas": 8,
    "max_bytes": 256,
    "max_ms": 250,
}
BOUNDED_CONFIG = config_sse_delivery.AGUI_SSEDeliveryConfig(
    strategy=BOUNDED,
    max_deltas=8,
    max_bytes=256,
    max_ms=250,
)
MESSAGE_CONFIG = config_sse_delivery.AGUI_SSEDeliveryConfig(strategy=MESSAGE)


@pytest.mark.parametrize(
    "config_yaml, expected",
    [
        ({"strategy": "message"}, MESSAGE_CONFIG),
        (BOUNDED_YAML, BOUNDED_CONFIG),
        (
            {
                "strategy": "bounded",
                "max_deltas": 1,
                "max_bytes": 1,
                "max_ms": 1,
            },
            config_sse_delivery.AGUI_SSEDeliveryConfig(
                strategy=BOUNDED,
                max_deltas=1,
                max_bytes=1,
                max_ms=1,
            ),
        ),
    ],
)
def test_sse_delivery_config_from_yaml(config_yaml, expected):
    found = config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config_yaml,
    )

    assert found == expected


def test_sse_delivery_config_from_yaml_does_not_mutate_input():
    config_yaml = dict(BOUNDED_YAML)

    config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config_yaml,
    )

    assert config_yaml == BOUNDED_YAML


@pytest.mark.parametrize(
    "config_yaml, match",
    [
        ("bounded", "must be a mapping"),
        (["bounded"], "must be a mapping"),
        (True, "must be a mapping"),
        ({}, "'strategy' is required"),
        ({"max_ms": 1}, "'strategy' is required"),
        ({"strategy": "per-delta"}, "unknown strategy"),
        ({"strategy": None}, "unknown strategy"),
        ({"strategy": "message", "colour": "blue"}, "unknown key"),
        ({"strategy": "message", "max_ms": 250}, "takes no bounds"),
        (
            {"strategy": "bounded", "max_bytes": 256, "max_ms": 250},
            "'max_deltas' is required",
        ),
        (
            {"strategy": "bounded", "max_deltas": 8, "max_ms": 250},
            "'max_bytes' is required",
        ),
        (
            {"strategy": "bounded", "max_deltas": 8, "max_bytes": 256},
            "'max_ms' is required",
        ),
    ],
)
def test_sse_delivery_config_from_yaml_invalid(config_yaml, match):
    with pytest.raises(
        config_sse_delivery.InvalidSSEDeliveryConfig,
        match=match,
    ) as exc_info:
        config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
            CONFIG_PATH,
            config_yaml,
        )

    assert str(CONFIG_PATH) in str(exc_info.value)


@pytest.mark.parametrize("key", ["max_deltas", "max_bytes", "max_ms"])
@pytest.mark.parametrize("value", [0, -1, True, False, 2.5, "8", None, [8]])
def test_sse_delivery_config_from_yaml_invalid_bound(key, value):
    with pytest.raises(
        config_sse_delivery.InvalidSSEDeliveryConfig,
        match=f"'{key}' must be a positive integer",
    ):
        config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
            CONFIG_PATH,
            BOUNDED_YAML | {key: value},
        )


@pytest.mark.parametrize(
    "config, expected",
    [
        (MESSAGE_CONFIG, {"strategy": "message"}),
        (BOUNDED_CONFIG, BOUNDED_YAML),
    ],
)
def test_sse_delivery_config_as_yaml(config, expected):
    assert config.as_yaml == expected


@pytest.mark.parametrize("config", [MESSAGE_CONFIG, BOUNDED_CONFIG])
def test_sse_delivery_config_round_trips(config):
    found = config_sse_delivery.AGUI_SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config.as_yaml,
    )

    assert found == config


def test_default_sse_delivery():
    assert config_sse_delivery.DEFAULT_SSE_DELIVERY == MESSAGE_CONFIG
