"""Moodle Workplace integration for Soliplex.

Provides an async HTTP client for the Moodle REST Web Services API
and a pydantic-ai agent factory that routes requests to
domain-specific skills (courses, users, organisation,
certifications, programs, dynamic rules, and reporting).
"""

from soliplex.moodle.agent import MOODLE_ROUTER_PROMPT
from soliplex.moodle.agent import moodle_tools_agent_factory
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient
from soliplex.moodle.models import ActivityCompletionStatus
from soliplex.moodle.models import AssignmentGrade
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
from soliplex.moodle.models import CourseCategory
from soliplex.moodle.models import CourseModule
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import CreatedCategory
from soliplex.moodle.models import CreatedCourse
from soliplex.moodle.models import CreatedEntity
from soliplex.moodle.models import CreatedUser
from soliplex.moodle.models import Department
from soliplex.moodle.models import DepartmentMember
from soliplex.moodle.models import DuplicatedCourse
from soliplex.moodle.models import DuplicatedProgram
from soliplex.moodle.models import EnrolmentRequest
from soliplex.moodle.models import ExportStatus
from soliplex.moodle.models import GradeItem
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
from soliplex.moodle.models import ImportStatus
from soliplex.moodle.models import Job
from soliplex.moodle.models import LearningPlan
from soliplex.moodle.models import MessageRequest
from soliplex.moodle.models import Position
from soliplex.moodle.models import PotentialParent
from soliplex.moodle.models import Program
from soliplex.moodle.models import ProgramCourse
from soliplex.moodle.models import ProgramCourseOption
from soliplex.moodle.models import ReportData
from soliplex.moodle.models import ReportRow
from soliplex.moodle.models import ReportSummary
from soliplex.moodle.models import Tenant
from soliplex.moodle.models import UnassignedManager
from soliplex.moodle.models import UpdatedEntity
from soliplex.moodle.models import UserCatalogueItem
from soliplex.moodle.skills import build_certifications_skill
from soliplex.moodle.skills import build_courses_skill
from soliplex.moodle.skills import build_organisation_skill
from soliplex.moodle.skills import build_programs_skill
from soliplex.moodle.skills import build_reporting_skill
from soliplex.moodle.skills import build_rules_skill
from soliplex.moodle.skills import build_users_skill

__all__ = [
    "MOODLE_ROUTER_PROMPT",
    "ActivityCompletionStatus",
    "AssignmentGrade",
    "BulkOperationResult",
    "CalendarEvent",
    "CatalogueItem",
    "CertificationSearchResult",
    "Certification",
    "CertificationAllocation",
    "CertificationLogEntry",
    "Cohort",
    "CompletionReportRow",
    "CourseCategory",
    "CreatedCategory",
    "CreatedCourse",
    "CreatedEntity",
    "CreatedUser",
    "CohortMembers",
    "CompetencyFramework",
    "CourseModule",
    "CourseSection",
    "Department",
    "DepartmentMember",
    "DuplicatedCourse",
    "DuplicatedProgram",
    "ExportStatus",
    "EnrolmentRequest",
    "GradeItem",
    "ImportStatus",
    "Group",
    "GroupMembers",
    "Job",
    "LearningPlan",
    "MessageRequest",
    "MoodleAPIError",
    "MoodleClient",
    "Position",
    "PotentialParent",
    "Program",
    "ProgramCourse",
    "ProgramCourseOption",
    "ReportData",
    "ReportRow",
    "ReportSummary",
    "Tenant",
    "UnassignedManager",
    "UpdatedEntity",
    "UserCatalogueItem",
    "build_certifications_skill",
    "build_courses_skill",
    "build_organisation_skill",
    "build_programs_skill",
    "build_reporting_skill",
    "build_rules_skill",
    "build_users_skill",
    "moodle_tools_agent_factory",
]
