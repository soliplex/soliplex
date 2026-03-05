"""Async HTTP client for the Moodle REST Web Services API."""

from __future__ import annotations

import os

import httpx

from soliplex.moodle.models import CompletionStatus
from soliplex.moodle.models import Course
from soliplex.moodle.models import EnrolledUser
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
