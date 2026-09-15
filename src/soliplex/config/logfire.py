from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing

import logfire

from . import _utils
from . import exceptions as config_exc
from . import interpolation as config_interp

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation

_env_whole_or_literal_field = config_interp.env_whole_or_literal_field
_no_repr_no_compare_none = _utils._no_repr_no_compare_none
_secret_whole_field = config_interp.secret_whole_field


# ============================================================================
#   Logfire configuration types
# ============================================================================


@dataclasses.dataclass(kw_only=True)
class LogfireInstrumentPydanticAI:
    include_binary_content: bool = True
    include_content: bool = True

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict | None,
    ):
        try:
            return cls(
                _config_path=config_path,
                **config_dict,
            )
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "logfire_instrument_pydantic_ai",
                config_dict,
            ) from exc

    @property
    def instrument_pydantic_ai_kwargs(self) -> dict[str, typing.Any]:
        return {
            "include_binary_content": self.include_binary_content,
            "include_content": self.include_content,
        }

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return self.instrument_pydantic_ai_kwargs


@dataclasses.dataclass(kw_only=True)
class LogfireInstrumentFastAPI:
    capture_headers: bool = False
    excluded_urls: list[str] = None
    record_send_receive: bool = False
    extra_spans: bool = False

    # Set by `from_yaml` factory
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict | None,
    ):
        try:
            return cls(
                _config_path=config_path,
                **config_dict,
            )
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "logfire_instrument_fast_api",
                config_dict,
            ) from exc

    @property
    def instrument_fast_api_kwargs(self) -> dict[str, typing.Any]:
        return {
            "capture_headers": self.capture_headers,
            "excluded_urls": self.excluded_urls,
            "record_send_receive": self.record_send_receive,
            "extra_spans": self.extra_spans,
        }

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return self.instrument_fast_api_kwargs


@dataclasses.dataclass(kw_only=True)
class LogfireConfig:
    send_to_logfire: bool | None = None
    token: str = _secret_whole_field()
    service_name: str = _env_whole_or_literal_field(
        default="env:LOGFIRE_SERVICE_NAME",
    )
    service_version: str = _env_whole_or_literal_field(
        default="env:LOGFIRE_SERVICE_VERSION",
    )
    environment: str = _env_whole_or_literal_field(
        default="env:LOGFIRE_ENVIRONMENT",
    )
    config_dir: pathlib.Path | str = _env_whole_or_literal_field(
        default="env:LOGFIRE_CONFIG_DIR",
    )
    data_dir: pathlib.Path | str = _env_whole_or_literal_field(
        default="env:LOGFIRE_DATA_DIR",
    )
    min_level: int | logfire.LevelName = _env_whole_or_literal_field(
        default="env:LOGFIRE_MIN_LEVEL",
    )
    inspect_arguments: bool = None
    add_baggage_to_attributes: bool = True
    distributed_tracing: bool = None
    base_url: str = _env_whole_or_literal_field(default=None)
    scrubbing_patterns: list[str] = None

    instrument_pydantic_ai: LogfireInstrumentPydanticAI = None
    instrument_fast_api: LogfireInstrumentFastAPI = None

    # Set by `from_yaml` factory
    _installation_config: config_installation.InstallationConfig = (
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @property
    def logfire_config_kwargs(self) -> dict[str, typing.Any]:
        """Return a mapping to be passed as kwargs to 'logfire.config()'"""

        kwargs = {
            "token": config_interp.resolve_field(self, "token"),
            "service_name": config_interp.resolve_field(self, "service_name"),
            "service_version": config_interp.resolve_field(
                self, "service_version"
            ),
            "environment": config_interp.resolve_field(self, "environment"),
            "config_dir": config_interp.resolve_field(self, "config_dir"),
            "data_dir": config_interp.resolve_field(self, "data_dir"),
            "min_level": config_interp.resolve_field(self, "min_level"),
            "add_baggage_to_attributes": self.add_baggage_to_attributes,
        }
        if self.send_to_logfire is not None:
            kwargs["send_to_logfire"] = self.send_to_logfire

        if self.inspect_arguments is not None:
            kwargs["inspect_arguments"] = self.inspect_arguments

        if self.distributed_tracing is not None:
            kwargs["distributed_tracing"] = self.distributed_tracing

        if self.base_url is not None:
            kwargs["advanced"] = {
                "base_url": config_interp.resolve_field(self, "base_url"),
            }

        if self.scrubbing_patterns is not None:
            kwargs["scrubbing"] = {
                "extra_patterns": self.scrubbing_patterns,
            }

        return kwargs

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        result = {
            "token": self.token,
            "service_name": self.service_name,
            "service_version": self.service_version,
            "environment": self.environment,
            "config_dir": self.config_dir,
            "data_dir": self.data_dir,
            "min_level": self.min_level,
            "add_baggage_to_attributes": self.add_baggage_to_attributes,
        }

        if self.send_to_logfire is not None:
            result["send_to_logfire"] = self.send_to_logfire

        if self.inspect_arguments is not None:
            result["inspect_arguments"] = self.inspect_arguments

        if self.distributed_tracing is not None:
            result["distributed_tracing"] = self.distributed_tracing

        if self.base_url is not None:
            result["base_url"] = self.base_url

        if self.scrubbing_patterns is not None:
            result["scrubbing_patterns"] = self.scrubbing_patterns

        if self.instrument_pydantic_ai is not None:
            result["instrument_pydantic_ai"] = (
                self.instrument_pydantic_ai.as_yaml
            )

        if self.instrument_fast_api is not None:
            result["instrument_fast_api"] = self.instrument_fast_api.as_yaml

        return result

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ):
        try:
            ipydai = config_dict.pop("instrument_pydantic_ai", None)

            if ipydai is not None:
                ipydai = LogfireInstrumentPydanticAI.from_yaml(
                    config_path,
                    ipydai,
                )
                config_dict["instrument_pydantic_ai"] = ipydai

            ifapi = config_dict.pop("instrument_fast_api", None)

            if ifapi is not None:
                ifapi = LogfireInstrumentFastAPI.from_yaml(
                    config_path,
                    ifapi,
                )
                config_dict["instrument_fast_api"] = ifapi

            return cls(
                _installation_config=installation_config,
                _config_path=config_path,
                **config_dict,
            )

        except config_exc.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "logfire_config",
                config_dict,
            ) from exc
