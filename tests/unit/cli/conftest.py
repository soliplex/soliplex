from __future__ import annotations

import dataclasses
import pathlib
import re
import shutil

import pytest
import yaml
from typer.testing import CliRunner

from soliplex import alembic_migrations
from soliplex.authz import schema as authz_schema
from tests._dburi import sqlite_dburi

# 'tests/unit/cli/conftest.py' -> parents[3] is the repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_EXAMPLE_DIR = _REPO_ROOT / "example"


# Matches a DBURI stanza in 'example/minimal.yaml' so a scratch copy can be
# repointed at throwaway sqlite files. Both databases are repointed: a CLI
# command brings them to the current revision (see
# 'soliplex.alembic_migrations'), so both have to be disposable.
def _dburi_re(key):
    return re.compile(
        rf'{key}:\n  sync_dburi: "[^"]*"\n  async_dburi: "[^"]*"',
    )


_DB_KEYS = {
    "agui": "thread_persistence_db",
    "authz": "authorization_db",
}

# Matches the bare 'OLLAMA_BASE_URL' environment requirement so a scratch
# copy can pin a dummy value inline (the CLI never connects to it),
# keeping the installation self-contained rather than depending on an
# ambient env var or a gitignored repo-root '.env'.
_OLLAMA_ENV_RE = re.compile(r'^  - "OLLAMA_BASE_URL"$', re.MULTILINE)


@dataclasses.dataclass(frozen=True)
class ScratchInstallation:
    """A throwaway copy of an example installation with a scratch authz DB.

    'path' is the installation YAML to hand to a CLI command;
    'dburi' / 'db_path' locate the (initially empty) sync authz database
    that the installation's 'authorization_dburi' has been repointed at,
    and 'agui_db_path' the thread-persistence one. 'session()' opens a sync
    SQLAlchemy session against the authz database, creating its schema on
    first use.
    """

    path: pathlib.Path
    dburi: str
    db_path: pathlib.Path
    agui_db_path: pathlib.Path

    def session(self):
        """A sync session over the authz DB, brought to the current
        revision first -- the same way a command or the server would, so
        the database a test seeds is stamped like any other."""
        alembic_migrations.upgrade(
            dburis={
                alembic_migrations.AGUI: sqlite_dburi(self.agui_db_path),
                alembic_migrations.AUTHZ: sqlite_dburi(self.db_path),
            }
        )
        return authz_schema.get_session(engine_url=self.dburi)


def _point_db(
    config_path: pathlib.Path, key: str, db_path: pathlib.Path
) -> None:
    """Repoint one of a copied installation's DBs at a scratch file.

    The replacement is passed to 'subn' as a callable because 're.sub'
    expands backslash escapes in a replacement *string*.

    Builds the URIs directly rather than via the 'authz_dburi_*' fixtures
    in 'tests/conftest.py': those derive from the function-scoped
    'tmp_path', and the caller here is the module-scoped
    '_installation_template', which cannot request them.
    """
    text = config_path.read_text()
    replacement = (
        f"{key}:\n"
        f'  sync_dburi: "{sqlite_dburi(db_path)}"\n'
        f'  async_dburi: "{sqlite_dburi(db_path, "+aiosqlite")}"'
    )
    text, n_subs = _dburi_re(key).subn(lambda _: replacement, text)
    # Fail loudly if the example config's shape drifts out from under us.
    assert n_subs == 1, f"expected one {key} stanza, found {n_subs}"
    config_path.write_text(text)


def _pin_ollama_base_url(config_path: pathlib.Path) -> None:
    """Pin a dummy 'OLLAMA_BASE_URL' value inline in a copied config.

    'example/minimal.yaml' lists a bare 'OLLAMA_BASE_URL' under
    'environment', i.e. one that must resolve from the ambient
    environment. Rewriting it to the 'name'/'value' form (the same shape
    'INSTALLATION_PATH' already uses) makes the scratch installation
    self-contained, so the suite does not depend on a host env var or a
    gitignored repo-root '.env' (which CI lacks). The CLI never connects
    to it -- the value only needs to resolve at config-load time.
    """
    text = config_path.read_text()
    replacement = (
        '  - name: "OLLAMA_BASE_URL"\n    value: "http://localhost:11434"'
    )
    text, n_subs = _OLLAMA_ENV_RE.subn(replacement, text)
    assert n_subs == 1, f"expected one OLLAMA_BASE_URL entry, found {n_subs}"
    config_path.write_text(text)


@pytest.fixture(scope="module")
def _installation_template(tmp_path_factory):
    """Copy the example installation once per module (copytree is slow)."""
    base = tmp_path_factory.mktemp("cli_installation")
    dst = base / "example"
    shutil.copytree(_EXAMPLE_DIR, dst)

    config_path = dst / "minimal.yaml"
    db_path = base / "authz.sqlite"
    agui_db_path = base / "agui.sqlite"
    _point_db(config_path, _DB_KEYS["authz"], db_path)
    _point_db(config_path, _DB_KEYS["agui"], agui_db_path)
    _pin_ollama_base_url(config_path)

    return config_path, db_path, agui_db_path


@pytest.fixture
def scratch_installation(_installation_template) -> ScratchInstallation:
    """A copy of 'example/minimal.yaml' backed by a fresh, empty authz DB.

    Reuses the module-scoped tree copy but deletes the scratch database
    before each test, so every test starts from the default-public state
    (no RoomPolicy / AdminUser rows). Intended to be shared by any CLI
    suite that needs to drive commands against a real installation and
    a real-but-disposable authorization database.
    """
    config_path, db_path, agui_db_path = _installation_template
    db_path.unlink(missing_ok=True)
    agui_db_path.unlink(missing_ok=True)
    return ScratchInstallation(
        path=config_path,
        dburi=sqlite_dburi(db_path),
        db_path=db_path,
        agui_db_path=agui_db_path,
    )


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _db_stanza(db_path: pathlib.Path, **extra) -> dict:
    return {
        "sync_dburi": sqlite_dburi(db_path),
        "async_dburi": sqlite_dburi(db_path, "+aiosqlite"),
        **extra,
    }


@pytest.fixture
def write_installation(tmp_path):
    """Write a minimal installation, and hand back its path.

    Two database stanzas and an id, and nothing else: the code under test
    here reads the configuration rather than the rooms, completions or
    OIDC beside it. Building that configuration for real, instead of
    doubling it, is what keeps these tests honest as more of it is read --
    a double has to be taught each new property by hand, and answers a
    'Mock' until it is.

    'agui' / 'authz' add sub-keys to the corresponding stanza, e.g.
    'authz={"migration_policy": "disabled"}'. 'in_memory' omits both
    stanzas, leaving the in-memory defaults.
    """

    def _write(*, agui=None, authz=None, in_memory=False):
        config = {"id": "cli-testcase"}
        if not in_memory:
            config["thread_persistence_db"] = _db_stanza(
                tmp_path / "agui.sqlite", **(agui or {})
            )
            config["authorization_db"] = _db_stanza(
                tmp_path / "authz.sqlite", **(authz or {})
            )
        path = tmp_path / "installation.yaml"
        path.write_text(yaml.safe_dump(config), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def cli_dburis(tmp_path) -> dict[str, str]:
    """The two sync DBURIs 'write_installation' names."""
    return {
        alembic_migrations.AGUI: sqlite_dburi(tmp_path / "agui.sqlite"),
        alembic_migrations.AUTHZ: sqlite_dburi(tmp_path / "authz.sqlite"),
    }
