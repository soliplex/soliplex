"""Moodle Workplace factory agent with tool calling.

The factory creates a ``pydantic_ai.Agent`` with tools for querying
and managing Moodle data (courses, users, enrollment, completion,
groups, grades, calendar, and write operations).  The LLM decides
which tools to call.
"""

from __future__ import annotations

import json
import re
import time

import httpx
import pydantic_ai
from haiku.skills import prompts as hs_prompts

from soliplex import agents
from soliplex import config
from soliplex.config import agents as config_agents
from soliplex.moodle.client import MAX_RESULTS
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient


def _parse_ids(csv_string: str, param_name: str = "IDs") -> list[int] | str:
    """Parse comma-separated numeric IDs.

    Returns list[int] on success, error JSON string on failure.
    """
    parts = [p.strip() for p in csv_string.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError:
        non_numeric = [p for p in parts if not p.isdigit()]
        return json.dumps({
            "error": (
                f"Invalid {param_name}: {non_numeric}. "
                f"Use numeric user IDs, not usernames. "
                f"Call find_user first to look up IDs."
            )
        })


def _parse_single_id(value: str, param_name: str = "user ID") -> int | str:
    """Parse a single numeric ID.

    Returns int on success, error JSON string on failure.
    """
    try:
        return int(value.strip())
    except ValueError:
        return json.dumps({
            "error": (
                f"Invalid {param_name}: '{value}'. "
                f"Use a numeric user ID, not a username. "
                f"Call find_user first to look up the ID."
            )
        })


MOODLE_TOOLS_PROMPT = """\
You are a training management assistant connected to \
Moodle Workplace.

IMPORTANT: Always call the relevant tool BEFORE answering. \
Never claim data is missing without checking first.

## Query Tools
- list_courses — discover courses and IDs (start here)
- find_user — look up user by username, email, or name
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

## Workplace Tools (Certifications, Programs, Tenants)
- list_certifications — list all certifications in the system
- get_certification_allocations — who holds a specific certification
- get_user_certifications — all certifications for a specific user
- get_certification_history — audit trail for a user's certification
- get_certification_user_details — detailed user+cert allocation view
- search_programs — find learning paths/programs by name
- get_user_program_courses — courses in a user's program with progress
- list_tenants — list organizational tenants

## Catalogue Tools
- browse_catalogue — search the course/program catalogue
- get_user_learning_catalogue — user's enrolled items with progress
- get_program_content — see courses inside a program

## Additional Management Tools
- search_courses_for_program — courses eligible for programs
- deallocate_user_from_program — remove user from a program
- deallocate_user_from_certification — remove user from a certification
- archive_certification — archive an entire certification
- allocate_users_to_tenant — assign users to a tenant
- suspend_users — suspend user accounts (system-wide)

## Organisation Structure Tools
- list_departments — list organisational departments
- list_positions — list organisational positions
- get_team_members — find users by department/position
- get_potential_parent_departments — find valid parents for dept hierarchy
- get_potential_parent_positions — find valid parents for position hierarchy
- assign_job — assign a user to a department and position
- assign_manager — set manager relationships

## Competency Tools
- list_competency_frameworks — list all competency frameworks
- get_user_learning_plans — user's learning plans
- get_user_competency — user competency summary
- get_course_competencies — competencies linked to a course

## Reporting Tools
- list_reports — list all custom Report Builder reports
- get_report_data — retrieve data from a Report Builder report (paginated)
- get_utm_report — UTM completion report for a course by department
- get_adv_comp_report — Advanced completion report for a course

## Write Tools (REQUIRE CONFIRMATION)
- enrol_users — enrol users into a course
- send_message — send messages to users
- certify_user — mark a user as certified
- revoke_certification — revoke a user's certification
- allocate_users_to_program — assign users to a learning path
- deallocate_user_from_program — remove user from a program
- deallocate_user_from_certification — remove user from a cert
- archive_certification — archive an entire certification
- allocate_users_to_tenant — assign users to a tenant
- suspend_users — suspend user accounts (system-wide)
- assign_job — assign a user to a department and position
- assign_manager — set manager relationships
- create_department — create a new department
- update_department — update or move a department (by idnumber)
- delete_department — delete a department
- create_position — create a new position
- update_position — update or move a position (by idnumber)
- delete_position — delete a position
- delete_job — delete a job assignment
- unassign_manager — remove manager relationships

WRITE OPERATIONS: For all write tools, you MUST first call the \
tool WITHOUT confirmed=True to generate a preview. Present the \
preview to the user and ask "Should I proceed?" Only call the \
tool with confirmed=True after the user explicitly approves.

Workflow:
1. ALWAYS start with list_courses to discover available courses \
and their IDs.  If the user mentions a course by name, call \
list_courses first and match the closest result — do NOT say a \
course does not exist without checking.
2. Use find_user to look up a user by name, username, or email and \
get their user ID. When the user mentions someone by first name or \
full name, use field="name".
3. Use the appropriate tool for the user's question.
4. For certification/compliance questions, start with \
list_certifications to discover certifications and their IDs, \
then use get_certification_allocations or get_user_certifications \
for details.
5. For learning path questions, use search_programs to find \
programs, then get_user_program_courses for progress details.
6. For browsing available content, use browse_catalogue. For \
program course details, use get_program_content.
7. For org structure questions, use list_departments and \
list_positions to discover structure, then get_team_members. \
For org modifications, use get_potential_parent_departments or \
get_potential_parent_positions to find valid hierarchy parents \
before creating or moving. When creating departments/positions, \
always set an idnumber so you can reference them for updates.
8. For competency questions, use list_competency_frameworks to \
discover frameworks, then get_user_learning_plans or \
get_user_competency for details.
9. For report/analytics questions, use list_reports to discover \
available custom reports and their IDs, then get_report_data to \
retrieve actual data. For completion reports by department, use \
get_utm_report or get_adv_comp_report directly.

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

    toolsets: list = []
    if skill_toolset_config is not None:
        toolset = skill_toolset_config.skill_toolset
        toolsets.append(toolset)
        instructions = hs_prompts.build_system_prompt(
            preamble=MOODLE_TOOLS_PROMPT,
            skill_catalog=toolset.skill_catalog,
        )
    else:
        instructions = MOODLE_TOOLS_PROMPT

    agent = pydantic_ai.Agent(
        model=model,
        instructions=instructions,
        deps_type=agents.AgentDependencies,
        toolsets=toolsets or None,
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
            field: The field to search. Supported values:
                   "username", "email", "id", "idnumber"
                   (exact match), or "name", "firstname",
                   "lastname" (substring search).
            value: The value to match.

        Returns JSON with id, username, fullname, and
        email for each matching user.
        """
        exact_fields = {"username", "email", "id", "idnumber"}
        name_fields = {"name", "firstname", "lastname"}

        try:
            if field in exact_fields:
                users = await client.get_users_by_field(field, [value])
            elif field in name_fields:
                if field == "name":
                    parts = value.split(None, 1)
                    criteria = [("firstname", parts[0])]
                    if len(parts) > 1:
                        criteria.append(("lastname", parts[1]))
                else:
                    criteria = [(field, value)]
                users = await client.search_users(criteria)
            else:
                return json.dumps({
                    "error": (
                        f"Unsupported field: '{field}'. "
                        f"Use one of: {sorted(exact_fields | name_fields)}"
                    )
                })
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
        parsed = _parse_ids(userids, "user IDs")
        if isinstance(parsed, str):
            return parsed
        user_list = parsed
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
        parsed = _parse_ids(userids, "user IDs")
        if isinstance(parsed, str):
            return parsed
        user_list = parsed
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

    # ---------------------------------------------------------------
    # Feature 8: Certifications (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_certifications(tenantid: int = 0) -> str:
        """List all certifications in the system.

        Args:
            tenantid: Optional tenant ID to filter by
                      (default 0 = all tenants).
        """
        try:
            certs = await client.get_certifications(tenantid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": c.id,
                    "fullname": c.fullname,
                    "idnumber": c.idnumber,
                    "status": c.status,
                }
                for c in certs
            ]
        )

    @agent.tool_plain
    async def get_certification_allocations(
        certificationid: int,
    ) -> str:
        """List users allocated to a specific certification.

        Args:
            certificationid: The certification ID.
        """
        try:
            allocs = await client.get_certification_allocations(
                certificationid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": a.id,
                    "userid": a.userid,
                    "userfullname": a.userfullname,
                    "certificationfullname": a.certificationfullname,
                    "timeallocated": a.timeallocated,
                }
                for a in allocs
            ]
        )

    @agent.tool_plain
    async def get_user_certifications(userid: int) -> str:
        """Get all certifications for a specific user.

        Args:
            userid: The Moodle user ID.
        """
        try:
            allocs = await client.get_user_certification_allocations(
                userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": a.id,
                    "certificationid": a.certificationid,
                    "certificationfullname": a.certificationfullname,
                    "timeallocated": a.timeallocated,
                }
                for a in allocs
            ]
        )

    @agent.tool_plain
    async def get_certification_history(
        certificationid: int,
        userid: int,
    ) -> str:
        """Get the audit trail for a user's certification.

        Args:
            certificationid: The certification ID.
            userid: The Moodle user ID.
        """
        try:
            entries = await client.get_certification_user_log(
                certificationid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": e.id,
                    "action": e.action,
                    "timecreated": e.timecreated,
                }
                for e in entries
            ]
        )

    @agent.tool_plain
    async def certify_user(
        userid: str,
        certificationid: int,
        confirmed: bool = False,
    ) -> str:
        """Mark a user as certified.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userid: The Moodle user ID (as string).
            certificationid: The certification ID.
            confirmed: Set True only after user approval.
        """
        uid = _parse_single_id(userid, "user ID")
        if isinstance(uid, str):
            return uid
        if not confirmed:
            return json.dumps(
                {
                    "action": "certify_user",
                    "preview": (
                        f"Will certify user {uid} for "
                        f"certification {certificationid}"
                    ),
                    "userid": uid,
                    "certificationid": certificationid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.certify_user(certificationid, uid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "userid": uid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @agent.tool_plain
    async def revoke_certification(
        userid: str,
        certificationid: int,
        confirmed: bool = False,
    ) -> str:
        """Revoke a user's certification.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userid: The Moodle user ID (as string).
            certificationid: The certification ID.
            confirmed: Set True only after user approval.
        """
        uid = _parse_single_id(userid, "user ID")
        if isinstance(uid, str):
            return uid
        if not confirmed:
            return json.dumps(
                {
                    "action": "revoke_certification",
                    "preview": (
                        f"Will revoke certification "
                        f"{certificationid} from user {uid}"
                    ),
                    "userid": uid,
                    "certificationid": certificationid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.revoke_certification(
                certificationid, uid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "userid": uid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 9: Programs / Learning Paths (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def search_programs(search: str = "") -> str:
        """Search for learning programs by name.

        Args:
            search: Optional search string to filter
                    programs (default "" = all).
        """
        try:
            programs = await client.search_programs(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": p.id,
                    "fullname": p.fullname,
                }
                for p in programs
            ]
        )

    @agent.tool_plain
    async def get_user_program_courses(userid: int) -> str:
        """Get courses in a user's assigned programs with progress.

        Args:
            userid: The Moodle user ID.
        """
        try:
            courses = await client.get_user_program_courses(userid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": c.id,
                    "shortname": c.shortname,
                    "fullname": c.fullname,
                    "completed": c.completed,
                }
                for c in courses
            ]
        )

    @agent.tool_plain
    async def allocate_users_to_program(
        userids: str,
        programid: int,
        confirmed: bool = False,
    ) -> str:
        """Assign users to a learning program.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userids: Comma-separated user IDs.
            programid: The program ID.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(userids, "user IDs")
        if isinstance(parsed, str):
            return parsed
        user_list = parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "allocate_users_to_program",
                    "preview": (
                        f"Will allocate {len(user_list)} user(s) "
                        f"to program {programid}"
                    ),
                    "user_ids": user_list,
                    "programid": programid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.allocate_users_to_program(
                programid, user_list
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "allocated": len(user_list),
                "programid": programid,
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 10: Tenants (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_tenants() -> str:
        """List all organizational tenants."""
        try:
            tenants = await client.get_tenants()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": t.id,
                    "name": t.name,
                    "sitename": t.sitename,
                    "idnumber": t.idnumber,
                    "isdefault": t.isdefault,
                }
                for t in tenants
            ]
        )

    @agent.tool_plain
    async def allocate_users_to_tenant(
        userids: str,
        tenantid: int,
        confirmed: bool = False,
    ) -> str:
        """Assign users to a tenant.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userids: Comma-separated user IDs.
            tenantid: The tenant ID.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(userids, "user IDs")
        if isinstance(parsed, str):
            return parsed
        user_list = parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "allocate_users_to_tenant",
                    "preview": (
                        f"Will assign {len(user_list)} user(s) "
                        f"to tenant {tenantid}"
                    ),
                    "user_ids": user_list,
                    "tenantid": tenantid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        allocations = [
            {"userid": uid, "tenantid": tenantid}
            for uid in user_list
        ]
        try:
            result = await client.allocate_users_to_tenant(allocations)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "allocated": len(user_list),
                "tenantid": tenantid,
                "result": result,
            }
        )

    @agent.tool_plain
    async def suspend_users(
        userids: str,
        confirmed: bool = False,
    ) -> str:
        """Suspend user accounts system-wide.

        WARNING: This suspends accounts across ALL of Moodle,
        not just a specific tenant. Pass confirmed=True only
        after the user has reviewed and approved the action.

        Args:
            userids: Comma-separated user IDs.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(userids, "user IDs")
        if isinstance(parsed, str):
            return parsed
        user_list = parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "suspend_users",
                    "preview": (
                        f"WARNING: This will suspend {len(user_list)} "
                        f"user(s) across ALL of Moodle, not just a "
                        f"specific tenant. User IDs: {user_list}"
                    ),
                    "user_ids": user_list,
                    "instructions": (
                        "Present this WARNING to the user and ask "
                        "for explicit confirmation. If confirmed, "
                        "call this tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.suspend_tenant_users(user_list)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "suspended": len(user_list),
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 11: Catalogue (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def browse_catalogue(query: str = "") -> str:
        """Search the course/program catalogue.

        Args:
            query: Optional search query (default "" = all).
        """
        try:
            items = await client.get_catalogue_page(query)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": i.id,
                    "title": i.title,
                    "url": i.url,
                }
                for i in items
            ]
        )

    @agent.tool_plain
    async def get_user_learning_catalogue(
        userid: int = 0,
        search: str = "",
    ) -> str:
        """Get a user's enrolled items with progress.

        Args:
            userid: The Moodle user ID (0 = current user).
            search: Optional search string.
        """
        try:
            items = await client.get_user_catalogue(userid, search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "itemid": i.itemid,
                    "fullname": i.fullname,
                    "numcourses": i.numcourses,
                    "progress": i.progress,
                    "duedate": i.duedate,
                    "isprogram": i.isprogram,
                    "categoryname": i.categoryname,
                }
                for i in items
            ]
        )

    @agent.tool_plain
    async def get_program_content(
        programid: int,
        userid: int = 0,
    ) -> str:
        """Get the courses inside a program.

        Args:
            programid: The program ID.
            userid: Optional user ID (0 = current user).
        """
        try:
            content = await client.get_program_content(
                programid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(content)

    # ---------------------------------------------------------------
    # Feature 12: Deeper Program Management (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def search_courses_for_program(search: str = "") -> str:
        """Search for courses eligible for programs.

        Args:
            search: Optional search string (default "" = all).
        """
        try:
            courses = await client.search_courses_for_program(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {"id": c.id, "fullname": c.fullname}
                for c in courses
            ]
        )

    @agent.tool_plain
    async def deallocate_user_from_program(
        userid: int,
        programid: int,
        confirmed: bool = False,
    ) -> str:
        """Remove a user from a program.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userid: The Moodle user ID.
            programid: The program ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "deallocate_user_from_program",
                    "preview": (
                        f"Will remove user {userid} from "
                        f"program {programid}"
                    ),
                    "userid": userid,
                    "programid": programid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.deallocate_user_from_program(
                programid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "programid": programid,
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 13: Deeper Certification Management (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_certification_user_details(
        certificationid: int,
        userid: int,
    ) -> str:
        """Get detailed user+certification allocation view.

        Args:
            certificationid: The certification ID.
            userid: The Moodle user ID.
        """
        try:
            details = await client.get_certification_user_allocation(
                certificationid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(details)

    @agent.tool_plain
    async def deallocate_user_from_certification(
        userid: int,
        certificationid: int,
        confirmed: bool = False,
    ) -> str:
        """Remove a user from a certification.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userid: The Moodle user ID.
            certificationid: The certification ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "deallocate_user_from_certification",
                    "preview": (
                        f"Will remove user {userid} from "
                        f"certification {certificationid}"
                    ),
                    "userid": userid,
                    "certificationid": certificationid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.deallocate_user_from_certification(
                certificationid, userid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @agent.tool_plain
    async def archive_certification(
        certificationid: int,
        confirmed: bool = False,
    ) -> str:
        """Archive an entire certification.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            certificationid: The certification ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "archive_certification",
                    "preview": (
                        f"Will archive certification "
                        f"{certificationid}"
                    ),
                    "certificationid": certificationid,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.archive_certification(
                certificationid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "certificationid": certificationid,
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 14: Organisation Structure (Workplace)
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_departments(search: str = "") -> str:
        """List organisational departments.

        Args:
            search: Optional search string (default "" = all).
        """
        try:
            depts = await client.get_departments(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": d.id,
                    "name": d.name,
                    "parentid": d.parentid,
                    "idnumber": d.idnumber,
                }
                for d in depts
            ]
        )

    @agent.tool_plain
    async def list_positions(search: str = "") -> str:
        """List organisational positions.

        Args:
            search: Optional search string (default "" = all).
        """
        try:
            positions = await client.get_positions(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "parentid": p.parentid,
                    "idnumber": p.idnumber,
                }
                for p in positions
            ]
        )

    @agent.tool_plain
    async def get_team_members(
        departmentid: int = 0,
        positionid: int = 0,
        search: str = "",
    ) -> str:
        """Find users by department, position, or name.

        Returns all users matching the filters (not scoped to
        a particular manager).

        Args:
            departmentid: Optional department ID to filter.
            positionid: Optional position ID to filter.
            search: Optional name search string.
        """
        # Try the custom plugin endpoint first (unrestricted).
        try:
            members = await client.get_department_members(
                departmentid, positionid, search
            )
            return json.dumps(
                [
                    {
                        "userid": m.userid,
                        "fullname": m.fullname,
                        "email": m.email,
                        "departmentname": m.departmentname,
                        "positionname": m.positionname,
                    }
                    for m in members
                ]
            )
        except MoodleAPIError:
            pass  # Plugin not installed — fall back
        except httpx.HTTPError as exc:
            return json.dumps({"error": str(exc)})

        # Fallback: legacy managed-users endpoint (scoped to token owner).
        try:
            users = await client.get_managed_users(
                departmentid, positionid, search
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        if not users:
            return json.dumps({
                "users": [],
                "note": (
                    "The legacy endpoint only returns direct reports "
                    "of the API token owner. Install the local_soliplex "
                    "plugin for unrestricted department queries."
                ),
            })
        return json.dumps(users)

    @agent.tool_plain
    async def assign_job(
        userid: int,
        department: str,
        position: str,
        confirmed: bool = False,
    ) -> str:
        """Assign a user to a department and position.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userid: The Moodle user ID.
            department: Department idnumber.
            position: Position idnumber.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "assign_job",
                    "preview": (
                        f"Will assign user {userid} to "
                        f"department '{department}' / "
                        f"position '{position}'"
                    ),
                    "userid": userid,
                    "department": department,
                    "position": position,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.create_job(
                userid, department, position
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "department": department,
                "position": position,
                "result": result,
            }
        )

    @agent.tool_plain
    async def assign_manager(
        userids: str,
        managerids: str,
        confirmed: bool = False,
    ) -> str:
        """Set manager relationships for users.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userids: Comma-separated user IDs.
            managerids: Comma-separated manager user IDs.
            confirmed: Set True only after user approval.
        """
        parsed_users = _parse_ids(userids, "user IDs")
        if isinstance(parsed_users, str):
            return parsed_users
        parsed_managers = _parse_ids(managerids, "manager IDs")
        if isinstance(parsed_managers, str):
            return parsed_managers
        user_list = parsed_users
        manager_list = parsed_managers
        if not confirmed:
            return json.dumps(
                {
                    "action": "assign_manager",
                    "preview": (
                        f"Will assign manager(s) {manager_list} "
                        f"to user(s) {user_list}"
                    ),
                    "user_ids": user_list,
                    "manager_ids": manager_list,
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.assign_managers(
                user_list, manager_list
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "user_ids": user_list,
                "manager_ids": manager_list,
                "result": result,
            }
        )

    # ---------------------------------------------------------------
    # Feature 15: Competencies & Learning Plans
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def list_competency_frameworks() -> str:
        """List all competency frameworks."""
        try:
            frameworks = await client.get_competency_frameworks()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": f.id,
                    "shortname": f.shortname,
                    "idnumber": f.idnumber,
                    "description": f.description,
                    "competencycount": f.competencycount,
                }
                for f in frameworks
            ]
        )

    @agent.tool_plain
    async def get_user_learning_plans(userid: int) -> str:
        """Get a user's learning plans.

        Args:
            userid: The Moodle user ID.
        """
        try:
            plans = await client.get_user_learning_plans(userid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "statusname": p.statusname,
                    "userid": p.userid,
                }
                for p in plans
            ]
        )

    @agent.tool_plain
    async def get_user_competency(
        userid: int,
        competencyid: int,
    ) -> str:
        """Get a user's competency summary.

        Args:
            userid: The Moodle user ID.
            competencyid: The competency ID.
        """
        try:
            summary = await client.get_user_competency_summary(
                userid, competencyid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(summary)

    @agent.tool_plain
    async def get_course_competencies(courseid: int) -> str:
        """Get competencies linked to a course.

        Args:
            courseid: The Moodle course ID.
        """
        try:
            competencies = await client.get_course_competencies(
                courseid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(competencies)

    # ---------------------------------------------------------------
    # Organisation CRUD tools
    # ---------------------------------------------------------------

    @agent.tool_plain
    async def get_potential_parent_departments(
        search: str = "",
        departmentid: int = 0,
    ) -> str:
        """Get valid parent departments for building hierarchy.

        Use before creating or moving a department to find
        valid parents.

        Args:
            search: Search string to filter results.
            departmentid: Department ID being edited (0 for new).
        """
        try:
            parents = await client.get_potential_parent_departments(
                search=search, departmentid=departmentid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {"id": p.id, "name": p.name, "path": p.path}
                for p in parents
            ]
        )

    @agent.tool_plain
    async def get_potential_parent_positions(
        search: str = "",
        positionid: int = 0,
    ) -> str:
        """Get valid parent positions for building hierarchy.

        Use before creating or moving a position to find
        valid parents.

        Args:
            search: Search string to filter results.
            positionid: Position ID being edited (0 for new).
        """
        try:
            parents = await client.get_potential_parent_positions(
                search=search, positionid=positionid
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {"id": p.id, "name": p.name, "path": p.path}
                for p in parents
            ]
        )

    @agent.tool_plain
    async def create_department(
        name: str,
        idnumber: str = "",
        parent: str = "",
        description: str = "",
        confirmed: bool = False,
    ) -> str:
        """Create a new department. REQUIRES USER CONFIRMATION.

        Always set an idnumber so the department can be
        referenced for later updates.

        Args:
            name: Department name (required).
            idnumber: Unique identifier for the department.
            parent: Parent department idnumber for hierarchy.
            description: Optional description.
            confirmed: Set True only after user approval.
        """
        dept: dict[str, str] = {"name": name}
        if idnumber:
            dept["idnumber"] = idnumber
        if parent:
            dept["parent"] = parent
        if description:
            dept["description"] = description
        if not confirmed:
            return json.dumps(
                {"preview": f"Create department '{name}'", "department": dept}
            )
        try:
            created, warnings = await client.create_departments([dept])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "created": [
                    {"id": c.id, "name": c.name, "idnumber": c.idnumber}
                    for c in created
                ],
                "warnings": warnings,
            }
        )

    @agent.tool_plain
    async def update_department(
        idnumber: str,
        name: str = "",
        parent: str = "",
        description: str = "",
        confirmed: bool = False,
    ) -> str:
        """Update or move a department. REQUIRES USER CONFIRMATION.

        Identifies the department by idnumber. Set parent to
        move the department to a new parent in the hierarchy.

        Args:
            idnumber: Department idnumber to update (required).
            name: New name (optional).
            parent: New parent idnumber to move (optional).
            description: New description (optional).
            confirmed: Set True only after user approval.
        """
        dept: dict[str, str] = {"idnumber": idnumber}
        if name:
            dept["name"] = name
        if parent:
            dept["parent"] = parent
        if description:
            dept["description"] = description
        if not confirmed:
            return json.dumps(
                {"preview": f"Update department '{idnumber}'", "changes": dept}
            )
        try:
            updated, warnings = await client.update_departments([dept])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "updated": [
                    {"id": u.id, "idnumber": u.idnumber}
                    for u in updated
                ],
                "warnings": warnings,
            }
        )

    @agent.tool_plain
    async def delete_department(
        department_id: int,
        confirmed: bool = False,
    ) -> str:
        """Delete a department. REQUIRES USER CONFIRMATION.

        The department must not have any jobs in its hierarchy.

        Args:
            department_id: Moodle internal department ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {"preview": f"Delete department id={department_id}"}
            )
        try:
            result = await client.delete_department(department_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    @agent.tool_plain
    async def create_position(
        name: str,
        idnumber: str = "",
        parent: str = "",
        description: str = "",
        department_manager: bool = False,
        global_manager: bool = False,
        confirmed: bool = False,
    ) -> str:
        """Create a new position. REQUIRES USER CONFIRMATION.

        Always set an idnumber so the position can be
        referenced for later updates.

        Args:
            name: Position name (required).
            idnumber: Unique identifier for the position.
            parent: Parent position idnumber for hierarchy.
            description: Optional description.
            department_manager: True if this is a department lead.
            global_manager: True if this is a manager role.
            confirmed: Set True only after user approval.
        """
        pos: dict[str, str | bool] = {"name": name}
        if idnumber:
            pos["idnumber"] = idnumber
        if parent:
            pos["parent"] = parent
        if description:
            pos["description"] = description
        if department_manager:
            pos["departmentmanager"] = True
        if global_manager:
            pos["globalmanager"] = True
        if not confirmed:
            return json.dumps(
                {"preview": f"Create position '{name}'", "position": pos}
            )
        try:
            created, warnings = await client.create_positions([pos])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "created": [
                    {"id": c.id, "name": c.name, "idnumber": c.idnumber}
                    for c in created
                ],
                "warnings": warnings,
            }
        )

    @agent.tool_plain
    async def update_position(
        idnumber: str,
        name: str = "",
        parent: str = "",
        description: str = "",
        department_manager: bool | None = None,
        global_manager: bool | None = None,
        confirmed: bool = False,
    ) -> str:
        """Update or move a position. REQUIRES USER CONFIRMATION.

        Identifies the position by idnumber. Set parent to
        move the position to a new parent in the hierarchy.

        Args:
            idnumber: Position idnumber to update (required).
            name: New name (optional).
            parent: New parent idnumber to move (optional).
            description: New description (optional).
            department_manager: Set department lead flag (optional).
            global_manager: Set manager flag (optional).
            confirmed: Set True only after user approval.
        """
        pos: dict[str, str | bool] = {"idnumber": idnumber}
        if name:
            pos["name"] = name
        if parent:
            pos["parent"] = parent
        if description:
            pos["description"] = description
        if department_manager is not None:
            pos["departmentmanager"] = department_manager
        if global_manager is not None:
            pos["globalmanager"] = global_manager
        if not confirmed:
            return json.dumps(
                {"preview": f"Update position '{idnumber}'", "changes": pos}
            )
        try:
            updated, warnings = await client.update_positions([pos])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "updated": [
                    {"id": u.id, "idnumber": u.idnumber}
                    for u in updated
                ],
                "warnings": warnings,
            }
        )

    @agent.tool_plain
    async def delete_position(
        position_id: int,
        confirmed: bool = False,
    ) -> str:
        """Delete a position. REQUIRES USER CONFIRMATION.

        The position must not have any jobs assigned.

        Args:
            position_id: Moodle internal position ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {"preview": f"Delete position id={position_id}"}
            )
        try:
            result = await client.delete_position(position_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    @agent.tool_plain
    async def delete_job(
        job_id: int,
        confirmed: bool = False,
    ) -> str:
        """Delete a job assignment. REQUIRES USER CONFIRMATION.

        Args:
            job_id: Internal Moodle job ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {"preview": f"Delete job id={job_id}"}
            )
        try:
            result = await client.delete_job(job_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    @agent.tool_plain
    async def unassign_manager(
        userids: str,
        managerids: str,
        unassign_all: bool = False,
        confirmed: bool = False,
    ) -> str:
        """Unassign manager relationships. REQUIRES USER CONFIRMATION.

        When unassign_all is False, removes the specified managers
        from the specified users. When True, removes ALL manager
        relationships for the given users and managers.

        Args:
            userids: Comma-separated user IDs (subordinates).
            managerids: Comma-separated manager user IDs.
            unassign_all: If True, unassign all relationships.
            confirmed: Set True only after user approval.
        """
        try:
            uid_list = [int(x.strip()) for x in userids.split(",")]
            mid_list = [int(x.strip()) for x in managerids.split(",")]
        except ValueError:
            return json.dumps(
                {"error": "IDs must be comma-separated integers"}
            )
        if not confirmed:
            return json.dumps(
                {
                    "preview": (
                        f"Unassign managers {mid_list}"
                        f" from users {uid_list}"
                    ),
                    "unassign_all": unassign_all,
                }
            )
        try:
            result = await client.unassign_managers(
                uid_list, mid_list, unassign_all=unassign_all
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    # ---------------------------------------------------------------
    # Reporting tools
    # ---------------------------------------------------------------

    def _strip_html(value: str | None) -> str:
        """Strip HTML tags from a report cell value."""
        if value is None:
            return ""
        return re.sub(r"<[^>]+>", "", value).strip()

    @agent.tool_plain
    async def list_reports() -> str:
        """List all custom reports available in Report Builder.

        Returns JSON with id, name, source type, and
        modification time for each report. Use the report
        id in get_report_data to retrieve actual data.
        """
        try:
            reports = await client.list_reports()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [
                {
                    "id": r.id,
                    "name": r.name,
                    "sourcename": r.sourcename,
                    "timemodified": r.timemodified,
                }
                for r in reports
            ]
        )

    @agent.tool_plain
    async def get_report_data(
        reportid: int,
        page: int = 0,
        perpage: int = 50,
    ) -> str:
        """Retrieve data from a custom report in Report Builder.

        Returns JSON with column headers and data rows.
        Each row is a list of cell values aligned with the
        headers. Use list_reports first to discover report
        IDs.

        Args:
            reportid: The report ID (from list_reports).
            page: Page number for pagination (default 0).
            perpage: Rows per page (default 50, max 100).
        """
        try:
            details, data = await client.retrieve_report(
                reportid, page=page, perpage=perpage
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "report_name": details.name,
                "source": details.sourcename,
                "headers": data.headers,
                "rows": [
                    [_strip_html(c) for c in row.columns]
                    for row in data.rows
                ],
                "total_rows": data.totalrowcount,
                "page": page,
                "perpage": perpage,
            }
        )

    @agent.tool_plain
    async def get_utm_report(
        courseid: int,
        departmentid: int = 0,
        completionstatus: int = 0,
    ) -> str:
        """Get UTM completion report for a course.

        Returns JSON with user completion data including
        department, start time, and completion time.

        Args:
            courseid: The Moodle course ID.
            departmentid: Optional department ID to filter by.
            completionstatus: 0=all, 1=completed, 2=not completed.
        """
        try:
            rows, totalcount = await client.get_utm_report(
                courseid,
                departmentid=departmentid,
                completionstatus=completionstatus,
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "rows": [
                    {
                        "userid": r.userid,
                        "username": r.username,
                        "name": f"{r.firstname} {r.lastname}",
                        "email": r.email,
                        "department": r.department,
                        "starttime": r.starttime,
                        "completedtime": r.completedtime,
                    }
                    for r in rows
                ],
                "total_rows": totalcount,
            }
        )

    @agent.tool_plain
    async def get_adv_comp_report(
        courseid: int,
        completionstatus: int = 0,
    ) -> str:
        """Get Advanced Completion report for a course.

        Returns JSON with user completion data including
        department, start time, and completion time.

        Args:
            courseid: The Moodle course ID.
            completionstatus: 0=all, 1=completed, 2=not completed.
        """
        try:
            rows, totalcount = await client.get_adv_comp_report(
                courseid,
                completionstatus=completionstatus,
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "rows": [
                    {
                        "userid": r.userid,
                        "username": r.username,
                        "name": f"{r.firstname} {r.lastname}",
                        "email": r.email,
                        "department": r.department,
                        "starttime": r.starttime,
                        "completedtime": r.completedtime,
                    }
                    for r in rows
                ],
                "total_rows": totalcount,
            }
        )

    return agent
