"""Moodle Workplace skill builders for haiku-skills composition.

Each builder creates a ``Skill`` with async tool closures over a
shared ``MoodleClient`` instance.  The tools are identical to the
former ``@agent.tool_plain`` functions -- only the registration
mechanism changes.
"""

from __future__ import annotations

import json
import re
import time

import httpx
from haiku.skills.models import Skill
from haiku.skills.models import SkillMetadata
from haiku.skills.models import SkillSource

from soliplex.moodle.client import MAX_RESULTS
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient

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


# -- Skill prompts --

_CONFIRM_INSTRUCTIONS = """\
WRITE OPERATIONS: For all write tools, you MUST first call the \
tool WITHOUT confirmed=True to generate a preview. Present the \
preview to the user and ask "Should I proceed?" Only call the \
tool with confirmed=True after the user explicitly approves.

Present data in clear tables when appropriate."""

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
- get_upcoming_events -- calendar events and deadlines
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
- assign_manager -- set manager relationships
- unassign_manager -- remove manager relationships

## Workflow guidance
Use get_potential_parent_departments/positions before creating \
or moving. Always set an idnumber when creating \
departments/positions so they can be referenced in updates.

"""
    + _CONFIRM_INSTRUCTIONS
)

_CERTIFICATIONS_PROMPT = (
    """\
You manage Moodle Workplace certifications: listing, \
allocating, revoking, archiving, and deleting.

## Available tools
- list_certifications -- list all certifications
- search_certifications -- lightweight name search
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
get_user_program_courses), NOT user IDs. Use browse_catalogue \
for learning catalogue. Use list_competency_frameworks for \
competencies.

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
- search_cohorts_for_rule -- cohorts for conditions/outcomes
- search_competencies_for_rule -- competencies for conditions
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
Archived -> delete (permanent). Use can_enable_rule before \
enabling. Use get_rule_matching_users to check impact.

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

"""
    + _CONFIRM_INSTRUCTIONS
)


# =================================================================
# 1. Courses skill (19 tools)
# =================================================================


def build_courses_skill(client: MoodleClient) -> Skill:
    """Build the moodle-courses skill (19 tools)."""

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
            cids = [int(c.strip()) for c in courseids.split(",") if c.strip()]
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

    async def list_categories() -> str:
        """List all course categories."""
        try:
            cats = await client.get_categories()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        cat_data: dict = {"name": name, "parent": parent}
        if description:
            cat_data["description"] = description
        try:
            result = await client.create_categories([cat_data])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "created": [{"id": c.id, "name": c.name} for c in result],
            }
        )

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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
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
        try:
            result = await client.create_courses([course_data])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "created": [
                    {"id": c.id, "shortname": c.shortname} for c in result
                ],
            }
        )

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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            await client.update_courses([updates])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "courseid": courseid})

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
                    "instructions": (
                        "Present this WARNING to the user and "
                        "ask for explicit confirmation. If "
                        "confirmed, call this tool again with "
                        "confirmed=True"
                    ),
                }
            )
        try:
            result = await client.delete_courses([courseid])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {"success": True, "deleted_courseid": courseid, "result": result}
        )

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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.duplicate_course(
                courseid, fullname, shortname, categoryid, visible
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
                "enrollments, completion, grades, calendar, "
                "and groups"
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
                return json.dumps(
                    {
                        "error": (
                            f"Unsupported field: '{field}'. "
                            f"Use one of: "
                            f"{sorted(exact_fields | name_fields)}"
                        )
                    }
                )
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

    async def create_user(
        username: str,
        firstname: str,
        lastname: str,
        email: str,
        password: str = "",
        createpassword: bool = True,
        confirmed: bool = False,
    ) -> str:
        """Create a new Moodle user account. REQUIRES USER CONFIRMATION.

        Args:
            username: Login username.
            firstname: User's first name.
            lastname: User's last name.
            email: User's email address.
            password: Optional password. If empty, a random
                password is generated and emailed.
            createpassword: If True and no password given,
                Moodle creates and emails a password.
            confirmed: Set True only after user approval.
        """
        if not confirmed:
            return json.dumps(
                {
                    "action": "create_user",
                    "preview": (
                        f"Will create user '{username}' "
                        f"({firstname} {lastname}, {email})"
                    ),
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
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
            user_data["createpassword"] = 1 if createpassword else 0
        try:
            result = await client.create_users([user_data])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "created": [
                    {"id": u.id, "username": u.username} for u in result
                ],
            }
        )

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
        if not confirmed:
            fields = {k: v for k, v in updates.items() if k != "id"}
            return json.dumps(
                {
                    "action": "update_user",
                    "preview": (f"Will update user {uid}: {fields}"),
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            await client.update_users([updates])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "userid": uid})

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
                    "instructions": (
                        "Present this WARNING to the user and "
                        "ask for explicit confirmation. If "
                        "confirmed, call this tool again with "
                        "confirmed=True"
                    ),
                }
            )
        try:
            await client.delete_users([uid])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "deleted_userid": uid})

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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            await client.update_users([{"id": uid, "suspended": 0}])
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "unsuspended_userid": uid})

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
            {"userid": uid, "tenantid": tenantid} for uid in user_list
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

    return Skill(
        metadata=SkillMetadata(
            name="moodle-users",
            description=(
                "Look up, create, update, suspend, and "
                "delete Moodle users; manage tenants and "
                "messaging"
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
        try:
            members = await client.get_department_members(
                departmentid, positionid, search
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
            [{"id": p.id, "name": p.name, "path": p.path} for p in parents]
        )

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
            [{"id": p.id, "name": p.name, "path": p.path} for p in parents]
        )

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
                    {"id": u.id, "idnumber": u.idnumber} for u in updated
                ],
                "warnings": warnings,
            }
        )

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
                    {"id": u.id, "idnumber": u.idnumber} for u in updated
                ],
                "warnings": warnings,
            }
        )

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
            return json.dumps({"preview": f"Delete position id={position_id}"})
        try:
            result = await client.delete_position(position_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
            result = await client.create_job(userid, department, position)
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
            return json.dumps({"preview": f"Delete job id={job_id}"})
        try:
            result = await client.delete_job(job_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
            result = await client.assign_managers(user_list, manager_list)
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
                        f"Unassign managers {mid_list} from users {uid_list}"
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

    async def search_certifications(
        search: str = "",
    ) -> str:
        """Search certifications by name.

        Lightweight search returning id and fullname.
        Use list_certifications for full details.

        Args:
            search: Search term to filter by name.
        """
        try:
            results = await client.search_certifications(search=search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [{"id": c.id, "fullname": c.fullname} for c in results]
        )

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

    async def get_user_certifications(userid: int) -> str:
        """Get all certifications for a specific user.

        Args:
            userid: The Moodle user ID.
        """
        try:
            allocs = await client.get_user_certification_allocations(userid)
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
            result = await client.revoke_certification(certificationid, uid)
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
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.archive_certification(certificationid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "success": True,
                "certificationid": certificationid,
                "result": result,
            }
        )

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
                    "preview": (f"DELETE certification id={certification_id}"),
                }
            )
        try:
            result = await client.delete_certification(certification_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                    "preview": (
                        f"Restore certification id={certification_id}"
                    ),
                }
            )
        try:
            result = await client.restore_certification(certification_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                    "preview": (
                        f"Deallocate {len(parsed)} certification user(s)"
                    ),
                    "allocation_ids": parsed,
                }
            )
        try:
            result = await client.bulk_deallocate_certification_users(parsed)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
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
            [{"id": c.id, "fullname": c.fullname} for c in courses]
        )

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
            content = await client.get_program_content(programid, userid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(content)

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

    async def get_course_competencies(courseid: int) -> str:
        """Get competencies linked to a course.

        Args:
            courseid: The Moodle course ID.
        """
        try:
            competencies = await client.get_course_competencies(courseid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(competencies)

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
            return json.dumps({"preview": f"Archive program id={program_id}"})
        try:
            result = await client.archive_program(program_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
            return json.dumps({"preview": f"Restore program id={program_id}"})
        try:
            result = await client.restore_program(program_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
            return json.dumps({"preview": f"DELETE program id={program_id}"})
        try:
            result = await client.delete_program(program_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                {"preview": f"Duplicate program id={program_id}"}
            )
        try:
            dup = await client.duplicate_program(program_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "duplicatedprogramid": dup.duplicatedprogramid,
                "redirecturl": dup.redirecturl,
            }
        )

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
                    "preview": (f"Set program id={program_id} to {label}"),
                }
            )
        try:
            result = await client.update_program_visibility(
                program_id, visible
            )
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                    "preview": (f"Deallocate {len(parsed)} program user(s)"),
                    "allocation_ids": parsed,
                }
            )
        try:
            result = await client.bulk_deallocate_program_users(parsed)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result.model_dump())

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
                    "preview": (
                        f"Reset progress for {len(parsed)} program user(s)"
                    ),
                    "allocation_ids": parsed,
                }
            )
        try:
            result = await client.bulk_reset_program_progress(parsed)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result.model_dump())

    return Skill(
        metadata=SkillMetadata(
            name="moodle-programs",
            description=(
                "Search and manage programs, catalogue, "
                "competencies, and learning plans in "
                "Moodle Workplace"
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

    # -- Private helpers (local to this builder) --

    async def _resolve_rule_id(
        rule_id: int = 0, rule_name: str = ""
    ) -> int | str:
        """Resolve a dynamic rule by ID or name.

        Returns the integer rule ID on success, or a JSON error
        string when the rule cannot be found.
        """
        if rule_id > 0:
            return rule_id
        if not rule_name:
            return json.dumps(
                {"error": "Provide either rule_id or rule_name."}
            )
        try:
            rules = await client.list_dynamic_rules()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        needle = rule_name.lower()
        matches = [r for r in rules if needle in r["name"].lower()]
        if len(matches) == 1:
            return matches[0]["id"]
        if len(matches) == 0:
            return json.dumps(
                {"error": f"No dynamic rule matching '{rule_name}'."}
            )
        return json.dumps(
            {
                "error": f"Multiple rules match '{rule_name}'.",
                "matches": [
                    {"id": m["id"], "name": m["name"]} for m in matches
                ],
            }
        )

    # -- Tool functions --

    async def list_dynamic_rules() -> str:
        """List all dynamic rules with names, IDs, and status.

        Returns a table of automation rules showing each rule's
        ID, name, enabled/disabled state, conditions, and actions.
        Use the rule ID or name from this list for other dynamic
        rule tools.
        """
        try:
            rules = await client.list_dynamic_rules()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(rules)

    async def can_enable_rule(rule_id: int = 0, rule_name: str = "") -> str:
        """Check whether a dynamic rule meets prerequisites to be enabled.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        try:
            result = await client.can_enable_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    async def get_rule_matching_users(
        rule_id: int = 0, rule_name: str = ""
    ) -> str:
        """Count users currently matching a dynamic rule's conditions.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        try:
            result = await client.count_matching_users(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    async def get_rule_matched_users(
        rule_id: int = 0, rule_name: str = ""
    ) -> str:
        """Count users historically matched by a dynamic rule.

        Args:
            rule_id: Moodle dynamic rule ID.
            rule_name: Rule name (alternative to rule_id).
        """
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        try:
            result = await client.count_matched_users(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    async def search_cohorts_for_rule(search: str) -> str:
        """Search cohorts available for dynamic rule conditions/outcomes.

        Args:
            search: Search string to filter cohorts by name.
        """
        try:
            items = await client.search_cohorts_for_rule(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps([{"id": i.id, "name": i.name} for i in items])

    async def search_competencies_for_rule(search: str) -> str:
        """Search competencies available for dynamic rule conditions.

        Args:
            search: Search string to filter competencies.
        """
        try:
            items = await client.search_competencies_for_rule(search)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            [{"id": i.id, "shortname": i.shortname} for i in items]
        )

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"Enable dynamic rule id={resolved}"}
            )
        try:
            result = await client.enable_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"Disable dynamic rule id={resolved}"}
            )
        try:
            result = await client.disable_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"Archive dynamic rule id={resolved}"}
            )
        try:
            result = await client.archive_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"Unarchive dynamic rule id={resolved}"}
            )
        try:
            result = await client.unarchive_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"DELETE dynamic rule id={resolved}"}
            )
        try:
            result = await client.delete_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
        resolved = await _resolve_rule_id(rule_id, rule_name)
        if isinstance(resolved, str):
            return resolved
        if not confirmed:
            return json.dumps(
                {"preview": f"Duplicate dynamic rule id={resolved}"}
            )
        try:
            result = await client.duplicate_rule(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                    "preview": (
                        f"Delete condition id={instanceid} from dynamic rule"
                    ),
                }
            )
        try:
            result = await client.delete_condition(instanceid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
                    "preview": (
                        f"Delete outcome id={instanceid} from dynamic rule"
                    ),
                }
            )
        try:
            result = await client.delete_outcome(instanceid)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    return Skill(
        metadata=SkillMetadata(
            name="moodle-rules",
            description=(
                "List, enable, disable, archive, and "
                "manage Moodle Workplace dynamic rules"
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

    def _strip_html(value: str | None) -> str:
        """Strip HTML tags from a report cell value."""
        if value is None:
            return ""
        return re.sub(r"<[^>]+>", "", value).strip()

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
                    [_strip_html(c) for c in row.columns] for row in data.rows
                ],
                "total_rows": data.totalrowcount,
                "page": page,
                "perpage": perpage,
            }
        )

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

    async def get_export_status(export_id: int) -> str:
        """Check the progress of a Workplace export job.

        Args:
            export_id: The export job ID.
        """
        try:
            status = await client.get_export_status(export_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "status": status.status,
                "message": status.statusmessage,
                "progress": status.progress,
                "is_complete": status.is_complete,
                "is_error": status.is_error,
            }
        )

    async def download_export(export_id: int) -> str:
        """Get download info for a completed Workplace export.

        Args:
            export_id: The export job ID.
        """
        try:
            result = await client.get_export_file(export_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    async def get_import_status(import_id: int) -> str:
        """Check the progress of a Workplace import job.

        Args:
            import_id: The import job ID.
        """
        try:
            status = await client.get_import_status(import_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(
            {
                "status": status.status,
                "message": status.statusmessage,
                "progress": status.progress,
                "is_complete": status.is_complete,
                "is_error": status.is_error,
            }
        )

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
        # Resolve short names to full class paths
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
        resolved = _EXPORTER_MAP.get(exporter, exporter)
        if not confirmed:
            return json.dumps(
                {
                    "action": "export_workplace_data",
                    "preview": (
                        f"Will export '{exporter}' data from Workplace"
                    ),
                    "instructions": (
                        "Present this to the user and ask for "
                        "confirmation. If confirmed, call this "
                        "tool again with confirmed=True"
                    ),
                }
            )
        try:
            result = await client.perform_export(resolved)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "result": result})

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
                    "instructions": (
                        "Present this WARNING to the user and "
                        "ask for explicit confirmation. If "
                        "confirmed, call this tool again with "
                        "confirmed=True"
                    ),
                }
            )
        try:
            result = await client.perform_import()
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps({"success": True, "result": result})

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
            return json.dumps({"preview": f"Delete export id={export_id}"})
        try:
            result = await client.delete_export(export_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

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
            return json.dumps({"preview": f"Delete import id={import_id}"})
        try:
            result = await client.delete_import(import_id)
        except (MoodleAPIError, httpx.HTTPError) as exc:
            return json.dumps({"error": str(exc)})
        return json.dumps(result)

    return Skill(
        metadata=SkillMetadata(
            name="moodle-reporting",
            description=(
                "Report Builder queries, UTM/Advanced "
                "completion reports, and Workplace "
                "import/export"
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
