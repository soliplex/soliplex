"""Pydantic models for Moodle REST API responses."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class Course(BaseModel):
    """Course record from ``core_course_get_courses``."""

    id: int
    shortname: str
    fullname: str
    categoryid: int = 0
    summary: str = ""
    startdate: int = 0
    enddate: int = 0
    visible: int = 1
    format: str = ""
    enablecompletion: int = 0


class UserProfile(BaseModel):
    """User profile from ``core_user_get_users_by_field``."""

    id: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    email: str = ""
    department: str = ""
    firstaccess: int = 0
    lastaccess: int = 0


class Role(BaseModel):
    """Role assignment embedded in enrolled-user records."""

    roleid: int
    name: str = ""
    shortname: str = ""


class EnrolledUser(BaseModel):
    """Enrolled user from ``core_enrol_get_enrolled_users``."""

    id: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    email: str = ""
    department: str = ""
    roles: list[Role] = Field(default_factory=list)


class CompletionDetails(BaseModel):
    """Nested detail block within a completion criterion."""

    type: str = ""
    criteria: str = ""
    requirement: str = ""
    status: str = ""


class CompletionCriteria(BaseModel):
    """Single completion criterion within a course completion status."""

    type: int = 0
    title: str = ""
    status: str = ""
    complete: bool = False
    timecompleted: int | None = None
    details: CompletionDetails | None = None


class CompletionStatus(BaseModel):
    """Course completion status.

    Returned by ``core_completion_get_course_completion_status``.
    """

    completed: bool
    aggregation: int = 0
    completions: list[CompletionCriteria] = Field(
        default_factory=list,
    )
