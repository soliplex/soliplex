import pytest

EMAIL = "phreddy@example.com"


def test_health_check(client_no_llm):
    response = client_no_llm.get("/api/ok")

    assert response.status_code == 200
    assert response.text == "OK"


def test_rooms_endpoints(client_no_llm):
    get_rooms_response = client_no_llm.get("/api/v1/rooms")
    rooms_manifest = get_rooms_response.json()

    room_id = "chat"
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


def test_room_authz_endpoints(client_no_llm):
    get_authz_response = client_no_llm.get("/api/v1/rooms/functest/authz")
    assert get_authz_response.status_code == 200
    room_policy = get_authz_response.json()

    assert room_policy is None

    NEW_POLICY = {
        "room_id": "functest",
        "default_allow_deny": "deny",
        "acl_entries": [
            {
                "allow_deny": "allow",
                "everyone": False,
                "authenticated": False,
                "preferred_username": None,
                "email": EMAIL,
            },
        ],
    }

    post_authz_response = client_no_llm.post(
        "/api/v1/rooms/functest/authz",
        json=NEW_POLICY,
    )
    assert post_authz_response.status_code == 204

    after_post_response = client_no_llm.get("/api/v1/rooms/functest/authz")
    assert after_post_response.status_code == 200
    after_post_room_policy = after_post_response.json()

    assert after_post_room_policy == NEW_POLICY

    delete_authz_response = client_no_llm.delete(
        "/api/v1/rooms/functest/authz",
    )
    assert delete_authz_response.status_code == 204

    after_delete_response = client_no_llm.get("/api/v1/rooms/functest/authz")
    assert after_delete_response.status_code == 200
    after_delete_room_policy = after_delete_response.json()

    assert after_delete_room_policy is None


@pytest.mark.needs_llm
def test_get_quiz_post_quiz_question(client):
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
