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

from soliplex import agents
from soliplex import config
from soliplex.config import agents as config_agents
from soliplex.config.skills import SoliplexSkillToolset
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

CRITICAL: You have NO knowledge of any Moodle data \
(courses, users, certifications, cohorts, programs, \
rules, departments, etc.) except what skill calls \
return. NEVER invent IDs, names, descriptions, counts, \
or other data. If a user asks about Moodle data, you \
MUST call the relevant skill via execute_skill — even \
if you think you remember the answer. If you respond \
without calling a skill on a data question, you are \
hallucinating.

## Routing rules
- Route each request to the most relevant skill.
- If a request spans multiple skills, call them in sequence \
— passing concrete IDs from one result into the next request. \
For example, to enrol a user by name: first call moodle-users \
to look up their ID, then call moodle-courses to enrol by ID.
- Each skill is an isolated agent that cannot see the \
conversation. Include ALL necessary data (IDs, names, \
parameters) in the request.

## Routing examples
- "list cohorts" / "cohort members" → moodle-courses
- "list tenants" → moodle-users
- "search cohorts/competencies for rule conditions" → \
moodle-rules (NOT moodle-courses or moodle-programs)
- "export courses/programs/certifications/users from \
Workplace" → moodle-reporting (NOT moodle-courses)
- "calendar events" / "training deadlines" / "upcoming \
deadlines" with no user specified → moodle-courses (call \
get_upcoming_events with no arguments)
- "completion report for <course name>": first call \
moodle-courses with "find course named X" to resolve the \
ID, then call moodle-reporting with the numeric ID
- "grades for user X" without a specific course: first \
call moodle-users find_user to resolve name → ID, then \
moodle-courses list_courses, then moodle-courses \
get_user_grades for each course
- "search certifications by name" / "find all \
certifications" / "what certifications exist" → \
moodle-certifications (call search_certifications or \
list_certifications; never ask the user for a search \
term — return all)
- "what dynamic rules exist" → moodle-rules \
(list_dynamic_rules)
- "update user N and change their department/email/name/\
etc." → moodle-users (update_user). The user.department \
field is a free-form string on the user profile; do NOT \
interpret this as a request to create or look up a \
Workplace organisation department.
- "create department X" / "delete department Y" / \
"assign manager" / "list departments" → \
moodle-organisation. The Workplace organisation \
department is a separate concept from the per-user \
department string.

## Anti-patterns (do NOT do these)
- Do NOT ask the user clarifying questions when a tool \
exists with sensible defaults. Dispatch first; if the \
tool returns nothing useful, then ask.
- Do NOT answer questions about Moodle data without \
calling a skill — even if the answer seems "obvious".

## Write operation confirmation
Skills are isolated subagents — each `execute_skill` call \
runs FRESH with no memory of prior previews. You (the \
router) are the ONLY component that sees the full \
conversation. This means YOU must carry preview context \
forward on confirmation.

When a skill returns a preview JSON for a write tool:
1. Render the preview's top-level fields (name, idnumber, \
parent, action, etc.) to the user as a markdown table, \
then ask "Should I proceed?".
2. Save mentally: which tool was previewed, and every \
parameter value the preview contains.
3. When the user confirms (says "yes", "go ahead", \
"confirm", "proceed", "do it", "yes please", or \
similar), DO NOT forward that bare phrase to the skill. \
Instead, call execute_skill with a self-contained \
request that:
   a. Names the exact tool (e.g. create_department, \
delete_department, certify_user, archive_program, etc.)
   b. Repeats EVERY parameter from the preview verbatim \
(name, idnumber, courseid, programid, ruleid, etc.)
   c. Ends with `confirmed=True`
   Example after a Security/SEC dept preview:
      execute_skill(skill_name="moodle-organisation", \
request="Call create_department with name='Security', \
idnumber='SEC', parent='', description='', \
confirmed=True")
   Example after a delete-department preview for SEC:
      execute_skill(skill_name="moodle-organisation", \
request="Call delete_department with idnumber='SEC', \
confirmed=True")
   Example after a duplicate_program preview for ID 2:
      execute_skill(skill_name="moodle-programs", \
request="Call duplicate_program with programid=2, \
confirmed=True")
4. If the user says "no", "cancel", or rejects, do NOT \
re-invoke the skill — just acknowledge.

CRITICAL: NEVER forward a bare "yes" / "go ahead" / \
"confirm" to a skill. The skill's subagent has no idea \
what was previewed. You MUST reconstruct the full tool \
call from the preview JSON in your conversation history.

## Reporting results to the user

After a confirmed write, the skill returns JSON.  The result \
status is unambiguous and you MUST honour it:

- ``"status": "ok"`` — the write succeeded.  Report it in one \
short sentence using ONLY values that appear in the result.  \
Do NOT invent IDs or names.
- ``"status": "error"`` — the write FAILED.  Surface the \
failure to the user, including the error message.  NEVER \
claim success.  NEVER fabricate IDs.
- No status field — the result is from a read tool or a \
preview.  Render it as a table or as a confirmation request.

Even a bare ``execute_skill`` result with no recognisable \
content does NOT mean "succeeded" — if you don't see \
``"status": "ok"`` in the skill output, the write did not \
happen.

Present data in clear tables when appropriate.
"""


def moodle_tools_agent_factory(
    agent_config: config.FactoryAgentConfig,
    *,
    tool_configs: agents.ToolConfigMap = None,  # noqa: U100
    mcp_client_toolset_configs: (config.MCP_ClientToolsetConfigMap) = None,  # noqa: U100
    skill_toolset_config: (agents.SkillToolsetConfig | None) = None,
) -> agents.SoliplexAgent:
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
    # Persistent httpx.AsyncClient inside `client` survives across
    # tool calls; close it on FastAPI shutdown.
    ic.register_cleanup(client.aclose)

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
    toolset = SoliplexSkillToolset(skills=all_skills, use_subagents=True)
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
