"""Async HTTP client for the Moodle REST Web Services API."""

from __future__ import annotations

import os

import httpx

from soliplex.moodle.models import ActivityCompletionStatus
from soliplex.moodle.models import CalendarEvent
from soliplex.moodle.models import CatalogueItem
from soliplex.moodle.models import Certification
from soliplex.moodle.models import CertificationAllocation
from soliplex.moodle.models import CertificationLogEntry
from soliplex.moodle.models import Cohort
from soliplex.moodle.models import CohortMembers
from soliplex.moodle.models import CompetencyFramework
from soliplex.moodle.models import CompletionReportRow
from soliplex.moodle.models import CompletionStatus
from soliplex.moodle.models import Course
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import CreatedEntity
from soliplex.moodle.models import Department
from soliplex.moodle.models import DepartmentMember
from soliplex.moodle.models import EnrolledUser
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
from soliplex.moodle.models import LearningPlan
from soliplex.moodle.models import Position
from soliplex.moodle.models import PotentialParent
from soliplex.moodle.models import Program
from soliplex.moodle.models import ProgramCourse
from soliplex.moodle.models import ProgramCourseOption
from soliplex.moodle.models import ReportData
from soliplex.moodle.models import ReportRow
from soliplex.moodle.models import ReportSummary
from soliplex.moodle.models import Tenant
from soliplex.moodle.models import UpdatedEntity
from soliplex.moodle.models import UserCatalogueItem
from soliplex.moodle.models import UserProfile

# Upper bound on results returned by list endpoints.
# Keeps LLM context bounded; acts as a client-side safeguard.
MAX_RESULTS = 100


class MoodleAPIError(Exception):
    """Raised when Moodle returns an error response."""

    def __init__(
        self,
        message: str,
        errorcode: str = "",
        exception: str = "",
    ):
        self.errorcode = errorcode
        self.exception = exception
        super().__init__(message)


class MoodleClient:
    """Thin async wrapper around Moodle's REST endpoint."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        verify: str | bool | None = None,
    ):
        self.base_url = (base_url or os.environ["MOODLE_BASE_URL"]).rstrip("/")
        self.token = token or os.environ["MOODLE_API_TOKEN"]
        self._endpoint = f"{self.base_url}/webservice/rest/server.php"
        self._verify = verify

    async def _call(
        self,
        wsfunction: str,
        **params: str | int,
    ) -> dict | list:
        """Call a Moodle web service function."""
        data: dict[str, str | int] = {
            "wstoken": self.token,
            "wsfunction": wsfunction,
            "moodlewsrestformat": "json",
            **params,
        }
        client_kw = {}
        if self._verify is not None:
            client_kw["verify"] = self._verify
        async with httpx.AsyncClient(**client_kw) as http:
            resp = await http.post(self._endpoint, data=data)
            resp.raise_for_status()

        result = resp.json()

        if isinstance(result, dict) and "exception" in result:
            raise MoodleAPIError(
                message=result.get("message", "Unknown error"),
                errorcode=result.get("errorcode", ""),
                exception=result.get("exception", ""),
            )

        return result

    # ---------------------------------------------------------------
    # Course functions
    # ---------------------------------------------------------------

    async def get_courses(self) -> list[Course]:
        """Return all courses via ``core_course_get_courses``.

        Results are truncated to ``MAX_RESULTS``.
        """
        raw = await self._call("core_course_get_courses")
        courses = [Course.model_validate(c) for c in raw]
        return courses[:MAX_RESULTS]

    async def get_courses_by_field(
        self,
        field: str = "",
        value: str = "",
    ) -> list[Course]:
        """Filter courses via ``core_course_get_courses_by_field``.

        Results are truncated to ``MAX_RESULTS``.
        """
        params: dict[str, str] = {}
        if field:
            params["field"] = field
            params["value"] = value
        raw = await self._call("core_course_get_courses_by_field", **params)
        course_list = raw.get("courses", [])
        return [Course.model_validate(c) for c in course_list][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # User functions
    # ---------------------------------------------------------------

    async def get_users_by_field(
        self,
        field: str,
        values: list[str],
    ) -> list[UserProfile]:
        """Look up users via ``core_user_get_users_by_field``.

        Results are truncated to ``MAX_RESULTS``.
        """
        params: dict[str, str] = {"field": field}
        for i, v in enumerate(values):
            params[f"values[{i}]"] = v
        raw = await self._call("core_user_get_users_by_field", **params)
        return [UserProfile.model_validate(u) for u in raw][:MAX_RESULTS]

    async def search_users(
        self,
        criteria: list[tuple[str, str]],
    ) -> list[UserProfile]:
        """Search users via ``core_user_get_users``.

        Each criterion is a ``(key, value)`` tuple where *key* is a
        field like ``firstname`` or ``lastname`` and *value* is a
        substring to match.

        Results are truncated to ``MAX_RESULTS``.
        """
        params: dict[str, str] = {}
        for i, (key, value) in enumerate(criteria):
            params[f"criteria[{i}][key]"] = key
            params[f"criteria[{i}][value]"] = value
        raw = await self._call("core_user_get_users", **params)
        users = raw.get("users", []) if isinstance(raw, dict) else []
        return [UserProfile.model_validate(u) for u in users][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Enrolment functions
    # ---------------------------------------------------------------

    async def get_enrolled_users(self, courseid: int) -> list[EnrolledUser]:
        """List enrolled users via ``core_enrol_get_enrolled_users``.

        Results are truncated to ``MAX_RESULTS``.
        """
        raw = await self._call(
            "core_enrol_get_enrolled_users",
            courseid=courseid,
        )
        return [EnrolledUser.model_validate(u) for u in raw][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Completion functions
    # ---------------------------------------------------------------

    async def get_course_completion_status(
        self,
        courseid: int,
        userid: int,
    ) -> CompletionStatus:
        """Get completion status.

        Calls ``core_completion_get_course_completion_status``.
        """
        raw = await self._call(
            "core_completion_get_course_completion_status",
            courseid=courseid,
            userid=userid,
        )
        return CompletionStatus.model_validate(
            raw.get("completionstatus", raw)
        )

    # ---------------------------------------------------------------
    # Course content (Feature 1)
    # ---------------------------------------------------------------

    async def get_course_contents(self, courseid: int) -> list[CourseSection]:
        """Return sections and modules via ``core_course_get_contents``."""
        raw = await self._call("core_course_get_contents", courseid=courseid)
        return [CourseSection.model_validate(s) for s in raw][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Activity completion (Feature 2)
    # ---------------------------------------------------------------

    async def get_activities_completion_status(
        self,
        courseid: int,
        userid: int,
    ) -> list[ActivityCompletionStatus]:
        """Per-activity completion via ``core_completion_get_activities_completion_status``."""
        raw = await self._call(
            "core_completion_get_activities_completion_status",
            courseid=courseid,
            userid=userid,
        )
        statuses = raw.get("statuses", [])
        return [
            ActivityCompletionStatus.model_validate(s) for s in statuses
        ][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Groups & cohorts (Feature 3)
    # ---------------------------------------------------------------

    async def get_course_groups(self, courseid: int) -> list[Group]:
        """List groups via ``core_group_get_course_groups``."""
        raw = await self._call(
            "core_group_get_course_groups", courseid=courseid
        )
        return [Group.model_validate(g) for g in raw][:MAX_RESULTS]

    async def get_group_members(
        self, groupids: list[int]
    ) -> list[GroupMembers]:
        """Get group members via ``core_group_get_group_members``."""
        params: dict[str, str | int] = {}
        for i, gid in enumerate(groupids):
            params[f"groupids[{i}]"] = gid
        raw = await self._call("core_group_get_group_members", **params)
        return [GroupMembers.model_validate(g) for g in raw][:MAX_RESULTS]

    async def get_cohorts(self) -> list[Cohort]:
        """List system cohorts via ``core_cohort_get_cohorts``."""
        raw = await self._call("core_cohort_get_cohorts")
        return [Cohort.model_validate(c) for c in raw][:MAX_RESULTS]

    async def get_cohort_members(
        self, cohortids: list[int]
    ) -> list[CohortMembers]:
        """Get cohort members via ``core_cohort_get_cohort_members``."""
        params: dict[str, str | int] = {}
        for i, cid in enumerate(cohortids):
            params[f"cohortids[{i}]"] = cid
        raw = await self._call("core_cohort_get_cohort_members", **params)
        return [CohortMembers.model_validate(c) for c in raw][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Grading & assessments (Feature 4)
    # ---------------------------------------------------------------

    async def get_assignment_grades(
        self, assignmentids: list[int]
    ) -> dict:
        """Get assignment grades via ``mod_assign_get_grades``."""
        params: dict[str, str | int] = {}
        for i, aid in enumerate(assignmentids):
            params[f"assignmentids[{i}]"] = aid
        raw = await self._call("mod_assign_get_grades", **params)
        return raw

    async def get_user_grades(self, courseid: int, userid: int) -> dict:
        """Get grade report via ``gradereport_user_get_grades_table``."""
        raw = await self._call(
            "gradereport_user_get_grades_table",
            courseid=courseid,
            userid=userid,
        )
        return raw

    # ---------------------------------------------------------------
    # Calendar & deadlines (Feature 5)
    # ---------------------------------------------------------------

    async def get_calendar_events(
        self,
        courseids: list[int] | None = None,
        timestart: int | None = None,
        timeend: int | None = None,
    ) -> list[CalendarEvent]:
        """Get calendar events via ``core_calendar_get_calendar_events``."""
        params: dict[str, str | int] = {}
        if courseids:
            for i, cid in enumerate(courseids):
                params[f"events[courseids][{i}]"] = cid
        if timestart is not None:
            params["options[timestart]"] = timestart
        if timeend is not None:
            params["options[timeend]"] = timeend
        raw = await self._call(
            "core_calendar_get_calendar_events", **params
        )
        events = raw.get("events", [])
        return [CalendarEvent.model_validate(e) for e in events][:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Write operations (Feature 7)
    # ---------------------------------------------------------------

    async def enrol_users(self, enrolments: list[dict]) -> dict:
        """Enrol users via ``enrol_manual_enrol_users``."""
        params: dict[str, str | int] = {}
        for i, e in enumerate(enrolments):
            params[f"enrolments[{i}][roleid]"] = e["roleid"]
            params[f"enrolments[{i}][userid]"] = e["userid"]
            params[f"enrolments[{i}][courseid]"] = e["courseid"]
        raw = await self._call("enrol_manual_enrol_users", **params)
        if raw is None:
            return {"warnings": []}
        return raw if isinstance(raw, dict) else {"warnings": []}

    async def send_messages(self, messages: list[dict]) -> list[dict]:
        """Send messages via ``core_message_send_instant_messages``."""
        params: dict[str, str | int] = {}
        for i, m in enumerate(messages):
            params[f"messages[{i}][touserid]"] = m["touserid"]
            params[f"messages[{i}][text]"] = m["text"]
            params[f"messages[{i}][textformat]"] = m.get("textformat", 0)
        raw = await self._call(
            "core_message_send_instant_messages", **params
        )
        return raw if isinstance(raw, list) else []

    # ---------------------------------------------------------------
    # Certifications (Workplace)
    # ---------------------------------------------------------------

    async def get_certifications(
        self, tenantid: int = 0
    ) -> list[Certification]:
        """List certifications via ``tool_certification_get_certifications``."""
        raw = await self._call(
            "tool_certification_get_certifications",
            tenantid=tenantid,
            showall=1,
        )
        return [Certification.model_validate(c) for c in raw][:MAX_RESULTS]

    async def get_certification_allocations(
        self, certificationid: int
    ) -> list[CertificationAllocation]:
        """Get allocated users via ``tool_certification_get_certification_allocations``."""
        raw = await self._call(
            "tool_certification_get_certification_allocations",
            certificationid=certificationid,
        )
        return [
            CertificationAllocation.model_validate(a) for a in raw
        ][:MAX_RESULTS]

    async def get_user_certification_allocations(
        self, userid: int
    ) -> list[CertificationAllocation]:
        """Get user's certs via ``tool_certification_get_user_certification_allocations``."""
        raw = await self._call(
            "tool_certification_get_user_certification_allocations",
            userid=userid,
        )
        return [
            CertificationAllocation.model_validate(a) for a in raw
        ][:MAX_RESULTS]

    async def get_certification_user_log(
        self, certificationid: int, userid: int
    ) -> list[CertificationLogEntry]:
        """Get cert history via ``tool_certification_get_certification_user_log``."""
        raw = await self._call(
            "tool_certification_get_certification_user_log",
            certificationid=certificationid,
            userid=userid,
        )
        entries = raw if isinstance(raw, list) else []
        return [
            CertificationLogEntry.model_validate(e) for e in entries
        ][:MAX_RESULTS]

    async def certify_user(
        self, certificationid: int, userid: int
    ) -> dict:
        """Certify user via ``tool_certification_certify_user``."""
        raw = await self._call(
            "tool_certification_certify_user",
            certificationid=certificationid,
            userid=userid,
        )
        return raw if isinstance(raw, dict) else {"result": True}

    async def revoke_certification(
        self, certificationid: int, userid: int
    ) -> dict:
        """Revoke cert via ``tool_certification_revoke_certification``."""
        raw = await self._call(
            "tool_certification_revoke_certification",
            certificationid=certificationid,
            userid=userid,
        )
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Programs / Learning Paths (Workplace)
    # ---------------------------------------------------------------

    async def search_programs(self, search: str = "") -> list[Program]:
        """Search programs via ``tool_program_potential_program_selector``."""
        raw = await self._call(
            "tool_program_potential_program_selector", search=search
        )
        programs = raw if isinstance(raw, list) else []
        return [Program.model_validate(p) for p in programs][:MAX_RESULTS]

    async def get_user_program_courses(
        self, userid: int
    ) -> list[ProgramCourse]:
        """Get user's program courses via ``tool_program_get_users_courses``."""
        raw = await self._call(
            "tool_program_get_users_courses", userid=userid
        )
        courses = raw if isinstance(raw, list) else []
        return [
            ProgramCourse.model_validate(c) for c in courses
        ][:MAX_RESULTS]

    async def allocate_users_to_program(
        self, programid: int, userids: list[int]
    ) -> dict:
        """Allocate users via ``tool_program_allocate_users``."""
        params: dict[str, str | int] = {"programid": programid}
        for i, uid in enumerate(userids):
            params[f"userids[{i}]"] = uid
        raw = await self._call("tool_program_allocate_users", **params)
        return raw if isinstance(raw, dict) else {"result": []}

    # ---------------------------------------------------------------
    # Tenants (Workplace)
    # ---------------------------------------------------------------

    async def get_tenants(self) -> list[Tenant]:
        """List tenants via ``tool_tenant_get_tenants``."""
        raw = await self._call("tool_tenant_get_tenants")
        tenants = raw if isinstance(raw, list) else []
        return [Tenant.model_validate(t) for t in tenants][:MAX_RESULTS]

    async def allocate_users_to_tenant(
        self, allocations: list[dict]
    ) -> dict:
        """Allocate users to a tenant via ``tool_tenant_allocate_users``.

        Each allocation dict must have ``userid`` and ``tenantid``.
        """
        params: dict[str, str | int] = {}
        for i, a in enumerate(allocations):
            params[f"allocations[{i}][userid]"] = a["userid"]
            params[f"allocations[{i}][tenantid]"] = a["tenantid"]
        raw = await self._call("tool_tenant_allocate_users", **params)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def suspend_tenant_users(
        self, userids: list[int]
    ) -> dict:
        """Suspend users system-wide via ``tool_tenant_suspend_users``."""
        params: dict[str, str | int] = {}
        for i, uid in enumerate(userids):
            params[f"userids[{i}]"] = uid
        raw = await self._call("tool_tenant_suspend_users", **params)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Catalogue (Workplace)
    # ---------------------------------------------------------------

    async def get_catalogue_page(
        self, query: str = ""
    ) -> list[CatalogueItem]:
        """Search the course/program catalogue via ``tool_catalogue_get_catalogue_page``."""
        params: dict[str, str | int] = {}
        if query:
            params["search"] = query
        raw = await self._call(
            "tool_catalogue_get_catalogue_page", **params
        )
        items = []
        if isinstance(raw, dict):
            contents = raw.get("contents", {})
            if isinstance(contents, dict):
                items = contents.get("catalogueitems", [])
        return [CatalogueItem.model_validate(i) for i in items][:MAX_RESULTS]

    async def get_user_catalogue(
        self, userid: int = 0, search: str = ""
    ) -> list[UserCatalogueItem]:
        """Get user's learning catalogue via ``tool_catalogue_get_user_catalogue``."""
        params: dict[str, str | int] = {}
        if userid:
            params["userid"] = userid
        if search:
            params["search"] = search
        raw = await self._call(
            "tool_catalogue_get_user_catalogue", **params
        )
        items = []
        if isinstance(raw, dict):
            catalogue = raw.get("catalogue", {})
            if isinstance(catalogue, dict):
                items = catalogue.get("listitems", [])
        return [
            UserCatalogueItem.model_validate(i) for i in items
        ][:MAX_RESULTS]

    async def get_program_content(
        self, programid: int, userid: int = 0
    ) -> dict:
        """Get courses inside a program via ``tool_catalogue_get_user_catalogue_program_content``."""
        params: dict[str, str | int] = {"programid": programid}
        if userid:
            params["userid"] = userid
        raw = await self._call(
            "tool_catalogue_get_user_catalogue_program_content",
            **params,
        )
        return raw if isinstance(raw, dict) else {}

    # ---------------------------------------------------------------
    # Deeper Program Management (Workplace)
    # ---------------------------------------------------------------

    async def search_courses_for_program(
        self, search: str = ""
    ) -> list[ProgramCourseOption]:
        """Search courses eligible for programs via ``tool_program_potential_courses_program_selector``."""
        raw = await self._call(
            "tool_program_potential_courses_program_selector",
            search=search,
        )
        courses = raw if isinstance(raw, list) else []
        return [
            ProgramCourseOption.model_validate(c) for c in courses
        ][:MAX_RESULTS]

    async def deallocate_user_from_program(
        self, programid: int, userid: int
    ) -> dict:
        """Remove a user from a program via ``tool_program_deallocate_user``."""
        raw = await self._call(
            "tool_program_deallocate_user",
            programid=programid,
            userid=userid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def reset_program_progress(
        self, programuserid: int
    ) -> dict:
        """Reset program progress via ``tool_program_reset_program_progress``.

        Takes the allocation ID (``programuserid``), not the user ID.
        """
        raw = await self._call(
            "tool_program_reset_program_progress",
            programuserid=programuserid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Deeper Certification Management (Workplace)
    # ---------------------------------------------------------------

    async def get_certification_user_allocation(
        self, certificationid: int, userid: int
    ) -> dict:
        """Get detailed user+cert allocation via ``tool_certification_get_certification_user_allocation``."""
        raw = await self._call(
            "tool_certification_get_certification_user_allocation",
            certificationid=certificationid,
            userid=userid,
        )
        return raw if isinstance(raw, dict) else {}

    async def deallocate_user_from_certification(
        self, certificationid: int, userid: int
    ) -> dict:
        """Remove a user from a certification via ``tool_certification_deallocate_user``."""
        raw = await self._call(
            "tool_certification_deallocate_user",
            certificationid=certificationid,
            userid=userid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def archive_certification(
        self, certificationid: int
    ) -> dict:
        """Archive a certification via ``tool_certification_archive_certification``."""
        raw = await self._call(
            "tool_certification_archive_certification",
            certificationid=certificationid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Organisation Structure (Workplace)
    # ---------------------------------------------------------------

    async def get_departments(
        self, search: str = ""
    ) -> list[Department]:
        """List departments via ``tool_organisation_get_teams_tab_filters``."""
        raw = await self._call(
            "tool_organisation_get_teams_tab_filters",
        )
        depts = []
        if isinstance(raw, dict):
            depts = raw.get("departments", [])
        if search:
            search_lower = search.lower()
            depts = [
                d for d in depts
                if search_lower in d.get("name", "").lower()
            ]
        return [Department.model_validate(d) for d in depts][:MAX_RESULTS]

    async def get_positions(
        self, search: str = ""
    ) -> list[Position]:
        """List positions via ``tool_organisation_get_teams_tab_filters``."""
        raw = await self._call(
            "tool_organisation_get_teams_tab_filters",
        )
        positions = []
        if isinstance(raw, dict):
            positions = raw.get("positions", [])
        if search:
            search_lower = search.lower()
            positions = [
                p for p in positions
                if search_lower in p.get("name", "").lower()
            ]
        return [Position.model_validate(p) for p in positions][:MAX_RESULTS]

    async def get_department_members(
        self,
        departmentid: int = 0,
        positionid: int = 0,
        search: str = "",
    ) -> list[DepartmentMember]:
        """Get users by department/position via ``local_soliplex_get_department_members``.

        Unlike ``get_managed_users``, results are not scoped to the
        token owner's direct reports — all matching users are returned.
        Requires the ``local_soliplex`` plugin to be installed.
        """
        params: dict[str, str | int] = {}
        if departmentid:
            params["departmentid"] = departmentid
        if positionid:
            params["positionid"] = positionid
        if search:
            params["search"] = search
        raw = await self._call(
            "local_soliplex_get_department_members", **params
        )
        members = raw if isinstance(raw, list) else []
        return [
            DepartmentMember.model_validate(m) for m in members
        ][:MAX_RESULTS]

    async def get_managed_users(
        self,
        departmentid: int = 0,
        positionid: int = 0,
        search: str = "",
    ) -> list[dict]:
        """Get managed users via ``tool_organisation_get_managed_users``.

        Results are scoped to the API token owner's direct reports.
        Admin accounts with no direct reports will see an empty list.

        .. deprecated::
            This endpoint is deprecated (moved to ``block_myteams``)
            but still works in Moodle Workplace 5.0.2.
        """
        params: dict[str, str | int] = {}
        if departmentid:
            params["departmentid"] = departmentid
        if positionid:
            params["positionid"] = positionid
        if search:
            params["search"] = search
        raw = await self._call(
            "tool_organisation_get_managed_users", **params
        )
        users = []
        if isinstance(raw, dict):
            users = raw.get("managedusers", [])
        elif isinstance(raw, list):
            users = raw
        return users[:MAX_RESULTS]

    async def create_job(
        self,
        userid: int,
        department_idnumber: str,
        position_idnumber: str,
    ) -> dict:
        """Create a job assignment via ``tool_organisation_create_job``."""
        raw = await self._call(
            "tool_organisation_create_job",
            userid=userid,
            jobdepartment=department_idnumber,
            jobposition=position_idnumber,
        )
        return raw if isinstance(raw, dict) else {"result": True}

    async def assign_managers(
        self, user_ids: list[int], manager_ids: list[int]
    ) -> dict:
        """Assign managers via ``tool_organisation_assign_managers``."""
        params: dict[str, str | int] = {}
        for i, uid in enumerate(user_ids):
            params[f"users[{i}][id]"] = uid
        for i, mid in enumerate(manager_ids):
            params[f"managers[{i}][id]"] = mid
        raw = await self._call(
            "tool_organisation_assign_managers", **params
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # -- Department CRUD --

    async def create_departments(
        self, departments: list[dict]
    ) -> tuple[list[CreatedEntity], list[dict]]:
        """Create departments via ``tool_organisation_create_departments``."""
        params: dict[str, str | int] = {}
        for i, d in enumerate(departments):
            params[f"departments[{i}][name]"] = d["name"]
            for key in ("idnumber", "parent", "description"):
                if key in d:
                    params[f"departments[{i}][{key}]"] = d[key]
        raw = await self._call(
            "tool_organisation_create_departments", **params
        )
        if not isinstance(raw, dict):
            return [], []
        result = [
            CreatedEntity.model_validate(r)
            for r in raw.get("result", [])
        ]
        return result, raw.get("warnings", [])

    async def update_departments(
        self, departments: list[dict]
    ) -> tuple[list[UpdatedEntity], list[dict]]:
        """Update departments via ``tool_organisation_update_departments``."""
        params: dict[str, str | int] = {}
        for i, d in enumerate(departments):
            params[f"departments[{i}][idnumber]"] = d["idnumber"]
            for key in ("name", "parent", "description"):
                if key in d:
                    params[f"departments[{i}][{key}]"] = d[key]
        raw = await self._call(
            "tool_organisation_update_departments", **params
        )
        if not isinstance(raw, dict):
            return [], []
        result = [
            UpdatedEntity.model_validate(r)
            for r in raw.get("result", [])
        ]
        return result, raw.get("warnings", [])

    async def delete_department(self, department_id: int) -> dict:
        """Delete a department via ``tool_organisation_department_delete``."""
        raw = await self._call(
            "tool_organisation_department_delete", id=department_id
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def get_potential_parent_departments(
        self,
        search: str = "",
        departmentid: int = 0,
        frameworkid: int = 0,
        tenantid: int = 0,
    ) -> list[PotentialParent]:
        """Get valid parent departments.

        Uses ``tool_organisation_get_potential_parent_departments``.
        """
        raw = await self._call(
            "tool_organisation_get_potential_parent_departments",
            search=search,
            departmentid=departmentid,
            frameworkid=frameworkid,
            tenantid=tenantid,
        )
        items = raw if isinstance(raw, list) else []
        return [
            PotentialParent.model_validate(p) for p in items
        ][:MAX_RESULTS]

    # -- Position CRUD --

    async def create_positions(
        self, positions: list[dict]
    ) -> tuple[list[CreatedEntity], list[dict]]:
        """Create positions via ``tool_organisation_create_positions``."""
        params: dict[str, str | int] = {}
        for i, p in enumerate(positions):
            params[f"positions[{i}][name]"] = p["name"]
            for key in ("idnumber", "parent", "description"):
                if key in p:
                    params[f"positions[{i}][{key}]"] = p[key]
            if p.get("departmentmanager"):
                params[f"positions[{i}][departmentmanager]"] = 1
            if p.get("globalmanager"):
                params[f"positions[{i}][globalmanager]"] = 1
        raw = await self._call(
            "tool_organisation_create_positions", **params
        )
        if not isinstance(raw, dict):
            return [], []
        result = [
            CreatedEntity.model_validate(r)
            for r in raw.get("result", [])
        ]
        return result, raw.get("warnings", [])

    async def update_positions(
        self, positions: list[dict]
    ) -> tuple[list[UpdatedEntity], list[dict]]:
        """Update positions via ``tool_organisation_update_positions``."""
        params: dict[str, str | int] = {}
        for i, p in enumerate(positions):
            params[f"positions[{i}][idnumber]"] = p["idnumber"]
            for key in ("name", "parent", "description"):
                if key in p:
                    params[f"positions[{i}][{key}]"] = p[key]
            if "departmentmanager" in p:
                params[f"positions[{i}][departmentmanager]"] = (
                    1 if p["departmentmanager"] else 0
                )
            if "globalmanager" in p:
                params[f"positions[{i}][globalmanager]"] = (
                    1 if p["globalmanager"] else 0
                )
        raw = await self._call(
            "tool_organisation_update_positions", **params
        )
        if not isinstance(raw, dict):
            return [], []
        result = [
            UpdatedEntity.model_validate(r)
            for r in raw.get("result", [])
        ]
        return result, raw.get("warnings", [])

    async def delete_position(self, position_id: int) -> dict:
        """Delete a position via ``tool_organisation_position_delete``."""
        raw = await self._call(
            "tool_organisation_position_delete", id=position_id
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def get_potential_parent_positions(
        self,
        search: str = "",
        positionid: int = 0,
        frameworkid: int = 0,
        tenantid: int = 0,
    ) -> list[PotentialParent]:
        """Get valid parent positions.

        Uses ``tool_organisation_get_potential_parent_positions``.
        """
        raw = await self._call(
            "tool_organisation_get_potential_parent_positions",
            search=search,
            positionid=positionid,
            frameworkid=frameworkid,
            tenantid=tenantid,
        )
        items = raw if isinstance(raw, list) else []
        return [
            PotentialParent.model_validate(p) for p in items
        ][:MAX_RESULTS]

    # -- Job & Manager Management --

    async def update_job(
        self,
        userid: int,
        department_idnumber: str,
        position_idnumber: str,
        startdate: int = 0,
        enddate: int = 0,
    ) -> dict:
        """Update a job assignment via ``tool_organisation_update_job``."""
        raw = await self._call(
            "tool_organisation_update_job",
            userid=userid,
            jobdepartment=department_idnumber,
            jobposition=position_idnumber,
            startdate=startdate,
            enddate=enddate,
        )
        return raw if isinstance(raw, dict) else {"status": True}

    async def delete_job(self, job_id: int) -> dict:
        """Delete a job assignment via ``tool_organisation_job_delete``."""
        raw = await self._call(
            "tool_organisation_job_delete", id=job_id
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def unassign_managers(
        self,
        user_ids: list[int],
        manager_ids: list[int],
        unassign_all: bool = False,
    ) -> dict:
        """Unassign managers via ``tool_organisation_unassign_managers``."""
        params: dict[str, str | int] = {}
        for i, uid in enumerate(user_ids):
            params[f"users[{i}][id]"] = uid
        for i, mid in enumerate(manager_ids):
            params[f"managers[{i}][id]"] = mid
        if unassign_all:
            params["unassignall"] = 1
        raw = await self._call(
            "tool_organisation_unassign_managers", **params
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Competencies & Learning Plans
    # ---------------------------------------------------------------

    async def get_competency_frameworks(self) -> list[CompetencyFramework]:
        """List competency frameworks via ``tool_lp_data_for_competency_frameworks_manage_page``."""
        raw = await self._call(
            "tool_lp_data_for_competency_frameworks_manage_page",
            **{"pagecontext[contextid]": 1},
        )
        frameworks = []
        if isinstance(raw, dict):
            frameworks = raw.get(
                "competencyframeworks", raw.get("frameworks", [])
            )
        return [
            CompetencyFramework.model_validate(f) for f in frameworks
        ][:MAX_RESULTS]

    async def get_user_learning_plans(
        self, userid: int
    ) -> list[LearningPlan]:
        """Get user's learning plans via ``tool_lp_data_for_plans_page``."""
        raw = await self._call(
            "tool_lp_data_for_plans_page", userid=userid
        )
        plans = []
        if isinstance(raw, dict):
            plans = raw.get("plans", [])
        return [LearningPlan.model_validate(p) for p in plans][:MAX_RESULTS]

    async def get_user_competency_summary(
        self, userid: int, competencyid: int
    ) -> dict:
        """Get user competency summary via ``tool_lp_data_for_user_competency_summary``."""
        raw = await self._call(
            "tool_lp_data_for_user_competency_summary",
            userid=userid,
            competencyid=competencyid,
        )
        return raw if isinstance(raw, dict) else {}

    async def get_course_competencies(
        self, courseid: int
    ) -> list[dict]:
        """Get course competencies via ``tool_lp_data_for_course_competencies_page``."""
        raw = await self._call(
            "tool_lp_data_for_course_competencies_page",
            courseid=courseid,
        )
        competencies = []
        if isinstance(raw, dict):
            competencies = raw.get("competencies", [])
        return competencies[:MAX_RESULTS]

    # ---------------------------------------------------------------
    # Report Builder
    # ---------------------------------------------------------------

    async def list_reports(
        self, page: int = 0, perpage: int = 0
    ) -> list[ReportSummary]:
        """List custom reports via ``core_reportbuilder_list_reports``."""
        params: dict[str, str | int] = {
            "page": page,
            "perpage": perpage or MAX_RESULTS,
        }
        raw = await self._call(
            "core_reportbuilder_list_reports", **params
        )
        reports = raw.get("reports", []) if isinstance(raw, dict) else []
        return [
            ReportSummary.model_validate(r) for r in reports
        ][:MAX_RESULTS]

    async def retrieve_report(
        self,
        reportid: int,
        page: int = 0,
        perpage: int = 0,
    ) -> tuple[ReportSummary, ReportData]:
        """Retrieve report content via ``core_reportbuilder_retrieve_report``."""
        params: dict[str, str | int] = {
            "reportid": reportid,
            "page": page,
            "perpage": min(perpage or MAX_RESULTS, MAX_RESULTS),
        }
        raw = await self._call(
            "core_reportbuilder_retrieve_report", **params
        )
        details = ReportSummary.model_validate(raw.get("details", {}))
        data_raw = raw.get("data", {})
        rows = [
            ReportRow.model_validate(r)
            for r in data_raw.get("rows", [])
        ][:MAX_RESULTS]
        data = ReportData(
            headers=data_raw.get("headers", []),
            rows=rows,
            totalrowcount=data_raw.get("totalrowcount", 0),
        )
        return details, data

    # ---------------------------------------------------------------
    # Custom Completion Reports (adv_comp / utm)
    # ---------------------------------------------------------------

    async def get_utm_report(
        self,
        courseid: int,
        departmentid: int = 0,
        completionstatus: int = 0,
        page: int = 0,
        perpage: int = 0,
    ) -> tuple[list[CompletionReportRow], int]:
        """Get UTM completion report via ``local_soliplex_get_utm_report``."""
        params: dict[str, str | int] = {
            "courseid": courseid,
            "page": page,
            "perpage": perpage or MAX_RESULTS,
        }
        if departmentid:
            params["departmentid"] = departmentid
        if completionstatus:
            params["completionstatus"] = completionstatus
        raw = await self._call(
            "local_soliplex_get_utm_report", **params
        )
        rows_raw = raw.get("rows", []) if isinstance(raw, dict) else []
        totalcount = raw.get("totalcount", 0) if isinstance(raw, dict) else 0
        rows = [
            CompletionReportRow.model_validate(r) for r in rows_raw
        ][:MAX_RESULTS]
        return rows, totalcount

    async def get_adv_comp_report(
        self,
        courseid: int,
        completionstatus: int = 0,
        page: int = 0,
        perpage: int = 0,
    ) -> tuple[list[CompletionReportRow], int]:
        """Get Advanced Completion report via ``local_soliplex_get_adv_comp_report``."""
        params: dict[str, str | int] = {
            "courseid": courseid,
            "page": page,
            "perpage": perpage or MAX_RESULTS,
        }
        if completionstatus:
            params["completionstatus"] = completionstatus
        raw = await self._call(
            "local_soliplex_get_adv_comp_report", **params
        )
        rows_raw = raw.get("rows", []) if isinstance(raw, dict) else []
        totalcount = raw.get("totalcount", 0) if isinstance(raw, dict) else 0
        rows = [
            CompletionReportRow.model_validate(r) for r in rows_raw
        ][:MAX_RESULTS]
        return rows, totalcount
