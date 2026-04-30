from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import typing

import logfire

from . import _utils
from . import exceptions as config_exc

_no_repr_no_compare_none = _utils._no_repr_no_compare_none


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
    token: str  # "secret:LOGFIRE_TOKEN" or similar
    service_name: str = "env:LOGFIRE_SERVICE_NAME"
    service_version: str = "env:LOGFIRE_SERVICE_VERSION"
    environment: str = "env:LOGFIRE_ENVIRONMENT"
    config_dir: pathlib.Path | str = "env:LOGFIRE_CONFIG_DIR"
    data_dir: pathlib.Path | str = "env:LOGFIRE_DATA_DIR"
    min_level: int | logfire.LevelName = "env:LOGFIRE_MIN_LEVEL"
    inspect_arguments: bool = None
    add_baggage_to_attributes: bool = True
    distributed_tracing: bool = None
    base_url: str = None
    scrubbing_patterns: list[str] = None

    instrument_pydantic_ai: LogfireInstrumentPydanticAI = None
    instrument_fast_api: LogfireInstrumentFastAPI = None

    # Set by `from_yaml` factory
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @property
    def logfire_config_kwargs(self) -> dict[str, typing.Any]:
        """Return a mapping to be passed as kwargs to 'logfire.config()'

        Resolve values prefixed with 'env:' using the installation
        configuration environment.
        """

        def maybe_getenv(key):
            if key.startswith("env:"):
                return self._installation_config.get_environment(key[4:])
            else:
                return key

        kwargs = {
            "token": self._installation_config.get_secret(self.token),
            "service_name": maybe_getenv(self.service_name),
            "service_version": maybe_getenv(self.service_version),
            "environment": maybe_getenv(self.environment),
            "config_dir": maybe_getenv(self.config_dir),
            "data_dir": maybe_getenv(self.data_dir),
            "min_level": maybe_getenv(self.min_level),
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
                "base_url": maybe_getenv(self.base_url),
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
        installation_config: InstallationConfig,  # noqa F821 cycles
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
