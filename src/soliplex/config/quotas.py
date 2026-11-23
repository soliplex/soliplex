from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing

from . import _utils

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_no_repr_no_compare_none = _utils._no_repr_no_compare_none

# ============================================================================
#   Room quota configuration types
# ============================================================================

# YAML key -> private field holding the value as written.
_FIELDS_BY_KEY = {"room_uploads_bytes": "_room_uploads_bytes"}


class InvalidQuotasConfig(ValueError):
    """Base class: a room's 'quotas' stanza is invalid"""

    def __init__(self, _config_path, reason: str):
        self._config_path = _config_path
        self.reason = reason

        super().__init__(f"Invalid 'quotas' in {_config_path}: {reason}")


class QuotasNotAMapping(InvalidQuotasConfig):
    def __init__(self, _config_path):
        super().__init__(_config_path, "must be a mapping")


class QuotasUnknownKeys(InvalidQuotasConfig):
    def __init__(self, _config_path, unknown_keys):
        super().__init__(
            _config_path,
            f"unknown key(s): {sorted(unknown_keys)}",
        )


class QuotasInvalidBytes(InvalidQuotasConfig):
    def __init__(self, _config_path, key):
        super().__init__(
            _config_path,
            f"'{key}' must be a non-negative integer",
        )


def _is_valid_bytes(value) -> bool:
    """Is 'value' a non-negative int?

    'type(value) is int' rejects 'bool', which YAML's 'true' would be.
    """
    return type(value) is int and value >= 0


@dataclasses.dataclass(frozen=True, kw_only=True)
class QuotasConfig:
    """Limits on what a room may consume

    'room_uploads_bytes' caps the total size of the regular files in the
    room's uploads directory ('rooms_upload_path / {room_id}');  symlinks
    placed there by an operator are not counted.  'None' means no limit;
    '0' refuses every new upload.
    """

    _room_uploads_bytes: int | None = None

    # Set by 'from_yaml'.
    _installation_config: config_installation.InstallationConfig = (
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = _no_repr_no_compare_none()

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: typing.Any,
    ) -> QuotasConfig:
        if not isinstance(config_dict, dict):
            raise QuotasNotAMapping(config_path)

        unknown = set(config_dict) - set(_FIELDS_BY_KEY)
        if unknown:
            raise QuotasUnknownKeys(config_path, unknown)

        for key, value in config_dict.items():
            if not _is_valid_bytes(value):
                raise QuotasInvalidBytes(config_path, key)

        return cls(
            **{
                _FIELDS_BY_KEY[key]: value
                for key, value in config_dict.items()
            },
            _installation_config=installation_config,
            _config_path=config_path,
        )

    @property
    def room_uploads_bytes(self) -> int | None:
        """The room-uploads quota in bytes, or 'None' for no limit"""
        return self._room_uploads_bytes

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        result = {}

        if self._room_uploads_bytes is not None:
            result["room_uploads_bytes"] = self._room_uploads_bytes

        return result
