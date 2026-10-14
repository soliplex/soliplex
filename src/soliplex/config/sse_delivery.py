from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import pathlib
import typing

# ============================================================================
#   AG-UI SSE delivery configuration types
# ============================================================================

_BOUND_KEYS = ("max_deltas", "max_bytes", "max_ms")


class InvalidSSEDeliveryConfig(ValueError):
    NOT_A_MAPPING = "must be a mapping"
    MISSING_STRATEGY = "'strategy' is required"
    UNKNOWN_KEYS = "unknown key(s): {}"
    UNKNOWN_STRATEGY = "unknown strategy: {!r}"
    MESSAGE_TAKES_NO_BOUNDS = "strategy 'message' takes no bounds"
    MISSING_BOUND = "'{}' is required for strategy 'bounded'"
    INVALID_BOUND = "'{}' must be a positive integer"

    def __init__(self, _config_path, reason: str, *args):
        self._config_path = _config_path
        self.reason = reason.format(*args)
        super().__init__(
            f"Invalid 'agui_sse_delivery' in {_config_path}: {self.reason}"
        )


class AGUI_SSEDeliveryStrategy(enum.StrEnum):
    MESSAGE = "message"
    BOUNDED = "bounded"


@dataclasses.dataclass(frozen=True, kw_only=True)
class AGUI_SSEDeliveryConfig:
    """How the AG-UI run endpoint groups streamed deltas into SSE events

    'message' applies 'soliplex.agui.compact_event_stream', which merges a
    message's deltas until any other event arrives (normally the message's
    end).  'bounded' applies 'soliplex.agui.coalesce_event_stream', which
    also sends the merged deltas once they hold 'max_deltas' deltas or
    'max_bytes' bytes, or have been held about 'max_ms' milliseconds.
    """

    strategy: AGUI_SSEDeliveryStrategy
    max_deltas: int | None = None
    max_bytes: int | None = None
    max_ms: int | None = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: typing.Any,
    ) -> AGUI_SSEDeliveryConfig:
        invalid = functools.partial(InvalidSSEDeliveryConfig, config_path)

        if not isinstance(config_dict, dict):
            raise invalid(InvalidSSEDeliveryConfig.NOT_A_MAPPING)

        if "strategy" not in config_dict:
            raise invalid(InvalidSSEDeliveryConfig.MISSING_STRATEGY)

        unknown = set(config_dict) - {"strategy", *_BOUND_KEYS}
        if unknown:
            raise invalid(
                InvalidSSEDeliveryConfig.UNKNOWN_KEYS, sorted(unknown)
            )

        try:
            strategy = AGUI_SSEDeliveryStrategy(config_dict["strategy"])
        except ValueError:
            raise invalid(
                InvalidSSEDeliveryConfig.UNKNOWN_STRATEGY,
                config_dict["strategy"],
            ) from None

        bounds = {
            key: config_dict[key] for key in _BOUND_KEYS if key in config_dict
        }

        if strategy == AGUI_SSEDeliveryStrategy.MESSAGE:
            if bounds:
                raise invalid(
                    InvalidSSEDeliveryConfig.MESSAGE_TAKES_NO_BOUNDS,
                )
            return cls(strategy=strategy)

        for key in _BOUND_KEYS:
            if key not in bounds:
                raise invalid(InvalidSSEDeliveryConfig.MISSING_BOUND, key)
            value = bounds[key]
            if type(value) is not int or value < 1:
                raise invalid(InvalidSSEDeliveryConfig.INVALID_BOUND, key)

        return cls(strategy=strategy, **bounds)

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        result = {"strategy": str(self.strategy)}
        if self.strategy == AGUI_SSEDeliveryStrategy.BOUNDED:
            result["max_deltas"] = self.max_deltas
            result["max_bytes"] = self.max_bytes
            result["max_ms"] = self.max_ms
        return result


DEFAULT_SSE_DELIVERY = AGUI_SSEDeliveryConfig(
    strategy=AGUI_SSEDeliveryStrategy.MESSAGE,
)
