"""Findings for config file paths which resolve outside their directory

Covers each room's 'logo_image', and the 'system_prompt' file of every
agent config:  the installation's 'agent_configs', and each room's and
each completion's agent.  The reports are gathered once per invocation,
and cached on 'ctx.obj'.
"""

from __future__ import annotations

import typer

from soliplex import installation
from soliplex.config import agents as config_agents
from soliplex.config import exceptions as config_exc

INSTALLATION = "installation"
ROOMS = "rooms"
COMPLETIONS = "completions"


def _non_local_path_finding(exc: config_exc.PathNotLocal) -> dict:
    """Return the finding recorded for a config path outside its directory"""
    return {"config_dir": str(exc.config_dir), "path": exc.path}


def _agent_config_findings(agent_config) -> dict:
    """Return findings for an agent config's non-local prompt file

    Agent configs other than 'AgentConfig' (e.g. 'FactoryAgentConfig')
    name no prompt file, and yield no findings.
    """
    findings = {}

    if isinstance(agent_config, config_agents.AgentConfig):
        try:
            agent_config.get_system_prompt_path()
        except config_exc.PathNotLocal as exc:
            findings["system_prompt"] = _non_local_path_finding(exc)

    return findings


def _installation_reports(i_config) -> dict:
    """Return findings for the installation's agent configs, by ID"""
    reports = {}

    for agent_config in i_config.agent_configs:
        findings = _agent_config_findings(agent_config)

        if findings:
            reports[agent_config.id] = findings

    return reports


def _room_reports(i_config) -> dict:
    """Return findings for each room's logo and agent, by room ID"""
    reports = {}

    for room_config in i_config.room_configs.values():
        findings = {}

        try:
            room_config.get_logo_image()
        except config_exc.PathNotLocal as exc:
            findings["logo_image"] = _non_local_path_finding(exc)

        findings |= _agent_config_findings(room_config.agent_config)

        if findings:
            reports[room_config.id] = findings

    return reports


def _completion_reports(i_config) -> dict:
    """Return findings for each completion's agent, by completion ID"""
    reports = {}

    for compl_config in i_config.completion_configs.values():
        findings = _agent_config_findings(compl_config.agent_config)

        if findings:
            reports[compl_config.id] = findings

    return reports


def _non_local_path_reports(
    ctx: typer.Context,
    the_installation: installation.Installation,
) -> dict:
    """Gather the reports once per invocation, caching on 'ctx.obj'

    Keyed by 'INSTALLATION', 'ROOMS', and 'COMPLETIONS'.
    """
    cached = ctx.obj.get("non_local_path_reports")

    if cached is None:
        i_config = the_installation._config
        cached = {
            INSTALLATION: _installation_reports(i_config),
            ROOMS: _room_reports(i_config),
            COMPLETIONS: _completion_reports(i_config),
        }
        ctx.obj["non_local_path_reports"] = cached

    return cached


def _non_local_path_findings(reports: dict, kind: str) -> dict:
    """Return the audit findings for one kind of report, if any"""
    if reports[kind]:
        return {f"{kind}_non_local_paths": reports[kind]}

    return {}


def _non_local_prompt_ids(reports: dict, kind: str) -> set:
    """Return the IDs whose agent's prompt file is not local"""
    return {
        item_id
        for item_id, findings in reports[kind].items()
        if "system_prompt" in findings
    }


def _print_non_local_path_findings(
    tc_print,
    findings: dict,
    prefix: str,
) -> None:  # pragma NO COVER UI ONLY
    """Print an 'ERROR' line for each finding for one item"""
    for field, finding in findings.items():
        tc_print(
            f"{prefix}ERROR: {field} path not local to "
            f"{finding['config_dir']}: {finding['path']}"
        )
