"""Unit tests for the Moodle agent factory and tool functions."""

from __future__ import annotations

import json
from unittest import mock

import httpx
import pydantic_ai
import pytest
from pydantic_ai.models.test import TestModel

# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

BASE_URL = "http://moodle.test"
TOKEN = "test_token_123"

EXTRA_CONFIG = {
    "moodle_base_url": "secret:MOODLE_BASE_URL",
    "moodle_api_token": "secret:MOODLE_API_TOKEN",
}


def _make_agent_config():
    """Build a minimal mock FactoryAgentConfig."""
    ic = mock.MagicMock()
    ic.get_secret.side_effect = lambda ref: {
        "secret:MOODLE_BASE_URL": BASE_URL,
        "secret:MOODLE_API_TOKEN": TOKEN,
    }[ref]

    cfg = mock.MagicMock()
    cfg._installation_config = ic
    cfg.extra_config = dict(EXTRA_CONFIG)
    return cfg


def _mock_response(json_data):
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


def _patch_httpx(response):
    mock_client = mock.AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__ = mock.AsyncMock(
        return_value=mock_client,
    )
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    return mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    )


def _build_agent():
    """Build the Moodle agent using mocked config + model."""
    from soliplex.moodle.agent import moodle_tools_agent_factory

    agent_config = _make_agent_config()

    with mock.patch(
        "soliplex.moodle.agent.agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        return moodle_tools_agent_factory(agent_config)


def _get_tool_fn(agent, name):
    """Extract a tool's underlying async function."""
    return agent._function_toolset.tools[name].function


# -----------------------------------------------------------------
# Factory tests
# -----------------------------------------------------------------


def test_factory_returns_agent():
    agent = _build_agent()
    assert isinstance(agent, pydantic_ai.Agent)


def test_factory_accepts_skill_toolset_config():
    from soliplex.moodle.agent import moodle_tools_agent_factory

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        agent = moodle_tools_agent_factory(
            agent_config, skill_toolset_config=None
        )
    assert isinstance(agent, pydantic_ai.Agent)


def test_factory_agent_has_expected_tools():
    agent = _build_agent()
    tool_names = set(agent._function_toolset.tools.keys())
    assert tool_names == {
        "list_courses",
        "find_user",
        "list_enrolled_users",
        "get_completion_status",
        "get_course_contents",
        "get_course_completion_overview",
        "list_course_groups",
        "get_group_members",
        "list_cohorts",
        "get_cohort_members",
        "get_user_grades",
        "get_assignment_grades",
        "get_upcoming_events",
        "enrol_users",
        "send_message",
    }


# -----------------------------------------------------------------
# list_courses tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_courses_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_courses")

    resp = _mock_response(
        [
            {"id": 1, "shortname": "site", "fullname": "Site"},
            {"id": 2, "shortname": "py101", "fullname": "Python 101"},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    # site course (id=1) should be excluded
    assert len(result) == 1
    assert result[0]["id"] == 2
    assert result[0]["fullname"] == "Python 101"


@pytest.mark.asyncio
async def test_list_courses_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_courses")

    resp = _mock_response(
        {
            "exception": "webservice_access_exception",
            "errorcode": "accessexception",
            "message": "Access denied",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result
    assert "Access denied" in result["error"]


# -----------------------------------------------------------------
# find_user tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_user_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    resp = _mock_response(
        [
            {
                "id": 5,
                "username": "jdoe",
                "fullname": "Jane Doe",
                "email": "jdoe@example.com",
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("username", "jdoe"))

    assert len(result) == 1
    assert result[0]["username"] == "jdoe"
    assert result[0]["email"] == "jdoe@example.com"


@pytest.mark.asyncio
async def test_find_user_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Invalid field",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("bad_field", "x"))

    assert "error" in result


# -----------------------------------------------------------------
# list_enrolled_users tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_enrolled_users_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_enrolled_users")

    resp = _mock_response(
        [
            {
                "id": 5,
                "username": "jdoe",
                "fullname": "Jane Doe",
                "roles": [
                    {"roleid": 5, "name": "Student", "shortname": "student"}
                ],
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert len(result) == 1
    assert result[0]["roles"] == ["student"]


@pytest.mark.asyncio
async def test_list_enrolled_users_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_enrolled_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(9999))

    assert "error" in result


# -----------------------------------------------------------------
# get_completion_status tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completion_status_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_completion_status")

    resp = _mock_response(
        {
            "completionstatus": {
                "completed": True,
                "aggregation": 1,
                "completions": [
                    {
                        "type": 1,
                        "title": "Activity completion",
                        "status": "Yes",
                        "complete": True,
                        "timecompleted": 1700000000,
                    }
                ],
            }
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 5))

    assert result["completed"] is True
    assert len(result["completions"]) == 1
    assert result["completions"][0]["complete"] is True


@pytest.mark.asyncio
async def test_get_completion_status_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_completion_status")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 5))

    assert "error" in result
    assert "No permission" in result["error"]


# -----------------------------------------------------------------
# Feature 1: get_course_contents tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_contents_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_contents")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "General",
                "visible": 1,
                "summary": "",
                "modules": [
                    {
                        "id": 10,
                        "name": "Forum",
                        "modname": "forum",
                        "visible": 1,
                        "completion": 0,
                    },
                    {
                        "id": 11,
                        "name": "Quiz 1",
                        "modname": "quiz",
                        "visible": 1,
                        "completion": 2,
                    },
                ],
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert len(result) == 1
    assert result[0]["name"] == "General"
    assert len(result[0]["modules"]) == 2
    assert result[0]["modules"][1]["modname"] == "quiz"


@pytest.mark.asyncio
async def test_get_course_contents_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_contents")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(9999))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 2: get_course_completion_overview tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_completion_overview_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_completion_overview")

    # We need to mock two different API calls:
    # 1. get_enrolled_users returns list of users
    # 2. get_course_completion_status returns per-user status
    # Since they share the same httpx mock, we use side_effect

    enrolled_resp = [
        {"id": 3, "username": "u1", "fullname": "User 1", "roles": []},
        {"id": 4, "username": "u2", "fullname": "User 2", "roles": []},
        {"id": 5, "username": "u3", "fullname": "User 3", "roles": []},
    ]
    completion_u1 = {
        "completionstatus": {
            "completed": True,
            "aggregation": 1,
            "completions": [{"type": 1, "title": "t", "status": "Yes", "complete": True}],
        }
    }
    completion_u2 = {
        "completionstatus": {
            "completed": False,
            "aggregation": 1,
            "completions": [],
        }
    }
    completion_u3 = {
        "completionstatus": {
            "completed": True,
            "aggregation": 1,
            "completions": [{"type": 1, "title": "t", "status": "Yes", "complete": True}],
        }
    }

    responses = [
        enrolled_resp,
        completion_u1,
        completion_u2,
        completion_u3,
    ]

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    call_idx = 0

    def make_response(data):
        r = mock.MagicMock(spec=httpx.Response)
        r.status_code = 200
        r.json.return_value = data
        r.raise_for_status.return_value = None
        return r

    async def post_side_effect(*args, **kwargs):
        nonlocal call_idx
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(2))

    assert result["total_enrolled"] == 3
    assert result["completed"] == 2
    assert result["incomplete"] == 1
    assert result["completion_rate"] == 66.7
    assert len(result["users"]) == 3


@pytest.mark.asyncio
async def test_get_course_completion_overview_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_completion_overview")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(9999))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 3: Groups & cohorts tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_course_groups_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_course_groups")

    resp = _mock_response(
        [
            {"id": 1, "courseid": 2, "name": "Group A", "description": "Desc A"},
            {"id": 2, "courseid": 2, "name": "Group B", "description": ""},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert len(result) == 2
    assert result[0]["name"] == "Group A"


@pytest.mark.asyncio
async def test_get_group_members_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_group_members")

    resp = _mock_response([{"groupid": 1, "userids": [3, 4, 5]}])
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert result["groupid"] == 1
    assert result["userids"] == [3, 4, 5]


@pytest.mark.asyncio
async def test_get_group_members_tool_empty():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_group_members")

    resp = _mock_response([])
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert result["groupid"] == 999
    assert result["userids"] == []


@pytest.mark.asyncio
async def test_list_cohorts_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_cohorts")

    resp = _mock_response(
        [
            {"id": 1, "name": "Engineering", "idnumber": "ENG", "visible": 1},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Engineering"


@pytest.mark.asyncio
async def test_get_cohort_members_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_cohort_members")

    resp = _mock_response([{"cohortid": 1, "userids": [3, 4]}])
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert result["cohortid"] == 1
    assert result["userids"] == [3, 4]


@pytest.mark.asyncio
async def test_get_cohort_members_tool_empty():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_cohort_members")

    resp = _mock_response([])
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert result["cohortid"] == 999
    assert result["userids"] == []


# -----------------------------------------------------------------
# Feature 4: Grading tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_grades_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_grades")

    resp = _mock_response(
        {
            "tables": [
                {
                    "courseid": 2,
                    "userid": 3,
                    "tabledata": [
                        {
                            "itemname": {"content": "Quiz 1"},
                            "grade": {"content": "90.00"},
                            "percentage": {"content": "90.00 %"},
                        },
                        {
                            "itemname": {"content": "Assignment 1"},
                            "grade": {"content": "75.00"},
                            "percentage": {"content": "75.00 %"},
                        },
                    ],
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 3))

    assert len(result) == 2
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == "90.00"
    assert result[1]["itemname"] == "Assignment 1"


@pytest.mark.asyncio
async def test_get_user_grades_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_grades")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 3))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_assignment_grades_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_assignment_grades")

    # First call: get_course_contents, second call: get_assignment_grades
    contents_resp = [
        {
            "id": 1,
            "name": "General",
            "visible": 1,
            "summary": "",
            "modules": [
                {"id": 10, "name": "Assign 1", "modname": "assign", "visible": 1, "completion": 0},
                {"id": 11, "name": "Quiz 1", "modname": "quiz", "visible": 1, "completion": 0},
            ],
        }
    ]
    grades_resp = {
        "assignments": [
            {
                "assignmentid": 10,
                "grades": [
                    {"userid": 3, "grade": "85.00", "timemodified": 1700000000},
                ],
            }
        ],
        "warnings": [],
    }

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    call_idx = 0

    def make_response(data):
        r = mock.MagicMock(spec=httpx.Response)
        r.status_code = 200
        r.json.return_value = data
        r.raise_for_status.return_value = None
        return r

    async def post_side_effect(*args, **kwargs):
        nonlocal call_idx
        responses = [contents_resp, grades_resp]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(2))

    assert len(result) == 1
    assert result[0]["assignmentid"] == 10
    assert result[0]["grades"][0]["grade"] == "85.00"


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_no_assignments():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_assignment_grades")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "General",
                "visible": 1,
                "summary": "",
                "modules": [
                    {"id": 10, "name": "Quiz 1", "modname": "quiz", "visible": 1, "completion": 0},
                ],
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert result["message"] == "No assignments found in this course"


# -----------------------------------------------------------------
# Feature 5: Calendar & deadlines tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_upcoming_events_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_upcoming_events")

    resp = _mock_response(
        {
            "events": [
                {
                    "id": 1,
                    "name": "Quiz Deadline",
                    "description": "",
                    "courseid": 2,
                    "modulename": "quiz",
                    "eventtype": "course",
                    "timestart": 1700000000,
                    "timeduration": 0,
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("2", 30))

    assert len(result) == 1
    assert result[0]["name"] == "Quiz Deadline"
    assert result[0]["courseid"] == 2


@pytest.mark.asyncio
async def test_get_upcoming_events_tool_no_filter():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_upcoming_events")

    resp = _mock_response({"events": []})
    with _patch_httpx(resp):
        result = json.loads(await fn("", 7))

    assert result == []


@pytest.mark.asyncio
async def test_get_upcoming_events_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_upcoming_events")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


# -----------------------------------------------------------------
# Feature 7: Write operation tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrol_users_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "enrol_users")

    # No HTTP call needed for preview mode
    result = json.loads(await fn("3,4", 2, 5, False))

    assert result["action"] == "enrol_users"
    assert result["user_ids"] == [3, 4]
    assert "preview" in result
    assert "instructions" in result


@pytest.mark.asyncio
async def test_enrol_users_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "enrol_users")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", 2, 5, True))

    assert result["success"] is True
    assert result["enrolled"] == 2


@pytest.mark.asyncio
async def test_enrol_users_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "enrol_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 2, 5, True))

    assert "error" in result


@pytest.mark.asyncio
async def test_send_message_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "send_message")

    result = json.loads(await fn("3,4", "Hello!", False))

    assert result["action"] == "send_message"
    assert result["user_ids"] == [3, 4]
    assert "preview" in result


@pytest.mark.asyncio
async def test_send_message_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "send_message")

    resp = _mock_response([{"msgid": 1}, {"msgid": 2}])
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", "Hello!", True))

    assert result["success"] is True
    assert result["sent"] == 2
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_send_message_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "send_message")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3", "Hello!", True))

    assert "error" in result
