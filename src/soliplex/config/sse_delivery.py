from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import pathlib
import typing

# ============================================================================
#   AG-UI SSE delivery configuration types
# ============================================================================

_BOUND_KEYS = ("max_deltas", "max_bytes", "max_ms")
_KNOWN_KEYS = {"strategy", "description", *_BOUND_KEYS}


class InvalidSSEDeliveryConfig(ValueError):
    """Base class: an 'agui_sse_delivery' stanza is invalid"""

    def __init__(self, _config_path, reason: str):
        self._config_path = _config_path
        self.reason = reason

        super().__init__(
            f"Invalid 'agui_sse_delivery' in {_config_path}: {reason}",
        )


class SSEDeliveryNotAMapping(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path):
        super().__init__(_config_path, "must be a mapping")


class SSEDeliveryMissingStrategy(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path):
        super().__init__(_config_path, "'strategy' is required")


class SSEDeliveryUnknownKeys(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, unknown_keys):
        super().__init__(
            _config_path,
            f"unknown key(s): {sorted(unknown_keys)}",
        )


class SSEDeliveryUnknownStrategy(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, strategy):
        super().__init__(_config_path, f"unknown strategy: {strategy!r}")


class SSEDeliveryTakesNoBounds(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path):
        super().__init__(_config_path, "strategy 'message' takes no bounds")


class SSEDeliveryMissingBound(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, key):
        super().__init__(
            _config_path,
            f"'{key}' is required for strategy 'bounded'",
        )


class SSEDeliveryInvalidBound(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, key):
        super().__init__(_config_path, f"'{key}' must be a positive integer")


class SSEDeliveryInvalidDescription(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path):
        super().__init__(
            _config_path,
            "'description' must be a non-empty string",
        )


class SSEDeliveryStrategy(enum.StrEnum):
    MESSAGE = "message"
    BOUNDED = "bounded"


@dataclasses.dataclass(frozen=True, kw_only=True)
class SSEDeliveryConfig:
    """How the AG-UI run endpoint groups streamed deltas into SSE events

    'message' applies 'soliplex.agui.sse_delivery.compact_event_stream',
    which merges a message's deltas until any other event arrives
    (normally the message's end).  'bounded' applies
    'soliplex.agui.sse_delivery.coalesce_event_stream', which also sends
    the merged deltas once they hold 'max_deltas' deltas or 'max_bytes'
    bytes, or have been held about 'max_ms' milliseconds.
    """

    strategy: SSEDeliveryStrategy
    max_deltas: int | None = None
    max_bytes: int | None = None
    max_ms: int | None = None
    description: str | None = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: typing.Any,
    ) -> SSEDeliveryConfig:
        if not isinstance(config_dict, dict):
            raise SSEDeliveryNotAMapping(config_path)

        if "strategy" not in config_dict:
            raise SSEDeliveryMissingStrategy(config_path)

        unknown = set(config_dict) - _KNOWN_KEYS
        if unknown:
            raise SSEDeliveryUnknownKeys(config_path, sorted(unknown))

        description = config_dict.get("description")
        if description is not None and (
            type(description) is not str or not description.strip()
        ):
            raise SSEDeliveryInvalidDescription(config_path)

        try:
            strategy = SSEDeliveryStrategy(config_dict["strategy"])
        except ValueError:
            raise SSEDeliveryUnknownStrategy(
                config_path,
                config_dict["strategy"],
            ) from None

        description = config_dict.get("description")
        bounds = {
            key: config_dict[key] for key in _BOUND_KEYS if key in config_dict
        }

        if strategy == SSEDeliveryStrategy.MESSAGE:
            if bounds:
                raise SSEDeliveryTakesNoBounds(config_path)
            return cls(strategy=strategy, description=description)

        for key in _BOUND_KEYS:
            if key not in bounds:
                raise SSEDeliveryMissingBound(config_path, key)
            value = bounds[key]
            if type(value) is not int or value < 1:
                raise SSEDeliveryInvalidBound(config_path, key)

        return cls(strategy=strategy, description=description, **bounds)

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        result = {"strategy": str(self.strategy)}
        if self.strategy == SSEDeliveryStrategy.BOUNDED:
            result["max_deltas"] = self.max_deltas
            result["max_bytes"] = self.max_bytes
            result["max_ms"] = self.max_ms

        if self.description is not None:
            result["description"] = self.description

        return result


SSEDeliveryConfigMap = dict[str, SSEDeliveryConfig]

_PROFILE_STANZA_KEYS = frozenset(["default", "configs"])


class SSEDeliveryMissingKey(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, key):
        super().__init__(_config_path, f"'{key}' is required")


class SSEDeliveryUnknownProfileName(InvalidSSEDeliveryConfig):
    def __init__(self, _config_path, name):
        super().__init__(_config_path, f"unknown profile name: {name!r}")


@dataclasses.dataclass(frozen=True, kw_only=True)
class SSEDeliveryProfilesConfig:
    """Named 'agui_sse_delivery' profiles, plus the installation's default

    Declared at the installation level, in the stanza 'sse_delivery'::

        sse_delivery:
          default: "fast"
          configs:
            "fast":
              strategy: "bounded"
              description: "Fine-grained deltas"
              max_deltas: 8
              max_bytes: 256
              max_ms: 250
            "plain":
              strategy: "message"
              description: "Whole messages"

    Rooms name one of these profiles as the default for their threads;
    AG-UI requests name one in 'forwardedProps'.  In both cases, an
    absent or unknown name falls back to the next level's default.
    """

    default: str
    configs: SSEDeliveryConfigMap

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: typing.Any,
    ) -> SSEDeliveryProfilesConfig:
        if not isinstance(config_dict, dict):
            raise SSEDeliveryNotAMapping(config_path)

        unknown = set(config_dict) - _PROFILE_STANZA_KEYS
        if unknown:
            raise SSEDeliveryUnknownKeys(config_path, sorted(unknown))

        default = config_dict.get("default")
        if default is None:
            raise SSEDeliveryMissingKey(config_path, "default")

        configs = config_dict.get("configs")
        if configs is None:
            raise SSEDeliveryMissingKey(config_path, "configs")

        if not isinstance(configs, dict):
            raise SSEDeliveryNotAMapping(config_path)

        validated = {
            name: SSEDeliveryConfig.from_yaml(config_path, block)
            for name, block in configs.items()
        }

        if default not in validated:
            raise SSEDeliveryUnknownProfileName(config_path, default)

        return cls(default=default, configs=validated)

    def get(self, name: str) -> SSEDeliveryConfig | None:
        return self.configs.get(name)

    @property
    def default_config(self) -> SSEDeliveryConfig:
        return self.configs[self.default]

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return {
            "default": self.default,
            "configs": {
                name: profiles_config.as_yaml
                for name, profiles_config in self.configs.items()
            },
        }


DEFAULT_SSE_DELIVERY_DESC = "code default (message)"
DEFAULT_SSE_DELIVERY = SSEDeliveryConfig(
    strategy=SSEDeliveryStrategy.MESSAGE,
    description=DEFAULT_SSE_DELIVERY_DESC,
)
