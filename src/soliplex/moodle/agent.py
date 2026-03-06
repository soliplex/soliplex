"""Moodle Workplace factory agent with tool calling.

The factory creates a ``pydantic_ai.Agent`` with tools for querying
and managing Moodle data (courses, users, enrollment, completion,
groups, grades, calendar, and write operations).  The LLM decides
which tools to call.
"""

from __future__ import annotations

import json
import time

import httpx
import pydantic_ai

from soliplex import agents
from soliplex import config
from soliplex.config import agents as config_agents
from soliplex.moodle.client import MAX_RESULTS
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient

MOODLE_TOOLS_PROMPT = """\
You are a training management assistant connected to \
Moodle Workplace.

IMPORTANT: Always call the relevant tool BEFORE answering. \
Never claim data is missing without checking first.

## Query Tools
- list_courses — discover courses and IDs (start here)
- find_user — look up user by username or email
- get_course_contents — see sections, activities, and modules \
in a course
- list_enrolled_users — who is in a course
- get_completion_status — check one user's completion
- get_course_completion_overview — bulk completion rates for a \
whole course
- get_user_grades — grade report for a user in a course
- get_assignment_grades — all grades for assignments in a course
- get_upcoming_events — calendar events and deadlines
- list_course_groups / get_group_members — course groups
- list_cohorts / get_cohort_members — organizational cohorts

## Write Tools (REQUIRE CONFIRMATION)
- enrol_users — enrol users into a course
- send_message — send messages to users

WRITE OPERATIONS: For enrol_users and send_message, you MUST \
first call the tool WITHOUT confirmed=True to generate a preview. \
Present the preview to the user and ask "Should I proceed?" Only \
call the tool with confirmed=True after the user explicitly approves.

Workflow:
1. ALWAYS start with list_courses to discover available courses \
and their IDs.  If the user mentions a course by name, call \
list_courses first and match the closest result — do NOT say a \
course does not exist without checking.
2. Use find_user to look up a user by username or email and get \
their user ID.
3. Use the appropriate tool for the user's question.

Present data in clear tables when appropriate.
"""


def moodle_tools_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: agents.ToolConfigMap = None,
    mcp_client_toolset_configs: (config.MCP_ClientToolsetConfigMap) = None,
    skill_toolset_config: agents.SkillToolsetConfig | None = None,
) -> pydantic_ai.Agent:
    """Create a Moodle Workplace agent with tool calling.

    Exposes Moodle API methods as Pydantic AI tools so
    the LLM decides which to call.

    Required ``extra_config`` keys on *agent_config*:

    * ``moodle_base_url`` — secret reference for the Moodle
      instance URL.
    * ``moodle_api_token`` — secret reference for the web
      service token.

    Optional ``extra_config`` keys:

    * ``moodle_verify_ssl`` — path to a CA bundle or ``False``
      to disable TLS verification (passed through to
      ``MoodleClient``).
    * ``provider_type``, ``model_name``, etc. — forwarded to
      ``get_model_from_factory_config``.
    """
    ic = agent_config._installation_config
    extra = agent_config.extra_config

    base_url = ic.get_secret(extra["moodle_base_url"])
    token = ic.get_secret(extra["moodle_api_token"])
    verify = extra.get("moodle_verify_ssl")
    client = MoodleClient(
        base_url=base_url, token=token, verify=verify
    )

    model = config_agents.get_model_from_factory_config(agent_config)

    agent = pydantic_ai.Agent(
        model=model,
        instructions=MOODLE_TOOLS_PROMPT,
        deps_type=agents.AgentDependencies,
    )

    # ---------------------------------------------------------------
    # Existing read tools
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_courses() -> str:
        """List all courses in Moodle.

        Returns JSON with id, shortname, and fullname
        for each course.  Use the course id in other
        tools.
        """
        try:
            courses = await client.get_courses()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
        try:
            users = await client.get_users_by_field(field, [value])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
        try:
            enrolled = await client.get_enrolled_users(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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

    # ---------------------------------------------------------------
    # Feature 1: Course content
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_course_contents(courseid: int) -> str:
        """Get the sections and activities inside a course.

        Args:
            courseid: The Moodle course ID.

        Returns JSON array of sections, each with nested
        modules showing name, type, and completion tracking.
        """
        try:
            sections = await client.get_course_contents(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": s.id,
                    "name": s.name,
                    "modules": [
                        {
                            "id": m.id,
                            "name": m.name,
                            "modname": m.modname,
                            "completion": m.completion,
                        }
                        for m in s.modules
                    ],
                }
                for s in sections
            ]
        )

    # ---------------------------------------------------------------
    # Feature 2: Compliance reporting
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_course_completion_overview(courseid: int) -> str:
        """Get completion status for ALL enrolled users in a course.

        Returns a summary with overall rate and per-user
        breakdown.

        Args:
            courseid: The Moodle course ID.
        """
        try:
            enrolled = await client.get_enrolled_users(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})

        users_capped = enrolled[:MAX_RESULTS]
        user_results = []
        completed_count = 0

        for user in users_capped:
            try:
                status = await client.get_course_completion_status(
                    courseid, user.id
                )
                if status.completed:
                    completed_count += 1
                user_results.append(
                    {
                        "userid": user.id,
                        "fullname": user.fullname,
                        "username": user.username,
                        "completed": status.completed,
                        "completions": len(status.completions),
                    }
                )
            except (MoodleAPIError, httpx.HTTPError):
                user_results.append(
                    {
                        "userid": user.id,
                        "fullname": user.fullname,
                        "username": user.username,
                        "completed": None,
                        "completions": 0,
                    }
                )

        total = len(users_capped)
        rate = (completed_count / total * 100) if total else 0
        return json.dumps(
            {
                "total_enrolled": total,
                "completed": completed_count,
                "incomplete": total - completed_count,
                "completion_rate": round(rate, 1),
                "users": user_results,
            }
        )

    # ---------------------------------------------------------------
    # Feature 3: Groups & cohorts
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_course_groups(courseid: int) -> str:
        """List groups within a course.

        Args:
            courseid: The Moodle course ID.
        """
        try:
            groups = await client.get_course_groups(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": g.id,
                    "name": g.name,
                    "description": g.description,
                }
                for g in groups
            ]
        )

    @agent.tool_plain
    async def get_group_members(groupid: int) -> str:
        """List members of a specific group.

        Args:
            groupid: The Moodle group ID.
        """
        try:
            results = await client.get_group_members([groupid])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        if results:
            return json.dumps(
                {
                    "groupid": results[0].groupid,
                    "userids": results[0].userids,
                }
            )
        return json.dumps({"groupid": groupid, "userids": []})

    @agent.tool_plain
    async def list_cohorts() -> str:
        """List all organizational cohorts."""
        try:
            cohorts = await client.get_cohorts()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "idnumber": c.idnumber,
                }
                for c in cohorts
            ]
        )

    @agent.tool_plain
    async def get_cohort_members(cohortid: int) -> str:
        """List members of a specific cohort.

        Args:
            cohortid: The Moodle cohort ID.
        """
        try:
            results = await client.get_cohort_members([cohortid])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        if results:
            return json.dumps(
                {
                    "cohortid": results[0].cohortid,
                    "userids": results[0].userids,
                }
            )
        return json.dumps({"cohortid": cohortid, "userids": []})

    # ---------------------------------------------------------------
    # Feature 4: Grading & assessments
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_user_grades(courseid: int, userid: int) -> str:
        """Get a user's grade report for a course.

        Args:
            courseid: The Moodle course ID.
            userid: The Moodle user ID.
        """
        try:
            raw = await client.get_user_grades(courseid, userid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        tables = raw.get("tables", [])
        items = []
        for table in tables:
            for row in table.get("tabledata", []):
                if isinstance(row, dict):
                    itemname = ""
                    grade = ""
                    percentage = ""
                    if "itemname" in row:
                        cell = row["itemname"]
                        itemname = (
                            cell.get("content", "")
                            if isinstance(cell, dict)
                            else str(cell)
                        )
                    if "grade" in row:
                        cell = row["grade"]
                        grade = (
                            cell.get("content", "")
                            if isinstance(cell, dict)
                            else str(cell)
                        )
                    if "percentage" in row:
                        cell = row["percentage"]
                        percentage = (
                            cell.get("content", "")
                            if isinstance(cell, dict)
                            else str(cell)
                        )
                    if itemname:
                        items.append(
                            {
                                "itemname": itemname,
                                "grade": grade,
                                "percentage": percentage,
                            }
                        )
        return json.dumps(items)

    @agent.tool_plain
    async def get_assignment_grades(courseid: int) -> str:
        """Get all grades for assignments in a course.

        Looks up course contents first to find assignment
        module IDs, then fetches grades for each.

        Args:
            courseid: The Moodle course ID.
        """
        try:
            sections = await client.get_course_contents(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})

        assign_ids = []
        for section in sections:
            for mod in section.modules:
                if mod.modname == "assign":
                    assign_ids.append(mod.id)

        if not assign_ids:
            return json.dumps(
                {"message": "No assignments found in this course"}
            )

        try:
            raw = await client.get_assignment_grades(assign_ids)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})

        assignments = raw.get("assignments", [])
        result = []
        for a in assignments:
            grades = a.get("grades", [])
            result.append(
                {
                    "assignmentid": a.get("assignmentid"),
                    "grades": [
                        {
                            "userid": g.get("userid"),
                            "grade": g.get("grade"),
                            "timemodified": g.get("timemodified"),
                        }
                        for g in grades
                    ],
                }
            )
        return json.dumps(result)

    # ---------------------------------------------------------------
    # Feature 5: Calendar & deadlines
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_upcoming_events(
        courseids: str = "",
        days_ahead: int = 30,
    ) -> str:
        """Get upcoming calendar events and deadlines.

        Args:
            courseids: Optional comma-separated course IDs
                       to filter by.
            days_ahead: Number of days to look ahead
                        (default 30).
        """
        cids: list[int] | None = None
        if courseids:
            cids = [
                int(c.strip())
                for c in courseids.split(",")
                if c.strip()
            ]
        now = int(time.time())
        end = now + days_ahead * 86400
        try:
            # The calendar API only returns course events when
            # course IDs are explicitly provided.  When the caller
            # doesn't specify any, fetch all courses first.
            if cids is None:
                all_courses = await client.get_courses()
                cids = [c.id for c in all_courses if c.id != 1]
            events = await client.get_calendar_events(
                courseids=cids, timestart=now, timeend=end
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": e.id,
                    "name": e.name,
                    "courseid": e.courseid,
                    "eventtype": e.eventtype,
                    "timestart": e.timestart,
                    "timeduration": e.timeduration,
                }
                for e in events
            ]
        )

    # ---------------------------------------------------------------
    # Feature 7: Write operations (with confirmation)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def enrol_users(
        userids: str,
        courseid: int,
        roleid: int = 5,
        confirmed: bool = False,
    ) -> str:
        """Enrol users into a course.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userids: Comma-separated user IDs.
            courseid: The Moodle course ID.
            roleid: Role ID (default 5 = student).
            confirmed: Set True only after user approval.
        """
        user_list = [
            int(uid.strip())
            for uid in userids.split(",")
            if uid.strip()
        ]
        if not confirmed:
            return json.dumps(
                {
                    "action": "enrol_users",
                    "preview": (
                        f"Will enrol {len(user_list)} user(s) into "
                        f"course {courseid} with role {roleid}"
                    ),
                    "user_ids": user_list,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        enrolments = [
            {"userid": uid, "courseid": courseid, "roleid": roleid}
            for uid in user_list
        ]
        try:
            result = await client.enrol_users(enrolments)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "enrolled": len(user_list),
                "warnings": result.get("warnings", []),
            }
        )

    @agent.tool_plain
    async def send_message(
        userids: str,
        text: str,
        confirmed: bool = False,
    ) -> str:
        """Send a message to one or more users.

        Pass confirmed=True only after the user has reviewed
        and approved.

        Args:
            userids: Comma-separated user IDs.
            text: Message text to send.
            confirmed: Set True only after user approval.
        """
        user_list = [
            int(uid.strip())
            for uid in userids.split(",")
            if uid.strip()
        ]
        if not confirmed:
            return json.dumps(
                {
                    "action": "send_message",
                    "preview": (
                        f"Will send message to {len(user_list)} "
                        f"user(s): \"{text[:100]}\""
                    ),
                    "user_ids": user_list,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        messages = [
            {"touserid": uid, "text": text, "textformat": 0}
            for uid in user_list
        ]
        try:
            result = await client.send_messages(messages)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "sent": len(user_list),
                "results": result,
            }
        )

    return agent
