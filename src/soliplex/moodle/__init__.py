"""Moodle Workplace integration for Soliplex.

Provides an async HTTP client for the Moodle REST Web Services API
and a pydantic-ai agent factory that exposes Moodle data as LLM
tools (courses, users, enrollment, completion, groups, grades,
calendar, and write operations).
"""

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
from soliplex.moodle.models import CourseModule
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import CreatedEntity
from soliplex.moodle.models import Department
from soliplex.moodle.models import DepartmentMember
from soliplex.moodle.models import DuplicatedProgram
from soliplex.moodle.models import EnrolmentRequest
from soliplex.moodle.models import GradeItem
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
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

__all__ = [
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
    "CreatedEntity",
    "CohortMembers",
    "CompetencyFramework",
    "CourseModule",
    "CourseSection",
    "Department",
    "DepartmentMember",
    "DuplicatedProgram",
    "EnrolmentRequest",
    "GradeItem",
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
    "moodle_tools_agent_factory",
]
