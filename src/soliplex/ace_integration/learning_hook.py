"""Feedback → Reflector → SkillManager learning pipeline."""

import asyncio
import logging

from ace import LiteLLMClient
from ace import Reflector
from ace import SkillManager
from ace.integrations.base import wrap_skillbook_context
from ace.roles import AgentOutput

from soliplex.ace_integration.config import ACERoomConfig
from soliplex.ace_integration.skillbook_store import SkillbookStore

logger = logging.getLogger(__name__)


def _run_learning_pipeline(
    *,
    room_id: str,
    run_id: str,
    feedback: str,
    reason: str | None,
    question: str,
    answer: str,
    skillbook_store: SkillbookStore,
    ace_config: ACERoomConfig,
) -> None:
    """Synchronous learning pipeline (runs in a thread)."""
    skillbook = skillbook_store.get_for_room(room_id)
    llm = LiteLLMClient(model=ace_config.learning_model)
    reflector = Reflector(llm)
    skill_manager = SkillManager(llm)

    feedback_text = feedback
    if reason:
        feedback_text = f"{feedback}: {reason}"

    agent_output = AgentOutput(
        reasoning=f"User question: {question}",
        final_answer=answer,
        skill_ids=[],
    )

    reflection = reflector.reflect(
        question=question,
        agent_output=agent_output,
        skillbook=skillbook,
        feedback=feedback_text,
    )

    sm_output = skill_manager.update_skills(
        reflection=reflection,
        skillbook=skillbook,
        question_context=question,
        progress="feedback",
    )

    skillbook.apply_update(sm_output.update)
    skillbook_store.persist(room_id)

    logger.info(
        "ACE learning complete for room=%s run=%s",
        room_id,
        run_id,
    )


async def learn_from_feedback(
    *,
    room_id: str,
    thread_id: str,
    run_id: str,
    feedback: str,
    reason: str | None,
    question: str,
    answer: str,
    skillbook_store: SkillbookStore,
    ace_config: ACERoomConfig,
) -> None:
    """Run the ACE learning pipeline for a single feedback event.

    This is designed to be called via ``asyncio.create_task`` so it does
    not block the HTTP response.  The blocking LLM calls run in a
    thread via ``asyncio.to_thread``.

    Parameters
    ----------
    question, answer:
        The user question and agent answer extracted from the run events.
    """
    try:
        await asyncio.to_thread(
            _run_learning_pipeline,
            room_id=room_id,
            run_id=run_id,
            feedback=feedback,
            reason=reason,
            question=question,
            answer=answer,
            skillbook_store=skillbook_store,
            ace_config=ace_config,
        )

    except Exception:
        logger.exception(
            "ACE learning failed for room=%s run=%s",
            room_id,
            run_id,
        )


def get_skillbook_context(
    skillbook_store: SkillbookStore,
    room_id: str,
) -> str:
    """Return formatted skillbook context for system prompt injection."""
    skillbook = skillbook_store.get_for_room(room_id)
    return wrap_skillbook_context(skillbook)
