from __future__ import annotations  # forward refs in typing decls

import abc
import dataclasses
import pathlib
import typing

from haiku.rag import client as hr_client
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


def _configured_databases(
    hr_config_obj: hr_config.AppConfig,
) -> dict[str, pathlib.Path | str]:
    """Every database a haiku.rag config places, keyed by name

    'DatabaseScope.resolve' answers for the configuration as written and
    for what it leaves to defaults, without opening anything.
    """
    scope = hr_client.DatabaseScope.resolve(hr_config_obj)

    return {ref.name: ref.location for ref in scope.databases}


class RagDbStemAndOverrideConflict(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure at most one of 'rag_lancedb_stem' or "
            f"'rag_lancedb_override_path' "
            f"(configured in {_config_path})"
        )


class RagDbEntryRequiresDatabase(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Each entry in 'rag_databases' names one database, via "
            f"'rag_lancedb_stem' or 'rag_lancedb_override_path' "
            f"(configured in {_config_path})"
        )


class RagDbTwoPlacements(ValueError):
    """Raised where a config names databases its haiku.rag config places

    The haiku.rag configuration may be the room's own or the
    installation's, since the room reads the two merged.
    """

    def __init__(self, declared, configured, _config_path):
        self.declared = declared
        self.configured = configured
        self._config_path = _config_path
        super().__init__(
            f"{_config_path} names {', '.join(declared)}, and the haiku.rag "
            f"configuration it reads places {', '.join(configured)} in "
            f"'lancedb.databases'. Name every database in one place: move "
            f"the room's own into 'lancedb.databases', or drop whichever "
            f"side is the duplicate"
        )


class RagDbFileNotFound(ValueError):
    def __init__(self, rag_db_filename, _config_path):
        self.rag_db_filename = rag_db_filename
        self._config_path = _config_path
        super().__init__(
            f"RAG DB file not found: {rag_db_filename} "
            f"(configured in {_config_path})"
        )


class RagDbSingleAndMultiConflict(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Configure either 'rag_databases' or a single database via "
            f"'rag_lancedb_stem' / 'rag_lancedb_override_path', not both "
            f"(configured in {_config_path})"
        )


class RagDbDuplicateDatabaseName(TypeError):
    def __init__(self, name, _config_path):
        self.name = name
        self._config_path = _config_path
        super().__init__(
            f"Duplicate name in 'rag_databases': {name!r} "
            f"(configured in {_config_path})"
        )


class RagDbEntryRequiresName(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"Each entry in 'rag_databases' needs a 'name' "
            f"(configured in {_config_path})"
        )


class RagDbNestedDatabases(TypeError):
    def __init__(self, _config_path):
        self._config_path = _config_path
        super().__init__(
            f"An entry in 'rag_databases' names one database, so it cannot "
            f"carry 'rag_databases' of its own "
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
class RAGDatabasesProtocol(typing.Protocol):
    """Expose the databases a config covers, keyed by name"""

    @property
    @abc.abstractmethod
    def rag_lancedb_databases(self) -> dict[str, pathlib.Path | str]:
        """Every database this config covers, keyed by name"""
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

                room_hr_config = hr_config.AppConfig.model_validate(
                    merged_config_yaml
                )
            else:
                room_hr_config = base_config

            self._haiku_rag_config = self._name_rag_databases(room_hr_config)

        return self._haiku_rag_config

    def _name_rag_databases(
        self,
        room_hr_config: hr_config.AppConfig,
    ) -> hr_config.AppConfig:
        """Name this config's databases in 'lancedb.databases'

        'names_own_databases' comes from '_RAGDatabasesBase', which
        DB-bearing configs mix in alongside this class.  A config naming
        none defers to the haiku.rag config, which is returned untouched.
        Copies rather than mutates: the installation's own config object is
        shared with every other room.
        """
        if not getattr(self, "names_own_databases", False):
            return room_hr_config

        # Before resolving anything: the database named beside a configured
        # one is typically a placeholder that was never created, and its
        # absence is not the diagnosis.
        if room_hr_config.lancedb.databases:
            raise RagDbTwoPlacements(
                self._declared_names,
                list(room_hr_config.lancedb.databases),
                self._config_path,
            )

        databases = self._declared_databases

        lancedb = room_hr_config.lancedb.model_copy(
            update={
                "databases": {
                    name: str(path) for name, path in databases.items()
                },
            },
        )

        return room_hr_config.model_copy(update={"lancedb": lancedb})


@dataclasses.dataclass(kw_only=True)
class _RAGDatabasesBase:
    """Base class for configs which expose a 'rag_databases' list

    Every database a config names lands in that list, whichever way the
    YAML spelled it: the two singular options are backward-compatible
    sugar for a one-entry list, normalized away here so nothing
    downstream has to know which spelling was used.
    """

    rag_databases: list[RAGDatabaseEntry] = _utils._default_list_field()

    # Sugar for a single unnamed database, folded into 'rag_databases'.
    rag_lancedb_stem: dataclasses.InitVar[str] = None
    rag_lancedb_override_path: dataclasses.InitVar[str] = None

    # Normally set via subclass 'from_yaml'
    _installation_config: config_installation.InstallationConfig = (
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    def __post_init__(
        self,
        rag_lancedb_stem: str | None,
        rag_lancedb_override_path: str | None,
    ):
        names_one = bool(rag_lancedb_stem or rag_lancedb_override_path)

        if self.rag_databases:
            if names_one:
                raise RagDbSingleAndMultiConflict(self._config_path)

            seen = set()

            for entry in self.rag_databases:
                if entry.name in seen:
                    raise RagDbDuplicateDatabaseName(
                        entry.name,
                        self._config_path,
                    )

                seen.add(entry.name)

            return

        if names_one:
            # The entry names itself after whichever option placed it,
            # and raises on the pair being spelled out together.
            self.rag_databases.append(
                RAGDatabaseEntry(
                    rag_lancedb_stem=rag_lancedb_stem,
                    rag_lancedb_override_path=rag_lancedb_override_path,
                    _installation_config=self._installation_config,
                    _config_path=self._config_path,
                )
            )

    @property
    def names_own_databases(self) -> bool:
        """Whether this config places databases, before resolving any"""
        return bool(self.rag_databases)

    @property
    def _declared_names(self) -> list[str]:
        """The names this config writes down, before any path resolves"""
        return [entry.name for entry in self.rag_databases]

    @property
    def _declared_databases(self) -> dict[str, pathlib.Path]:
        """Every database this config names itself, resolved

        Resolves paths, so callers guard on 'names_own_databases' first.
        Read by 'haiku_rag_config' while it builds, so this must never
        consult the built config.
        """
        return {
            entry.name: entry.rag_lancedb_path for entry in self.rag_databases
        }

    @property
    def rag_lancedb_databases(self) -> dict[str, pathlib.Path | str]:
        """Every database this config covers, keyed by name

        A config naming none covers whatever its haiku.rag config places,
        the installation's default database included.
        """
        if self.names_own_databases:
            return self._declared_databases

        return _configured_databases(self.haiku_rag_config)

    @property
    def rag_database_names(self) -> list[str]:
        if self.rag_databases:
            return [entry.database_name for entry in self.rag_databases]

        return list(_configured_databases(self.haiku_rag_config))

    @property
    def rag_db_audit_path(self) -> str:
        """Identify the database(s) this config reads, for audit records"""
        return ", ".join(
            f"{name}={location}"
            for name, location in self.rag_lancedb_databases.items()
        )

    def get_extra_parameters(self) -> dict:
        return {"database_names": self.rag_database_names}


def adjust_yaml_rag_databases(
    installation_config: config_installation.InstallationConfig,
    config_path: pathlib.Path,
    config_dict: dict,
) -> None:
    """Replace 'rag_databases' mappings with 'RAGDatabaseEntry's, in place

    A key with nothing under it parses as None, which is the field's
    default spelled out, so it is dropped rather than passed along.
    """
    rag_databases = config_dict.pop("rag_databases", None)

    if rag_databases is None:
        return

    config_dict["rag_databases"] = [
        RAGDatabaseEntry.from_yaml(
            installation_config,
            config_path,
            entry_dict,
        )
        for entry_dict in rag_databases
    ]


@dataclasses.dataclass(kw_only=True)
class RAGDatabaseEntry:
    """One named database, whether or not a config spells out its name

    The name is haiku.rag's identity for the database: it travels in search
    results, documents and citations, where a location must not.  An entry
    written without one takes the name from whichever option placed it, so
    every database has a name before any path resolves.
    """

    name: str = None

    # Exactly one of these two options places the database.
    rag_lancedb_stem: str = None
    rag_lancedb_override_path: str = None

    # Normally set via 'from_yaml'
    _installation_config: config_installation.InstallationConfig = (
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    def __post_init__(self):
        if self.rag_lancedb_override_path is not None:
            # However it arrived -- YAML string, sugar on the owning
            # config, or a caller's own Path -- an entry holds a Path, so
            # two spellings of one database compare equal.
            self.rag_lancedb_override_path = pathlib.Path(
                self.rag_lancedb_override_path
            )

        if self.rag_lancedb_stem and self.rag_lancedb_override_path:
            raise RagDbStemAndOverrideConflict(self._config_path)

        if not (self.rag_lancedb_stem or self.rag_lancedb_override_path):
            raise RagDbEntryRequiresDatabase(self._config_path)

        if self.name is None:
            self.name = self._placed_name
        elif not self.name.strip():
            # Spelled out, but empty: a typo, not a request to derive one.
            raise RagDbEntryRequiresName(self._config_path)

    @property
    def _placed_name(self) -> str:
        """Name the database after whichever option placed it

        Reads what the config wrote down rather than the resolved path: a
        database that is missing still answers to a name.
        """
        if self.rag_lancedb_stem:
            return self.rag_lancedb_stem

        return pathlib.Path(self.rag_lancedb_override_path).stem

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

        db_rag_dir = pathlib.Path(
            self._installation_config.get_environment(
                "RAG_LANCE_DB_PATH",
            )
        )
        rspdb = (db_rag_dir / f"{self.rag_lancedb_stem}.lancedb").resolve()

        if not rspdb.is_dir():
            raise RagDbFileNotFound(rspdb, self._config_path)

        return rspdb

    @property
    def database_name(self) -> str:
        """The name this database answers to, marked when it is missing"""
        try:
            _ = self.rag_lancedb_path  # property raises
        except RagDbFileNotFound:
            return f"MISSING: {self.name}"

        return self.name

    @classmethod
    def from_yaml(
        cls,
        installation_config: config_installation.InstallationConfig,
        config_path: pathlib.Path,
        config_dict: dict,
    ) -> RAGDatabaseEntry:
        config_dict = dict(config_dict)

        # An entry places one database, so it cannot nest a list of them.
        # Checked here rather than in '__post_init__': the field is gone,
        # and a bare TypeError names the keyword, not the mistake.
        if "rag_databases" in config_dict:
            raise RagDbNestedDatabases(config_path)

        config_dict["_installation_config"] = installation_config
        config_dict["_config_path"] = config_path
        return cls(**config_dict)

    @property
    def as_yaml(self) -> dict:
        result = {"name": self.name}

        if self.rag_lancedb_stem is not None:
            result["rag_lancedb_stem"] = self.rag_lancedb_stem
        else:
            result["rag_lancedb_override_path"] = str(
                self.rag_lancedb_override_path
            )

        return result
