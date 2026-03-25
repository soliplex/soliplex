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
    modulename: str | None = ""
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


# ---------------------------------------------------------------
# Feature 8: Certifications (Workplace)
# ---------------------------------------------------------------


class Certification(BaseModel):
    """Certification from ``tool_certification_get_certifications``."""

    id: int
    fullname: str = ""
    idnumber: str | None = ""
    description: str | None = ""
    status: int = 0
    timecreated: int = 0
    timemodified: int = 0


class CertificationAllocation(BaseModel):
    """User allocation from ``tool_certification_get_certification_allocations``."""

    id: int
    userid: int = 0
    certificationid: int = 0
    userfullname: str = ""
    certificationfullname: str = ""
    timeallocated: int = 0
    timecreated: int = 0
    timemodified: int = 0


class CertificationLogEntry(BaseModel):
    """Log entry from ``tool_certification_get_certification_user_log``."""

    id: int = 0
    action: str = ""
    timecreated: int = 0


# ---------------------------------------------------------------
# Feature 9: Programs / Learning Paths (Workplace)
# ---------------------------------------------------------------


class Program(BaseModel):
    """Program from ``tool_program_potential_program_selector``."""

    id: int
    fullname: str = ""


class ProgramCourse(BaseModel):
    """Course within a program from ``tool_program_get_users_courses``."""

    id: int
    shortname: str = ""
    fullname: str = ""
    completed: bool = False


# ---------------------------------------------------------------
# Feature 10: Tenants (Workplace)
# ---------------------------------------------------------------


class Tenant(BaseModel):
    """Tenant from ``tool_tenant_get_tenants``."""

    id: int
    name: str = ""
    sitename: str | None = ""
    idnumber: str | None = ""
    isdefault: bool = False


# ---------------------------------------------------------------
# Feature 11: Course Catalogue (Workplace)
# ---------------------------------------------------------------


class CatalogueItem(BaseModel):
    """Item from ``tool_catalogue_get_catalogue_page``."""

    id: int
    title: str = ""
    url: str = ""


class UserCatalogueItem(BaseModel):
    """User catalogue entry from ``tool_catalogue_get_user_catalogue``."""

    itemid: int
    fullname: str = ""
    numcourses: int = 0
    progress: int = 0
    duedate: int = 0
    isprogram: bool = False
    categoryname: str = ""


# ---------------------------------------------------------------
# Feature 12: Deeper Program Management (Workplace)
# ---------------------------------------------------------------


class ProgramCourseOption(BaseModel):
    """Course option for program management from ``tool_program_potential_courses_program_selector``."""

    id: int
    fullname: str = ""


# ---------------------------------------------------------------
# Feature 13: Organisation Structure (Workplace)
# ---------------------------------------------------------------


class Department(BaseModel):
    """Department from ``tool_organisation_get_teams_tab_filters``."""

    id: int
    name: str = ""
    parentid: int = 0
    idnumber: str = ""


class Position(BaseModel):
    """Position from ``tool_organisation_get_teams_tab_filters``."""

    id: int
    name: str = ""
    parentid: int = 0
    idnumber: str = ""


class Job(BaseModel):
    """Job assignment from ``tool_organisation_create_job``."""

    id: int
    userid: int = 0
    departmentid: int = 0
    positionid: int = 0


class PotentialParent(BaseModel):
    """Valid parent for department/position hierarchy."""

    id: int
    name: str = ""
    path: str = ""
    locked: int = 0


class CreatedEntity(BaseModel):
    """Result from creating a department or position."""

    id: int
    name: str = ""
    idnumber: str = ""


class UpdatedEntity(BaseModel):
    """Result from updating a department or position."""

    id: int
    idnumber: str = ""


class UnassignedManager(BaseModel):
    """Record from ``tool_organisation_unassign_managers``."""

    itemid: int = 0
    userid: int = 0
    managerid: int = 0


# ---------------------------------------------------------------
# Feature 14: Competencies & Learning Plans
# ---------------------------------------------------------------


class CompetencyFramework(BaseModel):
    """Competency framework from ``tool_lp_data_for_competency_frameworks_manage_page``."""

    id: int
    shortname: str = ""
    idnumber: str = ""
    description: str = ""
    competencycount: int = 0


class DepartmentMember(BaseModel):
    """User with job assignment from ``local_soliplex_get_department_members``."""

    userid: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    fullname: str = ""
    email: str = ""
    departmentid: int = 0
    departmentname: str = ""
    positionid: int = 0
    positionname: str = ""


class LearningPlan(BaseModel):
    """Learning plan from ``tool_lp_data_for_plans_page``."""

    id: int
    name: str = ""
    description: str = ""
    statusname: str = ""
    userid: int = 0


# ---------------------------------------------------------------
# Feature 15: Report Builder
# ---------------------------------------------------------------


class ReportSummary(BaseModel):
    """Report metadata from ``core_reportbuilder_list_reports``."""

    id: int
    name: str = ""
    source: str = ""
    sourcename: str | None = ""
    timecreated: int = 0
    timemodified: int = 0


class ReportRow(BaseModel):
    """Single data row from ``core_reportbuilder_retrieve_report``."""

    columns: list[str | None] = Field(default_factory=list)


class ReportData(BaseModel):
    """Report data from ``core_reportbuilder_retrieve_report``."""

    headers: list[str] = Field(default_factory=list)
    rows: list[ReportRow] = Field(default_factory=list)
    totalrowcount: int = 0


# ---------------------------------------------------------------
# Feature 16: Custom Completion Reports (adv_comp / utm)
# ---------------------------------------------------------------


class CompletionReportRow(BaseModel):
    """Row from ``local_soliplex_get_utm_report`` or ``local_soliplex_get_adv_comp_report``."""

    userid: int
    username: str = ""
    firstname: str = ""
    lastname: str = ""
    email: str = ""
    department: str | None = None
    starttime: int | None = None
    completedtime: int | None = None
