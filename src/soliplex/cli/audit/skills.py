from __future__ import annotations

import pathlib

import typer
from skills_ref import validator as skill_validator

from soliplex import installation
from soliplex.cli import types
from soliplex.cli.audit import _common as audit_common


def _find_skill_paths(to_search: pathlib.Path):
    """Yield a sequence of skill paths under 'to_search'

    Yielded values are paths, suitable for passing to
    'skill_parser.read_properties'.

    If 'to_search' has its own copy of 'SKILL.md', just yield the one
    config parsed from it.

    Otherwise, iterate over immediate subdirectories, yielding configs
    parsed from any which have copies of 'SKILL.md'
    """
    filename = "SKILL.md"
    config_file = to_search / filename

    if config_file.is_file():
        yield to_search

    else:
        for sub in sorted(to_search.glob("*")):
            # See #233
            if sub.name.startswith("."):
                continue

            if sub.is_dir():
                sub_config = sub / filename
                if sub_config.is_file():
                    yield sub
            else:  # pragma: NO COVER
                pass


def _invalid_skill_configs(
    the_installation: installation.Installation,
) -> dict:
    skills_errors: dict[str, list[str]] = {}

    available_skills = the_installation._config.skill_configs
    for skill_name, skill_config in available_skills.items():
        skill_errors = getattr(skill_config, "errors", None)
        if skill_errors:
            skills_errors[skill_name] = [str(e) for e in skill_errors]

    if skills_errors:
        return {"skills": skills_errors}
    return {}


def _invalid_filesystem_skills(
    the_installation: installation.Installation,
) -> dict:
    fs_errors: dict[str, list[str]] = {}

    for skills_path in the_installation._config.filesystem_skills_paths:
        for skill_path in _find_skill_paths(skills_path):
            skill_errors = skill_validator.validate(skill_path)
            if skill_errors:
                fs_errors[str(skill_path)] = [str(e) for e in skill_errors]

    if fs_errors:
        return {"skills_filesystem": fs_errors}
    return {}


def _audit_skills_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the skills section (rule header + configured + filesystem)."""
    quiet = ctx.obj["quiet"]
    the_installation = audit_common._get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = audit_common._quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured skills")
    tc_line()

    errors: dict = {}

    invalid = _invalid_skill_configs(the_installation)
    errors |= invalid
    config_invalid = invalid.get("skills", {})

    available_skills = the_installation._config.skill_configs
    for skill_name, skill_config in available_skills.items():
        tc_print(f"- [ {skill_config.kind}:{skill_name}  ]")
        skill_errors = config_invalid.get(skill_name)
        if skill_errors:
            tc_print("  Validation errors:")
            for error in skill_errors:
                tc_print(f"  - {error}")
        else:
            tc_print(f"  {skill_config.description}")
        tc_line()

    fs_invalid = _invalid_filesystem_skills(the_installation)
    errors |= fs_invalid
    fs_errors_map = fs_invalid.get("skills_filesystem", {})

    for skills_path in the_installation._config.filesystem_skills_paths:
        tc_print(f"Filesystem skills path: {skills_path}")
        for skill_path in _find_skill_paths(skills_path):
            tc_print(f"- {skill_path.name}")
            path_errors = fs_errors_map.get(str(skill_path))
            if path_errors:
                for error in path_errors:
                    tc_print(f"  {error}")
            else:
                tc_print("  OK")
        tc_line()

    return errors


def audit_skills(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List skills defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_skills_section(ctx, installation_path)
    audit_common._emit_errors(errors, quiet)
