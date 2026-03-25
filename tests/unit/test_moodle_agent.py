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


def test_factory_wires_skill_toolset():
    from haiku.skills.agent import SkillToolset
    from haiku.skills.models import Skill
    from haiku.skills.models import SkillMetadata
    from haiku.skills.models import SkillSource

    from soliplex.moodle.agent import MOODLE_TOOLS_PROMPT
    from soliplex.moodle.agent import moodle_tools_agent_factory

    skill = Skill(
        metadata=SkillMetadata(
            name="test-skill", description="A test skill"
        ),
        source=SkillSource.ENTRYPOINT,
        instructions="Test instructions",
    )
    toolset = SkillToolset(skills=[skill])
    stc = mock.MagicMock()
    stc.skill_toolset = toolset

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        agent = moodle_tools_agent_factory(
            agent_config, skill_toolset_config=stc
        )

    assert isinstance(agent, pydantic_ai.Agent)
    # The skill toolset should be wired in
    assert toolset in agent._user_toolsets
    # System prompt should contain both the Moodle prompt and skill catalog
    instructions = "\n".join(agent._instructions)
    assert MOODLE_TOOLS_PROMPT in instructions
    assert "test-skill" in instructions


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
        "list_certifications",
        "get_certification_allocations",
        "get_user_certifications",
        "get_certification_history",
        "certify_user",
        "revoke_certification",
        "search_programs",
        "get_user_program_courses",
        "allocate_users_to_program",
        "list_tenants",
        # Phase A & B tools
        "browse_catalogue",
        "get_user_learning_catalogue",
        "get_program_content",
        "search_courses_for_program",
        "deallocate_user_from_program",
        "get_certification_user_details",
        "deallocate_user_from_certification",
        "archive_certification",
        "allocate_users_to_tenant",
        "suspend_users",
        "list_departments",
        "list_positions",
        "get_team_members",
        "assign_job",
        "assign_manager",
        # Organisation CRUD tools
        "get_potential_parent_departments",
        "get_potential_parent_positions",
        "create_department",
        "update_department",
        "delete_department",
        "create_position",
        "update_position",
        "delete_position",
        "delete_job",
        "unassign_manager",
        "list_competency_frameworks",
        "get_user_learning_plans",
        "get_user_competency",
        "get_course_competencies",
        # Reporting tools
        "list_reports",
        "get_report_data",
        "get_utm_report",
        "get_adv_comp_report",
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


@pytest.mark.asyncio
async def test_get_course_completion_overview_per_user_error():
    """When per-user completion lookup fails, the user still appears with completed=None."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_completion_overview")

    enrolled_resp = [
        {"id": 3, "username": "u1", "fullname": "User 1", "roles": []},
    ]
    # Second call (completion) returns an error
    error_resp = {
        "exception": "moodle_exception",
        "errorcode": "nopermissions",
        "message": "No permission",
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
        responses = [enrolled_resp, error_resp]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(2))

    assert result["total_enrolled"] == 1
    assert result["completed"] == 0
    assert result["users"][0]["completed"] is None
    assert result["users"][0]["completions"] == 0


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
async def test_list_course_groups_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_course_groups")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_group_members_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_group_members")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert "error" in result


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


@pytest.mark.asyncio
async def test_list_cohorts_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_cohorts")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_cohort_members_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_cohort_members")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert "error" in result


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
async def test_get_user_grades_tool_string_cells():
    """Grade table cells can be plain strings instead of dicts."""
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
                            "itemname": "Quiz 1",
                            "grade": "90.00",
                            "percentage": "90.00 %",
                        },
                    ],
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 3))

    assert len(result) == 1
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == "90.00"
    assert result[0]["percentage"] == "90.00 %"


@pytest.mark.asyncio
async def test_get_user_grades_tool_missing_keys():
    """Rows with missing grade/percentage keys still parse; rows without itemname are skipped."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_grades")

    resp = _mock_response(
        {
            "tables": [
                {
                    "courseid": 2,
                    "userid": 3,
                    "tabledata": [
                        # Row with only itemname
                        {"itemname": {"content": "Quiz 1"}},
                        # Row with no itemname — should be skipped
                        {"grade": {"content": "50"}},
                        # Non-dict row — should be skipped
                        "leader",
                    ],
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2, 3))

    assert len(result) == 1
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == ""
    assert result[0]["percentage"] == ""


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


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_contents_error():
    """Error on the first API call (get_course_contents)."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_assignment_grades")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(999))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_grades_error():
    """Error on the second API call (get_assignment_grades)."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_assignment_grades")

    contents_resp = [
        {
            "id": 1,
            "name": "General",
            "visible": 1,
            "summary": "",
            "modules": [
                {"id": 10, "name": "Assign 1", "modname": "assign", "visible": 1, "completion": 0},
            ],
        }
    ]
    error_resp = {
        "exception": "moodle_exception",
        "errorcode": "err",
        "message": "fail",
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
        responses = [contents_resp, error_resp]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(2))

    assert "error" in result


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

    # When no courseids provided, the tool fetches all courses first,
    # then calls get_calendar_events with those course IDs.
    courses_resp = _mock_response(
        [
            {"id": 1, "shortname": "site", "fullname": "Site"},
            {"id": 2, "shortname": "c1", "fullname": "C1"},
        ]
    )
    events_resp = _mock_response({"events": []})
    with mock.patch("httpx.AsyncClient.post", side_effect=[courses_resp, events_resp]):
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


# -----------------------------------------------------------------
# Feature 8: Certification tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_certifications_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_certifications")

    resp = _mock_response(
        [
            {"id": 1, "fullname": "Workplace Safety", "idnumber": "WS01", "status": 0},
            {"id": 2, "fullname": "Data Privacy", "idnumber": "DP01", "status": 0},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 2
    assert result[0]["fullname"] == "Workplace Safety"


@pytest.mark.asyncio
async def test_list_certifications_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_certifications")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_certification_allocations_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_allocations")

    resp = _mock_response(
        [
            {
                "id": 10,
                "userid": 3,
                "certificationid": 1,
                "userfullname": "Alice Johnson",
                "certificationfullname": "Workplace Safety",
                "timeallocated": 1700000000,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert len(result) == 1
    assert result[0]["userfullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_certification_allocations_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_allocations")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_certifications_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_certifications")

    resp = _mock_response(
        [
            {
                "id": 10,
                "userid": 3,
                "certificationid": 1,
                "userfullname": "Alice Johnson",
                "certificationfullname": "Workplace Safety",
                "timeallocated": 1700000000,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert len(result) == 1
    assert result[0]["certificationfullname"] == "Workplace Safety"


@pytest.mark.asyncio
async def test_get_user_certifications_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_certifications")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_certification_history_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_history")

    resp = _mock_response(
        [
            {"id": 1, "action": "allocated", "timecreated": 1700000000},
            {"id": 2, "action": "certified", "timecreated": 1700001000},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1, 3))

    assert len(result) == 2
    assert result[0]["action"] == "allocated"
    assert result[1]["action"] == "certified"


@pytest.mark.asyncio
async def test_get_certification_history_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_history")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1, 3))

    assert "error" in result


@pytest.mark.asyncio
async def test_certify_user_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "certify_user")

    result = json.loads(await fn("3", 1, False))

    assert result["action"] == "certify_user"
    assert result["userid"] == 3
    assert result["certificationid"] == 1
    assert "preview" in result
    assert "instructions" in result


@pytest.mark.asyncio
async def test_certify_user_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "certify_user")

    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 1, True))

    assert result["success"] is True
    assert result["userid"] == 3
    assert result["certificationid"] == 1


@pytest.mark.asyncio
async def test_certify_user_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "certify_user")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 1, True))

    assert "error" in result


@pytest.mark.asyncio
async def test_revoke_certification_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "revoke_certification")

    result = json.loads(await fn("3", 1, False))

    assert result["action"] == "revoke_certification"
    assert result["userid"] == 3
    assert result["certificationid"] == 1
    assert "preview" in result


@pytest.mark.asyncio
async def test_revoke_certification_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "revoke_certification")

    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 1, True))

    assert result["success"] is True
    assert result["userid"] == 3


@pytest.mark.asyncio
async def test_revoke_certification_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "revoke_certification")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 1, True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 9: Program tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_programs_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "search_programs")

    resp = _mock_response(
        [
            {"id": 1, "fullname": "Onboarding Program"},
            {"id": 2, "fullname": "Leadership Track"},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 2
    assert result[0]["fullname"] == "Onboarding Program"


@pytest.mark.asyncio
async def test_search_programs_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "search_programs")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_program_courses_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_program_courses")

    resp = _mock_response(
        [
            {"id": 2, "shortname": "safety101", "fullname": "Safety Fundamentals", "completed": True},
            {"id": 3, "shortname": "cyber101", "fullname": "Cybersecurity Basics", "completed": False},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert len(result) == 2
    assert result[0]["completed"] is True
    assert result[1]["completed"] is False


@pytest.mark.asyncio
async def test_get_user_program_courses_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_program_courses")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert "error" in result


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_program")

    result = json.loads(await fn("3,4,5", 1, False))

    assert result["action"] == "allocate_users_to_program"
    assert result["user_ids"] == [3, 4, 5]
    assert result["programid"] == 1
    assert "preview" in result
    assert "instructions" in result


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_program")

    resp = _mock_response({"result": []})
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", 1, True))

    assert result["success"] is True
    assert result["allocated"] == 2
    assert result["programid"] == 1


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_program")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3", 1, True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 10: Tenant tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenants_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_tenants")

    resp = _mock_response(
        [
            {"id": 1, "name": "Default", "sitename": "Moodle", "idnumber": "", "isdefault": True},
            {"id": 2, "name": "Regional", "sitename": "Regional", "idnumber": "REG01", "isdefault": False},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 2
    assert result[0]["isdefault"] is True
    assert result[1]["name"] == "Regional"


@pytest.mark.asyncio
async def test_list_tenants_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_tenants")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


# -----------------------------------------------------------------
# Feature 11: Catalogue tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_browse_catalogue_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "browse_catalogue")

    resp = _mock_response(
        {
            "contents": {
                "catalogueitems": [
                    {"id": 1, "title": "Safety 101", "url": "/course/1"}
                ]
            }
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["title"] == "Safety 101"


@pytest.mark.asyncio
async def test_browse_catalogue_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "browse_catalogue")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_learning_catalogue")

    resp = _mock_response(
        {
            "catalogue": {
                "listitems": [
                    {
                        "itemid": 1,
                        "fullname": "Safety",
                        "numcourses": 2,
                        "progress": 50,
                        "duedate": 0,
                        "isprogram": False,
                        "categoryname": "Training",
                    }
                ]
            }
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert len(result) == 1
    assert result[0]["fullname"] == "Safety"
    assert result[0]["progress"] == 50


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_learning_catalogue")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_program_content_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_program_content")

    resp = _mock_response(
        {"sets": [{"name": "Core"}], "courses": [{"id": 2}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert "sets" in result
    assert "courses" in result


@pytest.mark.asyncio
async def test_get_program_content_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_program_content")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 12: Deeper Program Management tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_courses_for_program_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "search_courses_for_program")

    resp = _mock_response(
        [{"id": 2, "fullname": "Safety Fundamentals"}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["fullname"] == "Safety Fundamentals"


@pytest.mark.asyncio
async def test_search_courses_for_program_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "search_courses_for_program")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_program")

    result = json.loads(await fn(3, 1, False))

    assert result["action"] == "deallocate_user_from_program"
    assert "preview" in result
    assert "instructions" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_program")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1, True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_program")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1, True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 13: Deeper Certification Management tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_certification_user_details_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_user_details")

    resp = _mock_response(
        {"id": 10, "userid": 3, "status": "certified"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1, 3))

    assert result["id"] == 10
    assert result["userid"] == 3
    assert result["status"] == "certified"


@pytest.mark.asyncio
async def test_get_certification_user_details_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_certification_user_details")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1, 3))

    assert "error" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_certification")

    result = json.loads(await fn(3, 1, False))

    assert result["action"] == "deallocate_user_from_certification"
    assert "preview" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_certification")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1, True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "deallocate_user_from_certification")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1, True))

    assert "error" in result


@pytest.mark.asyncio
async def test_archive_certification_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "archive_certification")

    result = json.loads(await fn(1, False))

    assert result["action"] == "archive_certification"
    assert "preview" in result


@pytest.mark.asyncio
async def test_archive_certification_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "archive_certification")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(1, True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_archive_certification_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "archive_certification")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(1, True))

    assert "error" in result


# -----------------------------------------------------------------
# Tenant write tools (allocate_users_to_tenant, suspend_users)
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_tenant")

    result = json.loads(await fn("3,4", 2, False))

    assert result["action"] == "allocate_users_to_tenant"
    assert "preview" in result
    assert result["user_ids"] == [3, 4]
    assert result["tenantid"] == 2


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_tenant")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", 2, True))

    assert result["success"] is True
    assert result["allocated"] == 2


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_tenant")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", 2, True))

    assert "error" in result


@pytest.mark.asyncio
async def test_suspend_users_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "suspend_users")

    result = json.loads(await fn("3,4", False))

    assert result["action"] == "suspend_users"
    assert "preview" in result
    assert "WARNING" in result["preview"]
    assert result["user_ids"] == [3, 4]


@pytest.mark.asyncio
async def test_suspend_users_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "suspend_users")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", True))

    assert result["success"] is True
    assert result["suspended"] == 2


@pytest.mark.asyncio
async def test_suspend_users_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "suspend_users")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 14: Organisation Structure tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_departments_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_departments")

    resp = _mock_response(
        {"departments": [{"id": 1, "name": "Engineering"}], "positions": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Engineering"


@pytest.mark.asyncio
async def test_list_departments_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_departments")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_list_positions_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_positions")

    resp = _mock_response(
        {"departments": [], "positions": [{"id": 1, "name": "Manager"}]}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Manager"


@pytest.mark.asyncio
async def test_list_positions_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_positions")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_team_members_tool():
    """Primary path: custom plugin returns department members."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_team_members")

    resp = _mock_response([
        {
            "userid": 3,
            "username": "alice",
            "firstname": "Alice",
            "lastname": "Johnson",
            "fullname": "Alice Johnson",
            "email": "alice@example.com",
            "departmentid": 1,
            "departmentname": "Engineering",
            "positionid": 1,
            "positionname": "Manager",
        },
    ])
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["fullname"] == "Alice Johnson"
    assert result[0]["departmentname"] == "Engineering"
    assert result[0]["positionname"] == "Manager"


@pytest.mark.asyncio
async def test_get_team_members_tool_fallback():
    """Falls back to managed_users when plugin not installed."""
    from soliplex.moodle.client import MoodleAPIError

    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_team_members")

    managed_resp = _mock_response(
        {"managedusers": [{"id": 3, "fullname": "Alice Johnson"}], "totalcount": 1}
    )

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: plugin endpoint returns error
            error_resp = _mock_response(
                {"exception": "moodle_exception", "errorcode": "invalidfunction", "message": "not found"}
            )
            return error_resp
        # Second call: managed_users returns data
        return managed_resp

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = _side_effect
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["fullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_team_members_tool_fallback_empty():
    """Fallback returns helpful note when legacy endpoint is also empty."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_team_members")

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(
                {"exception": "moodle_exception", "errorcode": "invalidfunction", "message": "not found"}
            )
        return _mock_response({"managedusers": [], "totalcount": 0})

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = _side_effect
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn())

    assert result["users"] == []
    assert "local_soliplex" in result["note"]


@pytest.mark.asyncio
async def test_get_team_members_tool_fallback_error():
    """Error on both primary and fallback endpoints returns error."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_team_members")

    call_count = 0

    async def _side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _mock_response(
                {"exception": "moodle_exception", "errorcode": "invalidfunction", "message": "not found"}
            )
        return _mock_response(
            {"exception": "moodle_exception", "errorcode": "err", "message": "fallback fail"}
        )

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = _side_effect
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn())

    assert "error" in result
    assert "fallback fail" in result["error"]


@pytest.mark.asyncio
async def test_get_team_members_tool_error():
    """HTTP error on primary endpoint is returned directly."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_team_members")

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = httpx.ConnectError("connection refused")
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_assign_job_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_job")

    result = json.loads(await fn(3, "ENG", "MGR", False))

    assert result["action"] == "assign_job"
    assert "preview" in result


@pytest.mark.asyncio
async def test_assign_job_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_job")

    resp = _mock_response({"id": 1})
    with _patch_httpx(resp):
        result = json.loads(await fn(3, "ENG", "MGR", True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_assign_job_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_job")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3, "ENG", "MGR", True))

    assert "error" in result


@pytest.mark.asyncio
async def test_assign_manager_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_manager")

    result = json.loads(await fn("4", "3", False))

    assert result["action"] == "assign_manager"
    assert "preview" in result
    assert result["user_ids"] == [4]
    assert result["manager_ids"] == [3]


@pytest.mark.asyncio
async def test_assign_manager_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_manager")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("4", "3", True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_assign_manager_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_manager")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("4", "3", True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 15: Competency tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_competency_frameworks_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_competency_frameworks")

    resp = _mock_response(
        {
            "frameworks": [
                {
                    "id": 1,
                    "shortname": "Core",
                    "idnumber": "CORE01",
                    "description": "Core skills",
                    "competencycount": 3,
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["shortname"] == "Core"


@pytest.mark.asyncio
async def test_list_competency_frameworks_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_competency_frameworks")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_learning_plans_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_learning_plans")

    resp = _mock_response(
        {
            "plans": [
                {
                    "id": 1,
                    "name": "Alice's Plan",
                    "description": "Dev plan",
                    "statusname": "Active",
                    "userid": 3,
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert len(result) == 1
    assert result[0]["name"] == "Alice's Plan"


@pytest.mark.asyncio
async def test_get_user_learning_plans_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_learning_plans")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_competency_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_competency")

    resp = _mock_response(
        {"usercompetency": {"userid": 3, "competencyid": 1}}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1))

    assert "usercompetency" in result
    assert result["usercompetency"]["userid"] == 3


@pytest.mark.asyncio
async def test_get_user_competency_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_user_competency")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(3, 1))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_course_competencies_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_competencies")

    resp = _mock_response(
        {
            "competencies": [
                {"competency": {"id": 1, "shortname": "Communication"}}
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert len(result) == 1
    assert result[0]["competency"]["shortname"] == "Communication"


@pytest.mark.asyncio
async def test_get_course_competencies_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_course_competencies")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(2))

    assert "error" in result


# -----------------------------------------------------------------
# Non-numeric ID validation tests
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrol_users_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "enrol_users")

    result = json.loads(await fn("alice,bob", 2, 5, False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_certify_user_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "certify_user")

    result = json.loads(await fn("alice", 1, False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_assign_manager_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_manager")

    result = json.loads(await fn("alice", "3", False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_assign_manager_tool_non_numeric_manager():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "assign_manager")

    result = json.loads(await fn("4", "bob", False))

    assert "error" in result
    assert "bob" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_send_message_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "send_message")

    result = json.loads(await fn("alice", "Hello!", False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_revoke_certification_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "revoke_certification")

    result = json.loads(await fn("alice", 1, False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_program")

    result = json.loads(await fn("alice", 1, False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "allocate_users_to_tenant")

    result = json.loads(await fn("alice", 1, False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_suspend_users_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "suspend_users")

    result = json.loads(await fn("alice", False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


# -----------------------------------------------------------------
# Name-based find_user tests
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_user_by_name():
    """find_user with field='name' splits into firstname+lastname criteria."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    resp = _mock_response(
        {
            "users": [
                {
                    "id": 3,
                    "username": "testuser1",
                    "firstname": "Alice",
                    "lastname": "Johnson",
                    "fullname": "Alice Johnson",
                    "email": "alice@example.com",
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("name", "Alice Johnson"))

    assert len(result) == 1
    assert result[0]["id"] == 3
    assert result[0]["fullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_find_user_by_firstname():
    """find_user with field='firstname' uses search_users."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    resp = _mock_response(
        {
            "users": [
                {
                    "id": 3,
                    "username": "testuser1",
                    "firstname": "Alice",
                    "lastname": "Johnson",
                    "fullname": "Alice Johnson",
                    "email": "alice@example.com",
                }
            ]
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("firstname", "Alice"))

    assert len(result) == 1
    assert result[0]["fullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_find_user_unsupported_field():
    """find_user with an unsupported field returns an error."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    result = json.loads(await fn("phone", "1234"))

    assert "error" in result
    assert "Unsupported field" in result["error"]


@pytest.mark.asyncio
async def test_find_user_by_name_error():
    """find_user with field='name' returns error on API failure."""
    agent = _build_agent()
    fn = _get_tool_fn(agent, "find_user")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("name", "Alice"))

    assert "error" in result


# -----------------------------------------------------------------
# Reporting tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_reports")

    resp = _mock_response(
        {
            "reports": [
                {
                    "id": 1,
                    "name": "Test Report",
                    "source": "...",
                    "sourcename": "Users",
                    "type": 0,
                    "timecreated": 0,
                    "timemodified": 0,
                }
            ],
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Test Report"


@pytest.mark.asyncio
async def test_list_reports_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "list_reports")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_report_data_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_report_data")

    resp = _mock_response(
        {
            "details": {
                "id": 1,
                "name": "Test Report",
                "source": "...",
                "sourcename": "Users",
                "type": 0,
            },
            "data": {
                "headers": ["Name", "Email"],
                "rows": [
                    {"columns": ["<a href='#'>Alice</a>", "alice@example.com"]}
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(reportid=1))

    assert result["headers"] == ["Name", "Email"]
    assert result["rows"][0] == ["Alice", "alice@example.com"]
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_report_data_tool_strips_none_values():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_report_data")

    resp = _mock_response(
        {
            "details": {
                "id": 1,
                "name": "Test Report",
                "source": "...",
                "sourcename": "Users",
                "type": 0,
            },
            "data": {
                "headers": ["Name", "Email"],
                "rows": [{"columns": [None, "alice@example.com"]}],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(reportid=1))

    assert result["rows"][0] == ["", "alice@example.com"]


@pytest.mark.asyncio
async def test_get_report_data_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_report_data")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(reportid=9999))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_utm_report_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_utm_report")

    resp = _mock_response(
        {
            "rows": [
                {
                    "userid": 3,
                    "username": "testuser1",
                    "firstname": "Alice",
                    "lastname": "Johnson",
                    "email": "alice@example.com",
                    "department": "Engineering",
                    "starttime": 1700000000,
                    "completedtime": 1700100000,
                }
            ],
            "totalcount": 1,
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(courseid=2))

    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "Alice Johnson"
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_utm_report_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_utm_report")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(courseid=2))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_adv_comp_report_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_adv_comp_report")

    resp = _mock_response(
        {
            "rows": [
                {
                    "userid": 4,
                    "username": "testuser2",
                    "firstname": "Bob",
                    "lastname": "Smith",
                    "email": "bob@example.com",
                    "department": "Operations",
                    "starttime": 1700000000,
                    "completedtime": None,
                }
            ],
            "totalcount": 1,
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(courseid=2))

    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "Bob Smith"
    assert result["rows"][0]["completedtime"] is None
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_adv_comp_report_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_adv_comp_report")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(courseid=2))

    assert "error" in result


# -----------------------------------------------------------------
# Organisation CRUD tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_potential_parent_departments_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_potential_parent_departments")

    resp = _mock_response(
        [{"id": 1, "name": "Root", "path": "/Root", "locked": 0}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Root"


@pytest.mark.asyncio
async def test_get_potential_parent_departments_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_potential_parent_departments")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_potential_parent_positions_tool():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_potential_parent_positions")

    resp = _mock_response(
        [{"id": 1, "name": "Management", "path": "/Mgmt", "locked": 0}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Management"


@pytest.mark.asyncio
async def test_get_potential_parent_positions_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "get_potential_parent_positions")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_create_department_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_department")

    result = json.loads(await fn(name="Finance", idnumber="FIN"))

    assert "preview" in result
    assert result["department"]["name"] == "Finance"


@pytest.mark.asyncio
async def test_create_department_tool_preview_with_optional():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_department")

    result = json.loads(
        await fn(name="Security", parent="ENG", description="Sec team")
    )

    assert result["department"]["parent"] == "ENG"
    assert result["department"]["description"] == "Sec team"


@pytest.mark.asyncio
async def test_create_department_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_department")

    resp = _mock_response(
        {"result": [{"id": 10, "name": "Finance", "idnumber": "FIN"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="Finance", idnumber="FIN", confirmed=True))

    assert len(result["created"]) == 1
    assert result["created"][0]["idnumber"] == "FIN"


@pytest.mark.asyncio
async def test_create_department_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_department")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_update_department_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_department")

    result = json.loads(await fn(idnumber="FIN", name="Finance Dept"))

    assert "preview" in result
    assert result["changes"]["name"] == "Finance Dept"


@pytest.mark.asyncio
async def test_update_department_tool_preview_with_optional():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_department")

    result = json.loads(
        await fn(idnumber="FIN", parent="ROOT", description="Updated")
    )

    assert result["changes"]["parent"] == "ROOT"
    assert result["changes"]["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_department_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_department")

    resp = _mock_response(
        {"result": [{"id": 10, "idnumber": "FIN"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="FIN", name="Finance Dept", confirmed=True))

    assert len(result["updated"]) == 1
    assert result["updated"][0]["idnumber"] == "FIN"


@pytest.mark.asyncio
async def test_update_department_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_department")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_department_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_department")

    result = json.loads(await fn(department_id=10))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_department_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_department")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(department_id=10, confirmed=True))

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_delete_department_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_department")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(department_id=10, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_create_position_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_position")

    result = json.loads(await fn(name="Engineer", idnumber="ENG"))

    assert "preview" in result
    assert result["position"]["name"] == "Engineer"


@pytest.mark.asyncio
async def test_create_position_tool_preview_with_optional():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_position")

    result = json.loads(
        await fn(name="Analyst", parent="MGMT", description="Data team")
    )

    assert result["position"]["parent"] == "MGMT"
    assert result["position"]["description"] == "Data team"


@pytest.mark.asyncio
async def test_create_position_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_position")

    resp = _mock_response(
        {"result": [{"id": 5, "name": "Engineer", "idnumber": "ENG"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="Engineer", idnumber="ENG", confirmed=True))

    assert len(result["created"]) == 1
    assert result["created"][0]["idnumber"] == "ENG"


@pytest.mark.asyncio
async def test_create_position_tool_with_flags():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_position")

    resp = _mock_response(
        {"result": [{"id": 6, "name": "Lead", "idnumber": "LEAD"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(
                name="Lead",
                idnumber="LEAD",
                department_manager=True,
                global_manager=True,
                confirmed=True,
            )
        )

    assert len(result["created"]) == 1


@pytest.mark.asyncio
async def test_create_position_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "create_position")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_update_position_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_position")

    result = json.loads(await fn(idnumber="ENG", name="Senior Engineer"))

    assert "preview" in result
    assert result["changes"]["name"] == "Senior Engineer"


@pytest.mark.asyncio
async def test_update_position_tool_preview_with_optional():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_position")

    result = json.loads(
        await fn(idnumber="ENG", parent="MGMT", description="Updated")
    )

    assert result["changes"]["parent"] == "MGMT"
    assert result["changes"]["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_position_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_position")

    resp = _mock_response(
        {"result": [{"id": 5, "idnumber": "ENG"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="ENG", name="Senior Engineer", confirmed=True))

    assert len(result["updated"]) == 1


@pytest.mark.asyncio
async def test_update_position_tool_with_flags():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_position")

    resp = _mock_response(
        {"result": [{"id": 5, "idnumber": "ENG"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(idnumber="ENG", department_manager=True, global_manager=False, confirmed=True)
        )

    assert len(result["updated"]) == 1


@pytest.mark.asyncio
async def test_update_position_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "update_position")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_position_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_position")

    result = json.loads(await fn(position_id=5))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_position_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_position")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(position_id=5, confirmed=True))

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_delete_position_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_position")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(position_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_job_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_job")

    result = json.loads(await fn(job_id=42))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_job_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_job")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(job_id=42, confirmed=True))

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_delete_job_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "delete_job")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(job_id=42, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_preview():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "unassign_manager")

    result = json.loads(await fn(userids="3", managerids="5"))

    assert "preview" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_confirmed():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "unassign_manager")

    resp = _mock_response(
        {"warnings": [], "unassignedmanagers": [{"itemid": 1, "userid": 3, "managerid": 5}]}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(userids="3", managerids="5", confirmed=True))

    assert len(result["unassignedmanagers"]) == 1


@pytest.mark.asyncio
async def test_unassign_manager_tool_error():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "unassign_manager")

    resp = _mock_response(
        {"exception": "moodle_exception", "errorcode": "err", "message": "fail"}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(userids="3", managerids="5", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_non_numeric():
    agent = _build_agent()
    fn = _get_tool_fn(agent, "unassign_manager")

    result = json.loads(await fn(userids="abc", managerids="5"))

    assert "error" in result
