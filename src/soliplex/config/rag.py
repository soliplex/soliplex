from __future__ import annotations  # forward refs in typing decls

import dataclasses
import pathlib
import re

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


_URI_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


def _looks_like_uri(value) -> bool:
    """True if 'value' starts with a URI scheme like 's3://' or 'gs://'.

    Accepts anything with a string representation; existing call sites
    set 'rag_lancedb_override_path' to either a string or a 'pathlib.Path'.
    """
    return bool(_URI_SCHEME_RE.match(str(value)))


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
    def rag_lancedb_uri(self) -> str | None:
        """Return the configured LanceDB URI for this room, else None.

        Resolved from:

        1. ``rag_lancedb_override_path`` when it is a URI
           (e.g. ``s3://bucket/path.lancedb``).
        2. ``rag_lancedb_stem`` joined onto ``RAG_LANCE_DB_PATH`` when
           that env value is a URI base (e.g.
           ``RAG_LANCE_DB_PATH=s3://bucket/lancedbs`` +
           ``rag_lancedb_stem=docs`` ⇒ ``s3://bucket/lancedbs/docs.lancedb``).

        URI values are routed into ``haiku_rag_config.lancedb.uri`` so
        haiku.rag opens the database via object storage instead of
        treating the value as a local path.
        """
        rsop = self.rag_lancedb_override_path
        if rsop is not None:
            if _looks_like_uri(rsop):
                return str(rsop)
            return None

        if (
            self.rag_lancedb_stem is not None
            and self._installation_config is not None
        ):
            base = self._installation_config.get_environment(
                "RAG_LANCE_DB_PATH",
            )
            if base is not None and _looks_like_uri(base):
                return (
                    f"{str(base).rstrip('/')}/{self.rag_lancedb_stem}.lancedb"
                )
        return None

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        """Populate a haiku-rag config object w/ room-level overrides

        Use installation's 'haiku_rag_config' as a base.  If the room
        directory holds a 'haiku.rag.yaml' file, load it's mapping, and
        treat it as overrides.  When 'rag_lancedb_override_path' is a
        URI, overlay it as 'lancedb.uri' on top of the merged result.
        """
        if self._haiku_rag_config is None:
            if self._config_path is None:
                raise exceptions.NoConfigPath()

            base_config = self._installation_config.haiku_rag_config
            hr_config_file = self._config_path.parent / "haiku.rag.yaml"
            has_room_yaml = hr_config_file.is_file()
            uri_override = self.rag_lancedb_uri

            if has_room_yaml or uri_override is not None:
                merged = base_config.model_dump()

                if has_room_yaml:
                    room_config_yaml = hr_config.load_yaml_config(
                        hr_config_file
                    )
                    merged = merged | room_config_yaml

                if uri_override is not None:
                    lancedb_section = dict(merged.get("lancedb") or {})
                    lancedb_section["uri"] = uri_override
                    merged = merged | {"lancedb": lancedb_section}

                self._haiku_rag_config = hr_config.AppConfig.model_validate(
                    merged
                )
            else:
                self._haiku_rag_config = base_config

        return self._haiku_rag_config

    @property
    def rag_lancedb_path(self) -> pathlib.Path | None:
        """Compute the local path for the room's RAG database.

        Returns None when 'rag_lancedb_override_path' is a URI; in that
        case storage is configured via 'haiku_rag_config.lancedb.uri'
        and haiku.rag ignores the 'db_path' argument.
        """
        if self.rag_lancedb_uri is not None:
            return None

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
        uri = self.rag_lancedb_uri
        if uri is not None:
            return {"rag_lancedb_path": uri}

        try:
            rag_lancedb_path = self.rag_lancedb_path
        except RagDbFileNotFound as exc:
            rag_lancedb_path = f"MISSING: {exc.rag_db_filename}"

        return {
            "rag_lancedb_path": rag_lancedb_path,
        }
