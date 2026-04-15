import json
import re
import time
import uuid

import pydantic
from ag_ui import core as agui_core

from soliplex.agui import parser as agui_parser

EVENT_DESERIALIZER = pydantic.TypeAdapter(agui_core.Event)

IDENTITY_QUERY = "Who am I?"

SSE_ID_PREFIX = "id: "
SSE_DATA_PREFIX = "data: "


def test_post_rooms_roomid_agui_etc(client_no_llm):
    new_thread_request = {"metadata": {"name": "functest"}}

    room_id = "faux"

    print(f"New thread in room {room_id}")

    response = client_no_llm.post(
        f"/api/v1/rooms/{room_id}/agui",
        json=new_thread_request,
    )
    assert response.status_code == 200

    new_thread_json = response.json()
    assert new_thread_json["room_id"] == room_id
    thread_id = new_thread_json["thread_id"]

    (run_id,) = new_thread_json["runs"]

    initial_run_request = {
        "thread_id": thread_id,
        "run_id": run_id,
        "state": None,
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": IDENTITY_QUERY,
            },
        ],
        "context": [],
        "tools": [],
        "forwarded_props": None,
    }

    with client_no_llm.stream(
        method="POST",
        url=f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
        json=initial_run_request,
    ) as response:
        assert response.status_code == 200

        # Response is SSE JSON

        pfx = "data: "
        pfx_len = len(pfx)

        event_log = []
        esp = agui_parser.EventStreamParser(event_log=event_log)

        for raw_line in response.iter_lines():
            if raw_line and raw_line.startswith(pfx):
                event_json = json.loads(raw_line[pfx_len:])
                # Work around ag_ui issue #756??
                # agui_event = EVENT_DESERIALIZER.validate_python(
                #    event_json
                # )
                agui_event = agui_parser.agui_event_from_json(event_json)
                esp(agui_event)

    time.sleep(0.25)  # let background save complete

    response = client_no_llm.get(
        f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
    )
    run_json = response.json()
    events = run_json["events"]
    assert len(events) > 2
    assert events[0]["type"] == "RUN_STARTED"
    assert events[-1]["type"] == "RUN_FINISHED"

    # Attempt to exercise https://github.com/soliplex/soliplex/issues/733
    response = client_no_llm.delete(
        f"/api/v1/rooms/{room_id}/agui/{thread_id}",
    )

    # Exercise https://github.com/soliplex/soliplex/issues/950
    # New thread after thread deletion triggers bogus sqlite3
    # behaviour without a 'PRAGMA foreign_keys=ON' on each connection.
    response = client_no_llm.post(
        f"/api/v1/rooms/{room_id}/agui",
        json=new_thread_request,
    )
    assert response.status_code == 200


def _parse_sse_stream(response):
    """Parse an SSE response into a list of (event_id, event_json) pairs.

    ``event_id`` is the integer index from the ``id:`` line (or
    ``None`` if the frame had no ``id:`` field).
    """
    current_id = None
    pairs = []

    for raw_line in response.iter_lines():
        if not raw_line:
            continue

        if raw_line.startswith(SSE_ID_PREFIX):
            # e.g.  "id: <run_id>:3"
            id_value = raw_line[len(SSE_ID_PREFIX) :]
            match = re.search(r":(\d+)$", id_value)
            current_id = int(match.group(1)) if match else None

        elif raw_line.startswith(SSE_DATA_PREFIX):
            event_json = json.loads(raw_line[len(SSE_DATA_PREFIX) :])
            pairs.append((current_id, event_json))
            current_id = None

    return pairs


def test_sse_resume_with_last_event_id(client_no_llm):
    """Demonstrate SSE resume: start a run, let it finish, then
    reconnect with Last-Event-ID and verify that only the events
    after the given index are replayed.
    """
    room_id = "faux"

    # --- 1. Create a thread ---
    response = client_no_llm.post(
        f"/api/v1/rooms/{room_id}/agui",
        json={"metadata": {"name": "sse-resume-test"}},
    )
    assert response.status_code == 200

    new_thread = response.json()
    thread_id = new_thread["thread_id"]
    (run_id,) = new_thread["runs"]

    run_request = {
        "thread_id": thread_id,
        "run_id": run_id,
        "state": None,
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "role": "user",
                "content": IDENTITY_QUERY,
            },
        ],
        "context": [],
        "tools": [],
        "forwarded_props": None,
    }

    # --- 2. Stream the full run (first-connect) ---
    with client_no_llm.stream(
        method="POST",
        url=f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
        json=run_request,
    ) as response:
        assert response.status_code == 200
        all_pairs = _parse_sse_stream(response)

    # Wait for the background task to finish persisting events
    time.sleep(0.5)

    # Verify we got events with sequential IDs
    assert len(all_pairs) > 2
    all_ids = [eid for eid, _ in all_pairs]
    assert all_ids == list(range(len(all_pairs)))

    first_type = all_pairs[0][1]["type"]
    last_type = all_pairs[-1][1]["type"]
    assert first_type == "RUN_STARTED"
    assert last_type == "RUN_FINISHED"

    # --- 3. Reconnect with Last-Event-ID ---
    # Pretend we only received the first 2 events (index 0, 1)
    # and ask the server to resume from index 1
    resume_after = 1

    last_event_id = f"{run_id}:{resume_after}"

    with client_no_llm.stream(
        method="POST",
        url=f"/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}",
        json=run_request,
        headers={"Last-Event-ID": last_event_id},
    ) as response:
        assert response.status_code == 200
        resumed_pairs = _parse_sse_stream(response)

    # --- 4. Verify the resumed stream ---
    # The resumed stream should contain only events after index 1
    expected_events = [
        event_json for eid, event_json in all_pairs if eid > resume_after
    ]
    resumed_events = [event_json for _, event_json in resumed_pairs]

    assert len(resumed_events) == len(expected_events)
    assert len(resumed_events) > 0

    for resumed, original in zip(resumed_events, expected_events, strict=True):
        assert resumed["type"] == original["type"]

    # The resumed IDs should start from resume_after + 1
    resumed_ids = [eid for eid, _ in resumed_pairs]
    expected_ids = list(range(resume_after + 1, len(all_pairs)))
    assert resumed_ids == expected_ids

    # Last event in the resumed stream should still be RUN_FINISHED
    assert resumed_events[-1]["type"] == "RUN_FINISHED"

    # Clean up
    client_no_llm.delete(
        f"/api/v1/rooms/{room_id}/agui/{thread_id}",
    )
