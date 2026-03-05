"""Moodle Workplace integration for Soliplex.

Provides an async HTTP client for the Moodle REST Web Services API
and a pydantic-ai agent factory that exposes Moodle data as LLM
tools (courses, users, enrollment, completion).
"""

from soliplex.moodle.agent import moodle_tools_agent_factory
from soliplex.moodle.client import MoodleAPIError
from soliplex.moodle.client import MoodleClient

__all__ = ["MoodleAPIError", "MoodleClient", "moodle_tools_agent_factory"]
