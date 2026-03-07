from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib

from haiku.rag import config as hr_config

from . import _utils
from . import exceptions


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


@dataclasses.dataclass(kw_only=True)
class _RAGConfigBase:
    # Set in '__post_init__' below
    _rag_lancedb_path: pathlib.Path = None

    # One of these two options must be specified
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    # Normally set via subclass 'from_yaml'
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None
    _haiku_rag_config: hr_config.AppConfig | None = None

    def __post_init__(self):
        exclusive_required = [
            self.rag_lancedb_stem,
            self.rag_lancedb_override_path,
        ]
        passed = list(filter(None, exclusive_required))

        if len(list(passed)) != 1:
            raise RagDbExactlyOneOfStemOrOverride(self._config_path)

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
                base_config_yaml = base_config.model_dump()
                room_config_yaml = hr_config.load_yaml_config(hr_config_file)

                self._haiku_rag_config = hr_config.AppConfig.model_validate(
                    base_config_yaml | room_config_yaml
                )
            else:
                self._haiku_rag_config = base_config

        return self._haiku_rag_config

    @property
    def rag_lancedb_path(self) -> pathlib.Path:
        """Compute the path for the room's RAG rag_lancedb_path database"""
        if self.rag_lancedb_override_path is not None:
            rsop = self.rag_lancedb_override_path

            if self._config_path is not None:
                rsop = (self._config_path.parent / rsop).resolve()
            else:
                rsop = pathlib.Path(rsop).resolve()

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
            rag_lancedb_path = f"MISSING: {exc.rag_db_filename}"

        return {
            "rag_lancedb_path": rag_lancedb_path,
        }
