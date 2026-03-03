"""Moodle Workplace factory agent with tool calling.

The factory creates a ``pydantic_ai.Agent`` with four tools
for querying Moodle data (courses, users, enrollment,
completion).  The LLM decides which tools to call.
"""

from __future__ import annotations

import json

import httpx
import pydantic_ai

from soliplex import agents
from soliplex import config
from soliplex.config import agents as config_agents
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient

MOODLE_TOOLS_PROMPT = """\
You are a training management assistant connected to \
Moodle Workplace.

You have four tools for querying Moodle data.  IMPORTANT: \
Always call the relevant tool BEFORE answering.  Never \
claim data is missing without checking first.

Workflow:

1. ALWAYS start with `list_courses` to discover available \
courses and their IDs.  If the user mentions a course by \
name, call `list_courses` first and match the closest \
result — do NOT say a course does not exist without \
checking.
2. Use `find_user` to look up a user by username or \
email and get their user ID.
3. Use `list_enrolled_users` with a course ID to see \
who is enrolled.
4. Use `get_completion_status` with a course ID and \
user ID to check completion.

Present data in clear tables when appropriate.
"""


def moodle_tools_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: agents.ToolConfigMap = None,
    mcp_client_toolset_configs: (config.MCP_ClientToolsetConfigMap) = None,
) -> pydantic_ai.Agent:
    """Create a Moodle Workplace agent with tool calling.

    Exposes Moodle API methods as Pydantic AI tools so
    the LLM decides which to call.
    """
    ic = agent_config._installation_config
    extra = agent_config.extra_config

    base_url = ic.get_secret(extra["moodle_base_url"])
    token = ic.get_secret(extra["moodle_api_token"])
    client = MoodleClient(base_url=base_url, token=token)

    model = config_agents.get_model_from_factory_config(agent_config)

    agent = pydantic_ai.Agent(
        model=model,
        instructions=MOODLE_TOOLS_PROMPT,
        deps_type=agents.AgentDependencies,
    )

    @agent.tool_plain
    async def list_courses() -> str:
        """List all courses in Moodle.

        Returns JSON with id, shortname, and fullname
        for each course.  Use the course id in other
        tools.
        """
        courses = await client.get_courses()
        return json.dumps(
            [
                {
                    "id": c.id,
                    "shortname": c.shortname,
                    "fullname": c.fullname,
                }
                for c in courses
                if c.id != 1  # exclude Moodle site course
            ]
        )

    @agent.tool_plain
    async def find_user(field: str, value: str) -> str:
        """Look up a Moodle user by field.

        Args:
            field: The field to search — typically
                   "username" or "email".
            value: The value to match.

        Returns JSON with id, username, fullname, and
        email for each matching user.
        """
        users = await client.get_users_by_field(field, [value])
        return json.dumps(
            [
                {
                    "id": u.id,
                    "username": u.username,
                    "fullname": u.fullname,
                    "email": u.email,
                }
                for u in users
            ]
        )

    @agent.tool_plain
    async def list_enrolled_users(courseid: int) -> str:
        """List users enrolled in a course.

        Args:
            courseid: The Moodle course ID (from
                      list_courses).

        Returns JSON with id, username, fullname, and
        roles for each enrolled user.
        """
        enrolled = await client.get_enrolled_users(courseid)
        return json.dumps(
            [
                {
                    "id": u.id,
                    "username": u.username,
                    "fullname": u.fullname,
                    "roles": [r.shortname for r in u.roles],
                }
                for u in enrolled
            ]
        )

    @agent.tool_plain
    async def get_completion_status(
        courseid: int,
        userid: int,
    ) -> str:
        """Check a user's course completion status.

        Args:
            courseid: The Moodle course ID.
            userid: The Moodle user ID (from find_user
                    or list_enrolled_users).

        Returns JSON with completed flag and completion
        criteria details.
        """
        try:
            status = await client.get_course_completion_status(
                courseid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "completed": status.completed,
                "completions": [
                    {
                        "type": cr.type,
                        "title": cr.title,
                        "status": cr.status,
                        "complete": cr.complete,
                    }
                    for cr in status.completions
                ],
            }
        )

    return agent
