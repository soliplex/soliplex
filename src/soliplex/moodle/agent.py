"""Moodle Workplace factory agent with dynamic instructions.

The factory creates a standard ``pydantic_ai.Agent`` whose
``instructions`` parameter is an async callable.  Pydantic AI
evaluates instructions on EVERY request (unlike
``@agent.system_prompt`` which is skipped when AG-UI provides
``message_history``).  The callable pre-fetches Moodle data so
the LLM answers from context without tool calling.
"""

from __future__ import annotations

import logging

import pydantic_ai
from pydantic_ai.models import google as google_models
from pydantic_ai.models import openai as openai_models
from pydantic_ai.providers import google as google_providers
from pydantic_ai.providers import ollama as ollama_providers
from pydantic_ai.providers import openai as openai_providers

from soliplex import agents
from soliplex import config
from soliplex.moodle.client import MoodleClient

log = logging.getLogger(__name__)

MOODLE_BASE_PROMPT = """\
You are a training management assistant with access to \
Moodle Workplace data.

You can answer questions about courses, enrolled users, \
and completion status.

Present data in clear tables when appropriate.  If the \
Moodle data section below is empty or says unavailable, \
let the user know that Moodle data could not be loaded.
"""


def _build_model(
    agent_config: config.FactoryAgentConfig,
):
    """Build a pydantic-ai model from a factory agent config.

    Reuses the same provider logic as
    ``agents._get_default_agent_from_configs`` but works
    with ``FactoryAgentConfig`` (which lacks ``llm_provider_kw``).
    """
    ic = agent_config._installation_config
    extra = agent_config.extra_config

    provider_type = extra.get("provider_type", "ollama")
    model_name = extra.get("model_name", "gpt-oss:latest")

    if provider_type == "google":
        provider_kw = {}
        provider_base_url = extra.get("provider_base_url")
        if provider_base_url:
            provider_kw["base_url"] = provider_base_url
        provider_key = extra.get("provider_key")
        if provider_key:
            provider_kw["api_key"] = ic.get_secret(provider_key)
        provider = google_providers.GoogleProvider(**provider_kw)
        return google_models.GoogleModel(
            model_name=model_name,
            provider=provider,
        )

    if provider_type == "ollama":
        base_url = extra.get("provider_base_url")
        if base_url is None:
            base_url = ic.get_environment("OLLAMA_BASE_URL")
        provider_kw = {
            "base_url": f"{base_url}/v1",
            "api_key": "dummy",
        }
        provider = ollama_providers.OllamaProvider(**provider_kw)
        return openai_models.OpenAIChatModel(
            model_name=model_name,
            provider=provider,
        )

    # openai
    provider_kw = {}
    provider_base_url = extra.get("provider_base_url")
    if provider_base_url:
        provider_kw["base_url"] = provider_base_url
    provider_key = extra.get("provider_key")
    if provider_key:
        provider_kw["api_key"] = ic.get_secret(provider_key)
    provider = openai_providers.OpenAIProvider(**provider_kw)
    return openai_models.OpenAIChatModel(
        model_name=model_name,
        provider=provider,
    )


async def _fetch_moodle_context(
    client: MoodleClient,
) -> str:
    """Fetch all courses, enrollments, and completions.

    Returns a markdown-formatted string for injection
    into the system prompt.
    """
    courses = await client.get_courses()
    lines = ["## Moodle Workplace Data\n"]
    lines.append("### Courses")

    for c in courses:
        lines.append(f"- [{c.id}] {c.fullname}")
        enrolled = await client.get_enrolled_users(c.id)

        for u in enrolled:
            try:
                status = await client.get_course_completion_status(c.id, u.id)
                done = "COMPLETED" if status.completed else "incomplete"
            except Exception:
                done = "unknown"
            lines.append(f"  - {u.fullname} ({u.username}): {done}")

    return "\n".join(lines)


def moodle_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: agents.ToolConfigMap = None,
    mcp_client_toolset_configs: (config.MCP_ClientToolsetConfigMap) = None,
) -> pydantic_ai.Agent:
    """Create a Moodle Workplace agent.

    Returns a standard ``pydantic_ai.Agent`` with a dynamic
    system prompt that fetches Moodle data on every request.
    """
    ic = agent_config._installation_config
    extra = agent_config.extra_config

    base_url = ic.get_secret(extra["moodle_base_url"])
    token = ic.get_secret(extra["moodle_api_token"])
    client = MoodleClient(base_url=base_url, token=token)

    model = _build_model(agent_config)

    async def _instructions() -> str:
        """Build instructions with live Moodle data."""
        try:
            moodle_data = await _fetch_moodle_context(client)
        except Exception:
            log.exception("Failed to fetch Moodle data")
            moodle_data = (
                "Moodle data is currently unavailable. "
                "Answer from conversation context only."
            )
        return f"{MOODLE_BASE_PROMPT}\n{moodle_data}"

    agent = pydantic_ai.Agent(
        model=model,
        instructions=_instructions,
        deps_type=agents.AgentDependencies,
    )

    return agent
