import copy
import pathlib

import pytest

from soliplex.config import sse_delivery as config_sse_delivery

CONFIG_PATH = pathlib.Path("/path/to/config.yaml")

MESSAGE = config_sse_delivery.SSEDeliveryStrategy.MESSAGE
BOUNDED = config_sse_delivery.SSEDeliveryStrategy.BOUNDED
TEST_SSE_DESC = "test SSE Delivery Config"

BOUNDED_YAML = {
    "strategy": "bounded",
    "max_deltas": 8,
    "max_bytes": 256,
    "max_ms": 250,
}
BOUNDED_CONFIG = config_sse_delivery.SSEDeliveryConfig(
    strategy=BOUNDED,
    max_deltas=8,
    max_bytes=256,
    max_ms=250,
)

MESSAGE_YAML = {"strategy": MESSAGE}
MESSAGE_CONFIG = config_sse_delivery.SSEDeliveryConfig(strategy=MESSAGE)

WITH_DESC_MESSAGE_YAML = {
    "strategy": MESSAGE,
    "description": TEST_SSE_DESC,
}
WITH_DESC_MESSAGE_CONFIG = config_sse_delivery.SSEDeliveryConfig(
    strategy=MESSAGE,
    description=TEST_SSE_DESC,
)

WITH_DESC_BOUNDED_YAML = BOUNDED_YAML | {"description": TEST_SSE_DESC}
WITH_DESC_BOUNDED_CONFIG = config_sse_delivery.SSEDeliveryConfig(
    strategy=BOUNDED,
    max_deltas=8,
    max_bytes=256,
    max_ms=250,
    description=TEST_SSE_DESC,
)


@pytest.mark.parametrize(
    "config_yaml, expected",
    [
        (MESSAGE_YAML, MESSAGE_CONFIG),
        (BOUNDED_YAML, BOUNDED_CONFIG),
        (
            {
                "strategy": "bounded",
                "max_deltas": 1,
                "max_bytes": 1,
                "max_ms": 1,
            },
            config_sse_delivery.SSEDeliveryConfig(
                strategy=BOUNDED,
                max_deltas=1,
                max_bytes=1,
                max_ms=1,
            ),
        ),
        (WITH_DESC_MESSAGE_YAML, WITH_DESC_MESSAGE_CONFIG),
        (WITH_DESC_BOUNDED_YAML, WITH_DESC_BOUNDED_CONFIG),
    ],
)
def test_sse_delivery_config_from_yaml(config_yaml, expected):
    found = config_sse_delivery.SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config_yaml,
    )

    assert found == expected


def test_sse_delivery_config_from_yaml_does_not_mutate_input():
    config_yaml = dict(BOUNDED_YAML)

    config_sse_delivery.SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config_yaml,
    )

    assert config_yaml == BOUNDED_YAML


@pytest.mark.parametrize(
    "config_yaml, expected_exc, match",
    [
        (
            "bounded",
            config_sse_delivery.SSEDeliveryNotAMapping,
            "must be a mapping",
        ),
        (
            ["bounded"],
            config_sse_delivery.SSEDeliveryNotAMapping,
            "must be a mapping",
        ),
        (
            True,
            config_sse_delivery.SSEDeliveryNotAMapping,
            "must be a mapping",
        ),
        (
            {},
            config_sse_delivery.SSEDeliveryMissingStrategy,
            "'strategy' is required",
        ),
        (
            {"max_ms": 1},
            config_sse_delivery.SSEDeliveryMissingStrategy,
            "'strategy' is required",
        ),
        (
            {"strategy": "per-delta"},
            config_sse_delivery.SSEDeliveryUnknownStrategy,
            "unknown strategy: 'per-delta'",
        ),
        (
            {"strategy": None},
            config_sse_delivery.SSEDeliveryUnknownStrategy,
            "unknown strategy: None",
        ),
        (
            {"strategy": "message", "colour": "blue"},
            config_sse_delivery.SSEDeliveryUnknownKeys,
            "unknown key",
        ),
        (
            {"strategy": "message", "max_ms": 250},
            config_sse_delivery.SSEDeliveryTakesNoBounds,
            "takes no bounds",
        ),
        (
            {"strategy": "bounded", "max_bytes": 256, "max_ms": 250},
            config_sse_delivery.SSEDeliveryMissingBound,
            "'max_deltas' is required",
        ),
        (
            {"strategy": "bounded", "max_deltas": 8, "max_ms": 250},
            config_sse_delivery.SSEDeliveryMissingBound,
            "'max_bytes' is required",
        ),
        (
            {"strategy": "bounded", "max_deltas": 8, "max_bytes": 256},
            config_sse_delivery.SSEDeliveryMissingBound,
            "'max_ms' is required",
        ),
        (
            {"strategy": "message", "description": 42},
            config_sse_delivery.SSEDeliveryInvalidDescription,
            "non-empty string",
        ),
        (
            {"strategy": "message", "description": {"x": 1}},
            config_sse_delivery.SSEDeliveryInvalidDescription,
            "non-empty string",
        ),
        (
            {"strategy": "bounded", "description": "   "} | BOUNDED_YAML,
            config_sse_delivery.SSEDeliveryInvalidDescription,
            "non-empty string",
        ),
    ],
)
def test_sse_delivery_config_from_yaml_invalid(
    config_yaml, expected_exc, match
):
    with pytest.raises(
        expected_exc,
        match=match,
    ) as exc_info:
        config_sse_delivery.SSEDeliveryConfig.from_yaml(
            CONFIG_PATH,
            config_yaml,
        )

    assert str(CONFIG_PATH) in str(exc_info.value)


@pytest.mark.parametrize("key", ["max_deltas", "max_bytes", "max_ms"])
@pytest.mark.parametrize("value", [0, -1, True, False, 2.5, "8", None, [8]])
def test_sse_delivery_config_from_yaml_invalid_bound(key, value):
    with pytest.raises(
        config_sse_delivery.SSEDeliveryInvalidBound,
        match=f"'{key}' must be a positive integer",
    ):
        config_sse_delivery.SSEDeliveryConfig.from_yaml(
            CONFIG_PATH,
            BOUNDED_YAML | {key: value},
        )


@pytest.mark.parametrize(
    "config, expected",
    [
        (MESSAGE_CONFIG, MESSAGE_YAML),
        (BOUNDED_CONFIG, BOUNDED_YAML),
        (WITH_DESC_MESSAGE_CONFIG, WITH_DESC_MESSAGE_YAML),
        (WITH_DESC_BOUNDED_CONFIG, WITH_DESC_BOUNDED_YAML),
    ],
)
def test_sse_delivery_config_as_yaml(config, expected):
    assert config.as_yaml == expected


@pytest.mark.parametrize(
    "config",
    [
        MESSAGE_CONFIG,
        BOUNDED_CONFIG,
        WITH_DESC_MESSAGE_CONFIG,
        WITH_DESC_BOUNDED_CONFIG,
    ],
)
def test_sse_delivery_config_round_trips(config):
    found = config_sse_delivery.SSEDeliveryConfig.from_yaml(
        CONFIG_PATH,
        config.as_yaml,
    )

    assert found == config


def test_default_sse_delivery():
    assert (
        config_sse_delivery.DEFAULT_SSE_DELIVERY
        == config_sse_delivery.SSEDeliveryConfig(
            strategy=MESSAGE,
            description=config_sse_delivery.DEFAULT_SSE_DELIVERY_DESC,
        )
    )


FASTER_YAML = {
    "strategy": BOUNDED,
    "max_deltas": 16,
    "max_bytes": 512,
    "max_ms": 500,
}

PROFILES_CONFIG = config_sse_delivery.SSEDeliveryProfilesConfig(
    default="plain",
    configs={
        "plain": MESSAGE_CONFIG,
        "fast": BOUNDED_CONFIG,
        "faster": config_sse_delivery.SSEDeliveryConfig(
            strategy=BOUNDED,
            max_deltas=16,
            max_bytes=512,
            max_ms=500,
        ),
    },
)
PROFILES_YAML = {
    "default": "plain",
    "configs": {
        "plain": MESSAGE_YAML,
        "fast": BOUNDED_YAML,
        "faster": FASTER_YAML,
    },
}


def test_sse_delivery_profiles_from_yaml():
    found = config_sse_delivery.SSEDeliveryProfilesConfig.from_yaml(
        CONFIG_PATH,
        PROFILES_YAML,
    )

    assert found == PROFILES_CONFIG


def test_sse_delivery_profiles_from_yaml_does_not_mutate_input():
    config_dict = copy.deepcopy(PROFILES_YAML)

    config_sse_delivery.SSEDeliveryProfilesConfig.from_yaml(
        CONFIG_PATH,
        config_dict,
    )

    assert config_dict == PROFILES_YAML


@pytest.mark.parametrize(
    "config_yaml, expected_exc, match",
    [
        (
            "plain",
            config_sse_delivery.SSEDeliveryNotAMapping,
            "must be a mapping",
        ),
        (
            {
                "default": "plain",
                "configs": {"plain": MESSAGE_YAML},
                "colour": "blue",
            },
            config_sse_delivery.SSEDeliveryUnknownKeys,
            "unknown key",
        ),
        (
            {"configs": {"plain": MESSAGE_YAML}},
            config_sse_delivery.SSEDeliveryMissingKey,
            "'default' is required",
        ),
        (
            {"default": "plain"},
            config_sse_delivery.SSEDeliveryMissingKey,
            "'configs' is required",
        ),
        (
            {"default": "plain", "configs": ["plain"]},
            config_sse_delivery.SSEDeliveryNotAMapping,
            "must be a mapping",
        ),
        (
            {"default": "nope", "configs": {"plain": MESSAGE_YAML}},
            config_sse_delivery.SSEDeliveryUnknownProfileName,
            "unknown profile name: 'nope'",
        ),
        (
            {"default": "plain", "configs": {}},
            config_sse_delivery.SSEDeliveryUnknownProfileName,
            "unknown profile name: 'plain'",
        ),
        (
            {
                "default": "plain",
                "configs": {"plain": {"strategy": "message", "max_ms": 250}},
            },
            config_sse_delivery.SSEDeliveryTakesNoBounds,
            "takes no bounds",
        ),
    ],
)
def test_sse_delivery_profiles_from_yaml_invalid(
    config_yaml,
    expected_exc,
    match,
):
    with pytest.raises(expected_exc, match=match) as exc_info:
        config_sse_delivery.SSEDeliveryProfilesConfig.from_yaml(
            CONFIG_PATH,
            config_yaml,
        )

    assert str(CONFIG_PATH) in str(exc_info.value)


def test_sse_delivery_profiles_as_yaml():
    assert PROFILES_CONFIG.as_yaml == PROFILES_YAML


def test_sse_delivery_profiles_round_trips():
    found = config_sse_delivery.SSEDeliveryProfilesConfig.from_yaml(
        CONFIG_PATH,
        PROFILES_CONFIG.as_yaml,
    )

    assert found == PROFILES_CONFIG


def test_sse_delivery_profiles_get_and_default():
    assert PROFILES_CONFIG.get("fast") == BOUNDED_CONFIG
    assert PROFILES_CONFIG.get("nope") is None
    assert PROFILES_CONFIG.default_config == MESSAGE_CONFIG
