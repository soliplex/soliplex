"""Async HTTP client for the Moodle REST Web Services API."""

from __future__ import annotations

import html as html_mod
import os
import re

import httpx

from soliplex.moodle.models import ActivityCompletionStatus
from soliplex.moodle.models import BulkOperationResult
from soliplex.moodle.models import CalendarEvent
from soliplex.moodle.models import CatalogueItem
from soliplex.moodle.models import Certification
from soliplex.moodle.models import CertificationAllocation
from soliplex.moodle.models import CertificationLogEntry
from soliplex.moodle.models import CertificationSearchResult
from soliplex.moodle.models import Cohort
from soliplex.moodle.models import CohortMembers
from soliplex.moodle.models import CompetencyFramework
from soliplex.moodle.models import CompletionReportRow
from soliplex.moodle.models import CompletionStatus
from soliplex.moodle.models import Course
from soliplex.moodle.models import CourseCategory
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import CreatedCategory
from soliplex.moodle.models import CreatedCourse
from soliplex.moodle.models import CreatedEntity
from soliplex.moodle.models import CreatedUser
from soliplex.moodle.models import Department
from soliplex.moodle.models import DepartmentMember
from soliplex.moodle.models import DuplicatedCourse
from soliplex.moodle.models import DuplicatedProgram
from soliplex.moodle.models import EnrolledUser
from soliplex.moodle.models import ExportStatus
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
from soliplex.moodle.models import ImportStatus
from soliplex.moodle.models import LearningPlan
from soliplex.moodle.models import Position
from soliplex.moodle.models import PotentialParent
from soliplex.moodle.models import Program
from soliplex.moodle.models import ProgramCourse
from soliplex.moodle.models import ProgramCourseOption
from soliplex.moodle.models import ReportData
from soliplex.moodle.models import ReportRow
from soliplex.moodle.models import ReportSummary
from soliplex.moodle.models import SelectorItem
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
        """Per-activity completion via
        ``core_completion_get_activities_completion_status``."""
        raw = await self._call(
            "core_completion_get_activities_completion_status",
            courseid=courseid,
            userid=userid,
        )
        statuses = raw.get("statuses", [])
        return [ActivityCompletionStatus.model_validate(s) for s in statuses][
            :MAX_RESULTS
        ]

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

    async def get_assignment_grades(self, assignmentids: list[int]) -> dict:
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
        raw = await self._call("core_calendar_get_calendar_events", **params)
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
        raw = await self._call("core_message_send_instant_messages", **params)
        return raw if isinstance(raw, list) else []

    # ---------------------------------------------------------------
    # Certifications (Workplace)
    # ---------------------------------------------------------------

    async def get_certifications(
        self, tenantid: int = 0
    ) -> list[Certification]:
        """List certifications via
        ``tool_certification_get_certifications``."""
        raw = await self._call(
            "tool_certification_get_certifications",
            tenantid=tenantid,
            showall=1,
        )
        return [Certification.model_validate(c) for c in raw][:MAX_RESULTS]

    async def get_certification_allocations(
        self, certificationid: int
    ) -> list[CertificationAllocation]:
        """Get allocated users via
        ``tool_certification_get_certification_allocations``."""
        raw = await self._call(
            "tool_certification_get_certification_allocations",
            certificationid=certificationid,
        )
        return [CertificationAllocation.model_validate(a) for a in raw][
            :MAX_RESULTS
        ]

    async def get_user_certification_allocations(
        self, userid: int
    ) -> list[CertificationAllocation]:
        """Get user's certs via
        ``tool_certification_get_user_certification_allocations``."""
        raw = await self._call(
            "tool_certification_get_user_certification_allocations",
            userid=userid,
        )
        return [CertificationAllocation.model_validate(a) for a in raw][
            :MAX_RESULTS
        ]

    async def get_certification_user_log(
        self, certificationid: int, userid: int
    ) -> list[CertificationLogEntry]:
        """Get cert history via
        ``tool_certification_get_certification_user_log``."""
        raw = await self._call(
            "tool_certification_get_certification_user_log",
            certificationid=certificationid,
            userid=userid,
        )
        entries = raw if isinstance(raw, list) else []
        return [CertificationLogEntry.model_validate(e) for e in entries][
            :MAX_RESULTS
        ]

    async def certify_user(self, certificationid: int, userid: int) -> dict:
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
        """Get user's program courses via
        ``tool_program_get_users_courses``."""
        raw = await self._call("tool_program_get_users_courses", userid=userid)
        courses = raw if isinstance(raw, list) else []
        return [ProgramCourse.model_validate(c) for c in courses][:MAX_RESULTS]

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

    async def allocate_users_to_tenant(self, allocations: list[dict]) -> dict:
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

    async def suspend_tenant_users(self, userids: list[int]) -> dict:
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

    async def get_catalogue_page(self, query: str = "") -> list[CatalogueItem]:
        """Search the course/program catalogue via
        ``tool_catalogue_get_catalogue_page``."""
        params: dict[str, str | int] = {}
        if query:
            params["search"] = query
        raw = await self._call("tool_catalogue_get_catalogue_page", **params)
        items = []
        if isinstance(raw, dict):
            contents = raw.get("contents", {})
            if isinstance(contents, dict):
                items = contents.get("catalogueitems", [])
        return [CatalogueItem.model_validate(i) for i in items][:MAX_RESULTS]

    async def get_user_catalogue(
        self, userid: int = 0, search: str = ""
    ) -> list[UserCatalogueItem]:
        """Get user's learning catalogue via
        ``tool_catalogue_get_user_catalogue``."""
        params: dict[str, str | int] = {}
        if userid:
            params["userid"] = userid
        if search:
            params["search"] = search
        raw = await self._call("tool_catalogue_get_user_catalogue", **params)
        items = []
        if isinstance(raw, dict):
            catalogue = raw.get("catalogue", {})
            if isinstance(catalogue, dict):
                items = catalogue.get("listitems", [])
        return [UserCatalogueItem.model_validate(i) for i in items][
            :MAX_RESULTS
        ]

    async def get_program_content(
        self, programid: int, userid: int = 0
    ) -> dict:
        """Get courses inside a program via
        ``tool_catalogue_get_user_catalogue_program_content``."""
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
        """Search courses eligible for programs via
        ``tool_program_potential_courses_program_selector``."""
        raw = await self._call(
            "tool_program_potential_courses_program_selector",
            search=search,
        )
        courses = raw if isinstance(raw, list) else []
        return [ProgramCourseOption.model_validate(c) for c in courses][
            :MAX_RESULTS
        ]

    async def deallocate_user_from_program(
        self, programid: int, userid: int
    ) -> dict:
        """Remove a user from a program via
        ``tool_program_deallocate_user``."""
        raw = await self._call(
            "tool_program_deallocate_user",
            programid=programid,
            userid=userid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def reset_program_progress(self, programuserid: int) -> dict:
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
        """Get detailed user+cert allocation via
        ``tool_certification_get_certification_user_allocation``."""
        raw = await self._call(
            "tool_certification_get_certification_user_allocation",
            certificationid=certificationid,
            userid=userid,
        )
        return raw if isinstance(raw, dict) else {}

    async def deallocate_user_from_certification(
        self, certificationid: int, userid: int
    ) -> dict:
        """Remove a user from a certification via
        ``tool_certification_deallocate_user``."""
        raw = await self._call(
            "tool_certification_deallocate_user",
            certificationid=certificationid,
            userid=userid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def archive_certification(self, certificationid: int) -> dict:
        """Archive a certification via
        ``tool_certification_archive_certification``."""
        raw = await self._call(
            "tool_certification_archive_certification",
            certificationid=certificationid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Program & Certification Lifecycle (Workplace)
    # ---------------------------------------------------------------

    async def archive_program(self, programid: int) -> dict:
        """Archive a program via ``tool_program_archive_program``."""
        raw = await self._call(
            "tool_program_archive_program", programid=programid
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def restore_program(self, programid: int) -> dict:
        """Restore an archived program via ``tool_program_restore_program``."""
        raw = await self._call(
            "tool_program_restore_program", programid=programid
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_program(self, programid: int) -> dict:
        """Delete a program via ``tool_program_delete_program``."""
        raw = await self._call(
            "tool_program_delete_program", programid=programid
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def duplicate_program(self, programid: int) -> DuplicatedProgram:
        """Duplicate a program via ``tool_program_duplicate_program``."""
        raw = await self._call(
            "tool_program_duplicate_program",
            programid=programid,
        )
        if isinstance(raw, dict):
            return DuplicatedProgram.model_validate(raw)
        return DuplicatedProgram()

    async def update_program_visibility(
        self, programid: int, visibility: int
    ) -> dict:
        """Toggle visibility via ``tool_program_update_program_visibility``."""
        raw = await self._call(
            "tool_program_update_program_visibility",
            programid=programid,
            visibility=visibility,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def enrol_user_to_program_course(
        self, courseid: int, programid: int
    ) -> dict:
        """Enrol user to course in program context via
        ``tool_program_enrol_user_to_course``."""
        raw = await self._call(
            "tool_program_enrol_user_to_course",
            courseid=courseid,
            programid=programid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_program_set(self, setid: int) -> dict:
        """Delete a course set via ``tool_program_delete_set``."""
        raw = await self._call("tool_program_delete_set", setid=setid)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_program_course(self, programcourseid: int) -> dict:
        """Remove a course from program via ``tool_program_delete_course``."""
        raw = await self._call(
            "tool_program_delete_course",
            programcourseid=programcourseid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def bulk_deallocate_program_users(
        self, programuserids: list[int]
    ) -> BulkOperationResult:
        """Bulk deallocate users via ``tool_program_bulk_deallocate_user``."""
        params: dict[str, int] = {}
        for i, pid in enumerate(programuserids):
            params[f"programuserids[{i}]"] = pid
        raw = await self._call("tool_program_bulk_deallocate_user", **params)
        if isinstance(raw, dict):
            return BulkOperationResult.model_validate(raw)
        return BulkOperationResult()

    async def bulk_reset_program_progress(
        self, programuserids: list[int]
    ) -> BulkOperationResult:
        """Bulk reset progress via
        ``tool_program_bulk_reset_program_progress``."""
        params: dict[str, int] = {}
        for i, pid in enumerate(programuserids):
            params[f"programuserids[{i}]"] = pid
        raw = await self._call(
            "tool_program_bulk_reset_program_progress", **params
        )
        if isinstance(raw, dict):
            return BulkOperationResult.model_validate(raw)
        return BulkOperationResult()

    async def recalculate_program_completions(
        self, programuserids: list[int]
    ) -> BulkOperationResult:
        """Recalculate completions via
        ``tool_program_recalculate_program_user_completions``."""
        params: dict[str, int] = {}
        for i, pid in enumerate(programuserids):
            params[f"programuserids[{i}]"] = pid
        raw = await self._call(
            "tool_program_recalculate_program_user_completions",
            **params,
        )
        if isinstance(raw, dict):
            return BulkOperationResult.model_validate(raw)
        return BulkOperationResult()

    async def delete_certification(self, certificationid: int) -> dict:
        """Delete a certification via
        ``tool_certification_delete_certification``."""
        raw = await self._call(
            "tool_certification_delete_certification",
            certificationid=certificationid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def restore_certification(self, certificationid: int) -> dict:
        """Restore a certification via
        ``tool_certification_restore_certification``."""
        raw = await self._call(
            "tool_certification_restore_certification",
            certificationid=certificationid,
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def search_certifications(
        self, search: str = ""
    ) -> list[CertificationSearchResult]:
        """Search certifications via
        ``tool_certification_potential_certification_selector``."""
        raw = await self._call(
            "tool_certification_potential_certification_selector",
            search=search,
        )
        if not isinstance(raw, list):
            return []
        return [CertificationSearchResult.model_validate(c) for c in raw][
            :MAX_RESULTS
        ]

    async def bulk_deallocate_certification_users(
        self, certificationuserids: list[int]
    ) -> BulkOperationResult:
        """Bulk deallocate via ``tool_certification_bulk_deallocate_user``."""
        params: dict[str, int] = {}
        for i, cid in enumerate(certificationuserids):
            params[f"certificationuserids[{i}]"] = cid
        raw = await self._call(
            "tool_certification_bulk_deallocate_user", **params
        )
        if isinstance(raw, dict):
            return BulkOperationResult.model_validate(raw)
        return BulkOperationResult()

    # ---------------------------------------------------------------
    # Organisation Structure (Workplace)
    # ---------------------------------------------------------------

    async def get_departments(self, search: str = "") -> list[Department]:
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
                d for d in depts if search_lower in d.get("name", "").lower()
            ]
        return [Department.model_validate(d) for d in depts][:MAX_RESULTS]

    async def get_positions(self, search: str = "") -> list[Position]:
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
                p
                for p in positions
                if search_lower in p.get("name", "").lower()
            ]
        return [Position.model_validate(p) for p in positions][:MAX_RESULTS]

    async def get_department_members(
        self,
        departmentid: int = 0,
        positionid: int = 0,
        search: str = "",
    ) -> list[DepartmentMember]:
        """Get users by department/position via the Workplace jobs system
        report.

        Uses ``core_reportbuilder_retrieve_system_report`` with the
        ``tool_organisation`` jobs report.  Results are not scoped to
        the token owner's direct reports — all matching users are
        returned.  No custom plugin required.
        """
        raw = await self._call(
            "core_reportbuilder_retrieve_system_report",
            **{
                "source": (
                    r"tool_organisation\reportbuilder"
                    r"\local\systemreports\jobs"
                ),
                "context[contextid]": 1,
                "page": 0,
                "perpage": MAX_RESULTS,
            },
        )
        if not isinstance(raw, dict):
            return []
        rows = raw.get("data", {}).get("rows", [])
        _strip_html = re.compile(r"<[^>]+>")
        needle = search.lower() if search else ""
        members: list[DepartmentMember] = []
        for row in rows:
            cols = row.get("columns", [])
            if len(cols) < 3:
                continue
            # Column 0: '<a href="...?id=3">Alice Johnson</a>'
            m_id = re.search(r"\?id=(\d+)", cols[0])
            if not m_id:
                continue
            userid = int(m_id.group(1))
            fullname = _strip_html.sub("", cols[0]).strip()
            dept_name = cols[1].strip()
            pos_name = cols[2].strip()
            # Apply client-side filters (the system report
            # doesn't accept department/position/search params).
            if departmentid and dept_name == "":
                continue
            if positionid and pos_name == "":
                continue
            if needle and needle not in fullname.lower():
                continue
            parts = fullname.split(None, 1)
            firstname = parts[0] if parts else ""
            lastname = parts[1] if len(parts) > 1 else ""
            members.append(
                DepartmentMember(
                    userid=userid,
                    firstname=firstname,
                    lastname=lastname,
                    fullname=fullname,
                    departmentname=dept_name,
                    positionname=pos_name,
                )
            )
        return members[:MAX_RESULTS]

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
        raw = await self._call("tool_organisation_assign_managers", **params)
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
            CreatedEntity.model_validate(r) for r in raw.get("result", [])
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
            UpdatedEntity.model_validate(r) for r in raw.get("result", [])
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
        return [PotentialParent.model_validate(p) for p in items][:MAX_RESULTS]

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
        raw = await self._call("tool_organisation_create_positions", **params)
        if not isinstance(raw, dict):
            return [], []
        result = [
            CreatedEntity.model_validate(r) for r in raw.get("result", [])
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
        raw = await self._call("tool_organisation_update_positions", **params)
        if not isinstance(raw, dict):
            return [], []
        result = [
            UpdatedEntity.model_validate(r) for r in raw.get("result", [])
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
        return [PotentialParent.model_validate(p) for p in items][:MAX_RESULTS]

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
        raw = await self._call("tool_organisation_job_delete", id=job_id)
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
        raw = await self._call("tool_organisation_unassign_managers", **params)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    # ---------------------------------------------------------------
    # Competencies & Learning Plans
    # ---------------------------------------------------------------

    async def get_competency_frameworks(self) -> list[CompetencyFramework]:
        """List competency frameworks via
        ``tool_lp_data_for_competency_frameworks_manage_page``."""
        raw = await self._call(
            "tool_lp_data_for_competency_frameworks_manage_page",
            **{"pagecontext[contextid]": 1},
        )
        frameworks = []
        if isinstance(raw, dict):
            frameworks = raw.get(
                "competencyframeworks", raw.get("frameworks", [])
            )
        return [CompetencyFramework.model_validate(f) for f in frameworks][
            :MAX_RESULTS
        ]

    async def get_user_learning_plans(self, userid: int) -> list[LearningPlan]:
        """Get user's learning plans via ``tool_lp_data_for_plans_page``."""
        raw = await self._call("tool_lp_data_for_plans_page", userid=userid)
        plans = []
        if isinstance(raw, dict):
            plans = raw.get("plans", [])
        return [LearningPlan.model_validate(p) for p in plans][:MAX_RESULTS]

    async def get_user_competency_summary(
        self, userid: int, competencyid: int
    ) -> dict:
        """Get user competency summary via
        ``tool_lp_data_for_user_competency_summary``."""
        raw = await self._call(
            "tool_lp_data_for_user_competency_summary",
            userid=userid,
            competencyid=competencyid,
        )
        return raw if isinstance(raw, dict) else {}

    async def get_course_competencies(self, courseid: int) -> list[dict]:
        """Get course competencies via
        ``tool_lp_data_for_course_competencies_page``."""
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
        raw = await self._call("core_reportbuilder_list_reports", **params)
        reports = raw.get("reports", []) if isinstance(raw, dict) else []
        return [ReportSummary.model_validate(r) for r in reports][:MAX_RESULTS]

    async def retrieve_report(
        self,
        reportid: int,
        page: int = 0,
        perpage: int = 0,
    ) -> tuple[ReportSummary, ReportData]:
        """Retrieve report content via
        ``core_reportbuilder_retrieve_report``."""
        params: dict[str, str | int] = {
            "reportid": reportid,
            "page": page,
            "perpage": min(perpage or MAX_RESULTS, MAX_RESULTS),
        }
        raw = await self._call("core_reportbuilder_retrieve_report", **params)
        details = ReportSummary.model_validate(raw.get("details", {}))
        data_raw = raw.get("data", {})
        rows = [ReportRow.model_validate(r) for r in data_raw.get("rows", [])][
            :MAX_RESULTS
        ]
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
        raw = await self._call("local_soliplex_get_utm_report", **params)
        rows_raw = raw.get("rows", []) if isinstance(raw, dict) else []
        totalcount = raw.get("totalcount", 0) if isinstance(raw, dict) else 0
        rows = [CompletionReportRow.model_validate(r) for r in rows_raw][
            :MAX_RESULTS
        ]
        return rows, totalcount

    async def get_adv_comp_report(
        self,
        courseid: int,
        completionstatus: int = 0,
        page: int = 0,
        perpage: int = 0,
    ) -> tuple[list[CompletionReportRow], int]:
        """Get Advanced Completion report via
        ``local_soliplex_get_adv_comp_report``."""
        params: dict[str, str | int] = {
            "courseid": courseid,
            "page": page,
            "perpage": perpage or MAX_RESULTS,
        }
        if completionstatus:
            params["completionstatus"] = completionstatus
        raw = await self._call("local_soliplex_get_adv_comp_report", **params)
        rows_raw = raw.get("rows", []) if isinstance(raw, dict) else []
        totalcount = raw.get("totalcount", 0) if isinstance(raw, dict) else 0
        rows = [CompletionReportRow.model_validate(r) for r in rows_raw][
            :MAX_RESULTS
        ]
        return rows, totalcount

    # ---------------------------------------------------------------
    # Dynamic Rules (Workplace)
    # ---------------------------------------------------------------

    async def enable_rule(self, rule_id: int) -> dict:
        """Enable a dynamic rule via ``tool_dynamicrule_enable_rule``."""
        raw = await self._call("tool_dynamicrule_enable_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def disable_rule(self, rule_id: int) -> dict:
        """Disable a dynamic rule via ``tool_dynamicrule_disable_rule``."""
        raw = await self._call("tool_dynamicrule_disable_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def archive_rule(self, rule_id: int) -> dict:
        """Archive a dynamic rule via ``tool_dynamicrule_archive_rule``."""
        raw = await self._call("tool_dynamicrule_archive_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def unarchive_rule(self, rule_id: int) -> dict:
        """Unarchive a dynamic rule via ``tool_dynamicrule_unarchive_rule``."""
        raw = await self._call("tool_dynamicrule_unarchive_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_rule(self, rule_id: int) -> dict:
        """Delete a dynamic rule via ``tool_dynamicrule_delete_rule``."""
        raw = await self._call("tool_dynamicrule_delete_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def duplicate_rule(self, rule_id: int) -> dict:
        """Duplicate a dynamic rule via ``tool_dynamicrule_duplicate_rule``."""
        raw = await self._call("tool_dynamicrule_duplicate_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def can_enable_rule(self, rule_id: int) -> dict:
        """Check if a rule can be enabled via
        ``tool_dynamicrule_can_enable_rule``."""
        raw = await self._call("tool_dynamicrule_can_enable_rule", id=rule_id)
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_condition(self, instanceid: int) -> dict:
        """Delete a rule condition via
        ``tool_dynamicrule_delete_condition``."""
        raw = await self._call(
            "tool_dynamicrule_delete_condition", instanceid=instanceid
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def delete_outcome(self, instanceid: int) -> dict:
        """Delete a rule outcome via ``tool_dynamicrule_delete_outcome``."""
        raw = await self._call(
            "tool_dynamicrule_delete_outcome", instanceid=instanceid
        )
        if raw is None:
            return {"result": True}
        return raw if isinstance(raw, dict) else {"result": True}

    async def count_matching_users(self, rule_id: int) -> dict:
        """Count users currently matching a rule via
        ``tool_dynamicrule_count_matching_users``."""
        raw = await self._call(
            "tool_dynamicrule_count_matching_users", id=rule_id
        )
        if raw is None:
            return {"count": 0}
        return raw if isinstance(raw, dict) else {"count": raw}

    async def count_matched_users(self, rule_id: int) -> dict:
        """Count users historically matched by a rule via
        ``tool_dynamicrule_count_matched_users``."""
        raw = await self._call(
            "tool_dynamicrule_count_matched_users", id=rule_id
        )
        if raw is None:
            return {"count": 0}
        return raw if isinstance(raw, dict) else {"count": raw}

    async def search_cohorts_for_rule(
        self, search: str, instancetype: str = "condition"
    ) -> list[SelectorItem]:
        """Search cohorts for rule conditions/outcomes via
        ``tool_dynamicrule_potential_cohort_selector``."""
        raw = await self._call(
            "tool_dynamicrule_potential_cohort_selector",
            search=search,
            instancetype=instancetype,
        )
        if not isinstance(raw, list):
            return []
        return [SelectorItem.model_validate(c) for c in raw][:MAX_RESULTS]

    async def search_competencies_for_rule(
        self, search: str
    ) -> list[SelectorItem]:
        """Search competencies for rule conditions via
        ``tool_dynamicrule_potential_competency_selector``."""
        raw = await self._call(
            "tool_dynamicrule_potential_competency_selector",
            search=search,
        )
        if not isinstance(raw, list):
            return []
        return [SelectorItem.model_validate(c) for c in raw][:MAX_RESULTS]

    async def list_dynamic_rules(self) -> list[dict]:
        """List dynamic rules via the built-in system report.

        Uses ``core_reportbuilder_retrieve_system_report`` with the
        ``tool_dynamicrule`` rules report.  Parses the HTML columns
        to extract rule id, name, enabled state, conditions and actions.
        """
        raw = await self._call(
            "core_reportbuilder_retrieve_system_report",
            **{
                "source": (
                    r"tool_dynamicrule\reportbuilder"
                    r"\local\systemreports\rules"
                ),
                "context[contextid]": 1,
                "page": 0,
                "perpage": MAX_RESULTS,
            },
        )
        if not isinstance(raw, dict):
            return []
        rows = raw.get("data", {}).get("rows", [])
        _strip_html = re.compile(r"<[^>]+>")
        results: list[dict] = []
        for row in rows:
            cols = row.get("columns", [])
            if len(cols) < 2:
                continue
            toggle = cols[0]
            name_col = cols[1]
            m_id = re.search(r"rule-toggle-(\d+)", toggle)
            if not m_id:
                continue
            rule_id = int(m_id.group(1))
            enabled = "checked" in toggle
            m_name = re.search(r'data-value="([^"]+)"', name_col)
            name = html_mod.unescape(m_name.group(1)) if m_name else ""

            def _li_texts(col: str) -> list[str]:
                items = re.findall(r"<li[^>]*>(.*?)</li>", col, re.DOTALL)
                return [_strip_html.sub("", t).strip() for t in items]

            conditions = _li_texts(cols[3]) if len(cols) > 3 else []
            actions = _li_texts(cols[4]) if len(cols) > 4 else []
            results.append(
                {
                    "id": rule_id,
                    "name": name,
                    "enabled": enabled,
                    "conditions": conditions,
                    "actions": actions,
                }
            )
        return results[:MAX_RESULTS]

    # ---------------------------------------------------------------
    # User management CRUD (Feature 18)
    # ---------------------------------------------------------------

    async def create_users(
        self,
        users: list[dict],
    ) -> list[CreatedUser]:
        """Create users via ``core_user_create_users``.

        Each dict must contain at least ``username``, ``firstname``,
        ``lastname``, ``email``, and either ``password`` or
        ``createpassword=1``.
        """
        params: dict[str, str | int] = {}
        for i, u in enumerate(users):
            for key, val in u.items():
                params[f"users[{i}][{key}]"] = val
        raw = await self._call("core_user_create_users", **params)
        return [CreatedUser.model_validate(r) for r in raw]

    async def update_users(
        self,
        users: list[dict],
    ) -> None:
        """Update users via ``core_user_update_users``.

        Each dict must contain ``id`` and any fields to update.
        """
        params: dict[str, str | int] = {}
        for i, u in enumerate(users):
            for key, val in u.items():
                params[f"users[{i}][{key}]"] = val
        await self._call("core_user_update_users", **params)

    async def delete_users(
        self,
        userids: list[int],
    ) -> None:
        """Delete users via ``core_user_delete_users``."""
        params: dict[str, str | int] = {}
        for i, uid in enumerate(userids):
            params[f"userids[{i}]"] = uid
        await self._call("core_user_delete_users", **params)

    # ---------------------------------------------------------------
    # Course management CRUD (Feature 19)
    # ---------------------------------------------------------------

    async def get_categories(
        self,
    ) -> list[CourseCategory]:
        """List categories via ``core_course_get_categories``."""
        raw = await self._call("core_course_get_categories")
        return [CourseCategory.model_validate(c) for c in raw][:MAX_RESULTS]

    async def create_courses(
        self,
        courses: list[dict],
    ) -> list[CreatedCourse]:
        """Create courses via ``core_course_create_courses``.

        Each dict must contain at least ``fullname``,
        ``shortname``, and ``categoryid``.
        """
        params: dict[str, str | int] = {}
        for i, c in enumerate(courses):
            for key, val in c.items():
                params[f"courses[{i}][{key}]"] = val
        raw = await self._call("core_course_create_courses", **params)
        return [CreatedCourse.model_validate(r) for r in raw]

    async def update_courses(
        self,
        courses: list[dict],
    ) -> None:
        """Update courses via ``core_course_update_courses``.

        Each dict must contain ``id`` and any fields to update.
        """
        params: dict[str, str | int] = {}
        for i, c in enumerate(courses):
            for key, val in c.items():
                params[f"courses[{i}][{key}]"] = val
        raw = await self._call("core_course_update_courses", **params)
        if isinstance(raw, dict) and raw.get("warnings"):
            return raw
        return None

    async def delete_courses(
        self,
        courseids: list[int],
    ) -> dict:
        """Delete courses via ``core_course_delete_courses``."""
        params: dict[str, str | int] = {}
        for i, cid in enumerate(courseids):
            params[f"courseids[{i}]"] = cid
        raw = await self._call("core_course_delete_courses", **params)
        return raw if isinstance(raw, dict) else {}

    async def duplicate_course(
        self,
        courseid: int,
        fullname: str,
        shortname: str,
        categoryid: int,
        visible: int = 1,
    ) -> DuplicatedCourse:
        """Duplicate a course via ``core_course_duplicate_course``."""
        raw = await self._call(
            "core_course_duplicate_course",
            courseid=courseid,
            fullname=fullname,
            shortname=shortname,
            categoryid=categoryid,
            visible=visible,
        )
        return DuplicatedCourse.model_validate(raw)

    async def create_categories(
        self,
        categories: list[dict],
    ) -> list[CreatedCategory]:
        """Create categories via ``core_course_create_categories``.

        Each dict must contain ``name`` and optionally ``parent``.
        """
        params: dict[str, str | int] = {}
        for i, c in enumerate(categories):
            for key, val in c.items():
                params[f"categories[{i}][{key}]"] = val
        raw = await self._call("core_course_create_categories", **params)
        return [CreatedCategory.model_validate(r) for r in raw]

    # ---------------------------------------------------------------
    # Import / Export (Feature 20 — Workplace)
    # ---------------------------------------------------------------

    async def perform_export(self, exporter: str, **params: str | int) -> dict:
        """Start an export via ``tool_wp_perform_export``.

        ``exporter`` is the exporter class name, e.g.
        ``tool_wp\\tool_wp\\exporter\\courses``.
        """
        raw = await self._call(
            "tool_wp_perform_export",
            exporter=exporter,
            **params,
        )
        return raw if isinstance(raw, dict) else {}

    async def get_export_status(self, exportid: int) -> ExportStatus:
        """Check export progress via ``tool_wp_get_export_status``."""
        raw = await self._call("tool_wp_get_export_status", exportid=exportid)
        return ExportStatus.model_validate(raw)

    async def get_export_file(self, exportid: int) -> dict:
        """Get export file info via ``tool_wp_get_export_file``."""
        raw = await self._call("tool_wp_get_export_file", exportid=exportid)
        return raw if isinstance(raw, dict) else {}

    async def perform_import(self, **params: str | int) -> dict:
        """Start an import via ``tool_wp_perform_import``."""
        raw = await self._call("tool_wp_perform_import", **params)
        return raw if isinstance(raw, dict) else {}

    async def get_import_status(self, importid: int) -> ImportStatus:
        """Check import progress via ``tool_wp_get_import_status``."""
        raw = await self._call("tool_wp_get_import_status", importid=importid)
        return ImportStatus.model_validate(raw)

    async def delete_export(self, exportid: int) -> dict:
        """Delete an export via ``tool_wp_delete_export``."""
        raw = await self._call("tool_wp_delete_export", id=exportid)
        return raw if isinstance(raw, dict) else {}

    async def delete_import(self, importid: int) -> dict:
        """Delete an import via ``tool_wp_delete_import``."""
        raw = await self._call("tool_wp_delete_import", id=importid)
        return raw if isinstance(raw, dict) else {}
