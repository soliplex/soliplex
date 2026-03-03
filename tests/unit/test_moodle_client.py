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
