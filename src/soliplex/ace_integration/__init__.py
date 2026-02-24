"""ACE (Agentic Context Engine) integration for Soliplex."""

from soliplex.ace_integration.config import ACERoomConfig
from soliplex.ace_integration.learning_hook import get_skillbook_context
from soliplex.ace_integration.learning_hook import learn_from_feedback
from soliplex.ace_integration.skillbook_store import SkillbookStore

__all__ = [
    "ACERoomConfig",
    "SkillbookStore",
    "get_skillbook_context",
    "learn_from_feedback",
]
