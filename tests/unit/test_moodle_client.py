"""Unit tests for the Moodle REST API client."""

from __future__ import annotations

from unittest import mock

import httpx
import pytest

from soliplex.moodle.client import MAX_RESULTS
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient

BASE_URL = "http://moodle.test"
TOKEN = "test_token_123"


@pytest.fixture
def client():
    return MoodleClient(base_url=BASE_URL, token=TOKEN)


def _mock_response(json_data, status_code=200):
    """Create a mock httpx.Response."""
    resp = mock.MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=mock.MagicMock(),
            response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def _patch_httpx(response):
    """Patch httpx.AsyncClient to return the given response."""
    mock_client = mock.AsyncMock()
    mock_client.post.return_value = response
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    return mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    )


# ---------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_moodle_error_raises(client):
    resp = _mock_response(
        {
            "exception": "webservice_access_exception",
            "errorcode": "accessexception",
            "message": "Access denied",
        }
    )
    with _patch_httpx(resp):
        with pytest.raises(MoodleAPIError, match="Access denied"):
            await client.get_courses()


@pytest.mark.asyncio
async def test_http_error_raises(client):
    resp = _mock_response("Internal error", status_code=500)
    with _patch_httpx(resp):
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_courses()


# ---------------------------------------------------------------
# get_courses
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_courses(client):
    resp = _mock_response(
        [
            {
                "id": 1,
                "shortname": "site",
                "fullname": "Site",
                "categoryid": 0,
            },
            {
                "id": 2,
                "shortname": "test",
                "fullname": "Test Course",
                "categoryid": 1,
                "enablecompletion": 1,
            },
        ]
    )
    with _patch_httpx(resp):
        courses = await client.get_courses()

    assert len(courses) == 2
    assert courses[1].fullname == "Test Course"
    assert courses[1].enablecompletion == 1


@pytest.mark.asyncio
async def test_get_courses_empty(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        courses = await client.get_courses()
    assert courses == []


# ---------------------------------------------------------------
# get_courses_by_field
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_courses_by_field(client):
    resp = _mock_response(
        {
            "courses": [
                {
                    "id": 2,
                    "shortname": "test",
                    "fullname": "Test Course",
                }
            ]
        }
    )
    with _patch_httpx(resp):
        courses = await client.get_courses_by_field("shortname", "test")

    assert len(courses) == 1
    assert courses[0].shortname == "test"


@pytest.mark.asyncio
async def test_get_courses_by_field_no_filter(client):
    resp = _mock_response({"courses": []})
    with _patch_httpx(resp):
        courses = await client.get_courses_by_field()
    assert courses == []


# ---------------------------------------------------------------
# get_users_by_field
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_users_by_field(client):
    resp = _mock_response(
        [
            {
                "id": 3,
                "username": "testuser1",
                "firstname": "Test",
                "lastname": "User1",
                "fullname": "Test User1",
                "email": "test1@example.com",
            }
        ]
    )
    with _patch_httpx(resp):
        users = await client.get_users_by_field("username", ["testuser1"])

    assert len(users) == 1
    assert users[0].username == "testuser1"


# ---------------------------------------------------------------
# get_enrolled_users
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_enrolled_users(client):
    resp = _mock_response(
        [
            {
                "id": 3,
                "username": "testuser1",
                "fullname": "Test User1",
                "roles": [
                    {
                        "roleid": 5,
                        "name": "Student",
                        "shortname": "student",
                    }
                ],
            },
            {
                "id": 4,
                "username": "testuser2",
                "fullname": "Test User2",
                "roles": [],
            },
        ]
    )
    with _patch_httpx(resp):
        users = await client.get_enrolled_users(courseid=2)

    assert len(users) == 2
    assert users[0].roles[0].shortname == "student"


# ---------------------------------------------------------------
# get_course_completion_status
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_completion_status(client):
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
        status = await client.get_course_completion_status(
            courseid=2, userid=3
        )

    assert status.completed is True
    assert len(status.completions) == 1
    assert status.completions[0].timecompleted == 1700000000


# ---------------------------------------------------------------
# Result truncation
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_results_truncated_at_max(client):
    many_courses = [
        {
            "id": i,
            "shortname": f"c{i}",
            "fullname": f"C {i}",
        }
        for i in range(150)
    ]
    resp = _mock_response(many_courses)
    with _patch_httpx(resp):
        courses = await client.get_courses()
    assert len(courses) == MAX_RESULTS


# ---------------------------------------------------------------
# Client defaults from env
# ---------------------------------------------------------------


def test_client_from_env(monkeypatch):
    monkeypatch.setenv("MOODLE_BASE_URL", "http://env.test")
    monkeypatch.setenv("MOODLE_API_TOKEN", "env_token")
    c = MoodleClient()
    assert c.base_url == "http://env.test"
    assert c.token == "env_token"


def test_client_strips_trailing_slash():
    c = MoodleClient(base_url="http://moodle.test/", token="t")
    assert c.base_url == "http://moodle.test"


@pytest.mark.asyncio
async def test_client_passes_verify_to_httpx():
    c = MoodleClient(base_url=BASE_URL, token=TOKEN, verify=False)
    resp = _mock_response([])
    mock_client = mock.AsyncMock()
    mock_client.post.return_value = resp
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ) as async_client_cls:
        await c.get_courses()
    async_client_cls.assert_called_once_with(verify=False)


# ---------------------------------------------------------------
# MoodleAPIError attributes
# ---------------------------------------------------------------


def test_moodle_api_error_attributes():
    err = MoodleAPIError(
        "bad request",
        errorcode="invalidparam",
        exception="moodle_exception",
    )
    assert str(err) == "bad request"
    assert err.errorcode == "invalidparam"
    assert err.exception == "moodle_exception"


# ---------------------------------------------------------------
# Feature 1: get_course_contents
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_contents(client):
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
                        "name": "Welcome Forum",
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
            },
            {
                "id": 2,
                "name": "Week 1",
                "visible": 1,
                "summary": "",
                "modules": [],
            },
        ]
    )
    with _patch_httpx(resp):
        sections = await client.get_course_contents(courseid=2)

    assert len(sections) == 2
    assert sections[0].name == "General"
    assert len(sections[0].modules) == 2
    assert sections[0].modules[1].modname == "quiz"
    assert sections[0].modules[1].completion == 2


@pytest.mark.asyncio
async def test_get_course_contents_empty(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        sections = await client.get_course_contents(courseid=999)
    assert sections == []


# ---------------------------------------------------------------
# Feature 2: get_activities_completion_status
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_activities_completion_status(client):
    resp = _mock_response(
        {
            "statuses": [
                {
                    "cmid": 10,
                    "modname": "forum",
                    "instance": 1,
                    "state": 1,
                    "timecompleted": 1700000000,
                    "tracking": 2,
                },
                {
                    "cmid": 11,
                    "modname": "quiz",
                    "instance": 2,
                    "state": 0,
                    "timecompleted": 0,
                    "tracking": 2,
                },
            ]
        }
    )
    with _patch_httpx(resp):
        statuses = await client.get_activities_completion_status(
            courseid=2, userid=3
        )

    assert len(statuses) == 2
    assert statuses[0].cmid == 10
    assert statuses[0].state == 1
    assert statuses[1].state == 0


@pytest.mark.asyncio
async def test_get_activities_completion_status_empty(client):
    resp = _mock_response({"statuses": []})
    with _patch_httpx(resp):
        statuses = await client.get_activities_completion_status(
            courseid=2, userid=3
        )
    assert statuses == []


# ---------------------------------------------------------------
# Feature 3: Groups & cohorts
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_groups(client):
    resp = _mock_response(
        [
            {"id": 1, "courseid": 2, "name": "Group A", "description": ""},
            {"id": 2, "courseid": 2, "name": "Group B", "description": ""},
        ]
    )
    with _patch_httpx(resp):
        groups = await client.get_course_groups(courseid=2)

    assert len(groups) == 2
    assert groups[0].name == "Group A"


@pytest.mark.asyncio
async def test_get_group_members(client):
    resp = _mock_response(
        [{"groupid": 1, "userids": [3, 4, 5]}]
    )
    with _patch_httpx(resp):
        results = await client.get_group_members([1])

    assert len(results) == 1
    assert results[0].groupid == 1
    assert results[0].userids == [3, 4, 5]


@pytest.mark.asyncio
async def test_get_cohorts(client):
    resp = _mock_response(
        [
            {"id": 1, "name": "Engineering", "idnumber": "ENG", "visible": 1},
            {"id": 2, "name": "Sales", "idnumber": "SAL", "visible": 1},
        ]
    )
    with _patch_httpx(resp):
        cohorts = await client.get_cohorts()

    assert len(cohorts) == 2
    assert cohorts[0].name == "Engineering"


@pytest.mark.asyncio
async def test_get_cohort_members(client):
    resp = _mock_response(
        [{"cohortid": 1, "userids": [3, 4]}]
    )
    with _patch_httpx(resp):
        results = await client.get_cohort_members([1])

    assert len(results) == 1
    assert results[0].cohortid == 1
    assert results[0].userids == [3, 4]


# ---------------------------------------------------------------
# Feature 4: Grading & assessments
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_assignment_grades(client):
    resp = _mock_response(
        {
            "assignments": [
                {
                    "assignmentid": 1,
                    "grades": [
                        {
                            "id": 1,
                            "userid": 3,
                            "grade": "85.00",
                            "grader": 2,
                            "timemodified": 1700000000,
                        }
                    ],
                }
            ],
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = await client.get_assignment_grades([1])

    assert "assignments" in result
    assert len(result["assignments"]) == 1
    assert result["assignments"][0]["grades"][0]["grade"] == "85.00"


@pytest.mark.asyncio
async def test_get_user_grades(client):
    resp = _mock_response(
        {
            "tables": [
                {
                    "courseid": 2,
                    "userid": 3,
                    "tabledata": [
                        {
                            "itemname": {"content": "Quiz 1"},
                            "grade": {"content": "90"},
                            "percentage": {"content": "90%"},
                        }
                    ],
                }
            ],
        }
    )
    with _patch_httpx(resp):
        result = await client.get_user_grades(courseid=2, userid=3)

    assert "tables" in result
    assert len(result["tables"]) == 1


# ---------------------------------------------------------------
# Feature 5: Calendar & deadlines
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_calendar_events(client):
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
                },
            ]
        }
    )
    with _patch_httpx(resp):
        events = await client.get_calendar_events(
            courseids=[2], timestart=1699000000, timeend=1701000000
        )

    assert len(events) == 1
    assert events[0].name == "Quiz Deadline"
    assert events[0].courseid == 2


@pytest.mark.asyncio
async def test_get_calendar_events_no_filter(client):
    resp = _mock_response({"events": []})
    with _patch_httpx(resp):
        events = await client.get_calendar_events()
    assert events == []


# ---------------------------------------------------------------
# Feature 7: Write operations
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrol_users(client):
    # enrol_manual_enrol_users returns null on success
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.enrol_users(
            [{"userid": 3, "courseid": 2, "roleid": 5}]
        )

    assert result == {"warnings": []}


@pytest.mark.asyncio
async def test_enrol_users_returns_dict(client):
    resp = _mock_response({"warnings": [{"message": "already enrolled"}]})
    with _patch_httpx(resp):
        result = await client.enrol_users(
            [{"userid": 3, "courseid": 2, "roleid": 5}]
        )

    assert result == {"warnings": [{"message": "already enrolled"}]}


@pytest.mark.asyncio
async def test_enrol_users_returns_non_dict(client):
    # When the API returns a non-dict (e.g. a list), fall back to empty warnings
    resp = _mock_response([])
    with _patch_httpx(resp):
        result = await client.enrol_users(
            [{"userid": 3, "courseid": 2, "roleid": 5}]
        )

    assert result == {"warnings": []}


@pytest.mark.asyncio
async def test_send_messages(client):
    resp = _mock_response(
        [{"msgid": 1, "text": "Hello"}]
    )
    with _patch_httpx(resp):
        result = await client.send_messages(
            [{"touserid": 3, "text": "Hello", "textformat": 0}]
        )

    assert len(result) == 1
    assert result[0]["msgid"] == 1


# ---------------------------------------------------------------
# Certifications (Workplace)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_certifications(client):
    resp = _mock_response(
        [
            {
                "id": 1,
                "fullname": "Workplace Safety",
                "idnumber": "WS01",
                "status": 0,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
            {
                "id": 2,
                "fullname": "Data Privacy",
                "idnumber": "DP01",
                "status": 0,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
        ]
    )
    with _patch_httpx(resp):
        certs = await client.get_certifications()

    assert len(certs) == 2
    assert certs[0].fullname == "Workplace Safety"
    assert certs[1].idnumber == "DP01"


@pytest.mark.asyncio
async def test_get_certification_allocations(client):
    resp = _mock_response(
        [
            {
                "id": 10,
                "userid": 3,
                "certificationid": 1,
                "userfullname": "Alice Johnson",
                "certificationfullname": "Workplace Safety",
                "timeallocated": 1700000000,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
        ]
    )
    with _patch_httpx(resp):
        allocs = await client.get_certification_allocations(certificationid=1)

    assert len(allocs) == 1
    assert allocs[0].userid == 3
    assert allocs[0].userfullname == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_user_certification_allocations(client):
    resp = _mock_response(
        [
            {
                "id": 10,
                "userid": 3,
                "certificationid": 1,
                "userfullname": "Alice Johnson",
                "certificationfullname": "Workplace Safety",
                "timeallocated": 1700000000,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
            {
                "id": 11,
                "userid": 3,
                "certificationid": 2,
                "userfullname": "Alice Johnson",
                "certificationfullname": "Data Privacy",
                "timeallocated": 1700000000,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
        ]
    )
    with _patch_httpx(resp):
        allocs = await client.get_user_certification_allocations(userid=3)

    assert len(allocs) == 2
    assert allocs[0].certificationfullname == "Workplace Safety"
    assert allocs[1].certificationfullname == "Data Privacy"


@pytest.mark.asyncio
async def test_get_certification_user_log(client):
    resp = _mock_response(
        [
            {"id": 1, "action": "allocated", "timecreated": 1700000000},
            {"id": 2, "action": "certified", "timecreated": 1700001000},
        ]
    )
    with _patch_httpx(resp):
        entries = await client.get_certification_user_log(
            certificationid=1, userid=3
        )

    assert len(entries) == 2
    assert entries[0].action == "allocated"
    assert entries[1].action == "certified"


@pytest.mark.asyncio
async def test_get_certification_user_log_non_list(client):
    resp = _mock_response({"error": "unexpected"})
    with _patch_httpx(resp):
        entries = await client.get_certification_user_log(
            certificationid=1, userid=3
        )

    assert entries == []


@pytest.mark.asyncio
async def test_certify_user(client):
    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = await client.certify_user(certificationid=1, userid=3)

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_certify_user_non_dict(client):
    resp = _mock_response(True)
    with _patch_httpx(resp):
        result = await client.certify_user(certificationid=1, userid=3)

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_revoke_certification(client):
    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = await client.revoke_certification(
            certificationid=1, userid=3
        )

    assert result == {"result": True}


# ---------------------------------------------------------------
# Programs (Workplace)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_programs(client):
    resp = _mock_response(
        [
            {"id": 1, "fullname": "Onboarding Program"},
            {"id": 2, "fullname": "Leadership Track"},
        ]
    )
    with _patch_httpx(resp):
        programs = await client.search_programs()

    assert len(programs) == 2
    assert programs[0].fullname == "Onboarding Program"


@pytest.mark.asyncio
async def test_get_user_program_courses(client):
    resp = _mock_response(
        [
            {
                "id": 2,
                "shortname": "safety101",
                "fullname": "Safety Fundamentals",
                "completed": True,
            },
            {
                "id": 3,
                "shortname": "cyber101",
                "fullname": "Cybersecurity Basics",
                "completed": False,
            },
        ]
    )
    with _patch_httpx(resp):
        courses = await client.get_user_program_courses(userid=3)

    assert len(courses) == 2
    assert courses[0].completed is True
    assert courses[1].completed is False


@pytest.mark.asyncio
async def test_allocate_users_to_program(client):
    resp = _mock_response({"result": []})
    with _patch_httpx(resp):
        result = await client.allocate_users_to_program(
            programid=1, userids=[3, 4, 5]
        )

    assert result == {"result": []}


# ---------------------------------------------------------------
# Tenants (Workplace)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenants(client):
    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Default",
                "sitename": "Moodle Workplace",
                "idnumber": "",
                "isdefault": True,
            },
            {
                "id": 2,
                "name": "Regional Office",
                "sitename": "Regional",
                "idnumber": "REG01",
                "isdefault": False,
            },
        ]
    )
    with _patch_httpx(resp):
        tenants = await client.get_tenants()

    assert len(tenants) == 2
    assert tenants[0].isdefault is True
    assert tenants[1].name == "Regional Office"


# ---------------------------------------------------------------
# Tenant Write Operations
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_allocate_users_to_tenant(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.allocate_users_to_tenant(
            allocations=[{"userid": 3, "tenantid": 2}]
        )

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_returns_dict(client):
    resp = _mock_response({"warnings": []})
    with _patch_httpx(resp):
        result = await client.allocate_users_to_tenant(
            allocations=[{"userid": 3, "tenantid": 2}]
        )

    assert result == {"warnings": []}


@pytest.mark.asyncio
async def test_suspend_tenant_users(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.suspend_tenant_users(userids=[3, 4])

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_suspend_tenant_users_returns_dict(client):
    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = await client.suspend_tenant_users(userids=[3, 4])

    assert result == {"result": True}


# ---------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_catalogue_page(client):
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
        items = await client.get_catalogue_page()

    assert len(items) == 1
    assert items[0].title == "Safety 101"


@pytest.mark.asyncio
async def test_get_catalogue_page_empty(client):
    resp = _mock_response({"contents": {"catalogueitems": []}})
    with _patch_httpx(resp):
        items = await client.get_catalogue_page()

    assert items == []


@pytest.mark.asyncio
async def test_get_catalogue_page_missing_keys(client):
    resp = _mock_response({})
    with _patch_httpx(resp):
        items = await client.get_catalogue_page()

    assert items == []


@pytest.mark.asyncio
async def test_get_user_catalogue(client):
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
        items = await client.get_user_catalogue(userid=3)

    assert len(items) == 1
    assert items[0].fullname == "Safety"


@pytest.mark.asyncio
async def test_get_user_catalogue_empty(client):
    resp = _mock_response({"catalogue": {"listitems": []}})
    with _patch_httpx(resp):
        items = await client.get_user_catalogue(userid=3)

    assert items == []


@pytest.mark.asyncio
async def test_get_program_content(client):
    resp = _mock_response(
        {"sets": [{"name": "Core"}], "courses": [{"id": 2}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = await client.get_program_content(programid=1)

    assert result["sets"][0]["name"] == "Core"
    assert result["courses"][0]["id"] == 2
    assert result["warnings"] == []


# ---------------------------------------------------------------
# Deeper Program Management
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_courses_for_program(client):
    resp = _mock_response(
        [{"id": 2, "fullname": "Safety Fundamentals"}]
    )
    with _patch_httpx(resp):
        courses = await client.search_courses_for_program()

    assert len(courses) == 1
    assert courses[0].fullname == "Safety Fundamentals"


@pytest.mark.asyncio
async def test_search_courses_for_program_non_list(client):
    resp = _mock_response({"error": "unexpected"})
    with _patch_httpx(resp):
        courses = await client.search_courses_for_program()

    assert courses == []


@pytest.mark.asyncio
async def test_deallocate_user_from_program(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.deallocate_user_from_program(
            programid=1, userid=3
        )

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_deallocate_user_from_program_returns_dict(client):
    resp = _mock_response({"warnings": []})
    with _patch_httpx(resp):
        result = await client.deallocate_user_from_program(
            programid=1, userid=3
        )

    assert result == {"warnings": []}


@pytest.mark.asyncio
async def test_reset_program_progress(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.reset_program_progress(programuserid=10)

    assert result == {"result": True}


# ---------------------------------------------------------------
# Deeper Certification Management
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_certification_user_allocation(client):
    resp = _mock_response(
        {
            "id": 10,
            "userid": 3,
            "certificationid": 1,
            "status": "certified",
        }
    )
    with _patch_httpx(resp):
        result = await client.get_certification_user_allocation(
            certificationid=1, userid=3
        )

    assert result["id"] == 10
    assert result["userid"] == 3
    assert result["status"] == "certified"


@pytest.mark.asyncio
async def test_get_certification_user_allocation_non_dict(client):
    resp = _mock_response(True)
    with _patch_httpx(resp):
        result = await client.get_certification_user_allocation(
            certificationid=1, userid=3
        )

    assert result == {}


@pytest.mark.asyncio
async def test_deallocate_user_from_certification(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.deallocate_user_from_certification(
            certificationid=1, userid=3
        )

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_archive_certification(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.archive_certification(certificationid=1)

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_archive_certification_returns_dict(client):
    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = await client.archive_certification(certificationid=1)

    assert result == {"result": True}


# ---------------------------------------------------------------
# Organisation Structure
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_departments(client):
    resp = _mock_response(
        {"departments": [{"id": 1, "name": "Engineering"}], "positions": []}
    )
    with _patch_httpx(resp):
        depts = await client.get_departments()

    assert len(depts) == 1
    assert depts[0].name == "Engineering"


@pytest.mark.asyncio
async def test_get_departments_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        depts = await client.get_departments()

    assert depts == []


@pytest.mark.asyncio
async def test_get_departments_with_search(client):
    resp = _mock_response(
        {"departments": [{"id": 1, "name": "Engineering"}, {"id": 2, "name": "Operations"}]}
    )
    with _patch_httpx(resp):
        depts = await client.get_departments(search="eng")

    assert len(depts) == 1
    assert depts[0].name == "Engineering"


@pytest.mark.asyncio
async def test_get_positions(client):
    resp = _mock_response(
        {"departments": [], "positions": [{"id": 1, "name": "Manager"}]}
    )
    with _patch_httpx(resp):
        positions = await client.get_positions()

    assert len(positions) == 1
    assert positions[0].name == "Manager"


@pytest.mark.asyncio
async def test_get_positions_with_search(client):
    resp = _mock_response(
        {"positions": [{"id": 1, "name": "Manager"}, {"id": 2, "name": "Engineer"}]}
    )
    with _patch_httpx(resp):
        positions = await client.get_positions(search="eng")

    assert len(positions) == 1
    assert positions[0].name == "Engineer"


@pytest.mark.asyncio
async def test_get_positions_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        positions = await client.get_positions()

    assert positions == []


@pytest.mark.asyncio
async def test_get_managed_users(client):
    resp = _mock_response(
        {"managedusers": [{"id": 3, "fullname": "Alice Johnson"}], "totalcount": 1}
    )
    with _patch_httpx(resp):
        users = await client.get_managed_users()

    assert len(users) == 1
    assert users[0]["fullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_managed_users_empty_dict(client):
    resp = _mock_response({"managedusers": [], "totalcount": 0})
    with _patch_httpx(resp):
        users = await client.get_managed_users()

    assert users == []


@pytest.mark.asyncio
async def test_get_managed_users_legacy_list(client):
    """Backward compat: plain list response still works."""
    resp = _mock_response([{"id": 3, "fullname": "Alice Johnson"}])
    with _patch_httpx(resp):
        users = await client.get_managed_users()

    assert len(users) == 1
    assert users[0]["fullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_managed_users_unexpected_type(client):
    """Returns empty list when response is neither dict nor list."""
    resp = _mock_response(None)
    with _patch_httpx(resp):
        users = await client.get_managed_users()

    assert users == []


@pytest.mark.asyncio
async def test_create_job(client):
    resp = _mock_response({"id": 1, "userid": 3})
    with _patch_httpx(resp):
        result = await client.create_job(
            userid=3,
            department_idnumber="ENG",
            position_idnumber="MGR",
        )

    assert result["id"] == 1
    assert result["userid"] == 3


@pytest.mark.asyncio
async def test_assign_managers(client):
    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = await client.assign_managers(
            user_ids=[3], manager_ids=[2]
        )

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_assign_managers_returns_dict(client):
    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = await client.assign_managers(
            user_ids=[3], manager_ids=[2]
        )

    assert result == {"result": True}


# ---------------------------------------------------------------
# Competencies & Learning Plans
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_competency_frameworks(client):
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
        frameworks = await client.get_competency_frameworks()

    assert len(frameworks) == 1
    assert frameworks[0].shortname == "Core"


@pytest.mark.asyncio
async def test_get_competency_frameworks_empty(client):
    resp = _mock_response({"frameworks": []})
    with _patch_httpx(resp):
        frameworks = await client.get_competency_frameworks()

    assert frameworks == []


@pytest.mark.asyncio
async def test_get_competency_frameworks_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        frameworks = await client.get_competency_frameworks()

    assert frameworks == []


@pytest.mark.asyncio
async def test_get_user_learning_plans(client):
    resp = _mock_response(
        {
            "plans": [
                {
                    "id": 1,
                    "name": "Alice's Plan",
                    "description": "Development plan",
                    "statusname": "Active",
                    "userid": 3,
                }
            ]
        }
    )
    with _patch_httpx(resp):
        plans = await client.get_user_learning_plans(userid=3)

    assert len(plans) == 1
    assert plans[0].name == "Alice's Plan"


@pytest.mark.asyncio
async def test_get_user_learning_plans_empty(client):
    resp = _mock_response({"plans": []})
    with _patch_httpx(resp):
        plans = await client.get_user_learning_plans(userid=3)

    assert plans == []


@pytest.mark.asyncio
async def test_get_user_competency_summary(client):
    resp = _mock_response(
        {
            "usercompetency": {
                "userid": 3,
                "competencyid": 1,
                "grade": "B",
            }
        }
    )
    with _patch_httpx(resp):
        result = await client.get_user_competency_summary(
            userid=3, competencyid=1
        )

    assert result["usercompetency"]["userid"] == 3
    assert result["usercompetency"]["grade"] == "B"


@pytest.mark.asyncio
async def test_get_user_competency_summary_non_dict(client):
    resp = _mock_response(True)
    with _patch_httpx(resp):
        result = await client.get_user_competency_summary(
            userid=3, competencyid=1
        )

    assert result == {}


@pytest.mark.asyncio
async def test_get_course_competencies(client):
    resp = _mock_response(
        {
            "competencies": [
                {"competency": {"id": 1, "shortname": "Communication"}}
            ]
        }
    )
    with _patch_httpx(resp):
        competencies = await client.get_course_competencies(courseid=2)

    assert len(competencies) == 1
    assert competencies[0]["competency"]["shortname"] == "Communication"


@pytest.mark.asyncio
async def test_get_course_competencies_empty(client):
    resp = _mock_response({"competencies": []})
    with _patch_httpx(resp):
        competencies = await client.get_course_competencies(courseid=2)

    assert competencies == []


# ---------------------------------------------------------------
# Branch coverage: additional edge cases
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_catalogue_page_with_query(client):
    resp = _mock_response(
        {"contents": {"catalogueitems": [{"id": 1, "title": "Safety", "url": "/c/1"}]}}
    )
    with _patch_httpx(resp):
        items = await client.get_catalogue_page(query="safety")

    assert len(items) == 1


@pytest.mark.asyncio
async def test_get_catalogue_page_non_dict_contents(client):
    resp = _mock_response({"contents": "not a dict"})
    with _patch_httpx(resp):
        items = await client.get_catalogue_page()

    assert items == []


@pytest.mark.asyncio
async def test_get_catalogue_page_non_dict_response(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        items = await client.get_catalogue_page()

    assert items == []


@pytest.mark.asyncio
async def test_get_user_catalogue_with_search(client):
    resp = _mock_response(
        {"catalogue": {"listitems": [{"itemid": 1, "fullname": "Safety"}]}}
    )
    with _patch_httpx(resp):
        items = await client.get_user_catalogue(search="safety")

    assert len(items) == 1


@pytest.mark.asyncio
async def test_get_user_catalogue_non_dict_catalogue(client):
    resp = _mock_response({"catalogue": "not a dict"})
    with _patch_httpx(resp):
        items = await client.get_user_catalogue(userid=3)

    assert items == []


@pytest.mark.asyncio
async def test_get_user_catalogue_non_dict_response(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        items = await client.get_user_catalogue()

    assert items == []


@pytest.mark.asyncio
async def test_get_program_content_with_userid(client):
    resp = _mock_response({"sets": [], "courses": []})
    with _patch_httpx(resp):
        result = await client.get_program_content(programid=1, userid=3)

    assert result == {"sets": [], "courses": []}


@pytest.mark.asyncio
async def test_reset_program_progress_non_dict(client):
    resp = _mock_response(True)
    with _patch_httpx(resp):
        result = await client.reset_program_progress(programuserid=10)

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_non_dict(client):
    resp = _mock_response(True)
    with _patch_httpx(resp):
        result = await client.deallocate_user_from_certification(
            certificationid=1, userid=3
        )

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_get_managed_users_with_all_params(client):
    resp = _mock_response(
        {"managedusers": [{"id": 3, "fullname": "Alice Johnson"}], "totalcount": 1}
    )
    with _patch_httpx(resp):
        users = await client.get_managed_users(
            departmentid=1, positionid=2, search="Alice"
        )

    assert len(users) == 1


@pytest.mark.asyncio
async def test_get_user_learning_plans_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        plans = await client.get_user_learning_plans(userid=3)

    assert plans == []


@pytest.mark.asyncio
async def test_get_course_competencies_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        competencies = await client.get_course_competencies(courseid=2)

    assert competencies == []


# ---------------------------------------------------------------
# get_department_members (local_soliplex plugin)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_department_members(client):
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
        members = await client.get_department_members()

    assert len(members) == 1
    assert members[0].userid == 3
    assert members[0].fullname == "Alice Johnson"
    assert members[0].departmentname == "Engineering"
    assert members[0].positionname == "Manager"


@pytest.mark.asyncio
async def test_get_department_members_empty(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        members = await client.get_department_members()

    assert members == []


@pytest.mark.asyncio
async def test_get_department_members_with_filters(client):
    resp = _mock_response([
        {
            "userid": 4,
            "username": "bob",
            "firstname": "Bob",
            "lastname": "Smith",
            "fullname": "Bob Smith",
            "email": "bob@example.com",
            "departmentid": 1,
            "departmentname": "Engineering",
            "positionid": 2,
            "positionname": "Senior Engineer",
        },
    ])
    with _patch_httpx(resp):
        members = await client.get_department_members(
            departmentid=1, positionid=2, search="Bob"
        )

    assert len(members) == 1
    assert members[0].username == "bob"


@pytest.mark.asyncio
async def test_get_department_members_non_list(client):
    """Returns empty list when response is not a list."""
    resp = _mock_response({"unexpected": "format"})
    with _patch_httpx(resp):
        members = await client.get_department_members()

    assert members == []


# ---------------------------------------------------------------
# search_users
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_users(client):
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
        users = await client.search_users([("firstname", "Alice")])

    assert len(users) == 1
    assert users[0].username == "testuser1"
    assert users[0].fullname == "Alice Johnson"


@pytest.mark.asyncio
async def test_search_users_non_dict(client):
    """Returns empty list when response is not a dict."""
    resp = _mock_response([])
    with _patch_httpx(resp):
        users = await client.search_users([("firstname", "Nobody")])

    assert users == []


# ---------------------------------------------------------------
# Report Builder
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports(client):
    resp = _mock_response(
        {
            "reports": [
                {
                    "id": 1,
                    "name": "Course Completion Summary",
                    "source": "core_course\\reportbuilder\\datasource\\courses",
                    "sourcename": "Courses",
                    "type": 0,
                    "timecreated": 1700000000,
                    "timemodified": 1700000000,
                }
            ],
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        reports = await client.list_reports()

    assert len(reports) == 1
    assert reports[0].name == "Course Completion Summary"
    assert reports[0].sourcename == "Courses"


@pytest.mark.asyncio
async def test_list_reports_empty(client):
    resp = _mock_response({"reports": [], "warnings": []})
    with _patch_httpx(resp):
        reports = await client.list_reports()

    assert reports == []


@pytest.mark.asyncio
async def test_list_reports_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        reports = await client.list_reports()

    assert reports == []


@pytest.mark.asyncio
async def test_retrieve_report(client):
    resp = _mock_response(
        {
            "details": {
                "id": 1,
                "name": "Course Completion Summary",
                "source": "core_course\\...",
                "sourcename": "Courses",
                "type": 0,
                "timecreated": 1700000000,
                "timemodified": 1700000000,
            },
            "data": {
                "headers": ["Course Name", "Enrolled", "Completed"],
                "rows": [
                    {"columns": ["Safety 101", "25", "20"]},
                    {"columns": ["Cyber 101", "30", "15"]},
                ],
                "totalrowcount": 2,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        details, data = await client.retrieve_report(1)

    assert details.name == "Course Completion Summary"
    assert data.headers == ["Course Name", "Enrolled", "Completed"]
    assert len(data.rows) == 2
    assert data.rows[0].columns == ["Safety 101", "25", "20"]
    assert data.totalrowcount == 2


# ---------------------------------------------------------------
# Custom Completion Reports (UTM / adv_comp)
# ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_utm_report(client):
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
        rows, totalcount = await client.get_utm_report(2)

    assert len(rows) == 1
    assert rows[0].username == "testuser1"
    assert rows[0].department == "Engineering"
    assert rows[0].completedtime == 1700100000
    assert totalcount == 1


@pytest.mark.asyncio
async def test_get_utm_report_empty(client):
    resp = _mock_response({"rows": [], "totalcount": 0})
    with _patch_httpx(resp):
        rows, totalcount = await client.get_utm_report(2)

    assert rows == []
    assert totalcount == 0


@pytest.mark.asyncio
async def test_get_adv_comp_report(client):
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
        rows, totalcount = await client.get_adv_comp_report(2)

    assert len(rows) == 1
    assert rows[0].username == "testuser2"
    assert rows[0].completedtime is None
    assert totalcount == 1


@pytest.mark.asyncio
async def test_get_adv_comp_report_non_dict(client):
    resp = _mock_response([])
    with _patch_httpx(resp):
        rows, totalcount = await client.get_adv_comp_report(2)

    assert rows == []
    assert totalcount == 0
