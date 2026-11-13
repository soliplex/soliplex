"""Room uploads and quotas, end to end

The unit suite drives the upload views directly, with mocked
dependencies.  These tests go through the real app and the real CLI
instead, against a scratch copy of 'example/minimal.yaml':  multipart
parsing, the JSON the API returns (which the frontend builds against),
an 'env:' quota resolved by the installation and checked at startup, and
what 'soliplex-cli audit rooms' prints.  No LLM is required.
"""

import os
import pathlib
import shutil
import subprocess
import sys
import time

import pytest
from fastapi import testclient

from soliplex import main
from soliplex import util
from soliplex.config import quotas as config_quotas
from soliplex.config import routing as config_routing
from tests._dburi import sqlite_dburi

# 'tests/functional/test_room_uploads.py' -> parents[2] is the repo root.
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_EXAMPLE_DIR = _REPO_ROOT / "example"

QUOTA_ROOM = "faux"  # its agent needs no LLM
OPEN_ROOM = "joker"  # no quota
QUOTA_ENV = "FAUX_UPLOAD_QUOTA"
QUOTA_BYTES = 20

API = "/api/v1"


def _replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"expected one {old!r}"
    return text.replace(old, new)


def _upload_installation(
    tmp_path: pathlib.Path,
    *,
    quota_env_value: str | None = str(QUOTA_BYTES),
) -> pathlib.Path:
    """Copy 'example/' into 'tmp_path', for room-upload tests

    - Both databases are repointed at scratch sqlite files:  the example's
      DBURIs are relative to the working directory, i.e. the checkout.
    - Only the 'faux' and 'joker' rooms are loaded.
    - 'faux' takes its upload quota from 'env:FAUX_UPLOAD_QUOTA', whose
      value is 'quota_env_value' (with 'None', the name is not declared).
    - Uploads land under 'tmp_path / "uploads"', since the example's
      'rooms_upload_path' is relative to the installation.
    """
    dst = tmp_path / "example"
    shutil.copytree(_EXAMPLE_DIR, dst)
    config_path = dst / "minimal.yaml"
    text = config_path.read_text(encoding="utf-8")

    for db_name, db_stem in [
        ("thread_persistence_db", "thread_persistence"),
        ("authorization_db", "authorization"),
    ]:
        db_path = tmp_path / f"{db_stem}.sqlite"
        text = _replace_once(
            text,
            f"{db_name}:\n"
            f'  sync_dburi: "sqlite:///db/sqlite/{db_stem}.sqlite"\n'
            f'  async_dburi: "sqlite+aiosqlite:///db/sqlite/{db_stem}.sqlite"',
            f"{db_name}:\n"
            f'  sync_dburi: "{sqlite_dburi(db_path)}"\n'
            f'  async_dburi: "{sqlite_dburi(db_path, "+aiosqlite")}"',
        )

    environment = (
        '  - name: "OLLAMA_BASE_URL"\n    value: "http://localhost:11434"\n'
    )
    if quota_env_value is not None:
        environment += (
            f'  - name: "{QUOTA_ENV}"\n    value: "{quota_env_value}"\n'
        )
    text = _replace_once(text, '  - "OLLAMA_BASE_URL"\n', environment)

    start = text.index("room_paths:\n")
    end = text.index("\n\n", start)
    text = (
        text[:start]
        + f'room_paths:\n  - "./rooms/{QUOTA_ROOM}"\n  - "./rooms/{OPEN_ROOM}"'
        + text[end:]
    )
    config_path.write_text(text, encoding="utf-8")

    room_config = dst / "rooms" / QUOTA_ROOM / "room_config.yaml"
    room_config.write_text(
        room_config.read_text(encoding="utf-8")
        + f'\nquotas:\n  room_uploads_bytes: "env:{QUOTA_ENV}"\n',
        encoding="utf-8",
    )

    return config_path


def _app(config_path: pathlib.Path):
    config_routing.register_default_routers()
    app = main.create_app(str(config_path), no_auth_mode=True)
    config_routing.add_registered_routers(app)
    return app


@pytest.fixture
def installation(tmp_path) -> pathlib.Path:
    return _upload_installation(tmp_path)


@pytest.fixture
def room_dir(tmp_path) -> pathlib.Path:
    return tmp_path / "uploads" / "rooms" / QUOTA_ROOM


@pytest.fixture
def client(installation):
    # Not the shared module-scoped clients:  each test gets its own
    # installation, uploads tree, and databases.
    with testclient.TestClient(_app(installation)) as client:
        yield client


def _post(client, filename: str, content: bytes, room_id: str = QUOTA_ROOM):
    return client.post(
        f"{API}/uploads/{room_id}",
        files={"upload_file": (filename, content, "application/octet-stream")},
    )


def test_rooms_report_quotas(client):
    quota_room = client.get(f"{API}/rooms/{QUOTA_ROOM}")
    open_room = client.get(f"{API}/rooms/{OPEN_ROOM}")

    assert quota_room.status_code == 200
    assert quota_room.json()["quotas"] == {"room_uploads_bytes": QUOTA_BYTES}
    assert open_room.json()["quotas"] == {"room_uploads_bytes": None}

    listed = client.get(f"{API}/rooms").json()
    assert listed[QUOTA_ROOM]["quotas"] == {"room_uploads_bytes": QUOTA_BYTES}


def test_upload_list_download(client, room_dir):
    content = b"0123456789"

    posted = _post(client, "a.txt", content)

    assert posted.status_code == 204
    assert posted.content == b""
    assert (room_dir / "a.txt").read_bytes() == content
    assert list(room_dir.glob(f"{util.UPLOAD_RESERVATION_PREFIX}*")) == []

    listing = client.get(f"{API}/uploads/{QUOTA_ROOM}")

    assert listing.status_code == 200
    body = listing.json()
    assert body["room_id"] == QUOTA_ROOM
    assert body["total_size_bytes"] == len(content)
    assert body["quota_bytes"] == QUOTA_BYTES
    assert body["available_bytes"] == QUOTA_BYTES - len(content)
    [upload] = body["uploads"]
    assert upload["filename"] == "a.txt"
    assert upload["size_bytes"] == len(content)
    assert upload["modified_at"] is not None

    downloaded = client.get(upload["url"])

    assert downloaded.status_code == 200
    assert downloaded.content == content


def test_upload_over_quota(client, room_dir):
    assert _post(client, "a.txt", b"0123456789").status_code == 204

    refused = _post(client, "b.txt", b"x" * 11)

    assert refused.status_code == 507
    assert refused.json() == {
        "detail": (
            "room upload quota exceeded: 11 bytes requested, 10 available"
        ),
    }
    assert not (room_dir / "b.txt").exists()
    assert list(room_dir.glob(f"{util.UPLOAD_RESERVATION_PREFIX}*")) == []

    # Replacing a file counts only the difference in size.
    replaced = _post(client, "a.txt", b"y" * QUOTA_BYTES)

    assert replaced.status_code == 204
    assert (room_dir / "a.txt").read_bytes() == b"y" * QUOTA_BYTES


def test_delete_frees_quota(client):
    assert _post(client, "a.txt", b"x" * QUOTA_BYTES).status_code == 204
    assert _post(client, "b.txt", b"x").status_code == 507

    deleted = client.delete(f"{API}/uploads/{QUOTA_ROOM}/a.txt")

    assert deleted.status_code == 204
    assert _post(client, "b.txt", b"x").status_code == 204
    assert (
        client.get(f"{API}/uploads/{QUOTA_ROOM}").json()["total_size_bytes"]
        == 1
    )


def test_room_without_quota(client):
    assert _post(client, "big.bin", b"x" * 1000, OPEN_ROOM).status_code == 204

    body = client.get(f"{API}/uploads/{OPEN_ROOM}").json()

    assert body["total_size_bytes"] == 1000
    assert body["quota_bytes"] is None
    assert body["available_bytes"] is None


def test_internal_files_counted_not_served(client, room_dir):
    # An upload in progress (or orphaned) holds its reservation:  counted
    # against the quota, but never listed, downloaded, or deleted.
    room_dir.mkdir(parents=True)
    reservation = room_dir / f"{util.UPLOAD_RESERVATION_PREFIX}abc"
    reservation.write_bytes(b"r" * 15)

    body = client.get(f"{API}/uploads/{QUOTA_ROOM}").json()

    assert body["uploads"] == []
    assert body["total_size_bytes"] == 15
    assert body["available_bytes"] == 5
    assert _post(client, "a.txt", b"x" * 6).status_code == 507

    name = reservation.name
    assert (
        client.get(f"{API}/uploads/{QUOTA_ROOM}/file/{name}").status_code
        == 404
    )
    assert (
        client.delete(f"{API}/uploads/{QUOTA_ROOM}/{name}").status_code == 404
    )
    assert _post(client, name, b"x").status_code == 400
    assert reservation.read_bytes() == b"r" * 15


@pytest.mark.parametrize(
    "w_env_value, expected_exc",
    [
        (None, config_quotas.QuotasUnresolvedEnvironment),
        ("20MB", config_quotas.QuotasInvalidEnvironmentValue),
    ],
)
def test_startup_refuses_unresolvable_quota(
    tmp_path,
    w_env_value,
    expected_exc,
):
    config_path = _upload_installation(tmp_path, quota_env_value=w_env_value)
    app = _app(config_path)

    # The lifespan resolves every room's quota before serving anything.
    with (
        pytest.raises(expected_exc, match=QUOTA_ENV),
        testclient.TestClient(app),
    ):
        pass


# ---------------------------------------------------------------------------
# 'soliplex-cli audit rooms'
# ---------------------------------------------------------------------------


def _audit_rooms(config_path: pathlib.Path, *group_options: str):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "soliplex.cli.main",
            "audit",
            *group_options,
            "rooms",
            str(config_path),
        ],
        capture_output=True,
        text=True,
    )


def test_audit_rooms_notes_overage_and_orphans(tmp_path, room_dir):
    config_path = _upload_installation(tmp_path)
    room_dir.mkdir(parents=True)
    (room_dir / "big.bin").write_bytes(b"x" * (QUOTA_BYTES + 5))
    orphan = room_dir / f"{util.UPLOAD_RESERVATION_PREFIX}orphan"
    orphan.write_bytes(b"r" * 7)
    two_hours_ago = time.time() - 7200
    os.utime(orphan, (two_hours_ago, two_hours_ago))

    audited = _audit_rooms(config_path)

    # Overages and orphans are notes:  they do not fail the audit.
    assert audited.returncode == 0, audited.stdout + audited.stderr
    assert (
        f"Room uploads quota: {QUOTA_BYTES} bytes (from env:{QUOTA_ENV}) "
        f"(used {QUOTA_BYTES + 12}, 160%)"
    ) in audited.stdout
    assert "NOTE: room uploads OVER QUOTA by 12 bytes" in audited.stdout
    assert "NOTE: 1 orphaned upload files, 7 bytes" in audited.stdout
    assert orphan.name in audited.stdout
    assert orphan.exists()  # 'audit' never deletes

    quiet = _audit_rooms(config_path, "--quiet")

    assert quiet.returncode == 0, quiet.stdout + quiet.stderr
    assert quiet.stdout == ""


def test_audit_rooms_fails_on_unresolvable_quota(tmp_path):
    config_path = _upload_installation(tmp_path, quota_env_value=None)

    audited = _audit_rooms(config_path, "--quiet")

    assert audited.returncode == 1
    assert "room_quotas" in audited.stdout
    assert QUOTA_ENV in audited.stdout
