from unittest import mock  # s.b. only for the 'auth_module.authenticate' call

import pytest


def test_health_check(client_no_llm):
    response = client_no_llm.get("/api/ok")

    assert response.status_code == 200
    assert response.text == "OK"


@mock.patch("soliplex.auth.authenticate")
def test_rooms_endpoints(auth_fn, client_no_llm):
    get_rooms_response = client_no_llm.get("/api/v1/rooms")
    rooms_manifest = get_rooms_response.json()

    room_id = "haiku"
    room_info = rooms_manifest[room_id]

    get_room_response = client_no_llm.get(f"/api/v1/rooms/{room_id}")
    assert get_room_response.status_code == 200
    ext_room_info = get_room_response.json()

    # assert ext_room_info["name"] == room_info["name"]
    # assert ext_room_info["description"] == room_info["description"]
    assert ext_room_info["suggestions"] == room_info["suggestions"]
    assert ext_room_info["welcome_message"] == room_info["welcome_message"]
    assert (
        ext_room_info["enable_attachments"] == room_info["enable_attachments"]
    )


@mock.patch("soliplex.auth.authenticate")
@pytest.mark.needs_llm
def test_get_quiz_post_quiz_question(auth_fn, client):
    auth_fn.return_value = {
        "name": "Phreddy Phlyntstone",
        "email": "phreddy@example.com",
    }

    get_room_response = client.get("/api/v1/rooms/quiztest")
    assert get_room_response.status_code == 200
    room_info = get_room_response.json()

    quiz_id, *_ = room_info["quizzes"].keys()

    get_quiz_response = client.get(f"/api/v1/rooms/quiztest/quiz/{quiz_id}")
    assert get_quiz_response.status_code == 200
    quiz_info = get_quiz_response.json()

    for question in quiz_info["questions"]:
        uuid = question["metadata"]["uuid"]

        if "QA" in question["inputs"]:
            answer = "orange"
            expected = False
        elif "false" in question["metadata"]["options"]:
            answer = "orange"
            expected = False
        else:
            answer = "blue"
            expected = True

        post_question_response = client.post(
            f"/api/v1/rooms/quiztest/quiz/{quiz_id}/{uuid}",
            json={"text": answer},
        )
        assert post_question_response.status_code == 200
        answer_info = post_question_response.json()
        assert answer_info["correct"] == expected and "true" or "false"
        if not expected:
            assert (
                answer_info["expected_output"] == question["expected_output"]
            )
