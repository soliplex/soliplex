import json
import os
import random
import time
from unittest import mock  # s.b. only for the 'auth_module.authenticate' call

import pytest
from fastapi import testclient

from soliplex import main

#
#   Envvar:  limit max number of rooms tested.
#
SOLIPLEX_FUNCTEST_MAX_ROOMS = "SOLIPLEX_FUNCTEST_MAX_ROOMS"


@pytest.fixture
def client():
    with testclient.TestClient(main.create_app()) as client:
        yield client


def test_health_check(client):
    response = client.get("/api/ok")

    assert response.status_code == 200
    assert response.text == "OK"

@mock.patch("soliplex.auth.authenticate")
def test_rooms_endpoints(auth_fn, client):
    get_rooms_response = client.get("/api/v1/rooms")
    rooms_manifest = get_rooms_response.json()

    room_id = "haiku"
    room_info = rooms_manifest[room_id]

    get_room_response = client.get(f"/api/v1/rooms/{room_id}")
    assert get_room_response.status_code == 200
    ext_room_info = get_room_response.json()

    #assert ext_room_info["name"] == room_info["name"]
    #assert ext_room_info["description"] == room_info["description"]
    assert ext_room_info["suggestions"] == room_info["suggestions"]
    assert ext_room_info["welcome_message"] == room_info["welcome_message"]
    assert (
        ext_room_info["enable_attachments"] == room_info["enable_attachments"]
    )


@mock.patch("soliplex.auth.authenticate")
def test_post_convos_new_rooms(auth_fn, client):
    IDENTITY_QUERY = "Who am I?"
    identity_query = {"text": IDENTITY_QUERY}
    TIME_QUERY = "What time is it?"
    time_query = {"text": TIME_QUERY}

    auth_fn.return_value = {
        "name": "Phreddy Phlyntstone",
        "email": "phreddy@example.com",
    }

    get_rooms_response = client.get("/api/v1/rooms")
    assert get_rooms_response.status_code == 200
    rooms_manifest = get_rooms_response.json()

    room_ids = sorted(rooms_manifest)

    max_rooms = os.getenv(SOLIPLEX_FUNCTEST_MAX_ROOMS)
    if max_rooms is not None:
        room_ids = random.sample(room_ids, int(max_rooms))

    for room_id in room_ids:

        response = client.post(
            f"/api/v1/convos/new/{room_id}", json=identity_query,
        )
        assert response.status_code == 200

        new_convo_json = response.json()
        assert new_convo_json["room_id"] == room_id
        assert new_convo_json["name"] == IDENTITY_QUERY
        convo_uuid = new_convo_json["convo_uuid"]

        new_convo_messages = new_convo_json["message_history"]
        user_msg, llm_msg = new_convo_messages
        assert user_msg["origin"] == "user"
        assert user_msg["text"] == IDENTITY_QUERY
        assert llm_msg["origin"] == "llm"

        response = client.post(
            f"/api/v1/convos/{convo_uuid}", json=time_query,
        )
        assert response.status_code == 200

        # Response is NLD JSON.
        #old_convo_json = response.json()
        user_msg, *llm_messages = [
            json.loads(line) for line in response.text.splitlines()
        ]
        assert user_msg["role"] == "user"  #  why is this not "origin"?
        assert user_msg["content"] == TIME_QUERY  #  why is this not "text"?

        last_llm_msg = llm_messages[-1]
        assert last_llm_msg["role"] == "model"  # why is this not "origin"

        time.sleep(5)
