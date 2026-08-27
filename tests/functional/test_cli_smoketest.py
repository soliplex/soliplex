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
import sqlalchemy
import yaml

from soliplex import authz
from soliplex.authz import schema as authz_schema
from tests._dburi import sqlite_dburi

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
BOB = "bob"
ROLE_JP = '$[?$.role == "admin"]'
# A valid JSONPath used only to satisfy the 'ACLEntry' write-time validator
# when seeding a row that is then corrupted (below) to an uncompilable query.
SEED_ACL_JP = '$[?$.preferred_username == "seed-marker"]'
# An uncompilable query (the filter function is unregistered) carrying a
# distinctive marker, so 'audit room-authz' surfaces it -- and only it.
STALE_ACL_JP = "$[?stale_filter_func($.preferred_username)]"
STALE_ACL_MARKER = "stale_filter_func"
# A room configured in 'example/minimal.yaml' whose agent needs no LLM, so
# loading the installation for a 'room-authz' command requires no provider.
ROOM = "faux"
# The phrase the DB-reading 'audit' sections print for an authz DBURI that
# cannot be opened.
UNREACHABLE_MARKER = "authorization database unreachable"


@pytest.fixture
def scratch_installation(tmp_path, authz_dburi_sync, authz_dburi_async):
    """A copy of 'example/minimal.yaml' backed by a fresh, empty authz DB."""
    return _scratch_installation(tmp_path, authz_dburi_sync, authz_dburi_async)


@pytest.fixture
def unreachable_authz_installation(tmp_path):
    """A scratch installation whose authz DBURI the driver cannot open.

    The sqlite file sits under a directory that does not exist, standing in
    for any authz DBURI that fails to resolve -- the reported case was a
    Postgres unix socket nothing was listening on.
    """
    db_path = tmp_path / "no-such-dir" / "authz.sqlite"
    return _scratch_installation(
        tmp_path,
        sqlite_dburi(db_path),
        sqlite_dburi(db_path, "+aiosqlite"),
    )


def _scratch_installation(tmp_path, authz_dburi_sync, authz_dburi_async):
    """Copy 'example/' to 'tmp_path', repointed at the given authz DBURIs."""
    dst = tmp_path / "example"
    shutil.copytree(_EXAMPLE_DIR, dst)
    config_path = dst / "minimal.yaml"

    text = config_path.read_text()
    # Passed as a callable because 're.sub' expands backslash escapes in a
    # replacement *string*, which a Windows 'tmp_path' would trip over.
    authz_replacement = (
        "authorization_dburi:\n"
        f'  sync: "{authz_dburi_sync}"\n'
        f'  async: "{authz_dburi_async}"'
    )
    text, n_db = _AUTHZ_DBURI_RE.subn(
        lambda _: authz_replacement,
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


def _audit(config_path, subcommand, *rest):
    """Run an 'audit' subcommand via the real CLI binary."""
    return _run(config_path, "audit", subcommand, *rest)


def _ask(config_path, *rest):
    """Run the 'ask' command (no subcommand) via the real CLI binary."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "soliplex.cli.main",
            "ask",
            str(config_path),
            *rest,
        ],
        capture_output=True,
        text=True,
    )


def _listed(result):
    """Parse the JSON 'admin_users' dump from the last line of stdout."""
    last = [line for line in result.stdout.splitlines() if line.strip()][-1]
    return json.loads(last)["admin_users"]


def _policy(result):
    """Parse the JSON room-policy dump from the last line of stdout."""
    last = [line for line in result.stdout.splitlines() if line.strip()][-1]
    return json.loads(last)


def _seed_stale_acl_entry(db_path, room_id):
    """Give 'room_id' an ACL entry whose stored 'json_path' no longer compiles.

    The CLI cannot create such a row ('add-acl-entry' compile-validates
    its query), so seed a valid entry through the ORM -- satisfying the
    write-time validator -- then overwrite its 'json_path' with a raw
    UPDATE that bypasses the validator, mirroring the persistence-layer
    test. This is the scenario 'audit' must tolerate via the unchecked
    'list_room_policies' read.
    """
    session = authz_schema.get_session(
        engine_url=sqlite_dburi(db_path),
        init_schema=True,
    )
    with session:
        policy = session.scalars(
            sqlalchemy.select(authz_schema.RoomPolicy).where(
                authz_schema.RoomPolicy.room_id == room_id
            )
        ).one()
        entry = authz_schema.ACLEntry(
            allow_deny=authz.AllowDeny.DENY,
            json_path=SEED_ACL_JP,
        )
        entry.room_policy = policy
        session.add(entry)
        session.commit()
        session.execute(
            sqlalchemy.text(
                "UPDATE room_acl_entries SET json_path = :stale "
                "WHERE json_path = :seed"
            ),
            {"stale": STALE_ACL_JP, "seed": SEED_ACL_JP},
        )
        session.commit()


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


def test_audit_smoketest(scratch_installation, authz_db_path):
    # Seed admin + room-policy state through the mutation commands, then
    # confirm the 'audit' subcommands -- which now read the authz database
    # through the 'AdminUserPolicy' / 'RoomAuthorizationPolicy' async
    # policies rather than a direct sync session -- reflect it via the real
    # binary. This is deliberately a single multi-step sequence (a smoke
    # test), not a set of one-act unit tests.
    seeded_admin = _cli(scratch_installation, "add", ALICE)
    assert seeded_admin.returncode == 0, seeded_admin.stderr

    seeded_private = _room(scratch_installation, "make-private", ROOM)
    assert seeded_private.returncode == 0, seeded_private.stderr

    # A valid ACL entry for 'bob': it grants access, but being valid the
    # audit never prints its discriminator.
    granted_bob = _room(
        scratch_installation,
        "add-acl-entry",
        ROOM,
        "--allow",
        "--preferred-username",
        BOB,
    )
    assert granted_bob.returncode == 0, granted_bob.stderr

    # ... and one whose stored 'json_path' no longer compiles -- the only
    # kind 'audit room-authz' surfaces by its query string.
    _seed_stale_acl_entry(authz_db_path, ROOM)

    audited_admins = _audit(scratch_installation, "admin-users")
    assert audited_admins.returncode == 0, audited_admins.stderr
    assert ALICE in audited_admins.stdout

    # The uncompilable entry is an audit finding (non-zero exit) and its
    # query is printed; the valid 'bob' entry stays silent.
    audited_rooms = _audit(scratch_installation, "room-authz")
    assert audited_rooms.returncode == 1, audited_rooms.stdout
    assert STALE_ACL_MARKER in audited_rooms.stdout
    assert BOB not in audited_rooms.stdout


def test_audit_unreachable_authz_db_smoketest(unreachable_authz_installation):
    # An authz DBURI the driver cannot resolve is an audit finding, not a
    # crash: both DB-reading sections report it and exit non-zero rather
    # than letting the driver's exception escape as a traceback.
    # Deliberately one multi-step sequence (a smoke test), not one-act
    # unit tests.
    audited_admins = _audit(unreachable_authz_installation, "admin-users")
    assert audited_admins.returncode == 1, audited_admins.stdout
    assert UNREACHABLE_MARKER in audited_admins.stdout
    assert "Traceback" not in audited_admins.stderr

    audited_rooms = _audit(unreachable_authz_installation, "room-authz")
    assert audited_rooms.returncode == 1, audited_rooms.stdout
    assert UNREACHABLE_MARKER in audited_rooms.stdout
    assert "Traceback" not in audited_rooms.stderr


def test_ask_smoketest(scratch_installation):
    # Drive the 'ask' command end-to-end against the faux room (no LLM):
    # plain + JSON success on stdout, a prompt that makes the agent raise
    # (non-zero exit, diagnostic on stderr), and an unknown room. A single
    # multi-step smoke sequence, not a set of one-act unit tests.
    plain = _ask(scratch_installation, ROOM, "what is up?")
    assert plain.returncode == 0, plain.stderr
    assert "I don't know!" in plain.stdout

    as_json = _ask(scratch_installation, ROOM, "what is up?", "--json")
    assert as_json.returncode == 0, as_json.stderr
    payload = json.loads(as_json.stdout)
    assert payload["room_id"] == ROOM
    assert payload["response"] == "I don't know!"
    assert payload["thread_id"]

    failed = _ask(scratch_installation, ROOM, "fail")
    assert failed.returncode == 1
    assert "failing on request" in failed.stderr

    unknown = _ask(scratch_installation, "no-such-room", "hi")
    assert unknown.returncode == 1
    assert "No room configured" in unknown.stderr
