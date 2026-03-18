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
from soliplex.moodle.models import CalendarEvent
from soliplex.moodle.models import Certification
from soliplex.moodle.models import CertificationAllocation
from soliplex.moodle.models import CertificationLogEntry
from soliplex.moodle.models import Cohort
from soliplex.moodle.models import CohortMembers
from soliplex.moodle.models import CourseModule
from soliplex.moodle.models import CourseSection
from soliplex.moodle.models import EnrolmentRequest
from soliplex.moodle.models import GradeItem
from soliplex.moodle.models import Group
from soliplex.moodle.models import GroupMembers
from soliplex.moodle.models import MessageRequest
from soliplex.moodle.models import Program
from soliplex.moodle.models import ProgramCourse
from soliplex.moodle.models import Tenant

__all__ = [
    "ActivityCompletionStatus",
    "AssignmentGrade",
    "CalendarEvent",
    "Certification",
    "CertificationAllocation",
    "CertificationLogEntry",
    "Cohort",
    "CohortMembers",
    "CourseModule",
    "CourseSection",
    "EnrolmentRequest",
    "GradeItem",
    "Group",
    "GroupMembers",
    "MessageRequest",
    "MoodleAPIError",
    "MoodleClient",
    "Program",
    "ProgramCourse",
    "Tenant",
    "moodle_tools_agent_factory",
]
