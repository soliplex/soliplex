from __future__ import annotations

import dataclasses
import pathlib
import re
import shutil

import pytest
from typer.testing import CliRunner

from soliplex.authz import schema as authz_schema
from tests._dburi import sqlite_dburi

# 'tests/unit/cli/conftest.py' -> parents[3] is the repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_EXAMPLE_DIR = _REPO_ROOT / "example"

# Matches the 'authorization_dburi' stanza in 'example/minimal.yaml' so a
# scratch copy can be repointed at a throwaway sqlite file.
_AUTHZ_DBURI_RE = re.compile(
    r'authorization_dburi:\n  sync: "[^"]*"\n  async: "[^"]*"',
)

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
    that the installation's 'authorization_dburi' has been repointed at.
    'session()' opens a sync SQLAlchemy session against that database,
    creating the authz schema on first use.
    """

    path: pathlib.Path
    dburi: str
    db_path: pathlib.Path

    def session(self):
        return authz_schema.get_session(
            engine_url=self.dburi,
            init_schema=True,
        )


def _point_authz_db(config_path: pathlib.Path, db_path: pathlib.Path) -> None:
    """Repoint a copied installation's authz DB at an absolute scratch file.

    The replacement is passed to 'subn' as a callable because 're.sub'
    expands backslash escapes in a replacement *string*.

    Builds the URIs directly rather than via the 'authz_dburi_*' fixtures
    in 'tests/conftest.py': those derive from the function-scoped
    'tmp_path', and the caller here is the module-scoped
    '_installation_template', which cannot request them.
    """
    text = config_path.read_text()
    replacement = (
        "authorization_dburi:\n"
        f'  sync: "{sqlite_dburi(db_path)}"\n'
        f'  async: "{sqlite_dburi(db_path, "+aiosqlite")}"'
    )
    text, n_subs = _AUTHZ_DBURI_RE.subn(lambda _: replacement, text)
    # Fail loudly if the example config's shape drifts out from under us.
    assert n_subs == 1, f"expected one authz_dburi stanza, found {n_subs}"
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
    _point_authz_db(config_path, db_path)
    _pin_ollama_base_url(config_path)

    return config_path, db_path


@pytest.fixture
def scratch_installation(_installation_template) -> ScratchInstallation:
    """A copy of 'example/minimal.yaml' backed by a fresh, empty authz DB.

    Reuses the module-scoped tree copy but deletes the scratch database
    before each test, so every test starts from the default-public state
    (no RoomPolicy / AdminUser rows). Intended to be shared by any CLI
    suite that needs to drive commands against a real installation and
    a real-but-disposable authorization database.
    """
    config_path, db_path = _installation_template
    db_path.unlink(missing_ok=True)
    return ScratchInstallation(
        path=config_path,
        dburi=sqlite_dburi(db_path),
        db_path=db_path,
    )


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()
