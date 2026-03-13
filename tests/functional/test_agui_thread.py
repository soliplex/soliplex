import json
import time
import uuid

import pydantic
from ag_ui import core as agui_core

from soliplex.agui import parser as agui_parser

EVENT_DESERIALIZER = pydantic.TypeAdapter(agui_core.Event)

IDENTITY_QUERY = "Who am I?"


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
            if raw_line:
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
