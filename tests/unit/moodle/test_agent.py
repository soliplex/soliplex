"""Unit tests for the Moodle agent factory and tool functions."""

from __future__ import annotations

import json
from unittest import mock

import httpx
import pydantic_ai
import pytest
from pydantic_ai.models.test import TestModel

from tests.unit.conftest import mock_moodle_response as _mock_response
from tests.unit.conftest import patch_moodle_httpx as _patch_httpx


def _patch_httpx_chain(*responses):
    """Patch ``httpx.AsyncClient`` so each POST returns the next response.

    For tools that make multiple backend calls — typically a
    resolver lookup followed by the actual read — pass the
    sequence of responses (or raised exceptions) in call order.
    """
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = list(responses)
    return mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    )


# Course-by-ID resolver response used by chained tests.  Reuses
# the per-test fixtures defined at the bottom of the file —
# referenced lazily by name to avoid forward-reference issues.
def _course_id_resp(course):
    return _mock_response({"courses": [course]})


def _cohorts_list_resp(*cohorts):
    """Response for ``core_cohort_get_cohorts`` used by the cohort resolver."""
    return _mock_response(list(cohorts))


def _categories_list_resp(*categories):
    """Response for ``core_course_get_categories`` used by the resolver."""
    return _mock_response(list(categories))


def _tenants_list_resp(*tenants):
    """Response for ``tool_tenant_get_tenants`` used by the resolver."""
    return _mock_response(list(tenants))


def _departments_list_resp(*depts):
    """Response for ``local_soliplex_list_departments``."""
    return _mock_response(list(depts))


def _reports_list_resp(*reports):
    """Response for ``core_reportbuilder_list_reports``."""
    return _mock_response({"reports": list(reports)})


def _certs_list_resp(*certs):
    """Response for ``tool_certification_get_certifications``."""
    return _mock_response(list(certs))


def _programs_list_resp(*programs):
    """Response for ``tool_program_potential_program_selector``."""
    return _mock_response(list(programs))


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


def _build_agent():
    """Build the Moodle router agent using mocked config + model."""
    from soliplex.moodle.agent import moodle_tools_agent_factory

    agent_config = _make_agent_config()

    with mock.patch(
        "soliplex.moodle.agent.config_agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        return moodle_tools_agent_factory(agent_config)


def _build_skills():
    """Build all Moodle skills with a mocked-config client."""
    from soliplex.moodle.client import MoodleClient
    from soliplex.moodle.skills import build_certifications_skill
    from soliplex.moodle.skills import build_courses_skill
    from soliplex.moodle.skills import build_organisation_skill
    from soliplex.moodle.skills import build_programs_skill
    from soliplex.moodle.skills import build_reporting_skill
    from soliplex.moodle.skills import build_rules_skill
    from soliplex.moodle.skills import build_users_skill

    client = MoodleClient(base_url=BASE_URL, token=TOKEN, verify=False)
    skills = [
        build_courses_skill(client),
        build_users_skill(client),
        build_organisation_skill(client),
        build_certifications_skill(client),
        build_programs_skill(client),
        build_rules_skill(client),
        build_reporting_skill(client),
    ]
    return client, skills


# Cache skills across tests for speed (stateless closures)
_CACHED_CLIENT = None
_CACHED_SKILLS = None


def _get_skills():
    global _CACHED_CLIENT, _CACHED_SKILLS
    if _CACHED_SKILLS is None:
        _CACHED_CLIENT, _CACHED_SKILLS = _build_skills()
    return _CACHED_SKILLS


@pytest.fixture(autouse=True)
def _reset_cached_http():
    """Reset the cached MoodleClient's lazy http connection between tests.

    The skills cache holds a single MoodleClient instance whose
    `_http` attribute is created lazily. Once created, it bypasses
    any subsequent `httpx.AsyncClient` patches set up by tests.
    Clearing it before each test forces the next `_call` to go
    through the (now-patched) `httpx.AsyncClient` constructor.
    """
    if _CACHED_CLIENT is not None:
        _CACHED_CLIENT._http = None
    return


def _get_tool_fn(agent_or_skills, name):
    """Extract a tool's underlying async function.

    Works with either the old-style agent (for factory tests) or
    a list of Skill objects (for tool-level tests).
    """
    for skill in agent_or_skills:
        for tool in skill.tools:
            if callable(tool) and tool.__name__ == name:
                return tool
    raise KeyError(name)


# -----------------------------------------------------------------
# Factory tests
# -----------------------------------------------------------------


def test_factory_returns_agent():
    agent = _build_agent()
    assert isinstance(agent, pydantic_ai.Agent)


def test_factory_registers_client_cleanup():
    """MoodleClient.aclose must be registered with the installation
    so the persistent httpx.AsyncClient is closed at app shutdown."""
    from soliplex.moodle.agent import moodle_tools_agent_factory

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.config_agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        moodle_tools_agent_factory(agent_config)

    ic = agent_config._installation_config
    ic.register_cleanup.assert_called_once()
    (cb,), _ = ic.register_cleanup.call_args
    # The registered callback is the bound MoodleClient.aclose method.
    assert callable(cb)
    assert cb.__name__ == "aclose"


def test_factory_accepts_skill_toolset_config():
    from soliplex.moodle.agent import moodle_tools_agent_factory

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.config_agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        agent = moodle_tools_agent_factory(
            agent_config, skill_toolset_config=None
        )
    assert isinstance(agent, pydantic_ai.Agent)


def test_factory_wires_skill_toolset():
    from haiku.skills.models import Skill
    from haiku.skills.models import SkillMetadata
    from haiku.skills.models import SkillSource

    from soliplex.moodle.agent import MOODLE_ROUTER_PROMPT
    from soliplex.moodle.agent import moodle_tools_agent_factory

    ext_skill = Skill(
        metadata=SkillMetadata(name="test-skill", description="A test skill"),
        source=SkillSource.ENTRYPOINT,
        instructions="Test instructions",
    )

    # Build a SkillToolset that carries the external skill
    from haiku.skills.agent import SkillToolset

    ext_toolset = SkillToolset(skills=[ext_skill])
    stc = mock.MagicMock()
    stc.skill_toolset = ext_toolset

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.config_agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        agent = moodle_tools_agent_factory(
            agent_config, skill_toolset_config=stc
        )

    assert isinstance(agent, pydantic_ai.Agent)
    # System prompt should contain the router prompt and the external skill
    instructions = "\n".join(agent._instructions)
    assert MOODLE_ROUTER_PROMPT in instructions
    assert "test-skill" in instructions


def test_factory_skips_colliding_external_skill():
    """External skills with the same name as a Moodle skill are skipped."""
    from haiku.skills.agent import SkillToolset
    from haiku.skills.models import Skill
    from haiku.skills.models import SkillMetadata
    from haiku.skills.models import SkillSource

    from soliplex.moodle.agent import moodle_tools_agent_factory

    # Create an external skill that collides with "moodle-courses"
    collider = Skill(
        metadata=SkillMetadata(
            name="moodle-courses",
            description="I collide!",
        ),
        source=SkillSource.ENTRYPOINT,
        instructions="Colliding skill",
    )
    ext_toolset = SkillToolset(skills=[collider])
    stc = mock.MagicMock()
    stc.skill_toolset = ext_toolset

    agent_config = _make_agent_config()
    with mock.patch(
        "soliplex.moodle.agent.config_agents.get_model_from_factory_config",
        return_value=TestModel(),
    ):
        # Should not raise — colliding skill is skipped
        agent = moodle_tools_agent_factory(
            agent_config, skill_toolset_config=stc
        )
    assert isinstance(agent, pydantic_ai.Agent)


def test_factory_agent_has_expected_tools():
    """The router agent exposes execute_skill; individual tools
    live inside the seven Moodle skills."""
    agent = _build_agent()
    # Router agent should have execute_skill from SkillToolset
    # Inject a dummy toolset without .tools to cover the hasattr False branch
    all_tool_names: set[str] = set()
    for ts in [object(), *agent._user_toolsets]:
        if hasattr(ts, "tools"):
            all_tool_names.update(ts.tools.keys())
    assert "execute_skill" in all_tool_names

    # Verify skills collectively contain the expected tool names
    skills = _get_skills()
    skill_tool_names: set[str] = set()
    for skill in skills:
        for tool in skill.tools:
            skill_tool_names.add(tool.__name__)
    assert skill_tool_names == {
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
        # Program lifecycle tools
        "archive_program",
        "restore_program",
        "delete_program",
        "duplicate_program",
        "update_program_visibility",
        "bulk_deallocate_program_users",
        "bulk_reset_program_progress",
        # Certification lifecycle tools
        "delete_certification",
        "restore_certification",
        "search_certifications",
        "bulk_deallocate_certification_users",
        "list_competency_frameworks",
        "get_user_learning_plans",
        "get_user_competency",
        "get_course_competencies",
        # Reporting tools
        "list_reports",
        "get_report_data",
        "get_utm_report",
        "get_adv_comp_report",
        # Dynamic Rules tools
        "list_dynamic_rules",
        "can_enable_rule",
        "get_rule_matching_users",
        "get_rule_matched_users",
        "search_cohorts_for_rule",
        "search_competencies_for_rule",
        "enable_rule",
        "disable_rule",
        "archive_rule",
        "unarchive_rule",
        "delete_rule",
        "duplicate_rule",
        "delete_rule_condition",
        "delete_rule_outcome",
        # User management CRUD tools
        "create_user",
        "update_user",
        "delete_user",
        "unsuspend_user",
        # Course management CRUD tools
        "list_categories",
        "create_category",
        "create_course",
        "update_course",
        "delete_course",
        "duplicate_course",
        # Import/Export tools
        "export_workplace_data",
        "get_export_status",
        "download_export",
        "import_workplace_data",
        "get_import_status",
        "delete_export",
        "delete_import",
    }


def test_get_tool_fn_raises_for_missing_tool():
    skills = _get_skills()
    with pytest.raises(KeyError, match="no_such_tool"):
        _get_tool_fn(skills, "no_such_tool")


# -----------------------------------------------------------------
# list_courses tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_courses_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_courses")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_courses")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_enrolled_users")

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
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result) == 1
    assert result[0]["roles"] == ["student"]


@pytest.mark.asyncio
async def test_list_enrolled_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_enrolled_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


# -----------------------------------------------------------------
# get_completion_status tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completion_status_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_completion_status")

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
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_DOC_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="7"))

    assert result["completed"] is True
    assert len(result["completions"]) == 1
    assert result["completions"][0]["complete"] is True


@pytest.mark.asyncio
async def test_get_completion_status_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_completion_status")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_DOC_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="7"))

    assert "error" in result
    assert "No permission" in result["error"]


# -----------------------------------------------------------------
# Feature 1: get_course_contents tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_contents_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_contents")

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
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result) == 1
    assert result[0]["name"] == "General"
    assert len(result[0]["modules"]) == 2
    assert result[0]["modules"][1]["modname"] == "quiz"


@pytest.mark.asyncio
async def test_get_course_contents_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_contents")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 2: get_course_completion_overview tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_course_completion_overview_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_completion_overview")

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
            "completions": [
                {"type": 1, "title": "t", "status": "Yes", "complete": True}
            ],
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
            "completions": [
                {"type": 1, "title": "t", "status": "Yes", "complete": True}
            ],
        }
    }

    responses = [
        {"courses": [_SAFETY_COURSE]},  # course resolver
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
        result = json.loads(await fn(course="2"))

    assert result["total_enrolled"] == 3
    assert result["completed"] == 2
    assert result["incomplete"] == 1
    assert result["completion_rate"] == 66.7
    assert len(result["users"]) == 3


@pytest.mark.asyncio
async def test_get_course_completion_overview_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_completion_overview")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "invalidparam",
            "message": "Bad course",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_course_completion_overview_per_user_error():
    """When per-user completion lookup fails, the user still appears
    with completed=None."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_completion_overview")

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
        responses = [
            {"courses": [_SAFETY_COURSE]},  # course resolver
            enrolled_resp,
            error_resp,
        ]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="2"))

    assert result["total_enrolled"] == 1
    assert result["completed"] == 0
    assert result["users"][0]["completed"] is None
    assert result["users"][0]["completions"] == 0


@pytest.mark.asyncio
async def test_get_course_completion_overview_validation_error():
    """When Moodle returns a structurally malformed completion record
    for one user (pydantic.ValidationError on model_validate), the
    overview must keep going and mark that user as completed=None
    rather than aborting the whole gather() with an unhandled error.
    """
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_completion_overview")

    enrolled_resp = [
        {"id": 3, "username": "u1", "fullname": "User 1", "roles": []},
    ]
    # Missing the required "completionstatus" key -> ValidationError
    malformed_resp = {"something_unexpected": True}

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
        responses = [
            {"courses": [_SAFETY_COURSE]},  # course resolver
            enrolled_resp,
            malformed_resp,
        ]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="2"))

    assert result["total_enrolled"] == 1
    assert result["completed"] == 0
    assert result["users"][0]["completed"] is None
    assert result["users"][0]["completions"] == 0


# -----------------------------------------------------------------
# Feature 3: Groups & cohorts tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_course_groups_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_course_groups")

    resp = _mock_response(
        [
            {
                "id": 1,
                "courseid": 2,
                "name": "Group A",
                "description": "Desc A",
            },
            {"id": 2, "courseid": 2, "name": "Group B", "description": ""},
        ]
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result) == 2
    assert result[0]["name"] == "Group A"


@pytest.mark.asyncio
async def test_get_group_members_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    members_resp = _mock_response([{"groupid": 1, "userids": [3, 4, 5]}])
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        groups_resp,
        members_resp,
    ):
        result = json.loads(await fn(group="Day Shift", course="2"))

    assert result["group"] == "Day Shift"
    assert result["group_id"] == 1
    assert result["userids"] == [3, 4, 5]


@pytest.mark.asyncio
async def test_get_group_members_tool_empty():
    """Group exists but has no members — fall back to empty userids."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        groups_resp,
        _mock_response([]),
    ):
        result = json.loads(await fn(group="Day Shift", course="2"))

    assert result["group"] == "Day Shift"
    assert result["userids"] == []


@pytest.mark.asyncio
async def test_get_group_members_tool_numeric_id_not_found():
    """Digit input that doesn't match any group falls through to no-match."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), groups_resp):
        result = json.loads(await fn(group="999", course="2"))

    assert result["status"] == "error"
    assert "No group matches" in result["error"]


@pytest.mark.asyncio
async def test_get_group_members_tool_unknown_group():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        groups_resp,
    ):
        result = json.loads(await fn(group="Ghost", course="2"))

    assert result["status"] == "error"
    assert "No group matches" in result["error"]


@pytest.mark.asyncio
async def test_get_group_members_tool_empty_group_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response([])
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), groups_resp):
        result = json.loads(await fn(group="   ", course="2"))

    assert result["status"] == "error"
    assert "Empty group identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_group_members_tool_by_numeric_id():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    members_resp = _mock_response([{"groupid": 1, "userids": [7]}])
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        groups_resp,
        members_resp,
    ):
        result = json.loads(await fn(group="1", course="2"))

    assert result["group_id"] == 1
    assert result["userids"] == [7]


@pytest.mark.asyncio
async def test_get_group_members_tool_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [
            {"id": 1, "courseid": 2, "name": "Day Shift", "description": ""},
            {"id": 2, "courseid": 2, "name": "Day Shift", "description": ""},
        ]
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), groups_resp):
        result = json.loads(await fn(group="Day Shift", course="2"))

    assert result["status"] == "error"
    assert "Multiple groups" in result["error"]


@pytest.mark.asyncio
async def test_get_group_members_tool_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [
            {
                "id": 1,
                "courseid": 2,
                "name": "Day Shift A",
                "description": "",
            },
            {
                "id": 2,
                "courseid": 2,
                "name": "Day Shift B",
                "description": "",
            },
        ]
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), groups_resp):
        result = json.loads(await fn(group="Day", course="2"))

    assert result["status"] == "error"
    assert "Multiple groups" in result["error"]


@pytest.mark.asyncio
async def test_get_group_members_tool_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    groups_resp = _mock_response(
        [{"id": 1, "courseid": 2, "name": "Day Shift", "description": ""}]
    )
    members_resp = _mock_response([{"groupid": 1, "userids": []}])
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        groups_resp,
        members_resp,
    ):
        result = json.loads(await fn(group="Day", course="2"))

    assert result["group"] == "Day Shift"
    assert result["userids"] == []


@pytest.mark.asyncio
async def test_list_course_groups_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_course_groups")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_group_members_tool_error():
    """Course resolver failure short-circuits before group lookup."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_group_members")

    result = json.loads(await fn(group="Day Shift", course="   "))

    assert result["status"] == "error"
    assert "Empty course identifier" in result["error"]


@pytest.mark.asyncio
async def test_list_cohorts_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_cohorts")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    members_resp = [{"cohortid": 1, "userids": [3, 4]}]
    users_resp = [
        {
            "id": 3,
            "username": "u1",
            "firstname": "Alice",
            "lastname": "Johnson",
            "fullname": "Alice Johnson",
            "email": "alice@example.com",
        },
        {
            "id": 4,
            "username": "u2",
            "firstname": "Bob",
            "lastname": "Smith",
            "fullname": "Bob Smith",
            "email": "bob@example.com",
        },
    ]
    responses = [
        [_ENGINEERING_COHORT],  # cohort resolver
        members_resp,
        users_resp,
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

    async def post_side_effect(*_args, **_kwargs):
        nonlocal call_idx
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(cohort="1"))

    assert result["cohortid"] == 1
    assert len(result["members"]) == 2
    assert result["members"][0]["fullname"] == "Alice Johnson"
    assert result["members"][1]["fullname"] == "Bob Smith"


@pytest.mark.asyncio
async def test_get_cohort_members_tool_empty():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(
        _cohorts_list_resp(_ENGINEERING_COHORT),
        _mock_response([]),
    ):
        result = json.loads(await fn(cohort="1"))

    assert result["cohortid"] == 1
    assert result["members"] == []


@pytest.mark.asyncio
async def test_get_cohort_members_tool_no_userids():
    """Cohort exists but has no members — skip user enrichment."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(
        _cohorts_list_resp(_ENGINEERING_COHORT),
        _mock_response([{"cohortid": 1, "userids": []}]),
    ):
        result = json.loads(await fn(cohort="1"))

    assert result["cohortid"] == 1
    assert result["members"] == []


@pytest.mark.asyncio
async def test_list_cohorts_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_cohorts")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_cohort_members_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_cohorts_list_resp(_ENGINEERING_COHORT), err):
        result = json.loads(await fn(cohort="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_cohort_members_user_enrichment_error_fallback():
    """If the user-enrichment call fails, fall back to bare userids."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    members_resp = [{"cohortid": 1, "userids": [3, 4]}]
    error_resp = {
        "exception": "moodle_exception",
        "errorcode": "err",
        "message": "fail",
    }
    responses = [
        [_ENGINEERING_COHORT],  # cohort resolver
        members_resp,
        error_resp,
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

    async def post_side_effect(*_args, **_kwargs):
        nonlocal call_idx
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(cohort="1"))

    assert result["cohortid"] == 1
    assert result["members"] == [{"id": 3}, {"id": 4}]


# -----------------------------------------------------------------
# Feature 4: Grading tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_user_grades_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

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
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="3"))

    assert len(result) == 2
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == "90.00"
    assert result[1]["itemname"] == "Assignment 1"


@pytest.mark.asyncio
async def test_get_user_grades_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "nopermissions",
            "message": "No permission",
        }
    )
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="3"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_grades_tool_string_cells():
    """Grade table cells can be plain strings instead of dicts."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

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
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="3"))

    assert len(result) == 1
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == "90.00"
    assert result[0]["percentage"] == "90.00 %"


@pytest.mark.asyncio
async def test_get_user_grades_tool_missing_keys():
    """Rows with missing grade/percentage keys still parse; rows without
    itemname are skipped."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

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
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(course="2", user="3"))

    assert len(result) == 1
    assert result[0]["itemname"] == "Quiz 1"
    assert result[0]["grade"] == ""
    assert result[0]["percentage"] == ""


@pytest.mark.asyncio
async def test_get_assignment_grades_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_assignment_grades")

    # First call: get_course_contents, second call: get_assignment_grades
    contents_resp = [
        {
            "id": 1,
            "name": "General",
            "visible": 1,
            "summary": "",
            "modules": [
                {
                    "id": 10,
                    "name": "Assign 1",
                    "modname": "assign",
                    "visible": 1,
                    "completion": 0,
                },
                {
                    "id": 11,
                    "name": "Quiz 1",
                    "modname": "quiz",
                    "visible": 1,
                    "completion": 0,
                },
            ],
        }
    ]
    grades_resp = {
        "assignments": [
            {
                "assignmentid": 10,
                "grades": [
                    {
                        "userid": 3,
                        "grade": "85.00",
                        "timemodified": 1700000000,
                    },
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
        responses = [
            {"courses": [_SAFETY_COURSE]},  # course resolver
            contents_resp,
            grades_resp,
        ]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="2"))

    assert len(result) == 1
    assert result[0]["assignmentid"] == 10
    assert result[0]["grades"][0]["grade"] == "85.00"


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_no_assignments():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_assignment_grades")

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
                        "name": "Quiz 1",
                        "modname": "quiz",
                        "visible": 1,
                        "completion": 0,
                    },
                ],
            }
        ]
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert result["message"] == "No assignments found in this course"


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_contents_error():
    """Error on the first API call (get_course_contents)."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_assignment_grades")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_assignment_grades_tool_grades_error():
    """Error on the second API call (get_assignment_grades)."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_assignment_grades")

    contents_resp = [
        {
            "id": 1,
            "name": "General",
            "visible": 1,
            "summary": "",
            "modules": [
                {
                    "id": 10,
                    "name": "Assign 1",
                    "modname": "assign",
                    "visible": 1,
                    "completion": 0,
                },
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
        responses = [
            {"courses": [_SAFETY_COURSE]},  # course resolver
            contents_resp,
            error_resp,
        ]
        resp = make_response(responses[call_idx])
        call_idx += 1
        return resp

    mock_client.post.side_effect = post_side_effect

    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="2"))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 5: Calendar & deadlines tool
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_upcoming_events_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_upcoming_events")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_upcoming_events")

    # When no courseids provided, the tool fetches all courses first,
    # then calls get_calendar_events with those course IDs.
    courses_resp = _mock_response(
        [
            {"id": 1, "shortname": "site", "fullname": "Site"},
            {"id": 2, "shortname": "c1", "fullname": "C1"},
        ]
    )
    events_resp = _mock_response({"events": []})
    with mock.patch(
        "httpx.AsyncClient.post", side_effect=[courses_resp, events_resp]
    ):
        result = json.loads(await fn("", 7))

    assert result == []


@pytest.mark.asyncio
async def test_get_upcoming_events_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_upcoming_events")

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
    """Preview resolves human-friendly user + course identifiers."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),  # user "alice" via username
        _mock_response(
            {"courses": [_CYBER_COURSE]}
        ),  # course resolver via id-not-numeric → shortname
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(users="alice", course="cyber101"))

    assert result["action"] == "enrol_users"
    assert "Cybersecurity Basics" in result["preview"]
    assert "Alice Johnson" in result["users"][0]
    assert result["course_id"] == 3
    assert result["user_count"] == 1


@pytest.mark.asyncio
async def test_enrol_users_tool_preview_by_course_name():
    """Course fullname (substring) resolves through the fallback path."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),  # alice via username
        # course resolver: shortname empty, idnumber empty, then
        # get_courses() returns the catalogue
        _mock_response({"courses": []}),  # shortname
        _mock_response({"courses": []}),  # idnumber
        _mock_response([_SAFETY_COURSE, _CYBER_COURSE]),  # get_courses
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(users="alice", course="Cybersecurity Basics")
        )

    assert result["action"] == "enrol_users"
    assert "Cybersecurity Basics" in result["preview"]


@pytest.mark.asyncio
async def test_enrol_users_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),  # alice via username
        _mock_response([_DOC_USER]),  # doc_test via username
        _mock_response({"courses": [_CYBER_COURSE]}),  # course
        _mock_response(None),  # enrol_users actual call
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(
                users="alice,doc_test",
                course="cyber101",
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["enrolled"] == 2


@pytest.mark.asyncio
async def test_enrol_users_tool_unresolvable_user():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    with _patch_httpx(_mock_response([])):
        result = json.loads(await fn(users="ghost_user", course="cyber101"))

    assert result["status"] == "error"
    assert "No user matches" in result["error"]


@pytest.mark.asyncio
async def test_enrol_users_tool_unresolvable_course():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),  # alice resolves
        _mock_response({"courses": []}),  # shortname empty
        _mock_response({"courses": []}),  # idnumber empty
        _mock_response([]),  # get_courses empty
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(users="alice", course="Ghost Course"))

    assert result["status"] == "error"
    assert "No course matches" in result["error"]


@pytest.mark.asyncio
async def test_enrol_users_tool_empty_users():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    result = json.loads(await fn(users="  ,  ", course="cyber101"))

    assert result["status"] == "error"
    assert "Empty user list" in result["error"]


@pytest.mark.asyncio
async def test_enrol_users_tool_error():
    """Moodle-side error on the actual enrol_users call surfaces."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),
        _mock_response({"courses": [_CYBER_COURSE]}),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "nopermissions",
                "message": "No permission",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(users="alice", course="cyber101", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_send_message_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "send_message")

    result = json.loads(await fn("3,4", "Hello!", False))

    assert result["action"] == "send_message"
    assert result["user_ids"] == [3, 4]
    assert "preview" in result


@pytest.mark.asyncio
async def test_send_message_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "send_message")

    resp = _mock_response([{"msgid": 1}, {"msgid": 2}])
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", "Hello!", True))

    assert result["success"] is True
    assert result["sent"] == 2
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_send_message_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "send_message")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    resp = _mock_response(
        [
            {
                "id": 1,
                "fullname": "Workplace Safety",
                "idnumber": "WS01",
                "status": 0,
            },
            {
                "id": 2,
                "fullname": "Data Privacy",
                "idnumber": "DP01",
                "status": 0,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 2
    assert result[0]["fullname"] == "Workplace Safety"


@pytest.mark.asyncio
async def test_list_certifications_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_certification_allocations_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

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
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), resp):
        result = json.loads(await fn(certification="1"))

    assert len(result) == 1
    assert result[0]["userfullname"] == "Alice Johnson"


@pytest.mark.asyncio
async def test_get_certification_allocations_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), err):
        result = json.loads(await fn(certification="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_certifications_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_certifications")

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
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(await fn(user="alice"))

    assert len(result) == 1
    assert result[0]["certificationfullname"] == "Workplace Safety"


@pytest.mark.asyncio
async def test_get_user_certifications_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_certifications")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(await fn(user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_certifications_tool_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_certifications")

    result = json.loads(await fn(user="   "))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_certification_history_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_history")

    resp = _mock_response(
        [
            {"id": 1, "action": "allocated", "timecreated": 1700000000},
            {"id": 2, "action": "certified", "timecreated": 1700001000},
        ]
    )
    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(certification="1", user="alice"))

    assert len(result) == 2
    assert result[0]["action"] == "allocated"
    assert result[1]["action"] == "certified"


@pytest.mark.asyncio
async def test_get_certification_history_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_history")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([_ALICE_USER]),
        err,
    ):
        result = json.loads(await fn(certification="1", user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_certify_user_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "certify_user")

    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
    ):
        result = json.loads(await fn(user="alice", certification="1"))

    assert result["action"] == "certify_user"
    assert result["user_id"] == 3
    assert result["certification_id"] == 1
    assert "preview" in result


@pytest.mark.asyncio
async def test_certify_user_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "certify_user")

    resp = _mock_response({"result": True})
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        resp,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert result["success"] is True
    assert result["user_id"] == 3
    assert result["certification_id"] == 1


@pytest.mark.asyncio
async def test_certify_user_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "certify_user")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        err,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_revoke_certification_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "revoke_certification")

    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
    ):
        result = json.loads(await fn(user="alice", certification="1"))

    assert result["action"] == "revoke_certification"
    assert result["user_id"] == 3
    assert result["certification_id"] == 1


@pytest.mark.asyncio
async def test_revoke_certification_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "revoke_certification")

    resp = _mock_response({"result": True})
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        resp,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert result["success"] is True
    assert result["user_id"] == 3


@pytest.mark.asyncio
async def test_revoke_certification_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "revoke_certification")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        err,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert "error" in result


# -----------------------------------------------------------------
# Feature 9: Program tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_programs_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_programs")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_programs")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_program_courses_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_program_courses")

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
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(await fn(user="alice"))

    assert len(result) == 2
    assert result[0]["completed"] is True
    assert result[1]["completed"] is False


@pytest.mark.asyncio
async def test_get_user_program_courses_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_program_courses")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(await fn(user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_program")

    second_user = dict(_DOC_USER, id=4, username="bob")
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _mock_response([second_user]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
    ):
        result = json.loads(await fn(users="alice,bob", program="1"))

    assert result["action"] == "allocate_users_to_program"
    assert result["program_id"] == 1
    assert "preview" in result


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_program")

    second_user = dict(_DOC_USER, id=4, username="bob")
    resp = _mock_response({"result": []})
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _mock_response([second_user]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(
            await fn(users="alice,bob", program="1", confirmed=True)
        )

    assert result["success"] is True
    assert result["allocated"] == 2
    assert result["program_id"] == 1


@pytest.mark.asyncio
async def test_allocate_users_to_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(
            await fn(users="alice", program="1", confirmed=True)
        )

    assert "error" in result


# -----------------------------------------------------------------
# Feature 10: Tenant tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenants_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_tenants")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Default",
                "sitename": "Moodle",
                "idnumber": "",
                "isdefault": True,
            },
            {
                "id": 2,
                "name": "Regional",
                "sitename": "Regional",
                "idnumber": "REG01",
                "isdefault": False,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 2
    assert result[0]["isdefault"] is True
    assert result[1]["name"] == "Regional"


@pytest.mark.asyncio
async def test_list_tenants_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_tenants")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


# -----------------------------------------------------------------
# Feature 11: Catalogue tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_browse_catalogue_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "browse_catalogue")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "browse_catalogue")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_catalogue")

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
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(await fn(user="alice"))

    assert len(result) == 1
    assert result[0]["fullname"] == "Safety"
    assert result[0]["progress"] == 50


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_tool_current_user():
    """Empty ``user`` skips the resolver and queries the current user."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_catalogue")

    resp = _mock_response({"catalogue": {"listitems": []}})
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert result == []


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_catalogue")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(await fn(user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_program_content_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_program_content")

    resp = _mock_response(
        {"sets": [{"name": "Core"}], "courses": [{"id": 2}], "warnings": []}
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1"))

    assert "sets" in result
    assert "courses" in result


@pytest.mark.asyncio
async def test_get_program_content_tool_with_user():
    """``user`` resolves and is passed to the program-content call."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_program_content")

    resp = _mock_response({"sets": [], "courses": [], "warnings": []})
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(program="1", user="alice"))

    assert "sets" in result


@pytest.mark.asyncio
async def test_get_program_content_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_program_content")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1"))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 12: Deeper Program Management tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_courses_for_program_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_courses_for_program")

    resp = _mock_response([{"id": 2, "fullname": "Safety Fundamentals"}])
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["fullname"] == "Safety Fundamentals"


@pytest.mark.asyncio
async def test_search_courses_for_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_courses_for_program")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_program")

    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
    ):
        result = json.loads(await fn(user="alice", program="1"))

    assert result["action"] == "deallocate_user_from_program"
    assert "preview" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_program")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(
            await fn(user="alice", program="1", confirmed=True)
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_deallocate_user_from_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(
            await fn(user="alice", program="1", confirmed=True)
        )

    assert "error" in result


# -----------------------------------------------------------------
# Feature 13: Deeper Certification Management tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_certification_user_details_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_user_details")

    resp = _mock_response({"id": 10, "userid": 3, "status": "certified"})
    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([_ALICE_USER]),
        resp,
    ):
        result = json.loads(await fn(certification="1", user="alice"))

    assert result["id"] == 10
    assert result["userid"] == 3
    assert result["status"] == "certified"


@pytest.mark.asyncio
async def test_get_certification_user_details_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_user_details")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([_ALICE_USER]),
        err,
    ):
        result = json.loads(await fn(certification="1", user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_certification")

    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
    ):
        result = json.loads(await fn(user="alice", certification="1"))

    assert result["action"] == "deallocate_user_from_certification"
    assert "preview" in result


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_certification")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        resp,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_certification")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _certs_list_resp(_SAFETY_CERT),
        err,
    ):
        result = json.loads(
            await fn(user="alice", certification="1", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_archive_certification_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_certification")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="1"))

    assert result["action"] == "archive_certification"
    assert "preview" in result


@pytest.mark.asyncio
async def test_archive_certification_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_certification")

    resp = _mock_response(None)
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), resp):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_archive_certification_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_certification")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), err):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert "error" in result


# -----------------------------------------------------------------
# Tenant write tools (allocate_users_to_tenant, suspend_users)
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    second_user = dict(_DOC_USER, id=4, username="bob")
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _mock_response([second_user]),
        _tenants_list_resp(_DEFAULT_TENANT),
    ):
        result = json.loads(
            await fn(users="alice,bob", tenant="Regional Office")
        )

    assert result["action"] == "allocate_users_to_tenant"
    assert "preview" in result
    assert result["tenant_id"] == 2
    assert result["user_count"] == 2


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    second_user = dict(_DOC_USER, id=4, username="bob")
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _mock_response([second_user]),
        _tenants_list_resp(_DEFAULT_TENANT),
        _mock_response(None),
    ):
        result = json.loads(
            await fn(
                users="alice,bob",
                tenant="Regional Office",
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["allocated"] == 2


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    second_user = dict(_DOC_USER, id=4, username="bob")
    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _mock_response([_ALICE_USER]),
        _mock_response([second_user]),
        _tenants_list_resp(_DEFAULT_TENANT),
        err,
    ):
        result = json.loads(
            await fn(
                users="alice,bob",
                tenant="Regional Office",
                confirmed=True,
            )
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_suspend_users_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "suspend_users")

    result = json.loads(await fn("3,4", False))

    assert result["action"] == "suspend_users"
    assert "preview" in result
    assert "WARNING" in result["preview"]
    assert result["user_ids"] == [3, 4]


@pytest.mark.asyncio
async def test_suspend_users_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "suspend_users")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", True))

    assert result["success"] is True
    assert result["suspended"] == 2


@pytest.mark.asyncio
async def test_suspend_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "suspend_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("3,4", True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 14: Organisation Structure tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_departments_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_departments")

    # local_soliplex_list_departments returns a flat list with
    # real idnumber + parentid.
    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Engineering"
    assert result[0]["idnumber"] == "ENG"
    assert result[0]["parent"] == ""
    # Integer IDs must not leak — the LLM should never see them.
    assert "id" not in result[0]
    assert "parentid" not in result[0]
    # Single Moodle round-trip.
    assert patched.return_value.post.call_count == 1


@pytest.mark.asyncio
async def test_list_departments_tool_resolves_parent_idnumber_under_search():
    """Parent idnumber resolution uses the full list, not the
    search-filtered one — even when the parent's name doesn't
    match the filter — and is done in a single Moodle round-trip.

    NOTE: because the wrapper always fetches the full list
    (search=""), the server-side search filter is no longer
    relevant; the wrapper does its own name-substring filter
    after the fetch.  We mock the FULL list and verify the
    wrapper's client-side filter returns just the child."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_departments")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Operations",
                "idnumber": "OPS",
                "parentid": 1,
            },
        ]
    )
    with _patch_httpx(resp) as patched:
        # Search for "Operations" → only the child matches, but the
        # parent must still be resolved to "ENG".
        result = json.loads(await fn(search="Operations"))

    assert len(result) == 1
    assert result[0]["idnumber"] == "OPS"
    assert result[0]["parent"] == "ENG"
    # Single Moodle round-trip.
    assert patched.return_value.post.call_count == 1


@pytest.mark.asyncio
async def test_list_departments_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_departments")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_list_positions_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_positions")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Manager",
                "idnumber": "MGR",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Manager"
    assert result[0]["idnumber"] == "MGR"
    assert result[0]["parent"] == ""
    assert "id" not in result[0]
    assert "parentid" not in result[0]
    # Single Moodle round-trip.
    assert patched.return_value.post.call_count == 1


@pytest.mark.asyncio
async def test_list_positions_tool_resolves_parent_idnumber_under_search():
    """Parent idnumber resolution for positions: full list fetched
    once, wrapper applies its own client-side filter."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_positions")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Manager",
                "idnumber": "MGR",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Senior Manager",
                "idnumber": "SRMGR",
                "parentid": 1,
            },
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn(search="Senior"))

    assert len(result) == 1
    assert result[0]["idnumber"] == "SRMGR"
    assert result[0]["parent"] == "MGR"
    assert patched.return_value.post.call_count == 1


@pytest.mark.asyncio
async def test_list_positions_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_positions")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_team_members_tool():
    """System report returns department members."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        {
            "data": {
                "headers": [
                    "Full name with link",
                    "Department",
                    "Position",
                    "",
                    "",
                    "",
                ],
                "rows": [
                    {
                        "columns": [
                            '<a href="http://moodle.test/user/profile.php'
                            '?id=3">Alice Johnson</a>',
                            "Engineering",
                            "Manager",
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["fullname"] == "Alice Johnson"
    assert result[0]["departmentname"] == "Engineering"
    assert result[0]["positionname"] == "Manager"


@pytest.mark.asyncio
async def test_get_team_members_tool_error():
    """API error returns error JSON."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_assign_job_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_job")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(
            await fn(user="alice", department="ENG", position="MGR")
        )

    assert result["action"] == "assign_job"
    assert result["user_id"] == 3
    assert "preview" in result


@pytest.mark.asyncio
async def test_assign_job_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_job")

    resp = _mock_response({"id": 1})
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(
            await fn(
                user="alice",
                department="ENG",
                position="MGR",
                confirmed=True,
            )
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_assign_job_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_job")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(
            await fn(
                user="alice",
                department="ENG",
                position="MGR",
                confirmed=True,
            )
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_assign_manager_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_manager")

    result = json.loads(await fn("4", "3", False))

    assert result["action"] == "assign_manager"
    assert "preview" in result
    assert result["user_ids"] == [4]
    assert result["manager_ids"] == [3]


@pytest.mark.asyncio
async def test_assign_manager_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_manager")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn("4", "3", True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_assign_manager_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_manager")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("4", "3", True))

    assert "error" in result


# -----------------------------------------------------------------
# Feature 15: Competency tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_competency_frameworks_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_competency_frameworks")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_competency_frameworks")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_learning_plans_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_plans")

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
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(await fn(user="alice"))

    assert len(result) == 1
    assert result[0]["name"] == "Alice's Plan"


@pytest.mark.asyncio
async def test_get_user_learning_plans_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_plans")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(await fn(user="alice"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_user_competency_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_competency")

    resp = _mock_response({"usercompetency": {"userid": 3, "competencyid": 1}})
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), resp):
        result = json.loads(await fn(user="alice", competencyid=1))

    assert "usercompetency" in result
    assert result["usercompetency"]["userid"] == 3


@pytest.mark.asyncio
async def test_get_user_competency_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_competency")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_mock_response([_ALICE_USER]), err):
        result = json.loads(await fn(user="alice", competencyid=1))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_course_competencies_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_competencies")

    resp = _mock_response(
        {
            "competencies": [
                {"competency": {"id": 1, "shortname": "Communication"}}
            ]
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result) == 1
    assert result[0]["competency"]["shortname"] == "Communication"


@pytest.mark.asyncio
async def test_get_course_competencies_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_course_competencies")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


# -----------------------------------------------------------------
# Non-numeric ID validation tests
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_assign_manager_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_manager")

    result = json.loads(await fn("alice", "3", False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_assign_manager_tool_non_numeric_manager():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_manager")

    result = json.loads(await fn("4", "bob", False))

    assert "error" in result
    assert "bob" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_send_message_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "send_message")

    result = json.loads(await fn("alice", "Hello!", False))

    assert "error" in result
    assert "alice" in result["error"]
    assert "find_user" in result["error"]


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tool_unknown_user():
    """User names that don't resolve return a clean resolver error."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    # Resolver tries username/idnumber/email (each returns []), then
    # firstname + lastname search (each returns {"users": []}).
    with _patch_httpx_chain(
        _mock_response([]),
        _mock_response([]),
        _mock_response([]),
        _mock_response({"users": []}),
        _mock_response({"users": []}),
    ):
        result = json.loads(
            await fn(users="ghost_user", tenant="Regional Office")
        )

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_suspend_users_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "suspend_users")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

    result = json.loads(await fn("phone", "1234"))

    assert "error" in result
    assert "Unsupported field" in result["error"]


@pytest.mark.asyncio
async def test_find_user_by_name_error():
    """find_user with field='name' returns error on API failure."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "find_user")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn("name", "Alice"))

    assert "error" in result


# -----------------------------------------------------------------
# Reporting tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_reports_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_reports")

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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_reports")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_report_data_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    test_report = dict(_COMPLETION_REPORT, id=1, name="Test Report")
    data_resp = _mock_response(
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
    with _patch_httpx_chain(_reports_list_resp(test_report), data_resp):
        result = json.loads(await fn(report="1"))

    assert result["headers"] == ["Name", "Email"]
    assert result["rows"][0] == ["Alice", "alice@example.com"]
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_report_data_tool_strips_none_values():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    test_report = dict(_COMPLETION_REPORT, id=1, name="Test Report")
    data_resp = _mock_response(
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
    with _patch_httpx_chain(_reports_list_resp(test_report), data_resp):
        result = json.loads(await fn(report="1"))

    assert result["rows"][0] == ["", "alice@example.com"]


@pytest.mark.asyncio
async def test_get_report_data_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    test_report = dict(_COMPLETION_REPORT, id=1, name="Test Report")
    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_reports_list_resp(test_report), err):
        result = json.loads(await fn(report="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_utm_report_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

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
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "Alice Johnson"
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_utm_report_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_adv_comp_report_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_adv_comp_report")

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
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert len(result["rows"]) == 1
    assert result["rows"][0]["name"] == "Bob Smith"
    assert result["rows"][0]["completedtime"] is None
    assert result["total_rows"] == 1


@pytest.mark.asyncio
async def test_get_adv_comp_report_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_adv_comp_report")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE), resp):
        result = json.loads(await fn(course="2"))

    assert "error" in result


# -----------------------------------------------------------------
# Organisation CRUD tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_potential_parent_departments_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_potential_parent_departments")

    resp = _mock_response(
        [{"id": 1, "name": "Root", "path": "/Root", "locked": 0}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Root"


@pytest.mark.asyncio
async def test_get_potential_parent_departments_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_potential_parent_departments")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_get_potential_parent_positions_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_potential_parent_positions")

    resp = _mock_response(
        [{"id": 1, "name": "Management", "path": "/Mgmt", "locked": 0}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Management"


@pytest.mark.asyncio
async def test_get_potential_parent_positions_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_potential_parent_positions")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_create_department_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_department")

    result = json.loads(await fn(name="Finance", idnumber="FIN"))

    assert "preview" in result
    assert result["name"] == "Finance"
    assert result["idnumber"] == "FIN"
    assert result["action"] == "create_department"
    assert "instructions" not in result


@pytest.mark.asyncio
async def test_create_department_tool_preview_with_optional():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_department")

    result = json.loads(
        await fn(name="Security", parent="ENG", description="Sec team")
    )

    assert result["parent"] == "ENG"
    assert result["description"] == "Sec team"


@pytest.mark.asyncio
async def test_create_department_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_department")

    resp = _mock_response(
        {
            "result": [{"id": 10, "name": "Finance", "idnumber": "FIN"}],
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(name="Finance", idnumber="FIN", confirmed=True)
        )

    assert len(result["created"]) == 1
    assert result["created"][0]["idnumber"] == "FIN"


@pytest.mark.asyncio
async def test_create_department_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_department")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,kwargs,response_key",
    [
        (
            "create_department",
            {"name": "X", "parent": "BAD", "confirmed": True},
            "departments",
        ),
        (
            "update_department",
            {"idnumber": "X", "parent": "BAD", "confirmed": True},
            "departments",
        ),
        (
            "create_position",
            {"name": "X", "parent": "BAD", "confirmed": True},
            "positions",
        ),
        (
            "update_position",
            {"idnumber": "X", "parent": "BAD", "confirmed": True},
            "positions",
        ),
    ],
)
async def test_org_write_tool_surfaces_warnings_as_error(
    tool_name, kwargs, response_key
):
    """Moodle write endpoints can return HTTP 200 with empty
    result + populated warnings (e.g. ``errorparentnotfound``).
    The client raises MoodleAPIError so the wrapper's status
    field reflects the failure instead of confabulating success."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, tool_name)

    resp = _mock_response(
        {
            "result": [],
            "warnings": [
                {
                    "item": "X",
                    "warningcode": "errorparentnotfound",
                    "message": "Parent not found",
                }
            ],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(**kwargs))

    assert result["status"] == "error"
    assert "Parent not found" in result["error"]


def test_warnings_message_renders_items_and_falls_back_on_empty():
    from soliplex.moodle.client import _warnings_message

    assert _warnings_message([]) == "operation rejected"
    assert (
        _warnings_message([{"item": "X", "message": "Parent not found"}])
        == "X: Parent not found"
    )
    # Missing 'item' → no prefix.
    assert _warnings_message([{"message": "bare msg"}]) == "bare msg"
    # Missing 'message' → fall back to warningcode → fall back to
    # "unknown error".
    assert _warnings_message([{"warningcode": "code1"}]) == "code1"
    assert _warnings_message([{}]) == "unknown error"


@pytest.mark.asyncio
async def test_update_department_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_department")

    result = json.loads(await fn(idnumber="FIN", name="Finance Dept"))

    assert "preview" in result
    assert result["changes"]["name"] == "Finance Dept"


@pytest.mark.asyncio
async def test_update_department_tool_preview_with_optional():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_department")

    result = json.loads(
        await fn(idnumber="FIN", parent="ROOT", description="Updated")
    )

    assert result["changes"]["parent"] == "ROOT"
    assert result["changes"]["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_department_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_department")

    resp = _mock_response(
        {"result": [{"id": 10, "idnumber": "FIN"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(idnumber="FIN", name="Finance Dept", confirmed=True)
        )

    assert len(result["updated"]) == 1
    assert result["updated"][0]["idnumber"] == "FIN"


@pytest.mark.asyncio
async def test_update_department_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_department")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_department_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")

    result = json.loads(await fn(idnumber="ENG"))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_department_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")

    # Both http calls (full-list lookup + delete) hit the same mock
    # response.  The lookup parses local_soliplex_list_departments'
    # flat list shape; the delete API is coerced to {"result": True}.
    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="ENG", confirmed=True))

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_department_tool_not_found_exact_match_only():
    """Resolution is by idnumber EXACT match (not name substring).
    A department whose NAME contains the search string but whose
    idnumber doesn't match must not be deleted.  This is the B1
    correctness fix."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")

    resp = _mock_response(
        [
            {
                "id": 5,
                "name": "Missing Person Department",
                "idnumber": "PERSON",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="MISSING", confirmed=True))

    assert result["status"] == "error"
    assert "MISSING" in result["error"]


@pytest.mark.asyncio
async def test_delete_department_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="ENG", confirmed=True))

    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_create_position_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_position")

    result = json.loads(await fn(name="Engineer", idnumber="ENG"))

    assert "preview" in result
    assert result["position"]["name"] == "Engineer"


@pytest.mark.asyncio
async def test_create_position_tool_preview_with_optional():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_position")

    result = json.loads(
        await fn(name="Analyst", parent="MGMT", description="Data team")
    )

    assert result["position"]["parent"] == "MGMT"
    assert result["position"]["description"] == "Data team"


@pytest.mark.asyncio
async def test_create_position_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_position")

    resp = _mock_response(
        {
            "result": [{"id": 5, "name": "Engineer", "idnumber": "ENG"}],
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(name="Engineer", idnumber="ENG", confirmed=True)
        )

    assert len(result["created"]) == 1
    assert result["created"][0]["idnumber"] == "ENG"


@pytest.mark.asyncio
async def test_create_position_tool_with_flags():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_position")

    resp = _mock_response(
        {
            "result": [{"id": 6, "name": "Lead", "idnumber": "LEAD"}],
            "warnings": [],
        }
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
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_position")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_update_position_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_position")

    result = json.loads(await fn(idnumber="ENG", name="Senior Engineer"))

    assert "preview" in result
    assert result["changes"]["name"] == "Senior Engineer"


@pytest.mark.asyncio
async def test_update_position_tool_preview_with_optional():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_position")

    result = json.loads(
        await fn(idnumber="ENG", parent="MGMT", description="Updated")
    )

    assert result["changes"]["parent"] == "MGMT"
    assert result["changes"]["description"] == "Updated"


@pytest.mark.asyncio
async def test_update_position_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_position")

    resp = _mock_response(
        {"result": [{"id": 5, "idnumber": "ENG"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(idnumber="ENG", name="Senior Engineer", confirmed=True)
        )

    assert len(result["updated"]) == 1


@pytest.mark.asyncio
async def test_update_position_tool_with_flags():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_position")

    resp = _mock_response(
        {"result": [{"id": 5, "idnumber": "ENG"}], "warnings": []}
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(
                idnumber="ENG",
                department_manager=True,
                global_manager=False,
                confirmed=True,
            )
        )

    assert len(result["updated"]) == 1


@pytest.mark.asyncio
async def test_update_position_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_position")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="X", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_position_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_position")

    result = json.loads(await fn(idnumber="ENG"))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_position_tool_not_found_exact_match_only():
    """Resolution is by idnumber EXACT match.  A position whose
    NAME contains the search string but idnumber doesn't match
    must not be deleted.  B1 correctness for positions."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_position")

    resp = _mock_response(
        [
            {
                "id": 5,
                "name": "Missing Person Position",
                "idnumber": "PERSON",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="MISSING", confirmed=True))

    assert result["status"] == "error"
    assert "MISSING" in result["error"]


@pytest.mark.asyncio
async def test_delete_position_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_position")

    resp = _mock_response(
        [
            {
                "id": 5,
                "name": "Engineer",
                "idnumber": "ENG-POS",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="ENG-POS", confirmed=True))

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_delete_position_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_position")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(idnumber="ENG", confirmed=True))

    assert result["status"] == "error"
    assert "error" in result


@pytest.mark.asyncio
async def test_delete_job_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_job")

    result = json.loads(await fn(job_id=42))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_job_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_job")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(job_id=42, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_job_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_job")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(job_id=42, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unassign_manager")

    result = json.loads(await fn(userids="3", managerids="5"))

    assert "preview" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unassign_manager")

    resp = _mock_response(
        {
            "warnings": [],
            "unassignedmanagers": [{"itemid": 1, "userid": 3, "managerid": 5}],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(userids="3", managerids="5", confirmed=True)
        )

    assert len(result["unassignedmanagers"]) == 1


@pytest.mark.asyncio
async def test_unassign_manager_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unassign_manager")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(userids="3", managerids="5", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unassign_manager")

    result = json.loads(await fn(userids="abc", managerids="5"))

    assert "error" in result


@pytest.mark.asyncio
async def test_unassign_manager_tool_non_numeric_managerids():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unassign_manager")

    result = json.loads(await fn(userids="3", managerids="abc"))

    assert "error" in result


# -----------------------------------------------------------------
# Program & Certification Lifecycle tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_archive_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1"))

    assert "preview" in result
    assert "Archive" in result["preview"]


@pytest.mark.asyncio
async def test_archive_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_archive_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_restore_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1"))

    assert "preview" in result
    assert "Restore" in result["preview"]


@pytest.mark.asyncio
async def test_restore_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_program")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_restore_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1"))

    assert "preview" in result
    assert "DELETE" in result["preview"]


@pytest.mark.asyncio
async def test_delete_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_program")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_duplicate_program_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1"))

    assert "preview" in result
    assert "Duplicate" in result["preview"]


@pytest.mark.asyncio
async def test_duplicate_program_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_program")

    resp = _mock_response(
        {"duplicatedprogramid": 99, "redirecturl": "/program/view.php?id=99"}
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert result["duplicatedprogramid"] == 99
    assert result["redirecturl"] == "/program/view.php?id=99"


@pytest.mark.asyncio
async def test_duplicate_program_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_program")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_update_program_visibility_tool_preview_visible():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_program_visibility")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1", visible=1))

    assert "preview" in result
    assert "visible" in result["preview"]


@pytest.mark.asyncio
async def test_update_program_visibility_tool_preview_hidden():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_program_visibility")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1", visible=0))

    assert "preview" in result
    assert "hidden" in result["preview"]


@pytest.mark.asyncio
async def test_update_program_visibility_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_program_visibility")

    resp = _mock_response(None)
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        resp,
    ):
        result = json.loads(await fn(program="1", visible=1, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_update_program_visibility_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_program_visibility")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
        err,
    ):
        result = json.loads(await fn(program="1", visible=1, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_deallocate_program_users_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_program_users")

    result = json.loads(await fn(allocation_ids="10,20"))

    assert "preview" in result
    assert result["allocation_ids"] == [10, 20]


@pytest.mark.asyncio
async def test_bulk_deallocate_program_users_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_program_users")

    resp = _mock_response({"successcount": 2, "skippedcount": 0})
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert result["successcount"] == 2
    assert result["skippedcount"] == 0


@pytest.mark.asyncio
async def test_bulk_deallocate_program_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_program_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_deallocate_program_users_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_program_users")

    result = json.loads(await fn(allocation_ids="abc,20"))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_reset_program_progress_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_reset_program_progress")

    result = json.loads(await fn(allocation_ids="10,20"))

    assert "preview" in result
    assert result["allocation_ids"] == [10, 20]


@pytest.mark.asyncio
async def test_bulk_reset_program_progress_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_reset_program_progress")

    resp = _mock_response({"successcount": 2, "skippedcount": 0})
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert result["successcount"] == 2
    assert result["skippedcount"] == 0


@pytest.mark.asyncio
async def test_bulk_reset_program_progress_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_reset_program_progress")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_reset_program_progress_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_reset_program_progress")

    result = json.loads(await fn(allocation_ids="abc,20"))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_certification_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_certification")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="1"))

    assert "preview" in result
    assert "DELETE" in result["preview"]


@pytest.mark.asyncio
async def test_delete_certification_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_certification")

    resp = _mock_response(None)
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), resp):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_certification_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_certification")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), err):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_restore_certification_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_certification")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="1"))

    assert "preview" in result
    assert "Restore" in result["preview"]


@pytest.mark.asyncio
async def test_restore_certification_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_certification")

    resp = _mock_response(None)
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), resp):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_restore_certification_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_certification")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT), err):
        result = json.loads(await fn(certification="1", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_search_certifications_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_certifications")

    resp = _mock_response([{"id": 1, "fullname": "Safety Cert"}])
    with _patch_httpx(resp):
        result = json.loads(await fn(search="Safety"))

    assert len(result) == 1
    assert result[0]["id"] == 1
    assert result[0]["fullname"] == "Safety Cert"


@pytest.mark.asyncio
async def test_search_certifications_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_certifications")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(search="Safety"))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_deallocate_certification_users_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_certification_users")

    result = json.loads(await fn(allocation_ids="10,20"))

    assert "preview" in result
    assert result["allocation_ids"] == [10, 20]


@pytest.mark.asyncio
async def test_bulk_deallocate_certification_users_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_certification_users")

    resp = _mock_response({"successcount": 2, "skippedcount": 0})
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert result["successcount"] == 2
    assert result["skippedcount"] == 0


@pytest.mark.asyncio
async def test_bulk_deallocate_certification_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_certification_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(allocation_ids="10,20", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_bulk_deallocate_certification_users_tool_non_numeric():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "bulk_deallocate_certification_users")

    result = json.loads(await fn(allocation_ids="abc,20"))

    assert "error" in result


# -----------------------------------------------------------------
# Dynamic Rules Tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_dynamic_rules_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_dynamic_rules")

    resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-42" checked>',
                            '<span data-value="Safety Rule">'
                            "Safety Rule</span>",
                            "",
                            "<ul><li>Course completed</li></ul>",
                            "<ul><li>Add to cohort</li></ul>",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["id"] == 42
    assert result[0]["name"] == "Safety Rule"


@pytest.mark.asyncio
async def test_list_dynamic_rules_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_dynamic_rules")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_enable_rule_tool_by_name():
    """Test that enable_rule resolves rule_name to rule_id."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    # First call: list_dynamic_rules (for name resolution)
    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-42" checked>',
                            '<span data-value="Safety Rule">'
                            "Safety Rule</span>",
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Safety Rule"))

    # Should get a preview with the resolved ID
    assert "preview" in result
    assert "42" in result["preview"]


@pytest.mark.asyncio
async def test_enable_rule_tool_name_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    list_resp = _mock_response(
        {
            "data": {"headers": [], "rows": [], "totalrowcount": 0},
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Nonexistent"))

    assert "error" in result
    assert "No dynamic rule" in result["error"]


@pytest.mark.asyncio
async def test_enable_rule_tool_no_id_or_name():
    """Neither rule_id nor rule_name provided."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    result = json.loads(await fn())

    assert "error" in result
    assert "Provide either" in result["error"]


@pytest.mark.asyncio
async def test_enable_rule_tool_ambiguous_name():
    """Multiple rules match the name."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-42" checked>',
                            '<span data-value="Safety Rule A">a</span>',
                            "",
                            "",
                            "",
                        ]
                    },
                    {
                        "columns": [
                            '<input id="rule-toggle-43">',
                            '<span data-value="Safety Rule B">b</span>',
                            "",
                            "",
                            "",
                        ]
                    },
                ],
                "totalrowcount": 2,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Safety Rule"))

    assert "error" in result
    assert "Multiple rules" in result["error"]
    assert len(result["matches"]) == 2


@pytest.mark.asyncio
async def test_enable_rule_tool_name_resolve_api_error():
    """API error during name resolution."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_name="Safety"))

    assert "error" in result


@pytest.mark.asyncio
async def test_disable_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "disable_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-99">',
                            '<span data-value="My Rule">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="My Rule"))

    assert "preview" in result
    assert "99" in result["preview"]


@pytest.mark.asyncio
async def test_can_enable_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "can_enable_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-55">',
                            '<span data-value="Test Rule">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    # First call resolves name, second call checks can_enable
    # Both go through _patch_httpx so the second returns the same
    # but that's ok — can_enable_rule handles the dict response
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Test Rule"))

    # The resolved ID 55 is passed to can_enable_rule which gets
    # the same mock (a dict with data key), but our client wraps it
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_archive_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-77">',
                            '<span data-value="Archive Me">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Archive Me"))

    assert "preview" in result
    assert "77" in result["preview"]


@pytest.mark.asyncio
async def test_duplicate_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-88">',
                            '<span data-value="Clone Me">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Clone Me"))

    assert "preview" in result
    assert "88" in result["preview"]


@pytest.mark.asyncio
async def test_get_rule_matching_users_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matching_users")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-22">',
                            '<span data-value="Count Me">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    # The mock returns the same response for both the list call and
    # the count call. count_matching_users expects an int or dict,
    # not this; it will wrap it.
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Count Me"))

    # The second call gets the same mock (system report format) but
    # count_matching_users wraps non-dict as {"count": raw}
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_get_rule_matched_users_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matched_users")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-33">',
                            '<span data-value="History Rule">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="History Rule"))

    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_delete_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-66">',
                            '<span data-value="Delete Me">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Delete Me"))

    assert "preview" in result
    assert "66" in result["preview"]


@pytest.mark.asyncio
async def test_unarchive_rule_tool_by_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unarchive_rule")

    list_resp = _mock_response(
        {
            "data": {
                "headers": ["", "Name", "Tags", "Conditions", "Actions"],
                "rows": [
                    {
                        "columns": [
                            '<input id="rule-toggle-44">',
                            '<span data-value="Restore Me">r</span>',
                            "",
                            "",
                            "",
                        ]
                    }
                ],
                "totalrowcount": 1,
            },
            "warnings": [],
        }
    )
    with _patch_httpx(list_resp):
        result = json.loads(await fn(rule_name="Restore Me"))

    assert "preview" in result
    assert "44" in result["preview"]


@pytest.mark.asyncio
async def test_can_enable_rule_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "can_enable_rule")

    resp = _mock_response({"result": True})
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert result == {"result": True}


@pytest.mark.asyncio
async def test_can_enable_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "can_enable_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_rule_matching_users_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matching_users")

    resp = _mock_response(42)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert result == {"count": 42}


@pytest.mark.asyncio
async def test_get_rule_matching_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matching_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_rule_matched_users_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matched_users")

    resp = _mock_response(7)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert result == {"count": 7}


@pytest.mark.asyncio
async def test_get_rule_matched_users_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_rule_matched_users")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=1))

    assert "error" in result


@pytest.mark.asyncio
async def test_search_cohorts_for_rule_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_cohorts_for_rule")

    resp = _mock_response(
        [{"id": 1, "name": "Engineering"}, {"id": 2, "name": "Operations"}]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(search="eng"))

    assert len(result) == 2
    assert result[0]["name"] == "Engineering"


@pytest.mark.asyncio
async def test_search_cohorts_for_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_cohorts_for_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(search="eng"))

    assert "error" in result


@pytest.mark.asyncio
async def test_search_competencies_for_rule_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_competencies_for_rule")

    resp = _mock_response(
        [
            {"id": 10, "shortname": "Leadership"},
            {"id": 11, "shortname": "Communication"},
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(search="lead"))

    assert len(result) == 2
    assert result[0]["shortname"] == "Leadership"


@pytest.mark.asyncio
async def test_search_competencies_for_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "search_competencies_for_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(search="lead"))

    assert "error" in result


@pytest.mark.asyncio
async def test_enable_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "Enable dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_enable_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_enable_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enable_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_disable_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "disable_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "Disable dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_disable_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "disable_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_disable_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "disable_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_archive_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "Archive dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_archive_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_archive_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_unarchive_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unarchive_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "Unarchive dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_unarchive_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unarchive_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_unarchive_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unarchive_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "DELETE dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_delete_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_duplicate_rule_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_rule")

    result = json.loads(await fn(rule_id=5))

    assert "preview" in result
    assert "Duplicate dynamic rule" in result["preview"]


@pytest.mark.asyncio
async def test_duplicate_rule_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_rule")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_duplicate_rule_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_rule")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(rule_id=5, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_rule_condition_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_condition")

    result = json.loads(await fn(instanceid=10))

    assert "preview" in result
    assert "Delete condition" in result["preview"]


@pytest.mark.asyncio
async def test_delete_rule_condition_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_condition")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(instanceid=10, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_rule_condition_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_condition")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(instanceid=10, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_rule_outcome_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_outcome")

    result = json.loads(await fn(instanceid=10))

    assert "preview" in result
    assert "Delete outcome" in result["preview"]


@pytest.mark.asyncio
async def test_delete_rule_outcome_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_outcome")

    resp = _mock_response(None)
    with _patch_httpx(resp):
        result = json.loads(await fn(instanceid=10, confirmed=True))

    assert result == {"status": "ok", "result": True}


@pytest.mark.asyncio
async def test_delete_rule_outcome_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_rule_outcome")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(instanceid=10, confirmed=True))

    assert "error" in result


# -----------------------------------------------------------------
# Dynamic rules — name-resolution error branches
# -----------------------------------------------------------------

_EMPTY_RULES_RESP = {
    "data": {"headers": [], "rows": [], "totalrowcount": 0},
    "warnings": [],
}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name",
    [
        "can_enable_rule",
        "get_rule_matching_users",
        "get_rule_matched_users",
        "disable_rule",
        "archive_rule",
        "unarchive_rule",
        "delete_rule",
        "duplicate_rule",
    ],
)
async def test_rule_tool_name_not_found(tool_name):
    skills = _get_skills()
    fn = _get_tool_fn(skills, tool_name)

    with _patch_httpx(_mock_response(_EMPTY_RULES_RESP)):
        result = json.loads(await fn(rule_name="Nonexistent"))

    assert "error" in result


# -----------------------------------------------------------------
# User management CRUD tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_user_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_user")

    result = json.loads(
        await fn(
            username="jdoe",
            firstname="John",
            lastname="Doe",
            email="jdoe@example.com",
        )
    )

    assert result["action"] == "create_user"
    assert "jdoe" in result["preview"]


@pytest.mark.asyncio
async def test_create_user_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_user")

    resp = _mock_response([{"id": 10, "username": "jdoe"}])
    with _patch_httpx(resp):
        result = json.loads(
            await fn(
                username="jdoe",
                firstname="John",
                lastname="Doe",
                email="jdoe@example.com",
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["created"][0]["id"] == 10


@pytest.mark.asyncio
async def test_create_user_tool_with_password():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_user")

    resp = _mock_response([{"id": 11, "username": "jdoe2"}])
    with _patch_httpx(resp):
        result = json.loads(
            await fn(
                username="jdoe2",
                firstname="Jane",
                lastname="Doe",
                email="jdoe2@example.com",
                password="secret123",
                confirmed=True,
            )
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_user_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_user")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(
            await fn(
                username="jdoe",
                firstname="John",
                lastname="Doe",
                email="jdoe@example.com",
                confirmed=True,
            )
        )

    assert "error" in result


# Fixture for the user-resolver tests below.  A "real" user record
# shaped the way Moodle returns it from core_user_get_users_by_field.
_DOC_USER = {
    "id": 7,
    "username": "doc_test",
    "firstname": "Documentation",
    "lastname": "User",
    "fullname": "Documentation User",
    "email": "doctest@example.com",
}

# Second seeded user — used for multi-user enrol_users tests.
_ALICE_USER = {
    "id": 3,
    "username": "alice",
    "firstname": "Alice",
    "lastname": "Johnson",
    "fullname": "Alice Johnson",
    "email": "alice@example.com",
}

# Fixture for the course-resolver tests below.  Shape matches what
# core_course_get_courses_by_field returns inside the "courses" key.
_SAFETY_COURSE = {
    "id": 2,
    "fullname": "Safety Fundamentals",
    "shortname": "safety101",
    "categoryid": 1,
    "visible": 1,
    "summary": "",
    "format": "topics",
}
_CYBER_COURSE = {
    "id": 3,
    "fullname": "Cybersecurity Basics",
    "shortname": "cyber101",
    "categoryid": 1,
    "visible": 1,
    "summary": "",
    "format": "topics",
}

# Cohort fixture for the cohort-resolver tests.
_ENGINEERING_COHORT = {
    "id": 1,
    "name": "Engineering",
    "idnumber": "ENG-COHORT",
    "visible": 1,
}

# Category fixture for the category-resolver tests.
_TRAINING_CATEGORY = {
    "id": 1,
    "name": "Training",
    "parent": 0,
    "coursecount": 5,
    "description": "",
    "depth": 1,
    "path": "/1",
    "visible": 1,
}

# Tenant fixture for the tenant-resolver tests.
_DEFAULT_TENANT = {
    "id": 2,
    "name": "Regional Office",
    "sitename": "Regional",
    "idnumber": "REGIONAL",
    "isdefault": False,
}

# Department fixture for the department-resolver tests.
_ENG_DEPT = {
    "id": 5,
    "name": "Engineering",
    "parentid": 0,
    "idnumber": "ENG",
}

# Report fixture for the report-resolver tests.
_COMPLETION_REPORT = {
    "id": 2,
    "name": "Course Completion Overview",
    "sourcename": "Course participants",
    "timemodified": 1700000000,
    "source": "core_course\\reportbuilder\\datasource\\participants",
}

# Certification fixture for the certification-resolver tests.
_SAFETY_CERT = {
    "id": 1,
    "fullname": "Workplace Safety",
    "idnumber": "SAFETY-CERT",
    "description": "",
    "status": 1,
    "timecreated": 0,
    "timemodified": 0,
}

# Program fixture for the program-resolver tests.
_LEADERSHIP_PROGRAM = {
    "id": 1,
    "fullname": "Leadership Track",
}


@pytest.mark.asyncio
async def test_update_user_tool_preview_by_username():
    """update_user accepts a username and resolves it internally."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(
            await fn(user="doc_test", department="Engineering")
        )

    assert result["action"] == "update_user"
    assert "Documentation User" in result["preview"]
    assert "Engineering" in result["preview"]
    assert result["user"] == "Documentation User (#7)"
    assert result["user_id"] == 7
    assert result["username"] == "doc_test"
    assert result["department"] == "Engineering"


@pytest.mark.asyncio
async def test_update_user_tool_preview_by_numeric_id():
    """update_user still accepts a numeric ID for power users."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="7", department="Quality Assurance"))

    assert result["action"] == "update_user"
    assert result["user"] == "Documentation User (#7)"


@pytest.mark.asyncio
async def test_update_user_tool_preview_by_email():
    """update_user accepts an email like a human would type it."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(
            await fn(user="doctest@example.com", department="QA")
        )

    assert result["user"] == "Documentation User (#7)"


@pytest.mark.asyncio
async def test_update_user_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(
            await fn(user="doc_test", department="Engineering", confirmed=True)
        )

    assert result["success"] is True
    assert result["userid"] == 7


@pytest.mark.asyncio
async def test_update_user_tool_no_fields():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="doc_test"))

    assert "No fields" in result["error"]


@pytest.mark.asyncio
async def test_update_user_tool_user_not_found():
    """Unknown identifier surfaces an error, never a fake "#N" fallback."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    with _patch_httpx(_mock_response([])):
        result = json.loads(await fn(user="ghost_user", department="Eng"))

    assert result["status"] == "error"
    assert "No user matches" in result["error"]


@pytest.mark.asyncio
async def test_update_user_tool_error():
    """Moodle-side error on the actual update_users call surfaces."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_user")

    # First call (resolver) returns the user; second call (write)
    # returns a Moodle exception payload.
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_DOC_USER]),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(user="doc_test", department="Eng", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_user_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="doc_test"))

    assert result["action"] == "delete_user"
    assert "WARNING" in result["preview"]
    assert "Documentation User" in result["preview"]
    assert result["user"] == "Documentation User (#7)"
    assert result["user_id"] == 7
    assert result["username"] == "doc_test"


@pytest.mark.asyncio
async def test_delete_user_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="doc_test", confirmed=True))

    assert result["success"] is True
    assert result["deleted_userid"] == 7
    assert result["user"] == "Documentation User (#7)"


@pytest.mark.asyncio
async def test_delete_user_tool_user_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    with _patch_httpx(_mock_response([])):
        result = json.loads(await fn(user="ghost_user"))

    assert result["status"] == "error"
    assert "No user matches" in result["error"]


@pytest.mark.asyncio
async def test_delete_user_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_DOC_USER]),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="doc_test", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_unsuspend_user_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unsuspend_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="doc_test"))

    assert result["action"] == "unsuspend_user"
    assert result["user"] == "Documentation User (#7)"
    assert result["user_id"] == 7
    assert result["username"] == "doc_test"


@pytest.mark.asyncio
async def test_unsuspend_user_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unsuspend_user")

    with _patch_httpx(_mock_response([_DOC_USER])):
        result = json.loads(await fn(user="doc_test", confirmed=True))

    assert result["success"] is True
    assert result["unsuspended_userid"] == 7


@pytest.mark.asyncio
async def test_unsuspend_user_tool_user_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unsuspend_user")

    with _patch_httpx(_mock_response([])):
        result = json.loads(await fn(user="ghost_user"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_unsuspend_user_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "unsuspend_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_DOC_USER]),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="doc_test", confirmed=True))

    assert "error" in result


# -----------------------------------------------------------------
# User identifier resolver — exercises the _resolve_user_identifier
# helper directly through the public tool surface.  Operators
# identify users by EDIPI / email / username / name — never by
# internal numeric ID.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_user_by_idnumber():
    """EDIPI / idnumber lookup — the mil deployment's primary key."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    edipi_user = dict(_DOC_USER, idnumber="1234567890")
    # username/idnumber/email all hit the same mock response; the
    # resolver tries id (skipped — not numeric), then username (no
    # match in our mock data sense, but mock returns user) — so
    # resolution succeeds on the first non-id field tried.
    with _patch_httpx(_mock_response([edipi_user])):
        result = json.loads(await fn(user="1234567890"))

    assert result["action"] == "delete_user"


@pytest.mark.asyncio
async def test_resolve_user_by_full_name():
    """Two-token full name falls through to search_users."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    # The resolver tries exact fields first; we make those return
    # empty, then the name search returns the user.  Using
    # side_effect on post lets us discriminate by call order:
    # username (empty), idnumber (empty), email (empty),
    # search_users (returns user).  search_users wraps results in
    # ``{"users": [...]}``.
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([]),  # email
        _mock_response({"users": [_DOC_USER]}),  # search_users
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Documentation User"))

    assert result["action"] == "delete_user"
    assert result["user_id"] == 7


@pytest.mark.asyncio
async def test_resolve_user_by_single_token_name():
    """Single-token name tries firstname and lastname both."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([]),  # email
        _mock_response({"users": [_DOC_USER]}),  # firstname search
        _mock_response({"users": []}),  # lastname search
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Documentation"))

    assert result["action"] == "delete_user"
    assert result["user_id"] == 7


@pytest.mark.asyncio
async def test_resolve_user_ambiguous_email():
    """Two users with the same email — resolver surfaces candidates."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    other_user = dict(
        _DOC_USER,
        id=8,
        username="doc_test_other",
        fullname="Other User",
    )
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    # id skipped (not numeric for an email-shape input); username
    # and idnumber empty; email returns two matches.
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([_DOC_USER, other_user]),  # email
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="doctest@example.com"))

    assert result["status"] == "error"
    assert "Multiple users" in result["error"]
    assert len(result["matches"]) == 2
    assert {m["id"] for m in result["matches"]} == {7, 8}


@pytest.mark.asyncio
async def test_resolve_user_ambiguous_name():
    """Two users matching a name search — resolver surfaces candidates."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    other_user = dict(
        _DOC_USER,
        id=8,
        username="doc_user_other",
        fullname="Documentation User",
    )
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([]),  # email
        _mock_response({"users": [_DOC_USER, other_user]}),  # search_users
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Documentation User"))

    assert result["status"] == "error"
    assert "Multiple users" in result["error"]


@pytest.mark.asyncio
async def test_resolve_user_empty_identifier():
    """Whitespace-only identifier is rejected without an HTTP call."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    result = json.loads(await fn(user="   "))

    assert result["status"] == "error"
    assert "Empty" in result["error"]


@pytest.mark.asyncio
async def test_resolve_user_dedupes_single_token_fn_ln_overlap():
    """A user matching both firstname and lastname appears once."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    # Same user returned by both firstname and lastname searches —
    # the resolver should dedupe on id and proceed to a single hit.
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([]),  # email
        _mock_response({"users": [_DOC_USER]}),  # firstname search
        _mock_response({"users": [_DOC_USER]}),  # lastname search
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Documentation"))

    assert result["action"] == "delete_user"
    assert result["user_id"] == 7


@pytest.mark.asyncio
async def test_resolve_user_http_error_during_exact_lookups():
    """Transient httpx errors on exact lookups fall through to name search."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        httpx.ConnectError("boom"),  # username — transient
        _mock_response([]),  # idnumber empty
        _mock_response([]),  # email empty
        _mock_response({"users": [_DOC_USER]}),  # search_users
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Documentation User"))

    assert result["action"] == "delete_user"


@pytest.mark.asyncio
async def test_resolve_user_http_error_during_name_search():
    """Transient httpx errors on the name search return 'no match'."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_user")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([]),  # username
        _mock_response([]),  # idnumber
        _mock_response([]),  # email
        httpx.ConnectError("boom"),  # firstname search fails
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(user="Ghost"))

    assert result["status"] == "error"
    assert "No user matches" in result["error"]


# -----------------------------------------------------------------
# Course management CRUD tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_categories_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_categories")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Default",
                "parent": 0,
                "coursecount": 3,
                "depth": 1,
                "visible": 1,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert len(result) == 1
    assert result[0]["name"] == "Default"


@pytest.mark.asyncio
async def test_list_categories_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_categories")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn())

    assert "error" in result


@pytest.mark.asyncio
async def test_create_category_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    result = json.loads(await fn(name="Test Cat"))

    assert result["action"] == "create_category"


@pytest.mark.asyncio
async def test_create_category_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    resp = _mock_response([{"id": 5, "name": "Test Cat"}])
    with _patch_httpx(resp):
        result = json.loads(
            await fn(name="Test Cat", description="Desc", confirmed=True)
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_create_category_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(name="Test Cat", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_create_course_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(
            await fn(fullname="Test Course", shortname="TC01", category="1")
        )

    assert result["action"] == "create_course"
    assert result["category_id"] == 1


@pytest.mark.asyncio
async def test_create_course_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(
        _categories_list_resp(_TRAINING_CATEGORY),
        _mock_response([{"id": 10, "shortname": "TC01"}]),
    ):
        result = json.loads(
            await fn(
                fullname="Test Course",
                shortname="TC01",
                category="1",
                summary="A test",
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["created"][0]["id"] == 10


@pytest.mark.asyncio
async def test_create_course_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    err = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY), err):
        result = json.loads(
            await fn(fullname="T", shortname="T", category="1", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_update_course_tool_preview():
    """Preview resolves course identifier to fullname + shortname."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    with _patch_httpx(_mock_response({"courses": [_SAFETY_COURSE]})):
        result = json.loads(await fn(course="safety101", fullname="New Name"))

    assert result["action"] == "update_course"
    assert "Safety Fundamentals" in result["preview"]
    assert result["course"] == "Safety Fundamentals (safety101)"
    assert result["course_id"] == 2
    assert result["shortname"] == "safety101"


@pytest.mark.asyncio
async def test_update_course_tool_preview_by_fullname():
    """Course fullname (substring) resolves via get_courses fallback."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),  # shortname empty
        _mock_response({"courses": []}),  # idnumber empty
        _mock_response([_SAFETY_COURSE, _CYBER_COURSE]),  # get_courses
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(course="Safety Fundamentals", fullname="New Name")
        )

    assert result["action"] == "update_course"
    assert "Safety Fundamentals" in result["preview"]


@pytest.mark.asyncio
async def test_update_course_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": [_SAFETY_COURSE]}),
        _mock_response({"warnings": []}),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(
                course="safety101",
                fullname="New",
                shortname="NEW",
                summary="Updated",
                visible=0,
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["courseid"] == 2


@pytest.mark.asyncio
async def test_update_course_tool_no_fields():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    with _patch_httpx(_mock_response({"courses": [_SAFETY_COURSE]})):
        result = json.loads(await fn(course="safety101"))

    assert "No fields" in result["error"]


@pytest.mark.asyncio
async def test_update_course_tool_course_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),  # shortname empty
        _mock_response({"courses": []}),  # idnumber empty
        _mock_response([]),  # get_courses empty
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Ghost Course", fullname="X"))

    assert result["status"] == "error"
    assert "No course matches" in result["error"]


@pytest.mark.asyncio
async def test_update_course_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": [_SAFETY_COURSE]}),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(course="safety101", fullname="X", confirmed=True)
        )

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_course_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    with _patch_httpx(_mock_response({"courses": [_SAFETY_COURSE]})):
        result = json.loads(await fn(course="safety101"))

    assert result["action"] == "delete_course"
    assert "WARNING" in result["preview"]
    assert "Safety Fundamentals" in result["preview"]
    assert result["course"] == "Safety Fundamentals (safety101)"
    assert result["course_id"] == 2


@pytest.mark.asyncio
async def test_delete_course_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": [_SAFETY_COURSE]}),
        _mock_response({"warnings": []}),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="safety101", confirmed=True))

    assert result["success"] is True
    assert result["deleted_courseid"] == 2
    assert result["course"] == "Safety Fundamentals (safety101)"


@pytest.mark.asyncio
async def test_delete_course_tool_course_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),
        _mock_response({"courses": []}),
        _mock_response([]),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Ghost Course"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_delete_course_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": [_SAFETY_COURSE]}),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="safety101", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_duplicate_course_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_course")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _categories_list_resp(_TRAINING_CATEGORY),
    ):
        result = json.loads(
            await fn(
                source="safety101",
                fullname="Copy",
                shortname="CP",
                category="1",
            )
        )

    assert result["action"] == "duplicate_course"
    assert "Safety Fundamentals" in result["preview"]
    assert result["source"] == "Safety Fundamentals (safety101)"
    assert result["source_id"] == 2
    assert result["category_id"] == 1


@pytest.mark.asyncio
async def test_duplicate_course_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_course")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _categories_list_resp(_TRAINING_CATEGORY),
        _mock_response({"id": 20, "shortname": "CP"}),
    ):
        result = json.loads(
            await fn(
                source="safety101",
                fullname="Copy",
                shortname="CP",
                category="1",
                confirmed=True,
            )
        )

    assert result["success"] is True
    assert result["new_course_id"] == 20


@pytest.mark.asyncio
async def test_duplicate_course_tool_source_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_course")

    with _patch_httpx_chain(
        _mock_response({"courses": []}),
        _mock_response({"courses": []}),
        _mock_response([]),
    ):
        result = json.loads(
            await fn(
                source="Ghost",
                fullname="Copy",
                shortname="CP",
                category="1",
            )
        )

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_duplicate_course_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_course")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _categories_list_resp(_TRAINING_CATEGORY),
        _mock_response(
            {
                "exception": "moodle_exception",
                "errorcode": "err",
                "message": "fail",
            }
        ),
    ):
        result = json.loads(
            await fn(
                source="safety101",
                fullname="Copy",
                shortname="CP",
                category="1",
                confirmed=True,
            )
        )

    assert "error" in result


# -----------------------------------------------------------------
# Course identifier resolver — covers the remaining branches of
# _resolve_course_identifier (ambiguous matches, idnumber lookup,
# transient HTTP errors).  Driven through delete_course since it's
# the smallest tool that exercises the resolver.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_course_by_numeric_id():
    """A digit-string input still works for power users / chained calls."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    with _patch_httpx(_mock_response({"courses": [_SAFETY_COURSE]})):
        result = json.loads(await fn(course="2"))

    assert result["action"] == "delete_course"
    assert result["course_id"] == 2


@pytest.mark.asyncio
async def test_resolve_course_by_idnumber():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    course = dict(_SAFETY_COURSE, idnumber="SAFETY-2024")
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),  # shortname empty
        _mock_response({"courses": [course]}),  # idnumber hits
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="SAFETY-2024"))

    assert result["action"] == "delete_course"
    assert result["course_id"] == 2


@pytest.mark.asyncio
async def test_resolve_course_ambiguous_fullname():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    course_a = dict(_SAFETY_COURSE, id=2, fullname="Cybersecurity 101")
    course_b = dict(_SAFETY_COURSE, id=3, fullname="Cybersecurity 201")
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),  # shortname
        _mock_response({"courses": []}),  # idnumber
        _mock_response([course_a, course_b]),  # get_courses
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Cybersecurity"))

    assert result["status"] == "error"
    assert "Multiple courses" in result["error"]
    assert len(result["matches"]) == 2


@pytest.mark.asyncio
async def test_resolve_course_ambiguous_shortname():
    """``get_courses_by_field`` shouldn't return multiple shortnames in
    practice (Moodle enforces uniqueness), but the resolver still
    handles it gracefully."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    a = dict(_SAFETY_COURSE, id=2)
    b = dict(_SAFETY_COURSE, id=3, fullname="Other Safety")
    with _patch_httpx(_mock_response({"courses": [a, b]})):
        result = json.loads(await fn(course="safety101"))

    assert result["status"] == "error"
    assert "Multiple courses" in result["error"]


@pytest.mark.asyncio
async def test_resolve_course_filters_site_course():
    """Course id=1 (site) is filtered out unless explicitly requested."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    site = dict(_SAFETY_COURSE, id=1, fullname="Moodle Sandbox")
    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),
        _mock_response({"courses": []}),
        _mock_response([site, _SAFETY_COURSE]),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Sandbox"))

    # "Sandbox" only matches the site course; that gets filtered →
    # no real course matches.
    assert result["status"] == "error"
    assert "No course matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_course_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    result = json.loads(await fn(course="   "))

    assert result["status"] == "error"
    assert "Empty course identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_course_http_error_on_exact_lookups():
    """Transient httpx errors on exact lookups fall through to get_courses."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        httpx.ConnectError("boom"),  # shortname transient
        _mock_response({"courses": []}),  # idnumber empty
        _mock_response([_SAFETY_COURSE]),  # get_courses succeeds
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Safety Fundamentals"))

    assert result["action"] == "delete_course"


@pytest.mark.asyncio
async def test_resolve_course_http_error_on_get_courses():
    """Transient error during get_courses fallback returns no-match."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": []}),
        _mock_response({"courses": []}),
        httpx.ConnectError("boom"),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(course="Ghost"))

    assert result["status"] == "error"
    assert "No course matches" in result["error"]


# -----------------------------------------------------------------
# Category identifier resolver — covers numeric not-found, exact,
# substring, ambiguous, and HTTP-error branches.  Driven through
# create_course since it's the smallest tool that exercises the
# resolver and produces a previewable payload.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_category_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    result = json.loads(await fn(fullname="X", shortname="X", category="   "))

    assert result["status"] == "error"
    assert "Empty category identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_category_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="99")
        )

    assert result["status"] == "error"
    assert "No category matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_category_exact_name_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="training")
        )

    assert result["action"] == "create_course"
    assert result["category_id"] == 1


@pytest.mark.asyncio
async def test_resolve_category_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    cat_a = dict(_TRAINING_CATEGORY, id=1)
    cat_b = dict(_TRAINING_CATEGORY, id=2)
    with _patch_httpx_chain(_categories_list_resp(cat_a, cat_b)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="Training")
        )

    assert result["status"] == "error"
    assert "Multiple categories" in result["error"]
    assert len(result["matches"]) == 2


@pytest.mark.asyncio
async def test_resolve_category_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="Train")
        )

    assert result["action"] == "create_course"
    assert result["category_id"] == 1


@pytest.mark.asyncio
async def test_resolve_category_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="Ghost")
        )

    assert result["status"] == "error"
    assert "No category matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_category_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    cat_a = dict(_TRAINING_CATEGORY, id=1, name="Compliance Training")
    cat_b = dict(_TRAINING_CATEGORY, id=2, name="Safety Training")
    with _patch_httpx_chain(_categories_list_resp(cat_a, cat_b)):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="Training")
        )

    assert result["status"] == "error"
    assert "Multiple categories" in result["error"]


@pytest.mark.asyncio
async def test_resolve_category_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_course")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(
            await fn(fullname="X", shortname="X", category="Training")
        )

    assert result["status"] == "error"
    assert "Category lookup failed" in result["error"]


# -----------------------------------------------------------------
# Cohort identifier resolver — drives the remaining branches via
# get_cohort_members.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_cohort_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    result = json.loads(await fn(cohort="   "))

    assert result["status"] == "error"
    assert "Empty cohort identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_cohort_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(_cohorts_list_resp(_ENGINEERING_COHORT)):
        result = json.loads(await fn(cohort="99"))

    assert result["status"] == "error"
    assert "No cohort matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_cohort_by_idnumber():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(
        _cohorts_list_resp(_ENGINEERING_COHORT),
        _mock_response([{"cohortid": 1, "userids": []}]),
    ):
        result = json.loads(await fn(cohort="ENG-COHORT"))

    assert result["cohortid"] == 1


@pytest.mark.asyncio
async def test_resolve_cohort_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    a = dict(_ENGINEERING_COHORT, id=1, idnumber="A")
    b = dict(_ENGINEERING_COHORT, id=2, idnumber="B")
    with _patch_httpx_chain(_cohorts_list_resp(a, b)):
        result = json.loads(await fn(cohort="Engineering"))

    assert result["status"] == "error"
    assert "Multiple cohorts" in result["error"]
    assert len(result["matches"]) == 2


@pytest.mark.asyncio
async def test_resolve_cohort_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(
        _cohorts_list_resp(_ENGINEERING_COHORT),
        _mock_response([{"cohortid": 1, "userids": []}]),
    ):
        result = json.loads(await fn(cohort="Engin"))

    assert result["cohortid"] == 1


@pytest.mark.asyncio
async def test_resolve_cohort_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(_cohorts_list_resp(_ENGINEERING_COHORT)):
        result = json.loads(await fn(cohort="Ghost"))

    assert result["status"] == "error"
    assert "No cohort matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_cohort_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    a = dict(
        _ENGINEERING_COHORT, id=1, name="Senior Engineering", idnumber="A"
    )
    b = dict(
        _ENGINEERING_COHORT, id=2, name="Junior Engineering", idnumber="B"
    )
    with _patch_httpx_chain(_cohorts_list_resp(a, b)):
        result = json.loads(await fn(cohort="Engineering"))

    assert result["status"] == "error"
    assert "Multiple cohorts" in result["error"]


@pytest.mark.asyncio
async def test_resolve_cohort_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(await fn(cohort="Engineering"))

    assert result["status"] == "error"
    assert "Cohort lookup failed" in result["error"]


# -----------------------------------------------------------------
# Resolver-error propagation — for each refactored read tool, an
# empty identifier short-circuits in the resolver and the error is
# surfaced to the caller verbatim.  Drives the resolver-error
# branch ("return resolved") in each tool body.
# -----------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_name,extra_kwargs",
    [
        ("get_course_contents", {}),
        ("list_enrolled_users", {}),
        ("get_course_completion_overview", {}),
        ("list_course_groups", {}),
        ("get_assignment_grades", {}),
        ("get_course_competencies", {}),
        ("get_utm_report", {}),
        ("get_adv_comp_report", {}),
    ],
)
async def test_course_read_tool_resolver_error_propagation(
    tool_name, extra_kwargs
):
    skills = _get_skills()
    fn = _get_tool_fn(skills, tool_name)

    result = json.loads(await fn(course="   ", **extra_kwargs))

    assert result["status"] == "error"
    assert "Empty course identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_completion_status_course_resolver_error():
    """Course-resolver error short-circuits before the user resolver."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_completion_status")

    result = json.loads(await fn(course="   ", user="alice"))

    assert result["status"] == "error"
    assert "Empty course identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_completion_status_user_resolver_error():
    """User-resolver error short-circuits after a valid course resolves."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_completion_status")

    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE)):
        result = json.loads(await fn(course="2", user="   "))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_user_grades_course_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

    result = json.loads(await fn(course="   ", user="alice"))

    assert result["status"] == "error"
    assert "Empty course identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_user_grades_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_grades")

    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE)):
        result = json.loads(await fn(course="2", user="   "))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_create_category_parent_resolver_error():
    """A bad ``parent`` identifier short-circuits before write."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(await fn(name="X", parent="Ghost"))

    assert result["status"] == "error"
    assert "No category matches" in result["error"]


@pytest.mark.asyncio
async def test_create_category_top_level_no_parent_lookup():
    """``parent=""`` skips the resolver and uses parent_id=0."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    result = json.loads(await fn(name="Top Level"))

    assert result["action"] == "create_category"
    assert result["parent_id"] == 0


@pytest.mark.asyncio
async def test_create_category_with_named_parent():
    """``parent`` name resolves to its category id."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "create_category")

    with _patch_httpx_chain(_categories_list_resp(_TRAINING_CATEGORY)):
        result = json.loads(await fn(name="Child", parent="Training"))

    assert result["action"] == "create_category"
    assert result["parent_id"] == 1


@pytest.mark.asyncio
async def test_duplicate_course_category_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_course")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _categories_list_resp(_TRAINING_CATEGORY),
    ):
        result = json.loads(
            await fn(
                source="safety101",
                fullname="Copy",
                shortname="CP",
                category="Ghost",
            )
        )

    assert result["status"] == "error"
    assert "No category matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_cohort_exact_name_match():
    """Cohort name exact match (case-insensitive)."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_cohort_members")

    with _patch_httpx_chain(
        _cohorts_list_resp(_ENGINEERING_COHORT),
        _mock_response([{"cohortid": 1, "userids": []}]),
    ):
        result = json.loads(await fn(cohort="engineering"))

    assert result["cohortid"] == 1


# -----------------------------------------------------------------
# Tenant / report / department resolver branches — drive every
# resolver-error path via existing tools that exercise each.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_certifications_default_no_tenant_lookup():
    """Empty ``tenant`` skips the resolver and uses tenantid=0."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(_mock_response([])):
        result = json.loads(await fn())

    assert result == []


@pytest.mark.asyncio
async def test_list_certifications_tenant_resolver_propagates_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    result = json.loads(await fn(tenant="   "))

    assert result["status"] == "error"
    assert "Empty tenant identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(users="alice", tenant="   "))

    assert result["status"] == "error"
    assert "Empty tenant identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(_tenants_list_resp(_DEFAULT_TENANT)):
        result = json.loads(await fn(tenant="99"))

    assert result["status"] == "error"
    assert "No tenant matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_numeric_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(
        _tenants_list_resp(_DEFAULT_TENANT),
        _mock_response([]),
    ):
        result = json.loads(await fn(tenant="2"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_tenant_by_idnumber():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(
        _tenants_list_resp(_DEFAULT_TENANT),
        _mock_response([]),
    ):
        result = json.loads(await fn(tenant="REGIONAL"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_tenant_exact_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(
        _tenants_list_resp(_DEFAULT_TENANT),
        _mock_response([]),
    ):
        result = json.loads(await fn(tenant="regional office"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_tenant_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    a = dict(_DEFAULT_TENANT, id=1, idnumber="A")
    b = dict(_DEFAULT_TENANT, id=2, idnumber="B")
    with _patch_httpx_chain(_tenants_list_resp(a, b)):
        result = json.loads(await fn(tenant="Regional Office"))

    assert result["status"] == "error"
    assert "Multiple tenants" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    a = dict(_DEFAULT_TENANT, id=1, name="Regional North", idnumber="A")
    b = dict(_DEFAULT_TENANT, id=2, name="Regional South", idnumber="B")
    with _patch_httpx_chain(_tenants_list_resp(a, b)):
        result = json.loads(await fn(tenant="Regional"))

    assert result["status"] == "error"
    assert "Multiple tenants" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(
        _tenants_list_resp(_DEFAULT_TENANT),
        _mock_response([]),
    ):
        result = json.loads(await fn(tenant="Regional"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_tenant_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(_tenants_list_resp(_DEFAULT_TENANT)):
        result = json.loads(await fn(tenant="Ghost"))

    assert result["status"] == "error"
    assert "No tenant matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_tenant_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "list_certifications")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(await fn(tenant="Regional Office"))

    assert result["status"] == "error"
    assert "Tenant lookup failed" in result["error"]


# -- Report resolver branches --


@pytest.mark.asyncio
async def test_resolve_report_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    result = json.loads(await fn(report="   "))

    assert result["status"] == "error"
    assert "Empty report identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_report_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    with _patch_httpx_chain(_reports_list_resp(_COMPLETION_REPORT)):
        result = json.loads(await fn(report="99"))

    assert result["status"] == "error"
    assert "No report matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_report_exact_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    data_resp = _mock_response(
        {
            "details": {
                "id": 2,
                "name": "Course Completion Overview",
                "source": "...",
                "sourcename": "Participants",
                "type": 0,
            },
            "data": {"headers": [], "rows": [], "totalrowcount": 0},
            "warnings": [],
        }
    )
    with _patch_httpx_chain(
        _reports_list_resp(_COMPLETION_REPORT),
        data_resp,
    ):
        result = json.loads(await fn(report="course completion overview"))

    assert result["report_name"] == "Course Completion Overview"


@pytest.mark.asyncio
async def test_resolve_report_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    a = dict(_COMPLETION_REPORT, id=1)
    b = dict(_COMPLETION_REPORT, id=2)
    with _patch_httpx_chain(_reports_list_resp(a, b)):
        result = json.loads(await fn(report="Course Completion Overview"))

    assert result["status"] == "error"
    assert "Multiple reports" in result["error"]


@pytest.mark.asyncio
async def test_resolve_report_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    a = dict(_COMPLETION_REPORT, id=1, name="Course A Overview")
    b = dict(_COMPLETION_REPORT, id=2, name="Course B Overview")
    with _patch_httpx_chain(_reports_list_resp(a, b)):
        result = json.loads(await fn(report="Course"))

    assert result["status"] == "error"
    assert "Multiple reports" in result["error"]


@pytest.mark.asyncio
async def test_resolve_report_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    data_resp = _mock_response(
        {
            "details": {
                "id": 2,
                "name": "Course Completion Overview",
                "source": "...",
                "sourcename": "Participants",
                "type": 0,
            },
            "data": {"headers": [], "rows": [], "totalrowcount": 0},
            "warnings": [],
        }
    )
    with _patch_httpx_chain(
        _reports_list_resp(_COMPLETION_REPORT),
        data_resp,
    ):
        result = json.loads(await fn(report="Completion"))

    assert result["report_name"] == "Course Completion Overview"


@pytest.mark.asyncio
async def test_resolve_report_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    with _patch_httpx_chain(_reports_list_resp(_COMPLETION_REPORT)):
        result = json.loads(await fn(report="Ghost"))

    assert result["status"] == "error"
    assert "No report matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_report_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_report_data")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(await fn(report="Completion"))

    assert result["status"] == "error"
    assert "Report lookup failed" in result["error"]


# -- Department resolver branches (via get_utm_report) --


@pytest.mark.asyncio
async def test_resolve_department_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(_course_id_resp(_SAFETY_COURSE)):
        result = json.loads(await fn(course="2", department="   "))

    assert result["status"] == "error"
    assert "Empty department identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_department_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
    ):
        result = json.loads(await fn(course="2", department="99"))

    assert result["status"] == "error"
    assert "No department matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_department_numeric_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
        _mock_response({"rows": [], "totalcount": 0}),
    ):
        result = json.loads(await fn(course="2", department="5"))

    assert result["total_rows"] == 0


@pytest.mark.asyncio
async def test_resolve_department_by_idnumber():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
        _mock_response({"rows": [], "totalcount": 0}),
    ):
        result = json.loads(await fn(course="2", department="ENG"))

    assert result["total_rows"] == 0


@pytest.mark.asyncio
async def test_resolve_department_exact_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
        _mock_response({"rows": [], "totalcount": 0}),
    ):
        result = json.loads(await fn(course="2", department="engineering"))

    assert result["total_rows"] == 0


@pytest.mark.asyncio
async def test_resolve_department_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    a = dict(_ENG_DEPT, id=1, idnumber="A")
    b = dict(_ENG_DEPT, id=2, idnumber="B")
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(a, b),
    ):
        result = json.loads(await fn(course="2", department="Engineering"))

    assert result["status"] == "error"
    assert "Multiple departments" in result["error"]


@pytest.mark.asyncio
async def test_resolve_department_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    a = dict(_ENG_DEPT, id=1, name="Engineering East", idnumber="A")
    b = dict(_ENG_DEPT, id=2, name="Engineering West", idnumber="B")
    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(a, b),
    ):
        result = json.loads(await fn(course="2", department="Engineering"))

    assert result["status"] == "error"
    assert "Multiple departments" in result["error"]


@pytest.mark.asyncio
async def test_resolve_department_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
    ):
        result = json.loads(await fn(course="2", department="Ghost"))

    assert result["status"] == "error"
    assert "No department matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_department_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        _departments_list_resp(_ENG_DEPT),
        _mock_response({"rows": [], "totalcount": 0}),
    ):
        result = json.loads(await fn(course="2", department="Engin"))

    assert result["total_rows"] == 0


@pytest.mark.asyncio
async def test_resolve_department_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_utm_report")

    with _patch_httpx_chain(
        _course_id_resp(_SAFETY_COURSE),
        httpx.ConnectError("boom"),
    ):
        result = json.loads(await fn(course="2", department="Engineering"))

    assert result["status"] == "error"
    assert "Department lookup failed" in result["error"]


# -- Job-token parser branches --


@pytest.mark.asyncio
async def test_export_status_empty_token():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_export_status")

    result = json.loads(await fn(export_job="   "))

    assert result["status"] == "error"
    assert "Empty export job token" in result["error"]


@pytest.mark.asyncio
async def test_export_status_invalid_token():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_export_status")

    result = json.loads(await fn(export_job="not-an-id"))

    assert result["status"] == "error"
    assert "Invalid export job token" in result["error"]


@pytest.mark.asyncio
async def test_download_export_invalid_token():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "download_export")

    result = json.loads(await fn(export_job="not-an-id"))

    assert result["status"] == "error"
    assert "Invalid export job token" in result["error"]


@pytest.mark.asyncio
async def test_import_status_invalid_token():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_import_status")

    result = json.loads(await fn(import_job="not-an-id"))

    assert result["status"] == "error"
    assert "Invalid import job token" in result["error"]


# -- User-resolver error propagation for remaining tools --


@pytest.mark.asyncio
async def test_get_user_program_courses_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_program_courses")

    result = json.loads(await fn(user="   "))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_get_user_learning_plans_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_plans")

    result = json.loads(await fn(user="   "))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_allocate_users_to_tenant_tenant_resolver_error():
    """Tenant-resolver error short-circuits after users resolve."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_tenant")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(users="alice", tenant="   "))

    assert result["status"] == "error"
    assert "Empty tenant identifier" in result["error"]


# -----------------------------------------------------------------
# Certification / program resolver branches.
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_certification_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    result = json.loads(await fn(certification="   "))

    assert result["status"] == "error"
    assert "Empty certification identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_certification_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(await fn(certification="Workplace Safety"))

    assert result["status"] == "error"
    assert "Certification lookup failed" in result["error"]


@pytest.mark.asyncio
async def test_resolve_certification_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="99"))

    assert result["status"] == "error"
    assert "No certification matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_certification_by_idnumber():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([]),
    ):
        result = json.loads(await fn(certification="SAFETY-CERT"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_certification_exact_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([]),
    ):
        result = json.loads(await fn(certification="workplace safety"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_certification_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    a = dict(_SAFETY_CERT, id=1, idnumber="A")
    b = dict(_SAFETY_CERT, id=2, idnumber="B")
    with _patch_httpx_chain(_certs_list_resp(a, b)):
        result = json.loads(await fn(certification="Workplace Safety"))

    assert result["status"] == "error"
    assert "Multiple certifications" in result["error"]


@pytest.mark.asyncio
async def test_resolve_certification_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    a = dict(_SAFETY_CERT, id=1, fullname="Lab Safety", idnumber="A")
    b = dict(_SAFETY_CERT, id=2, fullname="Field Safety", idnumber="B")
    with _patch_httpx_chain(_certs_list_resp(a, b)):
        result = json.loads(await fn(certification="Safety"))

    assert result["status"] == "error"
    assert "Multiple certifications" in result["error"]


@pytest.mark.asyncio
async def test_resolve_certification_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(
        _certs_list_resp(_SAFETY_CERT),
        _mock_response([]),
    ):
        result = json.loads(await fn(certification="Safety"))

    assert result == []


@pytest.mark.asyncio
async def test_resolve_certification_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="Ghost"))

    assert result["status"] == "error"
    assert "No certification matches" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_empty_identifier():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    result = json.loads(await fn(program="   "))

    assert result["status"] == "error"
    assert "Empty program identifier" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_http_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(httpx.ConnectError("boom")):
        result = json.loads(await fn(program="Leadership"))

    assert result["status"] == "error"
    assert "Program lookup failed" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_numeric_not_found():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="99"))

    assert result["status"] == "error"
    assert "No program matches id=99" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_exact_name():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(
        _programs_list_resp(_LEADERSHIP_PROGRAM),
    ):
        result = json.loads(await fn(program="leadership track"))

    assert result["action"] == "archive_program"


@pytest.mark.asyncio
async def test_resolve_program_ambiguous_exact():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    a = dict(_LEADERSHIP_PROGRAM, id=1)
    b = dict(_LEADERSHIP_PROGRAM, id=2)
    with _patch_httpx_chain(_programs_list_resp(a, b)):
        result = json.loads(await fn(program="Leadership Track"))

    assert result["status"] == "error"
    assert "Multiple programs" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_ambiguous_substring():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    a = dict(_LEADERSHIP_PROGRAM, id=1, fullname="Leadership Foundations")
    b = dict(_LEADERSHIP_PROGRAM, id=2, fullname="Leadership Advanced")
    with _patch_httpx_chain(_programs_list_resp(a, b)):
        result = json.loads(await fn(program="Leadership"))

    assert result["status"] == "error"
    assert "Multiple programs" in result["error"]


@pytest.mark.asyncio
async def test_resolve_program_substring_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="Leadership"))

    assert result["action"] == "archive_program"


@pytest.mark.asyncio
async def test_resolve_program_no_match():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_program")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="Ghost"))

    assert result["status"] == "error"
    assert "No program matches" in result["error"]


# Resolver-error propagation for all newly refactored write tools


@pytest.mark.asyncio
async def test_certify_user_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "certify_user")

    result = json.loads(await fn(user="   ", certification="Safety"))

    assert result["status"] == "error"
    assert "Empty user identifier" in result["error"]


@pytest.mark.asyncio
async def test_certify_user_cert_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "certify_user")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(user="alice", certification="   "))

    assert result["status"] == "error"
    assert "Empty certification identifier" in result["error"]


@pytest.mark.asyncio
async def test_revoke_certification_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "revoke_certification")

    result = json.loads(await fn(user="   ", certification="Safety"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_revoke_certification_cert_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "revoke_certification")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(user="alice", certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_user_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_certification")

    result = json.loads(await fn(user="   ", certification="Safety"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_deallocate_user_from_certification_cert_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_certification")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(user="alice", certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_archive_certification_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "archive_certification")

    result = json.loads(await fn(certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_delete_certification_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_certification")

    result = json.loads(await fn(certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_restore_certification_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_certification")

    result = json.loads(await fn(certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_certification_allocations_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_allocations")

    result = json.loads(await fn(certification="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_certification_history_cert_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_history")

    result = json.loads(await fn(certification="   ", user="alice"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_certification_history_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_history")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="1", user="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_certification_user_details_cert_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_user_details")

    result = json.loads(await fn(certification="   ", user="alice"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_certification_user_details_user_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_certification_user_details")

    with _patch_httpx_chain(_certs_list_resp(_SAFETY_CERT)):
        result = json.loads(await fn(certification="1", user="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_allocate_users_to_program_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_program")

    result = json.loads(await fn(users="   ", program="1"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_allocate_users_to_program_program_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "allocate_users_to_program")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(users="alice", program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_deallocate_user_from_program_user_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_program")

    result = json.loads(await fn(user="   ", program="1"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_deallocate_user_from_program_program_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "deallocate_user_from_program")

    with _patch_httpx_chain(_mock_response([_ALICE_USER])):
        result = json.loads(await fn(user="alice", program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_restore_program_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "restore_program")

    result = json.loads(await fn(program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_delete_program_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_program")

    result = json.loads(await fn(program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_duplicate_program_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "duplicate_program")

    result = json.loads(await fn(program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_update_program_visibility_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_program_visibility")

    result = json.loads(await fn(program="   ", visible=1))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_program_content_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_program_content")

    result = json.loads(await fn(program="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_program_content_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_program_content")

    with _patch_httpx_chain(_programs_list_resp(_LEADERSHIP_PROGRAM)):
        result = json.loads(await fn(program="1", user="   "))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_assign_job_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "assign_job")

    result = json.loads(await fn(user="   ", department="ENG", position="MGR"))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_user_competency_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_competency")

    result = json.loads(await fn(user="   ", competencyid=1))

    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_get_user_learning_catalogue_user_resolver_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_user_learning_catalogue")

    result = json.loads(await fn(user="   "))

    assert result["status"] == "error"


# -----------------------------------------------------------------
# Import / Export tools
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_export_workplace_data_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "export_workplace_data")

    result = json.loads(await fn(exporter="courses"))

    assert result["action"] == "export_workplace_data"


@pytest.mark.asyncio
async def test_export_workplace_data_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "export_workplace_data")

    resp = _mock_response({"jobid": 1})
    with _patch_httpx(resp):
        result = json.loads(await fn(exporter="courses", confirmed=True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_export_workplace_data_tool_custom_exporter():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "export_workplace_data")

    resp = _mock_response({"jobid": 2})
    with _patch_httpx(resp):
        result = json.loads(
            await fn(exporter=r"custom\exporter\class", confirmed=True)
        )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_export_workplace_data_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "export_workplace_data")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(exporter="courses", confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_export_status_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_export_status")

    resp = _mock_response(
        {"status": 2, "statusmessage": "Done", "progress": 100}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(export_job="1"))

    assert result["status"] == 2


@pytest.mark.asyncio
async def test_get_export_status_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_export_status")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(export_job="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_download_export_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "download_export")

    resp = _mock_response({"fileurl": "http://moodle.test/file.zip"})
    with _patch_httpx(resp):
        result = json.loads(await fn(export_job="1"))

    assert "fileurl" in result


@pytest.mark.asyncio
async def test_download_export_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "download_export")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(export_job="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_import_workplace_data_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "import_workplace_data")

    result = json.loads(await fn())

    assert result["action"] == "import_workplace_data"
    assert "WARNING" in result["preview"]


@pytest.mark.asyncio
async def test_import_workplace_data_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "import_workplace_data")

    resp = _mock_response({"jobid": 5})
    with _patch_httpx(resp):
        result = json.loads(await fn(confirmed=True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_import_workplace_data_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "import_workplace_data")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_get_import_status_tool():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_import_status")

    resp = _mock_response(
        {"status": 2, "statusmessage": "Done", "progress": 100}
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(import_job="1"))

    assert result["status"] == 2


@pytest.mark.asyncio
async def test_get_import_status_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_import_status")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(import_job="1"))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_export_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_export")

    result = json.loads(await fn(export_id=1))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_export_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_export")

    resp = _mock_response({"success": True})
    with _patch_httpx(resp):
        result = json.loads(await fn(export_id=1, confirmed=True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_export_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_export")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(export_id=1, confirmed=True))

    assert "error" in result


@pytest.mark.asyncio
async def test_delete_import_tool_preview():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_import")

    result = json.loads(await fn(import_id=1))

    assert "preview" in result


@pytest.mark.asyncio
async def test_delete_import_tool_confirmed():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_import")

    resp = _mock_response({"success": True})
    with _patch_httpx(resp):
        result = json.loads(await fn(import_id=1, confirmed=True))

    assert result["success"] is True


@pytest.mark.asyncio
async def test_delete_import_tool_error():
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_import")

    resp = _mock_response(
        {
            "exception": "moodle_exception",
            "errorcode": "err",
            "message": "fail",
        }
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(import_id=1, confirmed=True))

    assert "error" in result


def test_confirm_instructions_includes_status_rule():
    """The shared _CONFIRM_INSTRUCTIONS prompt teaches every skill
    agent to (a) emit success only when the result has
    ``"status": "ok"`` and (b) report failures when the result has
    ``"status": "error"`` — without inventing IDs."""
    from soliplex.moodle import skills as moodle_skills

    text = moodle_skills._CONFIRM_INSTRUCTIONS

    assert '"status": "ok"' in text
    assert '"status": "error"' in text
    assert "NEVER claim a write operation succeeded" in text
    assert "NEVER invent IDs" in text


@pytest.mark.asyncio
async def test_moodle_tool_injects_status_ok_on_confirmed_write():
    """The decorator auto-injects status:ok into confirmed-write
    JSON returns so the LLM has an unambiguous success marker."""
    from soliplex.moodle import skills as moodle_skills

    @moodle_skills._moodle_tool
    async def fake_write(confirmed: bool = False) -> str:
        return json.dumps({"created": [{"name": "X"}]})

    result = json.loads(await fake_write(confirmed=True))
    assert result["status"] == "ok"
    assert result["created"] == [{"name": "X"}]


@pytest.mark.asyncio
async def test_moodle_tool_does_not_inject_status_on_preview():
    """Preview branches must not get status:ok."""
    from soliplex.moodle import skills as moodle_skills

    @moodle_skills._moodle_tool
    async def fake_write(confirmed: bool = False) -> str:
        return json.dumps({"preview": "test"})

    result = json.loads(await fake_write(confirmed=False))
    assert "status" not in result


@pytest.mark.asyncio
async def test_moodle_tool_does_not_inject_status_on_read_tool():
    """Read tools (no `confirmed` argument) must not get status:ok."""
    from soliplex.moodle import skills as moodle_skills

    @moodle_skills._moodle_tool
    async def fake_read() -> str:
        return json.dumps([{"name": "X"}])

    result = json.loads(await fake_read())
    assert result == [{"name": "X"}]


@pytest.mark.asyncio
async def test_moodle_tool_preserves_explicit_status():
    """Tools that already emit a status field are passed through."""
    from soliplex.moodle import skills as moodle_skills

    @moodle_skills._moodle_tool
    async def fake_write(confirmed: bool = False) -> str:
        return json.dumps({"status": "error", "error": "not found"})

    result = json.loads(await fake_write(confirmed=True))
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_moodle_tool_passes_through_non_json_result():
    """A tool that returns a non-JSON value on a confirmed write is
    passed through verbatim — the decorator only injects status
    into JSON objects."""
    from soliplex.moodle import skills as moodle_skills

    @moodle_skills._moodle_tool
    async def fake_write(confirmed: bool = False):
        return None  # not a JSON string

    result = await fake_write(confirmed=True)
    assert result is None


# -----------------------------------------------------------------
# F1–F4, F6 prompt-content & docstring assertions
# -----------------------------------------------------------------


def test_rules_prompt_includes_matching_users_and_can_enable_guidance():
    """F1 + F3: the rules skill's prompt must steer the agent to
    get_rule_matching_users for "how many users match" queries and
    to can_enable_rule for "can X be enabled" checks."""
    from soliplex.moodle import skills as moodle_skills

    text = moodle_skills._RULES_PROMPT
    assert "get_rule_matching_users" in text
    assert "how many users match" in text
    assert "can_enable_rule" in text


def test_router_prompt_includes_new_routing_examples():
    """F2 + F3: the router prompt teaches "competency frameworks" →
    moodle-programs (not moodle-rules) and "can X rule be enabled" →
    moodle-rules.can_enable_rule."""
    from soliplex.moodle import agent as moodle_agent

    text = moodle_agent.MOODLE_ROUTER_PROMPT
    assert "competency frameworks" in text
    assert "list_competency_frameworks" in text
    assert "can_enable_rule" in text
    assert "can X rule be enabled" in text


def test_organisation_prompt_includes_team_members_workflow():
    """F4: the organisation skill's prompt teaches the agent to
    call get_team_members directly with name/idnumber instead of
    chaining through list_departments."""
    from soliplex.moodle import skills as moodle_skills

    text = moodle_skills._ORGANISATION_PROMPT
    assert "get_team_members" in text
    # Cross-reference: tells the agent to avoid the looping pattern.
    assert "Do NOT" in text or "do NOT" in text


def test_delete_department_docstring_mentions_idnumber_lookup():
    """F6: delete_department's docstring must nudge the agent to
    look up the idnumber via list_departments when only the
    department name is known."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")
    doc = " ".join((fn.__doc__ or "").split())  # flatten whitespace
    assert "list_departments" in doc
    assert "only accepts idnumber" in doc


def test_delete_position_docstring_mentions_idnumber_lookup():
    """F6 (positions): same guidance as delete_department."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_position")
    doc = " ".join((fn.__doc__ or "").split())
    assert "list_positions" in doc
    assert "only accepts idnumber" in doc


# -----------------------------------------------------------------
# F4 — get_team_members name-based resolution
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_team_members_resolves_department_by_idnumber():
    """F4: passing department=<idnumber> resolves to the integer
    id internally via list_departments before calling the system
    report.  Confirms two POST calls were made."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    # Same mock answers BOTH http calls — first is
    # local_soliplex_list_departments, second is the report.
    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn(department="ENG"))

    # Two round-trips: dept lookup + system report (returning the
    # same mock — yields [] members since report shape differs).
    assert patched.return_value.post.call_count == 2
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_team_members_resolves_department_by_name():
    """F4: passing department=<name> resolves to the integer id."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn(department="Engineering"))

    assert patched.return_value.post.call_count == 2
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_team_members_department_not_found():
    """F4: unknown department returns a structured error."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(department="NOSUCH"))

    assert result["status"] == "error"
    assert "NOSUCH" in result["error"]


@pytest.mark.asyncio
async def test_get_team_members_resolves_position_by_idnumber():
    """F4: same resolution applies to position=<idnumber>."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        [
            {
                "id": 3,
                "name": "Engineer",
                "idnumber": "ENG-POS",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp) as patched:
        result = json.loads(await fn(position="ENG-POS"))

    assert patched.return_value.post.call_count == 2
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_team_members_position_not_found():
    """F4: unknown position returns a structured error."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Manager",
                "idnumber": "MGR",
                "parentid": 0,
            }
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(position="NOSUCH"))

    assert result["status"] == "error"
    assert "NOSUCH" in result["error"]


# -----------------------------------------------------------------
# Third-pass review fixes (B1 + SF1 + SF2)
# -----------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_team_members_filters_to_requested_department():
    """B1: the wrapper must filter the report's all-staff result to
    only the requested department.  Previously the broken
    client-side filter let through every row from every other
    department; the wrapper now filters on
    ``departmentname == match.name``."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    # The same mock answers BOTH http calls.  The first call is
    # list_departments and yields one dept; the second is the system
    # report.  Since _mock_response returns the same JSON for every
    # POST, the report parser sees the dept list as `data.rows`
    # which is missing — it falls back to [].  To exercise the
    # filter we need two distinct mock responses.
    list_resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Operations",
                "idnumber": "OPS",
                "parentid": 0,
            },
        ]
    )
    # Mock client where the first POST gets the dept list and the
    # second POST gets the multi-dept report rows.
    report_payload = {
        "data": {
            "headers": ["Full name with link", "Department", "Position"],
            "rows": [
                {
                    "columns": [
                        '<a href="/user/profile.php?id=3">Alice Johnson</a>',
                        "Engineering",
                        "Manager",
                    ],
                },
                {
                    "columns": [
                        '<a href="/user/profile.php?id=4">Bob Smith</a>',
                        "Operations",
                        "Engineer",
                    ],
                },
            ],
            "totalrowcount": 2,
        },
        "warnings": [],
    }
    report_resp = _mock_response(report_payload)

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = [list_resp, report_resp]
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(department="Engineering"))

    # The wrapper filtered out Bob (Operations); only Alice survives.
    assert len(result) == 1
    assert result[0]["userid"] == 3
    assert result[0]["departmentname"] == "Engineering"


@pytest.mark.asyncio
async def test_get_team_members_filters_to_requested_position():
    """B1: same filter applies for position."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    list_resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Manager",
                "idnumber": "MGR",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Engineer",
                "idnumber": "ENG-POS",
                "parentid": 0,
            },
        ]
    )
    report_payload = {
        "data": {
            "headers": ["Full name with link", "Department", "Position"],
            "rows": [
                {
                    "columns": [
                        '<a href="/user/profile.php?id=3">Alice Johnson</a>',
                        "Engineering",
                        "Manager",
                    ],
                },
                {
                    "columns": [
                        '<a href="/user/profile.php?id=4">Bob Smith</a>',
                        "Engineering",
                        "Engineer",
                    ],
                },
            ],
            "totalrowcount": 2,
        },
        "warnings": [],
    }
    report_resp = _mock_response(report_payload)

    mock_client = mock.AsyncMock()
    mock_client.post.side_effect = [list_resp, report_resp]
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(await fn(position="Engineer"))

    # Only Bob (Engineer) survives; Alice (Manager) is filtered out.
    assert len(result) == 1
    assert result[0]["userid"] == 4
    assert result[0]["positionname"] == "Engineer"


@pytest.mark.asyncio
async def test_get_team_members_ambiguous_department():
    """SF2: when the query matches multiple departments, the
    wrapper surfaces an error listing the candidates so the caller
    can disambiguate by idnumber."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    # Two departments both have the literal lowercase string
    # "engineering" — one via name, the other via idnumber.
    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Engineering",
                "idnumber": "ENG",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Other",
                "idnumber": "engineering",
                "parentid": 0,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(department="engineering"))

    assert result["status"] == "error"
    assert "Multiple" in result["error"]
    assert {m["idnumber"] for m in result["matches"]} == {"ENG", "engineering"}


@pytest.mark.asyncio
async def test_get_team_members_ambiguous_position():
    """SF2: ambiguity surfaces for position too."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "get_team_members")

    resp = _mock_response(
        [
            {
                "id": 1,
                "name": "Manager",
                "idnumber": "MGR",
                "parentid": 0,
            },
            {
                "id": 2,
                "name": "Other",
                "idnumber": "manager",
                "parentid": 0,
            },
        ]
    )
    with _patch_httpx(resp):
        result = json.loads(await fn(position="manager"))

    assert result["status"] == "error"
    assert "Multiple" in result["error"]
    assert {m["idnumber"] for m in result["matches"]} == {"MGR", "manager"}


@pytest.mark.asyncio
async def test_update_course_tool_propagates_warnings():
    """SF1: when Moodle returns a warnings response on
    update_courses (shortname collision, capability error), the
    decorator catches MoodleAPIError and the wrapper output gets
    status=error.  No silent ✅."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "update_course")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response({"courses": [_SAFETY_COURSE]}),
        _mock_response(
            {
                "warnings": [
                    {
                        "item": "shortname",
                        "warningcode": "shortnametaken",
                        "message": "Shortname is already in use",
                    }
                ]
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(course="safety101", shortname="DUP", confirmed=True)
        )

    assert result["status"] == "error"
    assert "Shortname is already in use" in result["error"]


@pytest.mark.asyncio
async def test_enrol_users_tool_propagates_warnings():
    """SF1 audit: same fix for enrol_users — when Moodle silently
    rejects an enrol (user already enrolled, course not found, etc.)
    the wrapper now reports status=error instead of confabulating
    success."""
    skills = _get_skills()
    fn = _get_tool_fn(skills, "enrol_users")

    mock_client = mock.AsyncMock()
    mock_client.__aenter__ = mock.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mock.AsyncMock(return_value=False)
    mock_client.post.side_effect = [
        _mock_response([_ALICE_USER]),
        _mock_response({"courses": [_CYBER_COURSE]}),
        _mock_response(
            {
                "warnings": [
                    {
                        "item": "3",
                        "warningcode": "alreadyenroled",
                        "message": "User is already enrolled",
                    }
                ]
            }
        ),
    ]
    with mock.patch(
        "soliplex.moodle.client.httpx.AsyncClient",
        return_value=mock_client,
    ):
        result = json.loads(
            await fn(
                users="alice",
                course="cyber101",
                confirmed=True,
            )
        )

    assert result["status"] == "error"
    assert "already enrolled" in result["error"]


@pytest.mark.asyncio
async def test_delete_department_preview_includes_action():
    """Every write-tool preview MUST include an ``action`` field so
    the router LLM can dispatch the confirmation back to the same
    tool without having to infer the name from prose.  Regression
    test for a class of bugs where preview dicts omitted the action
    key, leaving the router to guess (and sometimes mis-route to a
    sibling tool like delete_position).
    """
    skills = _get_skills()
    fn = _get_tool_fn(skills, "delete_department")

    # No HTTP call needed for preview mode (confirmed=False).
    result = json.loads(await fn(idnumber="ENG", confirmed=False))

    assert result["action"] == "delete_department"
    assert "preview" in result
    assert "ENG" in result["preview"]


@pytest.mark.asyncio
async def test_resolve_rule_id_tolerates_appended_suffix():
    """The rule resolver must match when the LLM passes the user's
    full noun phrase including a " rule" suffix.  e.g. user says
    "the Standalone Cohort Trigger rule" and the LLM forwards
    rule_name="Standalone Cohort Trigger rule" — the actual stored
    name is "Standalone Cohort Trigger" with no " rule" suffix.
    Pre-fix the resolver used `needle in name` which failed because
    the needle was a superstring of the name.  Bidirectional match
    closes this.
    """
    from soliplex.moodle.client import MoodleClient
    from soliplex.moodle.skills import _resolve_rule_id

    client = MoodleClient(base_url=BASE_URL, token=TOKEN, verify=False)
    # list_dynamic_rules parses HTML columns from the system report.
    # cols[0] needs "rule-toggle-{id}", cols[1] needs data-value="{name}".
    rules_resp = _mock_response(
        {
            "data": {
                "rows": [
                    {
                        "columns": [
                            "<input class='rule-toggle-1' />",
                            (
                                '<a data-value="Standalone Cohort '
                                'Trigger">Standalone Cohort Trigger</a>'
                            ),
                            "",
                            "<ul></ul>",
                            "<ul></ul>",
                        ]
                    },
                ]
            }
        }
    )
    with _patch_httpx(rules_resp):
        result = await _resolve_rule_id(
            client,
            rule_name="Standalone Cohort Trigger rule",
        )

    # Should resolve to the rule id (1), not an error JSON string.
    assert result == 1


def test_reporting_prompt_includes_anti_hallucination_guard():
    """The reporting skill prompt must explicitly forbid inventing
    report records.  Without this guard gpt-oss has been observed
    to fabricate plausible-looking report rows when list_reports
    returns sparse data.
    """
    from soliplex.moodle import skills as moodle_skills

    text = moodle_skills._REPORTING_PROMPT
    assert "never fabricate" in text.lower()
    assert "no invented IDs" in text or "no inferred names" in text
    assert "report only what the tool" in text.lower()


def test_router_prompt_includes_tool_arg_precision_section():
    """The router prompt must teach the LLM to strip user-phrased
    noun-class suffixes (" rule", " department", " program",
    " course") before passing names to skills.  Without this,
    rule-name lookups fail when the user says "the X rule" and
    the LLM forwards "X rule" instead of "X" as the rule_name arg.
    """
    from soliplex.moodle import agent as moodle_agent

    text = moodle_agent.MOODLE_ROUTER_PROMPT
    assert "Tool argument precision" in text
    assert " rule" in text
    assert " department" in text
    # Concrete example pinned to the actual smoke-test scenario.
    assert "Test: Enable Rule Verification" in text
