from __future__ import annotations  # forward refs in typing decls

import abc
import dataclasses
import pathlib
import typing

from haiku.rag import config as hr_config

from . import _utils
from . import exceptions

if typing.TYPE_CHECKING:  # avoid an import cycle at runtime
    from . import installation as config_installation


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


class RagDbExactlyOneOfStemOrOverride(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure exactly one of 'rag_lancedb_stem' or "
            f"'rag_lancedb_override_path' "
            f"(configured in {_config_path})"
        )


class RagDbFileNotFound(ValueError):
    def __init__(self, rag_db_filename, _config_path):
        self.rag_db_filename = rag_db_filename
        self._config_path = _config_path
        super().__init__(
            f"RAG DB file not found: {rag_db_filename} "
            f"(configured in {_config_path})"
        )


@typing.runtime_checkable
class RAGConfigProtocol(typing.Protocol):
    """Expose a haiku-rag configuration"""

    @property
    @abc.abstractmethod
    def haiku_rag_config(self) -> hr_config.AppConfig:
        """Populate a haiku-rag config object w/ room-level overrides"""
        ...


@typing.runtime_checkable
class SingleRAGDatabaseProtocol(typing.Protocol):
    """Expose a single lancedb path"""

    @property
    @abc.abstractmethod
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the room's RAG rag_lancedb_path database"""
        ...


@typing.runtime_checkable
class MultipleRAGDatabasesProtocol(typing.Protocol):
    """Expose a list of lancedb paths"""

    @property
    @abc.abstractmethod
    def rag_lancedb_paths(self) -> list[pathlib.Path]:
        """Compute the paths for the room's RAG rag_lancedb_path databases"""
        ...


@dataclasses.dataclass(kw_only=True)
class _RAGConfigBase:
    """Base class for configs which expose a 'haiku_rag_config' property"""

    _haiku_rag_config: hr_config.AppConfig | None = None

    # Normally set via subclass 'from_yaml'
    _installation_config: config_installation.InstallationConfig = (
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        """Populate a haiku-rag config object w/ room-level overrides

        Use installation's 'haiku_rag_config' as a base.  If the room
        directory holds a 'haiku.rag.yaml' file, load it's mapping, and
        treat it as overrides.
        """
        if self._haiku_rag_config is None:
            if self._config_path is None:
                raise exceptions.NoConfigPath()

            base_config = self._installation_config.haiku_rag_config

            hr_config_file = self._config_path.parent / "haiku.rag.yaml"

            if hr_config_file.is_file():
                base_config_yaml = base_config.model_dump(exclude_unset=True)
                room_config_yaml = hr_config.load_yaml_config(hr_config_file)
                merged_config_yaml = _deep_merge(
                    base_config_yaml,
                    room_config_yaml,
                )

                self._haiku_rag_config = hr_config.AppConfig.model_validate(
                    merged_config_yaml
                )
            else:
                self._haiku_rag_config = base_config

        return self._haiku_rag_config


@dataclasses.dataclass(kw_only=True)
class _RAGDatabaseBase:
    """Base class for configs which expose a 'rag_lancedb_path' property"""

    # One of these two options must be specified
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    # Normally set via subclass 'from_yaml'
    _installation_config: config_installation.InstallationConfig = (
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    def __post_init__(self):
        exclusive_required = [
            self.rag_lancedb_stem,
            self.rag_lancedb_override_path,
        ]
        passed = list(filter(None, exclusive_required))

        if len(list(passed)) != 1:
            raise RagDbExactlyOneOfStemOrOverride(self._config_path)

    @property
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the database"""
        if self.rag_lancedb_override_path is not None:
            # Expanded before joining: a '~' resolved against the room
            # directory is a literal directory name, never a home.
            rsop = pathlib.Path(self.rag_lancedb_override_path).expanduser()

            if self._config_path is not None:
                rsop = (self._config_path.parent / rsop).resolve()
            else:
                rsop = rsop.resolve()

            if not rsop.is_dir():
                raise RagDbFileNotFound(rsop, self._config_path)

            return rsop
        else:
            db_rag_dir = pathlib.Path(
                self._installation_config.get_environment(
                    "RAG_LANCE_DB_PATH",
                )
            )
            rspdb = (db_rag_dir / f"{self.rag_lancedb_stem}.lancedb").resolve()

            if not rspdb.is_dir():
                raise RagDbFileNotFound(rspdb, self._config_path)

            return rspdb

    def get_extra_parameters(self) -> dict:
        try:
            rag_lancedb_path = self.rag_lancedb_path
        except RagDbFileNotFound as exc:
            missing = exc.rag_db_filename
            db_name = f"MISSING: {missing.stem}"
        else:
            db_name = rag_lancedb_path.stem

        return {
            "database_names": [db_name],
        }


@dataclasses.dataclass(kw_only=True)
class _MultiRAGDatabasesBase:
    """Base class for configs which expose a 'rag_lancedb_paths' property"""

    db_configs: list[SingleRAGDatabaseProtocol] = _utils._default_list_field()

    @property
    def rag_lancedb_paths(self):
        return [cfg.rag_lancedb_path for cfg in self.db_configs]
