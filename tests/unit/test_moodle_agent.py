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
