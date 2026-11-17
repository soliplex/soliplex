from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import re
import typing

from . import _utils
from . import interpolation as config_interp

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_no_repr_no_compare_none = _utils._no_repr_no_compare_none

# ============================================================================
#   Room quota configuration types
# ============================================================================

# YAML key -> private field holding the value as written.
_FIELDS_BY_KEY = {"room_uploads_bytes": "_room_uploads_bytes"}

# What an 'env:' value must resolve to:  plain ASCII digits, so no units,
# signs, separators or whitespace.
_DIGITS_RE = re.compile(r"[0-9]+")


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
            f"'{key}' must be a non-negative integer, "
            "or a whole 'env:NAME' marker",
        )


class QuotasUnresolvedEnvironment(InvalidQuotasConfig):
    def __init__(self, _config_path, key, env_name):
        self.env_name = env_name
        super().__init__(
            _config_path,
            f"'{key}' names environment variable '{env_name}', "
            "which has no value",
        )


class QuotasInvalidEnvironmentValue(InvalidQuotasConfig):
    def __init__(self, _config_path, key, env_name, value):
        self.env_name = env_name
        self.value = value
        super().__init__(
            _config_path,
            f"'{key}' names environment variable '{env_name}', whose "
            f"value {value!r} is not a non-negative integer",
        )


def _is_valid_bytes(value) -> bool:
    """Is 'value' a non-negative int, or one whole 'env:NAME' marker?

    'type(value) is int' rejects 'bool', which YAML's 'true' would be.
    """
    if type(value) is int:
        return value >= 0

    return (
        type(value) is str
        and config_interp.ENVIRONMENT_RE.fullmatch(value) is not None
    )


@dataclasses.dataclass(frozen=True, kw_only=True)
class QuotasConfig:
    """Limits on what a room may consume

    'room_uploads_bytes' caps the total size of the regular files in the
    room's uploads directory ('rooms_upload_path / {room_id}'), counting
    uploads in progress; symlinks placed there by an operator are not
    counted.  'None' means no limit;  '0' refuses every new upload.

    The value may instead be one whole 'env:NAME' marker, resolved from
    the installation environment on access, as the migration policies
    are.  Unlike the Logfire fields, a name with no value is an error
    rather than "no limit":  a typo must not silently lift the quota.
    """

    _room_uploads_bytes: int | str | None = (
        config_interp.env_whole_or_literal_field(
            default=None,
            public_name="quotas.room_uploads_bytes",
            accessor="room_uploads_bytes",
        )
    )

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
        """The room-uploads quota in bytes, or 'None' for no limit

        Raise 'QuotasUnresolvedEnvironment' or
        'QuotasInvalidEnvironmentValue' for an 'env:' marker which does
        not resolve to plain digits.
        """
        stored = self._room_uploads_bytes

        if stored is None or type(stored) is int:
            return stored

        resolved = config_interp.resolve_field(self, "_room_uploads_bytes")
        env_name = self.room_uploads_bytes_env_name

        if resolved is None:
            raise QuotasUnresolvedEnvironment(
                self._config_path,
                "room_uploads_bytes",
                env_name,
            )

        # An 'environment:' entry written as a YAML integer arrives as one.
        if type(resolved) is int and resolved >= 0:
            return resolved

        if type(resolved) is not str or _DIGITS_RE.fullmatch(resolved) is None:
            raise QuotasInvalidEnvironmentValue(
                self._config_path,
                "room_uploads_bytes",
                env_name,
                resolved,
            )

        return int(resolved)

    @property
    def room_uploads_bytes_env_name(self) -> str | None:
        """The environment variable the quota names, if an 'env:' marker"""
        stored = self._room_uploads_bytes

        if type(stored) is not str:
            return None

        return config_interp.ENVIRONMENT_RE.fullmatch(stored)["env_name"]

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        """The stanza as written:  an 'env:' marker is kept, not resolved"""
        result = {}

        if self._room_uploads_bytes is not None:
            result["room_uploads_bytes"] = self._room_uploads_bytes

        return result
