"""Async HTTP client for the Moodle REST Web Services API."""

from __future__ import annotations

import os

import httpx

from soliplex.moodle.models import ActivityCompletionStatus
from soliplex.moodle.models import CalendarEvent
from soliplex.moodle.models import Certification
from soliplex.moodle.models import CertificationAllocation
from soliplex.moodle.models import CertificationLogEntry
from soliplex.moodle.models import Cohort
from soliplex.moodle.models import CohortMembers
from soliplex.moodle.models import CompletionStatus
from soliplex.moodle.models import Course
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import EnrolledUser
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
from soliplex.moodle.models import Program
from soliplex.moodle.models import ProgramCourse
from soliplex.moodle.models import Tenant
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
