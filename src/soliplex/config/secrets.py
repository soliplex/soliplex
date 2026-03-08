from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import re
import typing

from soliplex.agui import features as agui_features_module  # noqa F401

from . import _utils

_no_repr_no_compare_none = _utils._no_repr_no_compare_none

SECRET_PREFIX = "secret:"
SECRET_PATTERN = rf"{SECRET_PREFIX}(?P<secret_name>\w+)"
SECRET_RE = re.compile(SECRET_PATTERN)

# ============================================================================
#   Secrets configuration types
# ============================================================================


SECRET_GETTERS_BY_KIND = {}


class NotASecret(ValueError):
    def __init__(self, config_str):
        self.config_str = config_str
        super().__init__(
            f"Config '{config_str}' must be prefixed with 'secret:'"
        )


def strip_secret_prefix(config_str: str) -> str:
    if not config_str.startswith(SECRET_PREFIX):
        raise NotASecret(config_str)

    return config_str[len(SECRET_PREFIX) :]


class _BaseSecretSource:
    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config_dict: dict):
        config_dict["_config_path"] = config_path
        return cls(**config_dict)

    @property
    def as_yaml(self) -> dict:
        return {
            "kind": self.kind,
            "secret_name": self.secret_name,
            **self.extra_arguments,
        }


@dataclasses.dataclass(kw_only=True)
class EnvVarSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "env_var"
    secret_name: str
    env_var_name: str | None = None
    _config_path: pathlib.Path = None
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )

    def __post_init__(self):
        if self.env_var_name is None:
            self.env_var_name = self.secret_name

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"env_var_name": self.env_var_name}


@dataclasses.dataclass(kw_only=True)
class FilePathSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "file_path"
    secret_name: str
    file_path: str
    _config_path: pathlib.Path = None
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"file_path": self.file_path}


@dataclasses.dataclass(kw_only=True)
class SubprocessSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "subprocess"
    secret_name: str
    command: str
    args: list[str] | tuple[str] = ()
    _config_path: pathlib.Path = None
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )

    @property
    def command_line(self) -> str:
        listed = [self.command, *self.args]
        return " ".join(listed)

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"command_line": self.command_line}

    @property
    def as_yaml(self) -> dict:
        return {
            "kind": self.kind,
            "secret_name": self.secret_name,
            "command": self.command,
            "args": list(self.args),
        }


@dataclasses.dataclass(kw_only=True)
class RandomCharsSecretSource(_BaseSecretSource):
    kind: typing.ClassVar[str] = "random_chars"
    secret_name: str
    n_chars: int = 32
    _config_path: pathlib.Path = None
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )

    @property
    def extra_arguments(self) -> dict[str, typing.Any]:
        return {"n_chars": self.n_chars}


SecretSource = (
    EnvVarSecretSource
    | FilePathSecretSource
    | SubprocessSecretSource
    | RandomCharsSecretSource
)


SecretSources = list[SecretSource]


SourceClassesByKind = {
    klass.kind: klass
    for klass in [
        EnvVarSecretSource,
        FilePathSecretSource,
        SubprocessSecretSource,
        RandomCharsSecretSource,
    ]
}


@dataclasses.dataclass(kw_only=True)
class SecretConfig:
    secret_name: str
    sources: SecretSources = None

    # Set in 'from_yaml' below
    _config_path: pathlib.Path = None
    _installation_config: InstallationConfig = (  # noqa F821 cycles
        _no_repr_no_compare_none()
    )
    _resolved: str = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = [EnvVarSecretSource(secret_name=self.secret_name)]

    @classmethod
    def from_yaml(cls, config_path: pathlib.Path, config: dict | str):
        if isinstance(config, str):
            config_dict = {
                "secret_name": config,
                "sources": [
                    {"kind": "env_var", "env_var_name": config},
                ],
            }
        else:
            config_dict = config

        config_dict["_config_path"] = config_path
        source_configs = config_dict.pop("sources", None)

        sources = []

        for source_config in source_configs:
            source_config["secret_name"] = config_dict["secret_name"]
            source_kind = source_config.pop("kind")
            source_klass = SourceClassesByKind[source_kind]
            source_inst = source_klass.from_yaml(config_path, source_config)
            sources.append(source_inst)

        config_dict["sources"] = sources

        return cls(**config_dict)

    @property
    def as_yaml(self) -> dict:
        return {
            "secret_name": self.secret_name,
            "sources": [source.as_yaml for source in self.sources],
        }

    @property
    def resolved(self) -> str | None:
        return self._resolved
