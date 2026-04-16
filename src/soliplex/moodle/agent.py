"""Moodle Workplace factory agent with skill-based tool routing.

The factory creates a ``pydantic_ai.Agent`` that routes requests
to domain-specific skills via a ``SkillToolset``.  Each skill
contains a focused set of Moodle tools; the router LLM sees a
single ``execute_skill`` tool plus a short skill catalog instead
of ~100 individual tool schemas.
"""

from __future__ import annotations

import pydantic_ai
from haiku.skills import prompts as hs_prompts
from haiku.skills.agent import SkillToolset

from soliplex import agents
from soliplex import config
from soliplex.config import agents as config_agents
from soliplex.moodle.client import MoodleClient
from soliplex.moodle.skills import build_certifications_skill
from soliplex.moodle.skills import build_courses_skill
from soliplex.moodle.skills import build_organisation_skill
from soliplex.moodle.skills import build_programs_skill
from soliplex.moodle.skills import build_reporting_skill
from soliplex.moodle.skills import build_rules_skill
from soliplex.moodle.skills import build_users_skill

MOODLE_ROUTER_PROMPT = """\
You are a training management assistant connected to \
Moodle Workplace.

IMPORTANT: Always call the relevant skill BEFORE answering. \
Never claim data is missing without checking first.

## Routing rules
- Route each request to the most relevant skill.
- If a request spans multiple skills, call them in sequence \
— passing concrete IDs from one result into the next request. \
For example, to enrol a user by name: first call moodle-users \
to look up their ID, then call moodle-courses to enrol by ID.
- Each skill is an isolated agent that cannot see the \
conversation. Include ALL necessary data (IDs, names, \
parameters) in the request.

## Write operation confirmation
Many skills support write operations that require confirmation. \
When a skill returns a preview with confirmation instructions:
1. Present the preview to the user and ask "Should I proceed?"
2. Only after the user approves, call the skill again with a \
request that explicitly states the action is confirmed, \
including the concrete IDs from the preview.

Present data in clear tables when appropriate.
"""


def moodle_tools_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: agents.ToolConfigMap = None,
    mcp_client_toolset_configs: (config.MCP_ClientToolsetConfigMap) = None,
    skill_toolset_config: (agents.SkillToolsetConfig | None) = None,
) -> pydantic_ai.Agent:
    """Create a Moodle Workplace router agent with skills.

    Builds seven domain-specific Moodle skills and exposes them
    via a ``SkillToolset`` in subagent mode.  The router LLM
    sees ``execute_skill(skill_name, request)`` plus a short
    catalog; each skill invocation spawns a separate agent run
    with only that skill's tools loaded.

    Required ``extra_config`` keys on *agent_config*:

    * ``moodle_base_url`` — secret reference for the Moodle
      instance URL.
    * ``moodle_api_token`` — secret reference for the web
      service token.

    Optional ``extra_config`` keys:

    * ``moodle_verify_ssl`` — path to a CA bundle or ``False``
      to disable TLS verification (passed through to
      ``MoodleClient``).
    * ``provider_type``, ``model_name``, etc. — forwarded to
      ``get_model_from_factory_config``.
    """
    ic = agent_config._installation_config
    extra = agent_config.extra_config

    base_url = ic.get_secret(extra["moodle_base_url"])
    token = ic.get_secret(extra["moodle_api_token"])
    verify = extra.get("moodle_verify_ssl")
    client = MoodleClient(base_url=base_url, token=token, verify=verify)

    model = config_agents.get_model_from_factory_config(agent_config)
    model_settings = config_agents.get_model_settings_from_factory_config(
        agent_config
    )

    # -- Build seven Moodle skills --------------------------
    moodle_skills = [
        build_courses_skill(client),
        build_users_skill(client),
        build_organisation_skill(client),
        build_certifications_skill(client),
        build_programs_skill(client),
        build_rules_skill(client),
        build_reporting_skill(client),
    ]

    # -- Merge external skills (e.g. RAG) if provided -------
    all_skills = list(moodle_skills)
    if skill_toolset_config is not None:
        moodle_names = {s.metadata.name for s in moodle_skills}
        ext_toolset = skill_toolset_config.skill_toolset
        for name in ext_toolset.registry.names:
            if name not in moodle_names:
                all_skills.append(ext_toolset.registry.get(name))

    # -- Assemble router agent ------------------------------
    toolset = SkillToolset(skills=all_skills, use_subagents=True)
    instructions = hs_prompts.build_system_prompt(
        preamble=MOODLE_ROUTER_PROMPT,
        skill_catalog=toolset.skill_catalog,
    )

    return pydantic_ai.Agent(
        model=model,
        model_settings=model_settings,
        instructions=instructions,
        toolsets=[toolset],
        deps_type=agents.AgentDependencies,
    )
