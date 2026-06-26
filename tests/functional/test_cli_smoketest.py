"""End-to-end smoke tests driving the real ``soliplex-cli`` binary.

Unlike the unit suite -- which exercises the commands in-process via Typer's
``CliRunner`` -- these spawn the CLI in a subprocess against a throwaway copy
of ``example/minimal.yaml`` backed by a scratch authorization database, so the
whole entry-point -> config-load -> ``asyncio.run`` -> async-policy path runs
exactly as a user would hit it. No LLM is required, so they run by default
(not marked ``needs_llm``).
"""

import json
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
import yaml

# 'tests/functional/test_cli_smoketest.py' -> parents[2] is the repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_EXAMPLE_DIR = _REPO_ROOT / "example"

# The 'authorization_dburi' stanza in 'example/minimal.yaml', repointed at a
# throwaway sqlite file so the smoke test never touches the checked-in DB.
_AUTHZ_DBURI_RE = re.compile(
    r'authorization_dburi:\n  sync: "[^"]*"\n  async: "[^"]*"',
)
# The bare 'OLLAMA_BASE_URL' env requirement, pinned inline so the scratch
# installation resolves without an ambient env var or a repo-root '.env'.
_OLLAMA_ENV_RE = re.compile(r'^  - "OLLAMA_BASE_URL"$', re.MULTILINE)

ALICE = "alice@example.com"
ROLE_JP = '$[?$.role == "admin"]'
# A room configured in 'example/minimal.yaml' whose agent needs no LLM, so
# loading the installation for a 'room-authz' command requires no provider.
ROOM = "faux"


@pytest.fixture
def scratch_installation(tmp_path):
    """A copy of 'example/minimal.yaml' backed by a fresh, empty authz DB."""
    dst = tmp_path / "example"
    shutil.copytree(_EXAMPLE_DIR, dst)
    config_path = dst / "minimal.yaml"
    db_path = tmp_path / "authz.sqlite"

    text = config_path.read_text()
    text, n_db = _AUTHZ_DBURI_RE.subn(
        "authorization_dburi:\n"
        f'  sync: "sqlite:///{db_path}"\n'
        f'  async: "sqlite+aiosqlite:///{db_path}"',
        text,
    )
    assert n_db == 1, f"expected one authz_dburi stanza, found {n_db}"
    text, n_env = _OLLAMA_ENV_RE.subn(
        '  - name: "OLLAMA_BASE_URL"\n    value: "http://localhost:11434"',
        text,
    )
    assert n_env == 1, f"expected one OLLAMA_BASE_URL entry, found {n_env}"
    config_path.write_text(text)

    return config_path


def _run(config_path, group, subcommand, *rest, input_text=None):
    """Run '<group> <subcommand> <config> ...' via the real CLI binary."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "soliplex.cli.main",
            group,
            subcommand,
            str(config_path),
            *rest,
        ],
        capture_output=True,
        text=True,
        input=input_text,
    )


def _cli(config_path, subcommand, *rest):
    """Run an 'admin-users' subcommand via the real CLI binary."""
    return _run(config_path, "admin-users", subcommand, *rest)


def _room(config_path, subcommand, *rest, input_text=None):
    """Run a 'room-authz' subcommand via the real CLI binary."""
    return _run(
        config_path, "room-authz", subcommand, *rest, input_text=input_text
    )


def _listed(result):
    """Parse the JSON 'admin_users' dump from the last line of stdout."""
    last = [line for line in result.stdout.splitlines() if line.strip()][-1]
    return json.loads(last)["admin_users"]


def _policy(result):
    """Parse the JSON room-policy dump from the last line of stdout."""
    last = [line for line in result.stdout.splitlines() if line.strip()][-1]
    return json.loads(last)


def test_admin_users_smoketest(scratch_installation):
    # A faithful end-to-end run of the 'admin-users' subcommands against the
    # real binary: add (by email and by JSONPath), reject a duplicate, list,
    # dump to YAML, reject a non-matching delete, then delete and confirm.
    # This is deliberately a single multi-step sequence (a smoke test), not a
    # set of one-act unit tests.
    added_email = _cli(scratch_installation, "add", ALICE)
    assert added_email.returncode == 0, added_email.stderr
    assert ALICE in added_email.stdout

    added_json_path = _cli(scratch_installation, "add", "--json-path", ROLE_JP)
    assert added_json_path.returncode == 0, added_json_path.stderr

    duplicate = _cli(scratch_installation, "add", ALICE)
    assert duplicate.returncode == 1
    assert "already an admin" in duplicate.stdout

    listed = _cli(scratch_installation, "list")
    assert listed.returncode == 0, listed.stderr
    assert _listed(listed) == [ALICE, ROLE_JP]

    dumped = _cli(scratch_installation, "as-yaml")
    assert dumped.returncode == 0, dumped.stderr
    assert yaml.safe_load(dumped.stdout) == {
        "admin_users": [
            {"preferred_username": None, "email": ALICE, "json_path": None},
            {"preferred_username": None, "email": None, "json_path": ROLE_JP},
        ],
    }

    missing = _cli(scratch_installation, "delete", "nobody@example.com")
    assert missing.returncode == 1
    assert "is not an admin" in missing.stdout

    deleted = _cli(scratch_installation, "delete", ALICE)
    assert deleted.returncode == 0, deleted.stderr
    assert _listed(deleted) == [ROLE_JP]


def test_room_authz_smoketest(scratch_installation):
    # A faithful end-to-end run of the 'room-authz' subcommands against the
    # real binary, ending with a delete-then-recreate that proves the async
    # engine's 'PRAGMA foreign_keys=ON' cascades ACL rows (so no orphan
    # re-attaches to the new policy via SQLite primary-key reuse). This is
    # deliberately a single multi-step sequence (a smoke test), not a set of
    # one-act unit tests.
    private = _room(scratch_installation, "make-private", ROOM)
    assert private.returncode == 0, private.stderr
    assert _policy(private) == {
        "room_id": ROOM,
        "default_allow_deny": "DENY",
        "acl_entries": [],
    }

    added = _room(
        scratch_installation,
        "add-acl-entry",
        ROOM,
        "--allow",
        "--email",
        ALICE,
    )
    assert added.returncode == 0, added.stderr
    assert _policy(added)["acl_entries"] == [
        {
            "allow_deny": "ALLOW",
            "everyone": False,
            "authenticated": False,
            "preferred_username": None,
            "email": ALICE,
            "json_path": None,
        },
    ]

    shown = _room(scratch_installation, "show", ROOM)
    assert shown.returncode == 0, shown.stderr
    assert _policy(shown)["acl_entries"][0]["email"] == ALICE

    dumped = _room(scratch_installation, "as-yaml", ROOM)
    assert dumped.returncode == 0, dumped.stderr
    assert yaml.safe_load(dumped.stdout)["acl_entries"][0]["email"] == ALICE

    missing = _room(
        scratch_installation,
        "delete-acl-entry",
        ROOM,
        "--allow",
        "--email",
        "nobody@example.com",
    )
    assert missing.returncode == 1
    assert "No matching ACL entry" in missing.stdout

    # Drop the whole policy (with its ALLOW entry) via a 'null' from-yaml ...
    dropped = _room(
        scratch_installation, "from-yaml", ROOM, input_text="null\n"
    )
    assert dropped.returncode == 0, dropped.stderr

    # ... then recreate it: the ALLOW entry must not resurface.
    recreated = _room(scratch_installation, "make-private", ROOM)
    assert recreated.returncode == 0, recreated.stderr
    assert _policy(recreated)["acl_entries"] == []
