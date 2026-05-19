"""Moodle Workplace skill builders for haiku-skills composition.

Each builder creates a ``Skill`` with async tool closures over a
shared ``MoodleClient`` instance.  The tools are identical to the
former ``@agent.tool_plain`` functions -- only the registration
mechanism changes.
"""

from __future__ import annotations

import asyncio
import functools
import json
import re
import time

import httpx
import pydantic
from haiku.skills.models import Skill
from haiku.skills.models import SkillMetadata
from haiku.skills.models import SkillSource

from soliplex.moodle.client import MAX_RESULTS
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient


def _moodle_tool(fn):
    """Decorator that catches Moodle/HTTP errors and adds status fields.

    Wraps an async tool function so that:

    * Any ``MoodleAPIError`` or ``httpx.HTTPError`` raised during the
      call is serialized as ``{"status": "error", "error": "..."}``.
    * When the wrapped tool was invoked with ``confirmed=True`` (i.e.
      a real write op, not a preview), a ``"status": "ok"`` key is
      injected into the returned JSON object so the LLM has an
      unambiguous success marker.  Read tools and preview branches
      are left untouched.

    Tools that already emit an explicit ``status`` key (e.g. the
    delete wrappers that surface a "not found" error) are passed
    through verbatim.
    """

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            result = await fn(*args, **kwargs)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"status": "error", "error": str(exc)})

        if kwargs.get("confirmed") is True:
            try:
                payload = json.loads(result)
            except (TypeError, ValueError):
                return result
            if isinstance(payload, dict) and "status" not in payload:
                payload["status"] = "ok"
                return json.dumps(payload)
        return result

    return wrapper


# -- Module-level constants --

_EXPORTER_MAP = {
    "courses": r"tool_wp\tool_wp\exporter\courses",
    "users": r"tool_wp\tool_wp\exporter\users",
    "cohorts": r"tool_wp\tool_wp\exporter\cohorts",
    "reports": r"tool_wp\tool_wp\exporter\reports",
    "site": r"tool_wp\tool_wp\exporter\site",
    "certificates": (r"tool_wp\tool_wp\exporter\certificates"),
    "coursecategories": (r"tool_wp\tool_wp\exporter\coursecategories"),
    "programs": (r"tool_program\tool_wp\exporter\programs"),
    "certifications": (
        r"tool_certification\tool_wp"
        r"\exporter\certifications"
    ),
    "rules": (r"tool_dynamicrule\tool_wp\exporter\rules"),
    "departments_csv": (
        r"tool_organisation\tool_wp"
        r"\exporter\departments_csv"
    ),
    "positions_csv": (
        r"tool_organisation\tool_wp"
        r"\exporter\positions_csv"
    ),
    "jobs_csv": (
        r"tool_organisation\tool_wp"
        r"\exporter\jobs_csv"
    ),
    "orgstructure": (
        r"tool_organisation\tool_wp"
        r"\exporter\orgstructure"
    ),
    "jobs": (r"tool_organisation\tool_wp\exporter\jobs"),
    "tenants": (r"tool_tenant\tool_wp\exporter\tenants"),
}

# -- Shared helpers (used across multiple skills) --


def _parse_ids(csv_string: str, param_name: str = "IDs") -> list[int] | str:
    """Parse comma-separated numeric IDs.

    Returns list[int] on success, error JSON string on failure.
    """
    parts = [p.strip() for p in csv_string.split(",") if p.strip()]
    try:
        return [int(p) for p in parts]
    except ValueError:
        non_numeric = [p for p in parts if not p.isdigit()]
        return json.dumps(
            {
                "error": (
                    f"Invalid {param_name}: {non_numeric}. "
                    f"Use numeric user IDs, not usernames. "
                    f"Call find_user first to look up IDs."
                )
            }
        )


def _parse_single_id(value: str, param_name: str = "user ID") -> int | str:
    """Parse a single numeric ID.

    Returns int on success, error JSON string on failure.
    """
    try:
        return int(value.strip())
    except ValueError:
        return json.dumps(
            {
                "error": (
                    f"Invalid {param_name}: '{value}'. "
                    f"Use a numeric user ID, not a username. "
                    f"Call find_user first to look up the ID."
                )
            }
        )


def _strip_html(value: str | None) -> str:
    """Strip HTML tags from a report cell value (Report Builder).

    Many Report Builder columns return HTML wrapped values (anchors,
    icons). Reports are LLM-consumed so we strip the markup.
    """
    if value is None:
        return ""
    return re.sub(r"<[^>]+>", "", value).strip()


async def _resolve_rule_id(
    client: MoodleClient,
    rule_id: int = 0,
    rule_name: str = "",
) -> int | str:
    """Resolve a dynamic rule by ID or name.

    Returns the integer rule ID on success, or a JSON error string
    when the rule cannot be found, multiple match, or neither
    parameter is provided.
    """
    if rule_id > 0:
        return rule_id
    if not rule_name:
        return json.dumps({"error": "Provide either rule_id or rule_name."})
    try:
        rules = await client.list_dynamic_rules()
    except (MoodleAPIError, httpx.HTTPError) as exc:
        return json.dumps({"error": str(exc)})
    needle = rule_name.lower()
    # Bidirectional substring match: tolerant of both partial inputs
    # ("Cohort Trigger" → "Standalone Cohort Trigger") and superstring
    # inputs ("Standalone Cohort Trigger rule" → "Standalone Cohort
    # Trigger") where the LLM appends a noun-class suffix from the
    # user's phrasing.  Ambiguity is surfaced by the 0/1/many branching
    # below, so a tighter match is preferred but not required.
    matches = [
        r
        for r in rules
        if needle in r["name"].lower() or r["name"].lower() in needle
    ]
    if len(matches) == 1:
        return matches[0]["id"]
    if len(matches) == 0:
        return json.dumps(
            {"error": f"No dynamic rule matching '{rule_name}'."}
        )
    return json.dumps(
        {
            "error": f"Multiple rules match '{rule_name}'.",
            "matches": [{"id": m["id"], "name": m["name"]} for m in matches],
        }
    )


# -- Skill prompts --

_CONFIRM_INSTRUCTIONS = """\
WRITE OPERATIONS:

Case A — request does NOT mention confirmed=True:
Call the write tool with confirmed=False (preview mode). \
Return the preview JSON unchanged so the router can show \
it to the user.

Case B — request EXPLICITLY says "confirmed=True" or \
"with confirmed=True" or includes the parameter list \
verbatim from a prior preview:
Call the write tool with confirmed=True and ALL the \
parameters listed in the request. The router has already \
gotten user approval; do NOT preview again. Return the \
real tool result.

NEVER call a write tool with confirmed=False after the \
request explicitly contained "confirmed=True" — that \
silently re-previews the action and the user thinks it \
succeeded when nothing changed.

OUTPUT RULES (apply to every response):

1. Render tabular data as markdown tables. Do NOT narrate \
internal reasoning or quote the system instructions back \
to the user.

2. Do NOT include any preamble that describes your \
analysis steps. Phrases like "We identified...", "Now we \
need to...", "User wants to...", "According to the \
pattern..." are forbidden in user-facing output. Begin \
the response with the table or success line directly.

3. For preview responses, render only the tool's \
``action``, ``preview``, and structured parameter fields \
as a markdown table — never include any internal-directive \
fields the tool may emit. End with a single short \
question such as "Should I proceed?". Do NOT add \
"according to the system" or "per the instructions" \
narration.

4. For confirmed-write success responses (results containing \
``"status": "ok"``), output a single short sentence stating \
what changed (e.g. "Security department created."). No \
preamble, no "successfully completed the action of..." \
language.  Use only fields that appear in the tool result; \
do not invent IDs or other identifiers.

5. Result-status check (applies to write tools only).  If a \
tool result contains ``"status": "error"``, report the failure \
to the user.  Include the error message from the result so \
the user knows what went wrong.  NEVER claim a write \
operation succeeded, and NEVER invent IDs, unless the result \
contains ``"status": "ok"`` (see rule 4).  Read tools do not \
emit a status field and are unaffected by this rule."""

_COURSES_PROMPT = (
    """\
You manage Moodle courses, categories, enrollments, completion, \
grades, calendar events, and groups.

## Available tools
- list_courses -- discover courses and IDs (start here)
- get_course_contents -- sections, activities, and modules
- list_enrolled_users -- who is enrolled in a course
- get_completion_status -- one user's completion
- get_course_completion_overview -- bulk completion rates
- list_course_groups / get_group_members -- course groups
- list_cohorts / get_cohort_members -- organizational cohorts
- get_user_grades -- grade report for a user in a course
- get_assignment_grades -- all grades for assignments in a course
- get_upcoming_events -- calendar events and training \
deadlines (call with no args for all upcoming events)
- list_categories -- course categories
- enrol_users -- enrol users into a course
- create_category -- create a course category
- create_course -- create a new course
- update_course -- update course settings
- delete_course -- permanently delete a course
- duplicate_course -- copy a course as a template

## Workflow guidance
Start with list_courses to discover courses and IDs. Use \
list_categories before creating courses. Use duplicate_course \
to clone templates. delete_course is permanent.

For "upcoming deadlines / training deadlines / calendar \
events" with no user specified: call get_upcoming_events() \
with no arguments — it returns all upcoming events across \
all courses for the next 30 days.

For "grades for user X" without a specific course: first \
have the router resolve the name → user ID via moodle-users \
find_user, then list_courses, then call get_user_grades \
for each course.

For "who hasn't completed course X" / "who has completed \
course X" / completion overview queries: ALWAYS call \
get_course_completion_overview(courseid). Do NOT call UTM \
or advanced completion reports for this — those use \
plugin-specific tables and return 0 unless that plugin \
populated them. The standard Moodle completion API used \
by get_course_completion_overview is authoritative. \
Trust the per-user `completed` boolean returned by the \
tool — do NOT second-guess based on individual criterion \
status.

"""
    + _CONFIRM_INSTRUCTIONS
)

_USERS_PROMPT = (
    """\
You manage Moodle user accounts and tenants.

## Available tools
- find_user -- look up users by name/username/email
- list_tenants -- list organizational tenants
- create_user -- create a new user account
- update_user -- update user profile fields
- delete_user -- permanently delete a user
- unsuspend_user -- reactivate a suspended user
- send_message -- send messages to users
- allocate_users_to_tenant -- assign users to a tenant
- suspend_users -- suspend user accounts (system-wide)

## Workflow guidance
Use find_user to look up users by name/username/email. When \
searching by name, use field='name'. create_user requires \
username, firstname, lastname, email. delete_user is permanent.

For update_user: the `department` parameter is a free-form \
string field on the user profile (mdl_user.department), NOT \
a foreign key into Workplace's tool_organisation_department \
table. Do NOT call list_departments or try to "find" the \
department in the org structure — just pass the literal \
string the user provided.

When update_user returns a preview JSON, the rendered \
preview MUST identify the user by their full name plus ID \
(e.g. "Documentation User (#7)"). The preview JSON \
includes a `user` field with this exact label — use it in \
your heading. Do NOT abbreviate to just "user 7" or omit \
the user entirely. Required heading format:
"Here's a preview of changes for **<user>**:" \
where <user> is the JSON's `user` field verbatim.

"""
    + _CONFIRM_INSTRUCTIONS
)

_ORGANISATION_PROMPT = (
    """\
You manage Moodle Workplace organisational structure: \
departments, positions, jobs, and manager relationships.

## Available tools
- list_departments -- list organisational departments
- list_positions -- list organisational positions
- get_team_members -- find users by department/position
- get_potential_parent_departments -- valid parents for dept
- get_potential_parent_positions -- valid parents for position
- create_department -- create a new department
- update_department -- update or move a department
- delete_department -- delete a department
- create_position -- create a new position
- update_position -- update or move a position
- delete_position -- delete a position
- assign_job -- assign a user to a department and position
- delete_job -- delete a job assignment
- assign_manager -- set A as manager OF B (pass B as \
userids, A as managerids)
- unassign_manager -- remove manager relationships

## Workflow guidance
Use get_potential_parent_departments/positions before creating \
or moving. Always set an idnumber when creating \
departments/positions so they can be referenced in updates.

For "who is in the X department" / "team members for X" / \
"members of X department" — call get_team_members directly \
with department=X (the department name or idnumber).  Do \
NOT chain through list_departments first — the tool resolves \
the name/idnumber internally to find the matching members.

"""
    + _CONFIRM_INSTRUCTIONS
)

_CERTIFICATIONS_PROMPT = (
    """\
You manage Moodle Workplace certifications: listing, \
allocating, revoking, archiving, and deleting.

## Available tools
- list_certifications -- list all certifications
- search_certifications -- lightweight name search \
(pass empty string to return all)
- get_certification_allocations -- who holds a certification
- get_user_certifications -- all certs for a user
- get_certification_history -- audit trail for a user's cert
- get_certification_user_details -- detailed allocation view
- certify_user -- mark a user as certified
- revoke_certification -- revoke a user's certification
- deallocate_user_from_certification -- remove user from cert
- archive_certification -- archive a certification
- delete_certification -- permanently delete a certification
- restore_certification -- restore an archived certification
- bulk_deallocate_certification_users -- remove multiple users

## Workflow guidance
Start with list_certifications to discover IDs. Lifecycle: \
Active -> archive -> Archived -> delete (permanent) or \
restore -> Active. Bulk ops use allocation IDs (from \
get_certification_allocations), NOT user IDs.

For generic prompts like "search certifications by name" or \
"find certifications" without a specific query, call \
search_certifications(search="") to return all available \
certifications. Never ask the user for a search term — call \
the tool with an empty string and present the full list.

"""
    + _CONFIRM_INSTRUCTIONS
)

_PROGRAMS_PROMPT = (
    """\
You manage Moodle Workplace programs (learning paths), \
catalogue, and competencies.

## Available tools
- search_programs -- find programs by name
- get_user_program_courses -- courses in a user's program
- search_courses_for_program -- eligible courses for programs
- browse_catalogue -- search the course/program catalogue
- get_user_learning_catalogue -- user's enrolled items
- get_program_content -- courses inside a program
- list_competency_frameworks -- list competency frameworks
- get_user_learning_plans -- user's learning plans
- get_user_competency -- user competency summary
- get_course_competencies -- competencies linked to a course
- allocate_users_to_program -- assign users to a program
- deallocate_user_from_program -- remove user from program
- archive_program -- archive a program (reversible)
- restore_program -- restore an archived program
- delete_program -- permanently delete a program
- duplicate_program -- clone a program
- update_program_visibility -- show/hide a program
- bulk_deallocate_program_users -- remove multiple users
- bulk_reset_program_progress -- reset progress for users

## Workflow guidance
Use search_programs to find programs. Lifecycle: Active -> \
archive -> Archived -> delete (permanent) or restore -> \
Active. Bulk ops use allocation IDs (from \
get_user_program_courses), NOT user IDs.

For "learning catalogue for <user>" use \
get_user_learning_catalogue — it returns the user's \
personal mix of programs and courses with progress \
percentages and due dates. Use browse_catalogue only for \
global keyword search across the whole catalogue.

Use list_competency_frameworks for framework metadata; \
when the user asks for competencies usable in dynamic rule \
conditions, that's a moodle-rules concern \
(search_competencies_for_rule), NOT this skill.

"""
    + _CONFIRM_INSTRUCTIONS
)

_RULES_PROMPT = (
    """\
You manage Moodle Workplace dynamic rules (automation).

## Available tools
- list_dynamic_rules -- discover rules by name, ID, status
- can_enable_rule -- check if a rule meets prerequisites
- get_rule_matching_users -- users currently matching a rule
- get_rule_matched_users -- users historically matched
- search_cohorts_for_rule -- cohorts available for rule \
conditions/outcomes (pass empty string to return all)
- search_competencies_for_rule -- competencies available \
for rule conditions, returned directly from the competency \
table (use this, not list_competency_frameworks; pass \
empty string to return all)
- enable_rule -- enable a dynamic rule
- disable_rule -- disable a dynamic rule
- archive_rule -- archive a dynamic rule
- unarchive_rule -- restore an archived rule
- delete_rule -- permanently delete an archived rule
- duplicate_rule -- clone a dynamic rule
- delete_rule_condition -- remove a condition from a rule
- delete_rule_outcome -- remove an outcome from a rule

## Workflow guidance
Start with list_dynamic_rules to discover rules. Tools accept \
either rule_id or rule_name. State machine: Disabled -> \
enable -> Enabled, Enabled -> disable -> Disabled, any -> \
archive -> Archived, Archived -> unarchive -> Disabled, \
Archived -> delete (permanent).

For "how many users match X" / "count of users matching X" / \
"matching users for rule X" — call get_rule_matching_users \
(NOT list_cohorts or get_cohort_members).  The rule's \
conditions may include cohorts, competencies, or any other \
field; this tool returns the user count without you needing \
to introspect the conditions.

For "can X rule be enabled" / "is X rule enableable" / \
"verify X" — call can_enable_rule (NOT enable_rule with \
confirmed=False).  This checks prerequisites without changing \
state.

For preview-mode write operations (enable_rule, \
disable_rule, archive_rule, unarchive_rule, delete_rule, \
duplicate_rule, delete_rule_condition, \
delete_rule_outcome), you MUST call the write tool itself \
with confirmed=False to get the structured preview JSON. \
Do NOT describe the action from list_dynamic_rules / \
can_enable_rule output alone — those tools' results don't \
include the `action` / `instructions` keys the router \
needs to reconstruct the confirm step. Example flow for \
"enable rule X":
1. list_dynamic_rules(search="X") to resolve the rule ID.
2. (Optional) can_enable_rule(rule_id=N) to check prereqs.
3. enable_rule(rule_id=N, confirmed=False) — this returns \
the preview JSON. Return that JSON unchanged.

When the user asks for competencies that can be used in \
rule conditions, ALWAYS call search_competencies_for_rule \
(this skill) — never call list_competency_frameworks \
(moodle-programs), which returns framework metadata not \
the competency rows themselves.

"""
    + _CONFIRM_INSTRUCTIONS
)

_REPORTING_PROMPT = (
    """\
You manage Moodle reporting: Report Builder custom reports, \
UTM and Advanced Completion reports, and Workplace \
import/export.

## Available tools
- list_reports -- discover Report Builder reports
- get_report_data -- retrieve data from a report (paginated)
- get_utm_report -- UTM completion report by department
- get_adv_comp_report -- Advanced completion report
- get_export_status -- check export job progress
- download_export -- get download URL for completed export
- get_import_status -- check import job progress
- export_workplace_data -- start an export
- import_workplace_data -- import from an export file
- delete_export -- remove a completed export
- delete_import -- remove a completed import

## Workflow guidance
Use list_reports to discover Report Builder reports, then \
get_report_data for data. Use get_utm_report/get_adv_comp_report \
directly for completion reports. For export: start with \
export_workplace_data, poll with get_export_status, then \
download_export. For import: import_workplace_data then poll \
with get_import_status.

If a course is specified by name (not numeric ID), tell \
the router you need moodle-courses to resolve it via \
list_courses first; this skill cannot look up courses by \
name.

## CRITICAL: never fabricate report data
When list_reports returns N reports, your response MUST \
contain exactly those N reports — no inferred names, no \
invented IDs, no extra rows.  If list_reports returns an \
empty list, say "no custom reports exist in this Moodle \
installation" and stop.  The same rule applies to every \
read tool in this skill: report only what the tool \
returned, never plausible-looking extras.

"""
    + _CONFIRM_INSTRUCTIONS
)


# =================================================================
# 1. Courses skill (19 tools)
# =================================================================


def build_courses_skill(client: MoodleClient) -> Skill:
    """Build the moodle-courses skill (19 tools)."""

    @_moodle_tool
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

    @_moodle_tool
    async def get_course_contents(courseid: int) -> str:
        """Get the sections and activities inside a course.

        Args:
            courseid: The Moodle course ID.

        Returns JSON array of sections, each with nested
        modules showing name, type, and completion tracking.
        """
        sections = await client.get_course_contents(courseid)
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

    @_moodle_tool
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

    @_moodle_tool
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
        status = await client.get_course_completion_status(courseid, userid)
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

    @_moodle_tool
    async def get_course_completion_overview(courseid: int) -> str:
        """Get completion status for ALL enrolled users in a course.

        Returns a summary with overall rate and per-user
        breakdown.

        Args:
            courseid: The Moodle course ID.
        """
        enrolled = await client.get_enrolled_users(courseid)

        users_capped = enrolled[:MAX_RESULTS]

        async def _fetch_status(user):
            # Pydantic ValidationError is included because a single
            # malformed per-user record from Moodle would otherwise
            # escape gather() and abort the whole overview.  Treat
            # any per-user failure as "completed: null" instead of
            # surfacing a 500 to the agent.
            try:
                return await client.get_course_completion_status(
                    courseid, user.id
                )
            except (
                MoodleAPIError,
                httpx.HTTPError,
                pydantic.ValidationError,
            ):
                return None

        # Parallelise the per-user round-trips so a 100-user course
        # is bounded by the slowest single call (~200ms) rather
        # than 100 sequential calls (~20s, near the client's 30s
        # timeout).  Result order is preserved by asyncio.gather.
        statuses = await asyncio.gather(
            *(_fetch_status(u) for u in users_capped)
        )

        user_results = []
        completed_count = 0
        for user, status in zip(users_capped, statuses, strict=True):
            if status is None:
                user_results.append(
                    {
                        "userid": user.id,
                        "fullname": user.fullname,
                        "username": user.username,
                        "completed": None,
                        "completions": 0,
                    }
                )
                continue
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

    @_moodle_tool
    async def list_course_groups(courseid: int) -> str:
        """List groups within a course.

        Args:
            courseid: The Moodle course ID.
        """
        groups = await client.get_course_groups(courseid)
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

    @_moodle_tool
    async def get_group_members(groupid: int) -> str:
        """List members of a specific group.

        Args:
            groupid: The Moodle group ID.
        """
        results = await client.get_group_members([groupid])
        if results:
            return json.dumps(
                {
                    "groupid": results[0].groupid,
                    "userids": results[0].userids,
                }
            )
        return json.dumps({"groupid": groupid, "userids": []})

    @_moodle_tool
    async def list_cohorts() -> str:
        """List all organizational cohorts."""
        cohorts = await client.get_cohorts()
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

    @_moodle_tool
    async def get_cohort_members(cohortid: int) -> str:
        """List members of a specific cohort.

        Returns user details (id, username, fullname,
        email) so callers don't need a separate user lookup.

        Args:
            cohortid: The Moodle cohort ID.
        """
        results = await client.get_cohort_members([cohortid])
        if not results:
            return json.dumps({"cohortid": cohortid, "members": []})

        userids = results[0].userids
        members: list[dict] = []
        if userids:
            try:
                users = await client.get_users_by_field(
                    field="id",
                    values=[str(uid) for uid in userids],
                )
                members = [
                    {
                        "id": u.id,
                        "username": u.username,
                        "fullname": u.fullname,
                        "email": u.email,
                    }
                    for u in users
                ]
            except (MoodleAPIError, httpx.HTTPError):
                members = [{"id": uid} for uid in userids]
        return json.dumps(
            {"cohortid": results[0].cohortid, "members": members}
        )

    @_moodle_tool
    async def get_user_grades(courseid: int, userid: int) -> str:
        """Get a user's grade report for a course.

        Args:
            courseid: The Moodle course ID.
            userid: The Moodle user ID.
        """
        raw = await client.get_user_grades(courseid, userid)
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

    @_moodle_tool
    async def get_assignment_grades(courseid: int) -> str:
        """Get all grades for assignments in a course.

        Looks up course contents first to find assignment
        module IDs, then fetches grades for each.

        Args:
            courseid: The Moodle course ID.
        """
        sections = await client.get_course_contents(courseid)

        assign_ids = []
        for section in sections:
            for mod in section.modules:
                if mod.modname == "assign":
                    assign_ids.append(mod.id)

        if not assign_ids:
            return json.dumps(
                {"message": "No assignments found in this course"}
            )

        raw = await client.get_assignment_grades(assign_ids)

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

    @_moodle_tool
    async def get_upcoming_events(
        courseids: str = "",
        days_ahead: int = 30,
    ) -> str:
        """Get upcoming calendar events and deadlines.

        With no arguments, returns all upcoming events
        across all courses for the next 30 days.

        Args:
            courseids: Optional comma-separated course IDs
                       to filter by. Pass '' (empty) to
                       fetch events across every course.
            days_ahead: Number of days to look ahead
                        (default 30).
        """
        cids: list[int] | None = None
        if courseids:
            cids = [int(c.strip()) for c in courseids.split(",") if c.strip()]
        now = int(time.time())
        end = now + days_ahead * 86400
        # The calendar API only returns course events when
        # course IDs are explicitly provided.  When the caller
        # doesn't specify any, fetch all courses first.
        if cids is None:
            all_courses = await client.get_courses()
            cids = [c.id for c in all_courses if c.id != 1]
        events = await client.get_calendar_events(
            courseids=cids, timestart=now, timeend=end
        )
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

    @_moodle_tool
    async def list_categories() -> str:
        """List all course categories."""
        cats = await client.get_categories()
        return json.dumps(
            [
                {
                    "id": c.id,
                    "name": c.name,
                    "parent": c.parent,
                    "coursecount": c.coursecount,
                    "depth": c.depth,
                    "visible": c.visible,
                }
                for c in cats
            ]
        )

    @_moodle_tool
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
                    "course_id": courseid,
                    "role_id": roleid,
                    "user_count": len(user_list),
                }
            )
        enrolments = [
            {"userid": uid, "courseid": courseid, "roleid": roleid}
            for uid in user_list
        ]
        await client.enrol_users(enrolments)
        return json.dumps(
            {
                "success": True,
                "enrolled": len(user_list),
            }
        )

    @_moodle_tool
    async def create_category(
        name: str,
        parent: int = 0,
        description: str = "",
        confirmed: bool = False,
    ) -> str:
        """Create a course category. REQUIRES USER CONFIRMATION.

        Args:
            name: Category name.
            parent: Parent category ID (0 for top-level).
            description: Optional description.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "create_category",
                    "preview": (
                        f"Will create category '{name}' under parent={parent}"
                    ),
                }
            )
        cat_data: dict = {"name": name, "parent": parent}
        if description:
            cat_data["description"] = description
        result = await client.create_categories([cat_data])
        return json.dumps(
            {
                "success": True,
                "created": [{"id": c.id, "name": c.name} for c in result],
            }
        )

    @_moodle_tool
    async def create_course(
        fullname: str,
        shortname: str,
        categoryid: int,
        summary: str = "",
        visible: int = 1,
        format: str = "topics",
        confirmed: bool = False,
    ) -> str:
        """Create a new course. REQUIRES USER CONFIRMATION.

        Args:
            fullname: Full course name.
            shortname: Short identifier (must be unique).
            categoryid: Category to place the course in.
            summary: Optional course summary/description.
            visible: 1=visible, 0=hidden (default 1).
            format: Course format (default 'topics').
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "create_course",
                    "preview": (
                        f"Will create course '{fullname}' "
                        f"(shortname='{shortname}') in "
                        f"category {categoryid}"
                    ),
                }
            )
        course_data: dict = {
            "fullname": fullname,
            "shortname": shortname,
            "categoryid": categoryid,
            "format": format,
            "visible": visible,
        }
        if summary:
            course_data["summary"] = summary
        result = await client.create_courses([course_data])
        return json.dumps(
            {
                "success": True,
                "created": [
                    {"id": c.id, "shortname": c.shortname} for c in result
                ],
            }
        )

    @_moodle_tool
    async def update_course(
        courseid: int,
        fullname: str = "",
        shortname: str = "",
        summary: str = "",
        visible: int = -1,
        confirmed: bool = False,
    ) -> str:
        """Update course settings. REQUIRES USER CONFIRMATION.

        Only non-empty/non-default fields are updated.

        Args:
            courseid: Moodle course ID.
            fullname: New full name (leave empty to skip).
            shortname: New short name (leave empty to skip).
            summary: New summary (leave empty to skip).
            visible: 1=visible, 0=hidden, -1=skip.
            confirmed: Set True only after user approval.
        """
        updates: dict = {"id": courseid}
        if fullname:
            updates["fullname"] = fullname
        if shortname:
            updates["shortname"] = shortname
        if summary:
            updates["summary"] = summary
        if visible >= 0:
            updates["visible"] = visible
        if len(updates) == 1:
            return json.dumps(
                {"error": "No fields to update. Provide at least one field."}
            )
        if not confirmed:
            fields = {k: v for k, v in updates.items() if k != "id"}
            return json.dumps(
                {
                    "action": "update_course",
                    "preview": (f"Will update course {courseid}: {fields}"),
                }
            )
        await client.update_courses([updates])
        return json.dumps({"success": True, "courseid": courseid})

    @_moodle_tool
    async def delete_course(
        courseid: int,
        confirmed: bool = False,
    ) -> str:
        """Permanently delete a course. WARNING: This cannot be undone.

        REQUIRES USER CONFIRMATION.

        Args:
            courseid: Moodle course ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_course",
                    "preview": (
                        f"WARNING: Will PERMANENTLY delete "
                        f"course {courseid}. This cannot be undone."
                    ),
                }
            )
        result = await client.delete_courses([courseid])
        return json.dumps(
            {"success": True, "deleted_courseid": courseid, "result": result}
        )

    @_moodle_tool
    async def duplicate_course(
        courseid: int,
        fullname: str,
        shortname: str,
        categoryid: int,
        visible: int = 1,
        confirmed: bool = False,
    ) -> str:
        """Copy a course as a template. REQUIRES USER CONFIRMATION.

        Args:
            courseid: Source course ID to duplicate.
            fullname: Full name for the new copy.
            shortname: Short name for the new copy (must be unique).
            categoryid: Category for the new copy.
            visible: 1=visible, 0=hidden.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "duplicate_course",
                    "preview": (
                        f"Will duplicate course {courseid} as "
                        f"'{fullname}' (shortname='{shortname}') "
                        f"in category {categoryid}"
                    ),
                }
            )
        result = await client.duplicate_course(
            courseid, fullname, shortname, categoryid, visible
        )
        return json.dumps(
            {
                "success": True,
                "new_course_id": result.id,
                "shortname": result.shortname,
            }
        )

    return Skill(
        metadata=SkillMetadata(
            name="moodle-courses",
            description=(
                "Query and manage courses, categories, "
                "enrollments, completion, grades, calendar "
                "events / training deadlines, groups, and "
                "cohorts"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_COURSES_PROMPT,
        tools=[
            list_courses,
            get_course_contents,
            list_enrolled_users,
            get_completion_status,
            get_course_completion_overview,
            list_course_groups,
            get_group_members,
            list_cohorts,
            get_cohort_members,
            get_user_grades,
            get_assignment_grades,
            get_upcoming_events,
            list_categories,
            enrol_users,
            create_category,
            create_course,
            update_course,
            delete_course,
            duplicate_course,
        ],
    )


# =================================================================
# 2. Users skill (9 tools)
# =================================================================


def build_users_skill(client: MoodleClient) -> Skill:
    """Build the moodle-users skill (9 tools)."""

    @_moodle_tool
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
            return json.dumps(
                {
                    "error": (
                        f"Unsupported field: '{field}'. "
                        f"Use one of: "
                        f"{sorted(exact_fields | name_fields)}"
                    )
                }
            )
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

    @_moodle_tool
    async def list_tenants() -> str:
        """List all organizational tenants."""
        tenants = await client.get_tenants()
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

    @_moodle_tool
    async def create_user(
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str = "",
        confirmed: bool = False,
    ) -> str:
        """Create a new Moodle user account. REQUIRES USER CONFIRMATION.

        If no ``password`` is supplied, Moodle auto-generates one and
        emails it to the user — that is the default behaviour and the
        caller does not need to pass any flag for it.  The previous
        ``createpassword`` parameter was removed because the router
        was observed to send ``createpassword=False`` on the
        confirmation call, which causes Moodle to reject the create
        with "must provide a password, or set createpassword".

        Args:
            username: Login username.
            firstname: User's first name.
            lastname: User's last name.
            email: User's email address.
            password: Optional password. If empty, Moodle generates
                and emails one automatically.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            password_method = (
                "explicit password provided"
                if password
                else "auto-generated and emailed"
            )
            return json.dumps(
                {
                    "action": "create_user",
                    "preview": (
                        f"Will create user '{username}' "
                        f"({firstname} {lastname}, {email})"
                    ),
                    "username": username,
                    "firstname": firstname,
                    "lastname": lastname,
                    "email": email,
                    "password_method": password_method,
                }
            )
        user_data: dict = {
            "username": username,
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
        }
        if password:
            user_data["password"] = password
        else:
            # Always request Moodle-generated password when none given.
            # Hard-coded to 1 because Moodle's create_users rejects the
            # row otherwise — never expose this as an agent-tunable
            # flag.
            user_data["createpassword"] = 1
        result = await client.create_users([user_data])
        return json.dumps(
            {
                "success": True,
                "created": [
                    {"id": u.id, "username": u.username} for u in result
                ],
            }
        )

    @_moodle_tool
    async def update_user(
        userid: str,
        firstname: str = "",
        lastname: str = "",
        email: str = "",
        city: str = "",
        country: str = "",
        description: str = "",
        institution: str = "",
        department: str = "",
        confirmed: bool = False,
    ) -> str:
        """Update a user's profile fields. REQUIRES USER CONFIRMATION.

        Only non-empty fields are updated. Pass the user ID and
        any fields you want to change.

        Args:
            userid: Moodle user ID.
            firstname: New first name (leave empty to skip).
            lastname: New last name (leave empty to skip).
            email: New email (leave empty to skip).
            city: City (leave empty to skip).
            country: Country code, e.g. 'AU' (leave empty to skip).
            description: Profile description (leave empty to skip).
            institution: Institution (leave empty to skip).
            department: Department name (leave empty to skip).
            confirmed: Set True only after user approval.
        """
        uid = _parse_single_id(userid, "user ID")
        if isinstance(uid, str):
            return uid
        updates: dict = {"id": uid}
        for field, value in [
            ("firstname", firstname),
            ("lastname", lastname),
            ("email", email),
            ("city", city),
            ("country", country),
            ("description", description),
            ("institution", institution),
            ("department", department),
        ]:
            if value:
                updates[field] = value
        if len(updates) == 1:
            return json.dumps(
                {"error": "No fields to update. Provide at least one field."}
            )
        # Look up the user's display name so the preview can show
        # "Documentation User (#7)" instead of just "#7". Best-effort:
        # if the lookup fails for any reason we still produce a
        # usable preview with the bare ID.
        user_label = f"#{uid}"
        try:
            users = await client.get_users_by_field(
                field="id", values=[str(uid)]
            )
            if users:
                user_label = f"{users[0].fullname} (#{uid})"
        except Exception:  # noqa: BLE001 - intentionally broad
            pass

        if not confirmed:
            fields = {k: v for k, v in updates.items() if k != "id"}
            payload = {
                "action": "update_user",
                "preview": (f"Will update {user_label} with: {fields}"),
                "user": user_label,
                "user_id": uid,
                "changes": fields,
            }
            for k, v in fields.items():
                payload[k] = v
            return json.dumps(payload)
        await client.update_users([updates])
        return json.dumps({"success": True, "userid": uid, "user": user_label})

    @_moodle_tool
    async def delete_user(
        userid: str,
        confirmed: bool = False,
    ) -> str:
        """Permanently delete a user. WARNING: This cannot be undone.

        REQUIRES USER CONFIRMATION.

        Args:
            userid: Moodle user ID.
            confirmed: Set True only after user approval.
        """
        uid = _parse_single_id(userid, "user ID")
        if isinstance(uid, str):
            return uid
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_user",
                    "preview": (
                        f"WARNING: Will PERMANENTLY delete "
                        f"user {uid}. This cannot be undone."
                    ),
                }
            )
        await client.delete_users([uid])
        return json.dumps({"success": True, "deleted_userid": uid})

    @_moodle_tool
    async def unsuspend_user(
        userid: str,
        confirmed: bool = False,
    ) -> str:
        """Reactivate a suspended user. REQUIRES USER CONFIRMATION.

        Args:
            userid: Moodle user ID.
            confirmed: Set True only after user approval.
        """
        uid = _parse_single_id(userid, "user ID")
        if isinstance(uid, str):
            return uid
        if not confirmed:
            return json.dumps(
                {
                    "action": "unsuspend_user",
                    "preview": f"Will unsuspend (reactivate) user {uid}",
                }
            )
        await client.update_users([{"id": uid, "suspended": 0}])
        return json.dumps({"success": True, "unsuspended_userid": uid})

    @_moodle_tool
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
                        f'user(s): "{text[:100]}"'
                    ),
                    "user_ids": user_list,
                }
            )
        messages = [
            {"touserid": uid, "text": text, "textformat": 0}
            for uid in user_list
        ]
        result = await client.send_messages(messages)
        return json.dumps(
            {
                "success": True,
                "sent": len(user_list),
                "results": result,
            }
        )

    @_moodle_tool
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
                }
            )
        allocations = [
            {"userid": uid, "tenantid": tenantid} for uid in user_list
        ]
        result = await client.allocate_users_to_tenant(allocations)
        return json.dumps(
            {
                "success": True,
                "allocated": len(user_list),
                "tenantid": tenantid,
                "result": result,
            }
        )

    @_moodle_tool
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
                }
            )
        result = await client.suspend_tenant_users(user_list)
        return json.dumps(
            {
                "success": True,
                "suspended": len(user_list),
                "result": result,
            }
        )

    return Skill(
        metadata=SkillMetadata(
            name="moodle-users",
            description=(
                "Look up users, list tenants, "
                "create/update/suspend/delete Moodle users, "
                "send messages"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_USERS_PROMPT,
        tools=[
            find_user,
            list_tenants,
            create_user,
            update_user,
            delete_user,
            unsuspend_user,
            send_message,
            allocate_users_to_tenant,
            suspend_users,
        ],
    )


# =================================================================
# 3. Organisation skill (15 tools)
# =================================================================


def build_organisation_skill(client: MoodleClient) -> Skill:
    """Build the moodle-organisation skill (15 tools)."""

    @_moodle_tool
    async def list_departments(search: str = "") -> str:
        """List organisational departments.

        Args:
            search: Optional search string (default "" = all).

        Implementation note: Moodle's underlying endpoint always
        returns the full department set (search filtering is purely
        client-side), so we fetch once and filter in-process.  The
        MAX_RESULTS cap in ``client.get_departments`` applies to the
        unfiltered set; a search that should match items past the
        cap will miss them — same pre-existing limitation that
        already affects parent resolution.
        """
        all_depts = await client.get_departments("")
        id_to_idnumber = {d.id: d.idnumber for d in all_depts}
        if search:
            search_lower = search.lower()
            filtered = [d for d in all_depts if search_lower in d.name.lower()]
        else:
            filtered = all_depts
        return json.dumps(
            [
                {
                    "name": d.name,
                    "idnumber": d.idnumber,
                    "parent": id_to_idnumber.get(d.parentid, ""),
                }
                for d in filtered
            ]
        )

    @_moodle_tool
    async def list_positions(search: str = "") -> str:
        """List organisational positions.

        Args:
            search: Optional search string (default "" = all).

        Implementation note: Moodle's underlying endpoint always
        returns the full position set (search filtering is purely
        client-side), so we fetch once and filter in-process.  The
        MAX_RESULTS cap in ``client.get_positions`` applies to the
        unfiltered set; a search that should match items past the
        cap will miss them — same pre-existing limitation that
        already affects parent resolution.
        """
        all_positions = await client.get_positions("")
        id_to_idnumber = {p.id: p.idnumber for p in all_positions}
        if search:
            search_lower = search.lower()
            filtered = [
                p for p in all_positions if search_lower in p.name.lower()
            ]
        else:
            filtered = all_positions
        return json.dumps(
            [
                {
                    "name": p.name,
                    "idnumber": p.idnumber,
                    "parent": id_to_idnumber.get(p.parentid, ""),
                }
                for p in filtered
            ]
        )

    @_moodle_tool
    async def get_team_members(
        department: str = "",
        position: str = "",
        search: str = "",
    ) -> str:
        """Find users by department, position, or name.

        Returns all users matching the filters (not scoped to a
        particular manager).  ``department`` / ``position`` are
        resolved by exact (case-insensitive) name or idnumber
        match.  If a query string is ambiguous (e.g. matches
        multiple departments) the wrapper surfaces an error
        listing the candidates so the caller can disambiguate by
        idnumber.  Members are filtered by the resolved
        department's / position's canonical name against the
        Workplace jobs system report — the report endpoint
        accepts no filter parameters, so filtering happens
        client-side here in the wrapper.

        Args:
            department: Optional department name or idnumber to
                filter by.
            position: Optional position name or idnumber to filter
                by.
            search: Optional user-name search string (matches
                firstname/lastname).
        """
        department_match = None
        position_match = None

        if department:
            depts = await client.get_departments("")
            target = department.lower()
            matches = [
                d
                for d in depts
                if d.idnumber == department or d.name.lower() == target
            ]
            if len(matches) == 0:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"No department matches {department!r} "
                            f"(by idnumber or name)"
                        ),
                    }
                )
            if len(matches) > 1:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Multiple departments match "
                            f"{department!r}; specify by idnumber."
                        ),
                        "matches": [
                            {"name": d.name, "idnumber": d.idnumber}
                            for d in matches
                        ],
                    }
                )
            department_match = matches[0]

        if position:
            positions = await client.get_positions("")
            target = position.lower()
            matches = [
                p
                for p in positions
                if p.idnumber == position or p.name.lower() == target
            ]
            if len(matches) == 0:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"No position matches {position!r} "
                            f"(by idnumber or name)"
                        ),
                    }
                )
            if len(matches) > 1:
                return json.dumps(
                    {
                        "status": "error",
                        "error": (
                            f"Multiple positions match {position!r}; "
                            f"specify by idnumber."
                        ),
                        "matches": [
                            {"name": p.name, "idnumber": p.idnumber}
                            for p in matches
                        ],
                    }
                )
            position_match = matches[0]

        members = await client.get_department_members(search)
        if department_match is not None:
            target = department_match.name.lower()
            members = [
                m for m in members if m.departmentname.lower() == target
            ]
        if position_match is not None:
            target = position_match.name.lower()
            members = [m for m in members if m.positionname.lower() == target]
        return json.dumps(
            [
                {
                    "userid": m.userid,
                    "fullname": m.fullname,
                    "departmentname": m.departmentname,
                    "positionname": m.positionname,
                }
                for m in members
            ]
        )

    @_moodle_tool
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
        parents = await client.get_potential_parent_departments(
            search=search, departmentid=departmentid
        )
        return json.dumps(
            [{"id": p.id, "name": p.name, "path": p.path} for p in parents]
        )

    @_moodle_tool
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
        parents = await client.get_potential_parent_positions(
            search=search, positionid=positionid
        )
        return json.dumps(
            [{"id": p.id, "name": p.name, "path": p.path} for p in parents]
        )

    @_moodle_tool
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
                {
                    "action": "create_department",
                    "preview": f"Create department '{name}'",
                    "name": name,
                    "idnumber": idnumber or "(none)",
                    "parent": parent or "(top-level)",
                    "description": description or "(none)",
                }
            )
        created, warnings = await client.create_departments([dept])
        return json.dumps(
            {
                "created": [
                    {"name": c.name, "idnumber": c.idnumber} for c in created
                ],
                "warnings": warnings,
            }
        )

    @_moodle_tool
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
                {
                    "action": "update_department",
                    "preview": f"Update department '{idnumber}'",
                    "changes": dept,
                }
            )
        updated, warnings = await client.update_departments([dept])
        return json.dumps(
            {
                "updated": [{"idnumber": u.idnumber} for u in updated],
                "warnings": warnings,
            }
        )

    @_moodle_tool
    async def delete_department(
        idnumber: str,
        confirmed: bool = False,
    ) -> str:
        """Delete a department. REQUIRES USER CONFIRMATION.

        The department must not have any jobs in its hierarchy.

        If the user named the department by name (e.g. "the
        Security department") and you don't already know the
        idnumber, FIRST call ``list_departments`` to look it up;
        the response includes the idnumber.  This tool only
        accepts idnumber — it does not resolve names.

        Args:
            idnumber: Department idnumber.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_department",
                    "preview": f"Delete department '{idnumber}'",
                }
            )
        # Fetch every department, exact-match the idnumber.  Filtering
        # the server-side search by idnumber would be wrong — that
        # search is name-based, and idnumber is often unrelated to
        # the name (e.g. "ENG" / "Engineering").
        depts = await client.get_departments("")
        match = next((d for d in depts if d.idnumber == idnumber), None)
        if match is None:
            return json.dumps(
                {
                    "status": "error",
                    "error": (f"No department with idnumber {idnumber!r}"),
                }
            )
        result = await client.delete_department(match.id)
        return json.dumps({"status": "ok", "result": result})

    @_moodle_tool
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
                {
                    "action": "create_position",
                    "preview": f"Create position '{name}'",
                    "position": pos,
                }
            )
        created, warnings = await client.create_positions([pos])
        return json.dumps(
            {
                "created": [
                    {"name": c.name, "idnumber": c.idnumber} for c in created
                ],
                "warnings": warnings,
            }
        )

    @_moodle_tool
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
                {
                    "action": "update_position",
                    "preview": f"Update position '{idnumber}'",
                    "changes": pos,
                }
            )
        updated, warnings = await client.update_positions([pos])
        return json.dumps(
            {
                "updated": [{"idnumber": u.idnumber} for u in updated],
                "warnings": warnings,
            }
        )

    @_moodle_tool
    async def delete_position(
        idnumber: str,
        confirmed: bool = False,
    ) -> str:
        """Delete a position. REQUIRES USER CONFIRMATION.

        The position must not have any jobs assigned.

        If the user named the position by name and you don't
        already know the idnumber, FIRST call ``list_positions``
        to look it up; the response includes the idnumber.  This
        tool only accepts idnumber — it does not resolve names.

        Args:
            idnumber: Position idnumber.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_position",
                    "preview": f"Delete position '{idnumber}'",
                }
            )
        # Same rationale as delete_department: search the full set
        # then exact-match the idnumber.  The server-side search is
        # name-based.
        positions = await client.get_positions("")
        match = next((p for p in positions if p.idnumber == idnumber), None)
        if match is None:
            return json.dumps(
                {
                    "status": "error",
                    "error": (f"No position with idnumber {idnumber!r}"),
                }
            )
        result = await client.delete_position(match.id)
        return json.dumps({"status": "ok", "result": result})

    @_moodle_tool
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
                }
            )
        result = await client.create_job(userid, department, position)
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "department": department,
                "position": position,
                "result": result,
            }
        )

    @_moodle_tool
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
                {
                    "action": "delete_job",
                    "preview": f"Delete job id={job_id}",
                }
            )
        result = await client.delete_job(job_id)
        return json.dumps(result)

    @_moodle_tool
    async def assign_manager(
        userids: str,
        managerids: str,
        confirmed: bool = False,
    ) -> str:
        """Set manager relationships for users.

        Example: to assign Bob as Carol's manager, pass
        userids=carol_id, managerids=bob_id.

        Pass confirmed=True only after the user has reviewed
        and approved the action.

        Args:
            userids: Comma-separated subordinate user IDs
                     (the people who will report TO the
                     manager).
            managerids: Comma-separated manager user IDs
                        (the people who will become the
                        manager).
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
                }
            )
        result = await client.assign_managers(user_list, manager_list)
        return json.dumps(
            {
                "success": True,
                "user_ids": user_list,
                "manager_ids": manager_list,
                "result": result,
            }
        )

    @_moodle_tool
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
        uid_list = _parse_ids(userids, "user IDs")
        if isinstance(uid_list, str):
            return uid_list
        mid_list = _parse_ids(managerids, "manager IDs")
        if isinstance(mid_list, str):
            return mid_list
        if not confirmed:
            return json.dumps(
                {
                    "action": "unassign_manager",
                    "preview": (
                        f"Unassign managers {mid_list} from users {uid_list}"
                    ),
                    "unassign_all": unassign_all,
                }
            )
        result = await client.unassign_managers(
            uid_list, mid_list, unassign_all=unassign_all
        )
        return json.dumps(result)

    return Skill(
        metadata=SkillMetadata(
            name="moodle-organisation",
            description=(
                "Manage departments, positions, jobs, "
                "and manager relationships in Moodle "
                "Workplace"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_ORGANISATION_PROMPT,
        tools=[
            list_departments,
            list_positions,
            get_team_members,
            get_potential_parent_departments,
            get_potential_parent_positions,
            create_department,
            update_department,
            delete_department,
            create_position,
            update_position,
            delete_position,
            assign_job,
            delete_job,
            assign_manager,
            unassign_manager,
        ],
    )


# =================================================================
# 4. Certifications skill (13 tools)
# =================================================================


def build_certifications_skill(client: MoodleClient) -> Skill:
    """Build the moodle-certifications skill (13 tools)."""

    @_moodle_tool
    async def list_certifications(tenantid: int = 0) -> str:
        """List all certifications in the system.

        Args:
            tenantid: Optional tenant ID to filter by
                      (default 0 = all tenants).
        """
        certs = await client.get_certifications(tenantid)
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

    @_moodle_tool
    async def search_certifications(
        search: str = "",
    ) -> str:
        """Search certifications by name.

        Lightweight search returning id and fullname.
        Use list_certifications for full details.

        Args:
            search: Optional search term to filter by name.
                    Pass '' (empty) to return all
                    certifications.
        """
        results = await client.search_certifications(search=search)
        return json.dumps(
            [{"id": c.id, "fullname": c.fullname} for c in results]
        )

    @_moodle_tool
    async def get_certification_allocations(
        certificationid: int,
    ) -> str:
        """List users allocated to a specific certification.

        Args:
            certificationid: The certification ID.
        """
        allocs = await client.get_certification_allocations(certificationid)
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

    @_moodle_tool
    async def get_user_certifications(userid: int) -> str:
        """Get all certifications for a specific user.

        Args:
            userid: The Moodle user ID.
        """
        allocs = await client.get_user_certification_allocations(userid)
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

    @_moodle_tool
    async def get_certification_history(
        certificationid: int,
        userid: int,
    ) -> str:
        """Get the audit trail for a user's certification.

        Args:
            certificationid: The certification ID.
            userid: The Moodle user ID.
        """
        entries = await client.get_certification_user_log(
            certificationid, userid
        )
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

    @_moodle_tool
    async def get_certification_user_details(
        certificationid: int,
        userid: int,
    ) -> str:
        """Get detailed user+certification allocation view.

        Args:
            certificationid: The certification ID.
            userid: The Moodle user ID.
        """
        details = await client.get_certification_user_allocation(
            certificationid, userid
        )
        return json.dumps(details)

    @_moodle_tool
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
                }
            )
        result = await client.certify_user(certificationid, uid)
        return json.dumps(
            {
                "success": True,
                "userid": uid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @_moodle_tool
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
                }
            )
        result = await client.revoke_certification(certificationid, uid)
        return json.dumps(
            {
                "success": True,
                "userid": uid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @_moodle_tool
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
                }
            )
        result = await client.deallocate_user_from_certification(
            certificationid, userid
        )
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @_moodle_tool
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
                        f"Will archive certification {certificationid}"
                    ),
                    "certificationid": certificationid,
                }
            )
        result = await client.archive_certification(certificationid)
        return json.dumps(
            {
                "success": True,
                "certificationid": certificationid,
                "result": result,
            }
        )

    @_moodle_tool
    async def delete_certification(
        certification_id: int,
        confirmed: bool = False,
    ) -> str:
        """Permanently delete a certification.
        REQUIRES USER CONFIRMATION.

        The certification must be archived first -- use
        archive_certification before calling this. This
        cannot be undone.

        Args:
            certification_id: Moodle certification ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_certification",
                    "preview": (f"DELETE certification id={certification_id}"),
                }
            )
        result = await client.delete_certification(certification_id)
        return json.dumps(result)

    @_moodle_tool
    async def restore_certification(
        certification_id: int,
        confirmed: bool = False,
    ) -> str:
        """Restore an archived certification.
        REQUIRES USER CONFIRMATION.

        The certification must already be archived. Use
        archive_certification first if it is currently
        active.

        Args:
            certification_id: Moodle certification ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "restore_certification",
                    "preview": (
                        f"Restore certification id={certification_id}"
                    ),
                }
            )
        result = await client.restore_certification(certification_id)
        return json.dumps(result)

    @_moodle_tool
    async def bulk_deallocate_certification_users(
        allocation_ids: str,
        confirmed: bool = False,
    ) -> str:
        """Remove multiple users from a certification.
        REQUIRES USER CONFIRMATION.

        Takes certification-user allocation IDs (NOT user IDs).
        Get allocation IDs from get_certification_allocations.

        Args:
            allocation_ids: Comma-separated allocation IDs.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(allocation_ids, "allocation IDs")
        if isinstance(parsed, str):
            return parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "bulk_deallocate_certification_users",
                    "preview": (
                        f"Deallocate {len(parsed)} certification user(s)"
                    ),
                    "allocation_ids": parsed,
                }
            )
        result = await client.bulk_deallocate_certification_users(parsed)
        return json.dumps(result.model_dump())

    return Skill(
        metadata=SkillMetadata(
            name="moodle-certifications",
            description=(
                "List, search, allocate, revoke, archive, "
                "and delete Moodle Workplace certifications"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_CERTIFICATIONS_PROMPT,
        tools=[
            list_certifications,
            search_certifications,
            get_certification_allocations,
            get_user_certifications,
            get_certification_history,
            get_certification_user_details,
            certify_user,
            revoke_certification,
            deallocate_user_from_certification,
            archive_certification,
            delete_certification,
            restore_certification,
            bulk_deallocate_certification_users,
        ],
    )


# =================================================================
# 5. Programs skill (19 tools)
# =================================================================


def build_programs_skill(client: MoodleClient) -> Skill:
    """Build the moodle-programs skill (19 tools)."""

    @_moodle_tool
    async def search_programs(search: str = "") -> str:
        """Search for learning programs by name.

        Args:
            search: Optional search string to filter
                    programs (default "" = all).
        """
        programs = await client.search_programs(search)
        return json.dumps(
            [
                {
                    "id": p.id,
                    "fullname": p.fullname,
                }
                for p in programs
            ]
        )

    @_moodle_tool
    async def get_user_program_courses(userid: int) -> str:
        """Get courses in a user's assigned programs with progress.

        Args:
            userid: The Moodle user ID.
        """
        courses = await client.get_user_program_courses(userid)
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

    @_moodle_tool
    async def search_courses_for_program(search: str = "") -> str:
        """Search for courses eligible for programs.

        Args:
            search: Optional search string (default "" = all).
        """
        courses = await client.search_courses_for_program(search)
        return json.dumps(
            [{"id": c.id, "fullname": c.fullname} for c in courses]
        )

    @_moodle_tool
    async def browse_catalogue(query: str = "") -> str:
        """Search the course/program catalogue.

        Args:
            query: Optional search query (default "" = all).
        """
        items = await client.get_catalogue_page(query)
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

    @_moodle_tool
    async def get_user_learning_catalogue(
        userid: int = 0,
        search: str = "",
    ) -> str:
        """Get a user's enrolled items with progress.

        Args:
            userid: The Moodle user ID (0 = current user).
            search: Optional search string.
        """
        items = await client.get_user_catalogue(userid, search)
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

    @_moodle_tool
    async def get_program_content(
        programid: int,
        userid: int = 0,
    ) -> str:
        """Get the courses inside a program.

        Args:
            programid: The program ID.
            userid: Optional user ID (0 = current user).
        """
        content = await client.get_program_content(programid, userid)
        return json.dumps(content)

    @_moodle_tool
    async def list_competency_frameworks() -> str:
        """List all competency frameworks."""
        frameworks = await client.get_competency_frameworks()
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

    @_moodle_tool
    async def get_user_learning_plans(userid: int) -> str:
        """Get a user's learning plans.

        Args:
            userid: The Moodle user ID.
        """
        plans = await client.get_user_learning_plans(userid)
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

    @_moodle_tool
    async def get_user_competency(
        userid: int,
        competencyid: int,
    ) -> str:
        """Get a user's competency summary.

        Args:
            userid: The Moodle user ID.
            competencyid: The competency ID.
        """
        summary = await client.get_user_competency_summary(
            userid, competencyid
        )
        return json.dumps(summary)

    @_moodle_tool
    async def get_course_competencies(courseid: int) -> str:
        """Get competencies linked to a course.

        Args:
            courseid: The Moodle course ID.
        """
        competencies = await client.get_course_competencies(courseid)
        return json.dumps(competencies)

    @_moodle_tool
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
                }
            )
        result = await client.allocate_users_to_program(programid, user_list)
        return json.dumps(
            {
                "success": True,
                "allocated": len(user_list),
                "programid": programid,
                "result": result,
            }
        )

    @_moodle_tool
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
                        f"Will remove user {userid} from program {programid}"
                    ),
                    "userid": userid,
                    "programid": programid,
                }
            )
        result = await client.deallocate_user_from_program(programid, userid)
        return json.dumps(
            {
                "success": True,
                "userid": userid,
                "programid": programid,
                "result": result,
            }
        )

    @_moodle_tool
    async def archive_program(
        program_id: int,
        confirmed: bool = False,
    ) -> str:
        """Archive a program (reversible). REQUIRES USER CONFIRMATION.

        Moves the program from active to archived state.
        Archived programs can be restored or permanently deleted.

        Args:
            program_id: Moodle program ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "archive_program",
                    "preview": f"Archive program id={program_id}",
                }
            )
        result = await client.archive_program(program_id)
        return json.dumps(result)

    @_moodle_tool
    async def restore_program(
        program_id: int,
        confirmed: bool = False,
    ) -> str:
        """Restore an archived program. REQUIRES USER CONFIRMATION.

        The program must already be archived. Use
        archive_program first if it is currently active.

        Args:
            program_id: Moodle program ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "restore_program",
                    "preview": f"Restore program id={program_id}",
                }
            )
        result = await client.restore_program(program_id)
        return json.dumps(result)

    @_moodle_tool
    async def delete_program(
        program_id: int,
        confirmed: bool = False,
    ) -> str:
        """Permanently delete a program. REQUIRES USER CONFIRMATION.

        The program must be archived first -- use
        archive_program before calling this. This cannot
        be undone.

        Args:
            program_id: Moodle program ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_program",
                    "preview": f"DELETE program id={program_id}",
                }
            )
        result = await client.delete_program(program_id)
        return json.dumps(result)

    @_moodle_tool
    async def duplicate_program(
        program_id: int,
        confirmed: bool = False,
    ) -> str:
        """Clone a program. REQUIRES USER CONFIRMATION.

        Creates a copy of the program with its structure.
        Returns the new program ID.

        Args:
            program_id: Moodle program ID to duplicate.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "duplicate_program",
                    "preview": f"Duplicate program id={program_id}",
                }
            )
        dup = await client.duplicate_program(program_id)
        return json.dumps(
            {
                "duplicatedprogramid": dup.duplicatedprogramid,
                "redirecturl": dup.redirecturl,
            }
        )

    @_moodle_tool
    async def update_program_visibility(
        program_id: int,
        visible: int,
        confirmed: bool = False,
    ) -> str:
        """Show or hide a program. REQUIRES USER CONFIRMATION.

        Args:
            program_id: Moodle program ID.
            visible: 1 to show, 0 to hide.
            confirmed: Set True only after user approval.
        """
        label = "visible" if visible else "hidden"
        if not confirmed:
            return json.dumps(
                {
                    "action": "update_program_visibility",
                    "preview": (f"Set program id={program_id} to {label}"),
                }
            )
        result = await client.update_program_visibility(program_id, visible)
        return json.dumps(result)

    @_moodle_tool
    async def bulk_deallocate_program_users(
        allocation_ids: str,
        confirmed: bool = False,
    ) -> str:
        """Remove multiple users from a program.
        REQUIRES USER CONFIRMATION.

        Takes program-user allocation IDs (NOT user IDs).
        Get allocation IDs from get_user_program_courses.

        Args:
            allocation_ids: Comma-separated allocation IDs.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(allocation_ids, "allocation IDs")
        if isinstance(parsed, str):
            return parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "bulk_deallocate_program_users",
                    "preview": (f"Deallocate {len(parsed)} program user(s)"),
                    "allocation_ids": parsed,
                }
            )
        result = await client.bulk_deallocate_program_users(parsed)
        return json.dumps(result.model_dump())

    @_moodle_tool
    async def bulk_reset_program_progress(
        allocation_ids: str,
        confirmed: bool = False,
    ) -> str:
        """Reset progress for multiple program users.
        REQUIRES USER CONFIRMATION.

        Takes program-user allocation IDs (NOT user IDs).
        Get allocation IDs from get_user_program_courses.

        Args:
            allocation_ids: Comma-separated allocation IDs.
            confirmed: Set True only after user approval.
        """
        parsed = _parse_ids(allocation_ids, "allocation IDs")
        if isinstance(parsed, str):
            return parsed
        if not confirmed:
            return json.dumps(
                {
                    "action": "bulk_reset_program_progress",
                    "preview": (
                        f"Reset progress for {len(parsed)} program user(s)"
                    ),
                    "allocation_ids": parsed,
                }
            )
        result = await client.bulk_reset_program_progress(parsed)
        return json.dumps(result.model_dump())

    return Skill(
        metadata=SkillMetadata(
            name="moodle-programs",
            description=(
                "Search and manage programs, personal "
                "learning catalogues with progress and due "
                "dates, competency frameworks, and learning "
                "plans"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_PROGRAMS_PROMPT,
        tools=[
            search_programs,
            get_user_program_courses,
            search_courses_for_program,
            browse_catalogue,
            get_user_learning_catalogue,
            get_program_content,
            list_competency_frameworks,
            get_user_learning_plans,
            get_user_competency,
            get_course_competencies,
            allocate_users_to_program,
            deallocate_user_from_program,
            archive_program,
            restore_program,
            delete_program,
            duplicate_program,
            update_program_visibility,
            bulk_deallocate_program_users,
            bulk_reset_program_progress,
        ],
    )


# =================================================================
# 6. Rules skill (14 tools)
# =================================================================


def build_rules_skill(client: MoodleClient) -> Skill:
    """Build the moodle-rules skill (14 tools)."""

    # -- Tool functions --

    @_moodle_tool
    async def list_dynamic_rules() -> str:
        """List all dynamic rules with names, IDs, and status.

        Returns a table of automation rules showing each rule's
        ID, name, enabled/disabled state, conditions, and actions.
        Use the rule ID or name from this list for other dynamic
        rule tools.
        """
        rules = await client.list_dynamic_rules()
        return json.dumps(rules)

    @_moodle_tool
    async def can_enable_rule(rule_id: int = 0, rule_name: str = "") -> str:
        """Check whether a dynamic rule meets prerequisites to be enabled.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        result = await client.can_enable_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def get_rule_matching_users(
        rule_id: int = 0, rule_name: str = ""
    ) -> str:
        """Count users currently matching a dynamic rule's conditions.

        Use this for any "how many users match X" or "count of
        users for rule X" question.  Do NOT call list_cohorts or
        get_cohort_members instead — the rule may include cohort
        conditions but the user-count answer requires this tool,
        not manual condition inspection.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        result = await client.count_matching_users(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def get_rule_matched_users(
        rule_id: int = 0, rule_name: str = ""
    ) -> str:
        """Count users historically matched by a dynamic rule.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        result = await client.count_matched_users(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def search_cohorts_for_rule(search: str = "") -> str:
        """Search cohorts available for dynamic rule conditions/outcomes.

        Args:
            search: Optional search term to filter by name.
                    Pass '' (empty) to return all cohorts
                    available for rule conditions.
        """
        items = await client.search_cohorts_for_rule(search)
        return json.dumps([{"id": i.id, "name": i.name} for i in items])

    @_moodle_tool
    async def search_competencies_for_rule(search: str = "") -> str:
        """Search competencies available for dynamic rule conditions.

        Returns competencies from the Moodle competency table
        directly — independent of framework associations.
        Use this (not list_competency_frameworks) when the
        user asks for competencies usable in dynamic rule
        conditions.

        Args:
            search: Optional search term to filter by name.
                    Pass '' (empty) to return all
                    competencies available for rule
                    conditions.
        """
        items = await client.search_competencies_for_rule(search)
        return json.dumps(
            [{"id": i.id, "shortname": i.shortname} for i in items]
        )

    @_moodle_tool
    async def enable_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Enable a dynamic rule. REQUIRES USER CONFIRMATION.

        Activates the rule so it begins matching users and
        applying outcomes.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "enable_rule",
                    "preview": f"Enable dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.enable_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def disable_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Disable a dynamic rule. REQUIRES USER CONFIRMATION.

        Stops the rule from matching users and applying outcomes.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "disable_rule",
                    "preview": f"Disable dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.disable_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def archive_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Archive a dynamic rule (reversible). REQUIRES USER CONFIRMATION.

        Moves the rule to archived state. Archived rules can be
        restored with unarchive_rule or permanently deleted.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "archive_rule",
                    "preview": f"Archive dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.archive_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def unarchive_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Restore an archived dynamic rule. REQUIRES USER CONFIRMATION.

        Moves the rule back to disabled state so it can be
        re-enabled.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "unarchive_rule",
                    "preview": f"Unarchive dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.unarchive_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def delete_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Permanently DELETE a dynamic rule. REQUIRES USER CONFIRMATION.

        The rule must be archived first. This action is irreversible.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_rule",
                    "preview": f"DELETE dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.delete_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def duplicate_rule(
        rule_id: int = 0,
        rule_name: str = "",
        confirmed: bool = False,
    ) -> str:
        """Clone a dynamic rule. REQUIRES USER CONFIRMATION.

        Creates a copy of the rule with the same conditions and
        outcomes. The new rule is created in disabled state.

        Args:
            rule_id: Moodle dynamic rule ID to copy.
            rule_name: Rule name (alternative to rule_id).
            confirmed: Set True only after user approval.
        """
        resolved = await _resolve_rule_id(client, rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {
                    "action": "duplicate_rule",
                    "preview": f"Duplicate dynamic rule id={resolved}",
                    "rule_id": resolved,
                }
            )
        result = await client.duplicate_rule(resolved)
        return json.dumps(result)

    @_moodle_tool
    async def delete_rule_condition(
        instanceid: int,
        confirmed: bool = False,
    ) -> str:
        """Remove a condition from a dynamic rule. REQUIRES USER CONFIRMATION.

        Args:
            instanceid: The condition instance ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_rule_condition",
                    "preview": (
                        f"Delete condition id={instanceid} from dynamic rule"
                    ),
                    "instanceid": instanceid,
                }
            )
        result = await client.delete_condition(instanceid)
        return json.dumps(result)

    @_moodle_tool
    async def delete_rule_outcome(
        instanceid: int,
        confirmed: bool = False,
    ) -> str:
        """Remove an outcome from a dynamic rule. REQUIRES USER CONFIRMATION.

        Args:
            instanceid: The outcome instance ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_rule_outcome",
                    "preview": (
                        f"Delete outcome id={instanceid} from dynamic rule"
                    ),
                    "instanceid": instanceid,
                }
            )
        result = await client.delete_outcome(instanceid)
        return json.dumps(result)

    return Skill(
        metadata=SkillMetadata(
            name="moodle-rules",
            description=(
                "List, enable, disable, archive, manage "
                "Moodle Workplace dynamic rules; search "
                "cohorts and competencies for rule "
                "conditions"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_RULES_PROMPT,
        tools=[
            list_dynamic_rules,
            can_enable_rule,
            get_rule_matching_users,
            get_rule_matched_users,
            search_cohorts_for_rule,
            search_competencies_for_rule,
            enable_rule,
            disable_rule,
            archive_rule,
            unarchive_rule,
            delete_rule,
            duplicate_rule,
            delete_rule_condition,
            delete_rule_outcome,
        ],
    )


# =================================================================
# 7. Reporting skill (11 tools)
# =================================================================


def build_reporting_skill(client: MoodleClient) -> Skill:
    """Build the moodle-reporting skill (11 tools)."""

    @_moodle_tool
    async def list_reports() -> str:
        """List all custom reports available in Report Builder.

        Returns JSON with id, name, source type, and
        modification time for each report. Use the report
        id in get_report_data to retrieve actual data.
        """
        reports = await client.list_reports()
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

    @_moodle_tool
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
        details, data = await client.retrieve_report(
            reportid, page=page, perpage=perpage
        )
        return json.dumps(
            {
                "report_name": details.name,
                "source": details.sourcename,
                "headers": data.headers,
                "rows": [
                    [_strip_html(c) for c in row.columns] for row in data.rows
                ],
                "total_rows": data.totalrowcount,
                "page": page,
                "perpage": perpage,
            }
        )

    @_moodle_tool
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
        rows, totalcount = await client.get_utm_report(
            courseid,
            departmentid=departmentid,
            completionstatus=completionstatus,
        )
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

    @_moodle_tool
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
        rows, totalcount = await client.get_adv_comp_report(
            courseid,
            completionstatus=completionstatus,
        )
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

    @_moodle_tool
    async def get_export_status(export_id: int) -> str:
        """Check the progress of a Workplace export job.

        Args:
            export_id: The export job ID.
        """
        status = await client.get_export_status(export_id)
        return json.dumps(
            {
                "status": status.status,
                "message": status.statusmessage,
                "progress": status.progress,
                "is_complete": status.is_complete,
                "is_error": status.is_error,
            }
        )

    @_moodle_tool
    async def download_export(export_id: int) -> str:
        """Get download info for a completed Workplace export.

        Args:
            export_id: The export job ID.
        """
        result = await client.get_export_file(export_id)
        return json.dumps(result)

    @_moodle_tool
    async def get_import_status(import_id: int) -> str:
        """Check the progress of a Workplace import job.

        Args:
            import_id: The import job ID.
        """
        status = await client.get_import_status(import_id)
        return json.dumps(
            {
                "status": status.status,
                "message": status.statusmessage,
                "progress": status.progress,
                "is_complete": status.is_complete,
                "is_error": status.is_error,
            }
        )

    @_moodle_tool
    async def export_workplace_data(
        exporter: str,
        confirmed: bool = False,
    ) -> str:
        """Start an export of Workplace data. REQUIRES USER CONFIRMATION.

        After starting, use get_export_status to poll progress
        and download_export to retrieve the file.

        Available exporters:
        - courses, users, cohorts, reports, site,
          certificates, coursecategories
        - programs, certifications, rules
        - departments_csv, positions_csv, jobs_csv,
          orgstructure, jobs
        - tenants

        Use the short name (e.g. 'courses') -- the full
        class path is resolved automatically.

        Args:
            exporter: Short name like 'courses' or full
                class path.
            confirmed: Set True only after user approval.
        """
        resolved = _EXPORTER_MAP.get(exporter, exporter)
        if not confirmed:
            return json.dumps(
                {
                    "action": "export_workplace_data",
                    "preview": (
                        f"Will export '{exporter}' data from Workplace"
                    ),
                }
            )
        result = await client.perform_export(resolved)
        return json.dumps({"success": True, "result": result})

    @_moodle_tool
    async def import_workplace_data(
        confirmed: bool = False,
    ) -> str:
        """Import Workplace data from an export file.
        WARNING: This can modify programs, certifications,
        and org structure. REQUIRES USER CONFIRMATION.

        After starting, use get_import_status to poll progress.

        Args:
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "import_workplace_data",
                    "preview": (
                        "WARNING: Will start a Workplace data "
                        "import. This can modify programs, "
                        "certifications, and org structure."
                    ),
                }
            )
        result = await client.perform_import()
        return json.dumps({"success": True, "result": result})

    @_moodle_tool
    async def delete_export(
        export_id: int,
        confirmed: bool = False,
    ) -> str:
        """Delete a completed export. REQUIRES USER CONFIRMATION.

        Args:
            export_id: The export job ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_export",
                    "preview": f"Delete export id={export_id}",
                }
            )
        result = await client.delete_export(export_id)
        return json.dumps(result)

    @_moodle_tool
    async def delete_import(
        import_id: int,
        confirmed: bool = False,
    ) -> str:
        """Delete a completed import record. REQUIRES USER CONFIRMATION.

        Args:
            import_id: The import job ID.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "delete_import",
                    "preview": f"Delete import id={import_id}",
                }
            )
        result = await client.delete_import(import_id)
        return json.dumps(result)

    return Skill(
        metadata=SkillMetadata(
            name="moodle-reporting",
            description=(
                "Report Builder queries, UTM/Advanced "
                "completion reports, and Workplace data "
                "export/import (courses, programs, "
                "certifications, organisation structure, "
                "rules, etc.)"
            ),
        ),
        source=SkillSource.ENTRYPOINT,
        instructions=_REPORTING_PROMPT,
        tools=[
            list_reports,
            get_report_data,
            get_utm_report,
            get_adv_comp_report,
            get_export_status,
            download_export,
            get_import_status,
            export_workplace_data,
            import_workplace_data,
            delete_export,
            delete_import,
        ],
    )
