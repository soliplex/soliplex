"""Unit tests for revision '6fc1ea379a76' ('soliplex-v0.94').

The revision deletes stored 'THINKING_*' events from the AGUI database.
Each test prepares a throwaway SQLite database at the previous revision,
holding a mix of events, then migrates it, online or through the SQL that
offline ('--sql') mode emits.
"""

from __future__ import annotations

import json
import sqlite3

import pytest
import sqlalchemy as sa

from soliplex import alembic_migrations

AGUI = alembic_migrations.AGUI
PREVIOUS = "e5d2f5ef98a3"
REVISION = "6fc1ea379a76"

# event id -> the event as stored in 'run_event.data'
EVENTS = {
    1: {"type": "THINKING_START", "timestamp": None},
    2: {"type": "THINKING_TEXT_MESSAGE_START", "timestamp": None},
    3: {"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": "hmm"},
    4: {"type": "THINKING_TEXT_MESSAGE_END", "timestamp": None},
    5: {"type": "THINKING_END", "timestamp": None},
    6: {"type": "REASONING_START", "message_id": "m-1"},
    7: {
        "type": "TEXT_MESSAGE_CONTENT",
        "delta": '{"type": "THINKING_START"}',
    },
    # A tool result carrying binary output:  'json.dumps' escapes the NUL
    # as '\u0000'.
    8: {"type": "TOOL_CALL_RESULT", "content": "%PDF-1.5\x00\x01"},
}
KEPT = {6, 7, 8}


@pytest.fixture
def agui_path(tmp_path):
    return tmp_path / "agui.sqlite"


@pytest.fixture
def previous_agui(agui_path):
    """An AGUI database at the previous revision, holding 'EVENTS'"""
    dburi = f"sqlite:///{agui_path}"
    alembic_migrations.upgrade(PREVIOUS, dburis={AGUI: dburi})

    engine = sa.create_engine(dburi)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO thread "
                    "(id_, thread_id, room_id, created, user_name) "
                    "VALUES (1, 't-1', 'room', '2026-11-25', 'phreddy')"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO run (id_, thread_id_, run_id, created) "
                    "VALUES (1, 1, 'r-1', '2026-11-25')"
                )
            )
            for event_id, event in EVENTS.items():
                connection.execute(
                    sa.text(
                        "INSERT INTO run_event "
                        "(id_, created, run_id_, data) "
                        "VALUES (:id_, '2026-11-25', 1, :data)"
                    ),
                    {"id_": event_id, "data": json.dumps(event)},
                )
    finally:
        engine.dispose()

    return dburi


def _event_ids(agui_path) -> set[int]:
    with sqlite3.connect(agui_path) as connection:
        rows = connection.execute("SELECT id_ FROM run_event").fetchall()

    return {event_id for (event_id,) in rows}


def test_upgrade_agui_deletes_thinking_events(agui_path, previous_agui):

    alembic_migrations.upgrade(REVISION, dburis={AGUI: previous_agui})

    assert _event_ids(agui_path) == KEPT


def test_upgrade_agui_offline_deletes_thinking_events(
    tmp_path, monkeypatch, agui_path, previous_agui
):
    monkeypatch.chdir(tmp_path)
    alembic_migrations.upgrade(
        f"{PREVIOUS}:{REVISION}", dburis={AGUI: previous_agui}, sql=True
    )
    script = (tmp_path / f"{AGUI}.sql").read_text(encoding="utf-8")

    with sqlite3.connect(agui_path) as connection:
        connection.executescript(script)

    assert _event_ids(agui_path) == KEPT
