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


# ---------------------------------------------------------------
# Feature 1: Course Content
# ---------------------------------------------------------------


class CourseModule(BaseModel):
    """Single activity/resource within a course section."""

    id: int
    name: str = ""
    modname: str = ""
    description: str = ""
    visible: int = 1
    completion: int = 0


class CourseSection(BaseModel):
    """Section within a course from ``core_course_get_contents``."""

    id: int
    name: str = ""
    visible: int = 1
    summary: str = ""
    modules: list[CourseModule] = Field(default_factory=list)


# ---------------------------------------------------------------
# Feature 2: Activity Completion
# ---------------------------------------------------------------


class ActivityCompletionStatus(BaseModel):
    """Per-activity completion from ``core_completion_get_activities_completion_status``."""

    cmid: int
    modname: str = ""
    instance: int = 0
    state: int = 0
    timecompleted: int = 0
    tracking: int = 0


# ---------------------------------------------------------------
# Feature 3: Groups & Cohorts
# ---------------------------------------------------------------


class Group(BaseModel):
    """Course group from ``core_group_get_course_groups``."""

    id: int
    courseid: int = 0
    name: str = ""
    description: str = ""


class GroupMembers(BaseModel):
    """Group member list from ``core_group_get_group_members``."""

    groupid: int
    userids: list[int] = Field(default_factory=list)


class Cohort(BaseModel):
    """System cohort from ``core_cohort_get_cohorts``."""

    id: int
    name: str = ""
    idnumber: str = ""
    visible: int = 1


class CohortMembers(BaseModel):
    """Cohort member list from ``core_cohort_get_cohort_members``."""

    cohortid: int
    userids: list[int] = Field(default_factory=list)


# ---------------------------------------------------------------
# Feature 4: Grading & Assessments
# ---------------------------------------------------------------


class AssignmentGrade(BaseModel):
    """Single grade from ``mod_assign_get_grades``."""

    id: int
    userid: int = 0
    grade: str = ""
    grader: int = 0
    timemodified: int = 0


class GradeItem(BaseModel):
    """Grade table row from ``gradereport_user_get_grades_table``."""

    itemname: str = ""
    grade: str = ""
    percentage: str = ""
    feedback: str = ""


# ---------------------------------------------------------------
# Feature 5: Calendar & Deadlines
# ---------------------------------------------------------------


class CalendarEvent(BaseModel):
    """Calendar event from ``core_calendar_get_calendar_events``."""

    id: int
    name: str = ""
    description: str = ""
    courseid: int = 0
    modulename: str = ""
    eventtype: str = ""
    timestart: int = 0
    timeduration: int = 0


# ---------------------------------------------------------------
# Feature 7: Write Operations
# ---------------------------------------------------------------


class EnrolmentRequest(BaseModel):
    """Enrolment request for ``enrol_manual_enrol_users``."""

    userid: int
    courseid: int
    roleid: int = 5


class MessageRequest(BaseModel):
    """Message request for ``core_message_send_instant_messages``."""

    touserid: int
    text: str
    textformat: int = 0
