from __future__ import annotations

import asyncio
import pathlib
import sys
import warnings

import typer
import yaml
from haiku.rag import client as hr_client
from skills_ref import validator as skill_validator
from typer import core as typer_core

from soliplex import installation
from soliplex import models
from soliplex import secrets
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.config import installation as config_installation
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rag as config_rag

the_console = cli_util.the_console


AUDIT_HELP = "Audit a Soliplex installation configuration"


_QUIET_OPTION = typer.Option(
    False,
    "-q",
    "--quiet",
    help="Show only errors",
)


def _noop(*args, **kwargs):  # pragma: NO COVER
    return None


def _quiet_console_funcs(quiet):
    """Return ``(line, rule, print, print_exception)`` callables.

    When ``quiet`` is true the returned callables are no-ops, suppressing
    human-focused output.
    """
    if quiet:
        return _noop, _noop, _noop, _noop
    return (
        the_console.line,
        the_console.rule,
        the_console.print,
        the_console.print_exception,
    )


def _emit_errors(errors, quiet):
    """Emit a JSON error report (in quiet mode) and exit ``1`` if any."""
    if errors:
        if quiet:
            the_console.print_json(data=errors)
        sys.exit(1)


def _get_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> installation.Installation:
    """Load the installation once per invocation, caching on ``ctx.obj``."""
    cached = ctx.obj.get("the_installation")
    if cached is None:
        cached = cli_util.get_installation(installation_path, auditing=True)
        ctx.obj["the_installation"] = cached
    return cached


class _AuditGroup(typer_core.TyperGroup):
    """Default to the 'all' subcommand when none is given.

    Allows 'soliplex-cli audit', 'soliplex-cli audit -q', and
    'soliplex-cli audit <path>' as shorthands for the corresponding
    'soliplex-cli audit all ...' invocation. The path-less forms rely
    on Typer's ``SOLIPLEX_INSTALLATION_PATH`` envvar fallback on
    'audit all'.
    """

    def parse_args(self, ctx, args):
        for i, token in enumerate(args):
            if token.startswith("-"):
                continue
            if token not in self.commands:
                args = [*args[:i], "all", *args[i:]]
            break
        else:
            args = [*args, "all"]
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="audit",
    help=AUDIT_HELP,
    cls=_AuditGroup,
)


@app.callback()
def _audit_callback(
    ctx: typer.Context,
    quiet: bool = _QUIET_OPTION,
):
    ctx.obj = {"quiet": quiet}


@app.command(
    "all",
    help=AUDIT_HELP,
)
def audit_all(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    quiet = ctx.obj["quiet"]
    errors: dict = {}

    errors |= _audit_installation_section(ctx, installation_path)
    errors |= _audit_secrets_section(ctx, installation_path)
    errors |= _audit_environment_section(ctx, installation_path)
    errors |= _audit_oidc_section(ctx, installation_path)
    errors |= _audit_rooms_section(ctx, installation_path)
    errors |= _audit_completions_section(ctx, installation_path)
    errors |= _audit_quizzes_section(ctx, installation_path)
    errors |= _audit_skills_section(ctx, installation_path)
    errors |= _audit_logging_section(ctx, installation_path)
    errors |= _audit_logfire_section(ctx, installation_path)

    _emit_errors(errors, quiet)


def _invalid_installation(
    the_installation: installation.Installation,
) -> dict:
    errors = {}

    try:
        models.Installation.from_config(the_installation._config)
    except Exception as exc:
        errors["installation_model"] = str(exc)

    return errors


def _audit_installation_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the installation-model section (rule header + OK/ERROR)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured installation model")
    tc_line()

    errors = _invalid_installation(the_installation)
    exc = errors.get("installation_model")
    if exc:
        tc_print(f"ERROR: {exc}")
    else:
        tc_print("OK")
    return errors


@app.command("installation")
def audit_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Check that the installation config renders as a model"""
    quiet = ctx.obj["quiet"]
    errors = _audit_installation_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _missing_secrets(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = exc.secret_names.split(",")
        return {"missing_secrets": missing}
    return {}


def _audit_secrets_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the secrets section (rule header + per-secret OK/MISSING)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured secrets")
    tc_line()

    errors = _missing_secrets(the_installation)
    missing_names = set(errors.get("missing_secrets", ()))

    for secret_config in the_installation._config.secrets:
        flag = (
            "MISSING" if secret_config.secret_name in missing_names else "OK"
        )
        tc_print(f"- {secret_config.secret_name:25} {flag}")

    tc_print()
    return errors


@app.command("secrets")
def audit_secrets(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List secrets defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_secrets_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _missing_env_vars(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        missing = exc.env_vars.split(",")
        return {"missing_env_vars": missing}
    return {}


def _audit_environment_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    *,
    verbose: bool = False,
) -> dict:
    """Print the environment section (rule header + per-var listing)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured environment")
    tc_line()

    errors = _missing_env_vars(the_installation)
    missing = set(errors.get("missing_env_vars", ()))

    for key, value in the_installation._config.environment.items():
        if key in missing:
            value = "MISSING"

        tc_print(f"- {key:25}: {value}")

        if verbose:
            for i_source, source in enumerate(
                the_installation.get_environment_sources(key)
            ):
                mark = " " if i_source else "*"
                tc_print(
                    f"  {mark}{str(source.source_type):24}: {source.value}"
                )

        tc_print()

    tc_print()
    return errors


@app.command("environment")
def audit_environment(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="""\
Show available sources, and which is selected.
""",
    ),
):
    """List environment variables defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_environment_section(
        ctx,
        installation_path,
        verbose=verbose,
    )
    _emit_errors(errors, quiet)


def _invalid_oidc_auth_providers(
    the_installation: installation.Installation,
) -> dict:
    errors = {}

    for oidc_config in the_installation.oidc_auth_system_configs:
        try:
            models.OIDCAuthSystem.from_config(oidc_config)
        except Exception as exc:
            errors.setdefault("oidc", {})[oidc_config.id] = str(exc)

    return errors


def _audit_oidc_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the OIDC section (rule header + per-provider listing)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured OIDC authentication systems")
    tc_line()

    errors = _invalid_oidc_auth_providers(the_installation)
    invalid_providers = errors.get("oidc", {})

    for oidc_config in the_installation.oidc_auth_system_configs:
        tc_print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        tc_print(f"  {oidc_config.server_url}")
        exc = invalid_providers.get(oidc_config.id)
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        tc_line()

    return errors


@app.command("oidc")
def audit_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_oidc_section(ctx, installation_path)
    _emit_errors(errors, quiet)


async def _async_count(rag):
    with warnings.catch_warnings():
        return await rag.count_documents()


def _count_rag_documents(rag: hr_client.HaikuRAG):
    try:
        count = asyncio.run(_async_count(rag))
    except Exception:
        return "error"

    return f"{count} documents"


def _invalid_rooms(the_installation: installation.Installation) -> dict:
    errors: dict[str, str] = {}

    for room_config in the_installation._config.room_configs.values():
        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            errors[room_config.id] = str(exc)

    if errors:
        return {"room": errors}
    return {}


def _iter_room_rag_candidates(room_config):
    """Yield ``(source_label, cfg)`` for each RAG-bearing sub-config."""
    if isinstance(room_config.agent_config, config_rag._RAGConfigBase):
        yield "agent", room_config.agent_config

    if room_config.skills is not None:
        for s_name, s_config in room_config.skills.skill_configs.items():
            if isinstance(s_config, config_rag._RAGConfigBase):
                yield f"skill:{s_name}", s_config

    for tool_config in room_config.tool_configs.values():
        if isinstance(tool_config, config_rag._RAGConfigBase):
            yield f"tool:{tool_config.tool_name}", tool_config


def _invalid_room_rag_dbs(
    the_installation: installation.Installation,
) -> dict:
    rag_errors: dict[str, dict[str, str]] = {}

    for room_config in the_installation._config.room_configs.values():
        per_room: dict[str, str] = {}

        for source, cfg in _iter_room_rag_candidates(room_config):
            try:
                cfg.rag_lancedb_path  # noqa B018
            except Exception as exc:
                per_room[source] = str(exc)

        if per_room:
            rag_errors[room_config.id] = per_room

    if rag_errors:
        return {"rag": rag_errors}
    return {}


def _audit_rooms_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the rooms section (rule header + per-room RAG validity/counts)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured rooms")
    tc_line()

    errors: dict = {}

    invalid = _invalid_rooms(the_installation)
    errors |= invalid
    invalid_rooms = invalid.get("room", {})

    rag_invalid = _invalid_room_rag_dbs(the_installation)
    errors |= rag_invalid
    rag_invalid_rooms = rag_invalid.get("rag", {})

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs
    cwd = pathlib.Path.cwd()

    for room_config in available_rooms.values():
        tc_print(f"- [ {room_config.id} ] {room_config.name}: ")
        tc_print(f"  {room_config.description}")

        room_exc = invalid_rooms.get(room_config.id)
        if room_exc is not None:
            tc_print(f"  ERROR: {room_exc}")

        per_room_rag = rag_invalid_rooms.get(room_config.id, {})
        candidates = list(_iter_room_rag_candidates(room_config))

        if candidates:
            tc_print()
            tc_print("   Haiku Rag DBs")
            for source, cfg in candidates:
                exc = per_room_rag.get(source)
                if exc is not None:
                    tc_print(f"   - {source:20}: ERROR: {exc}")
                else:
                    db_path = cfg.rag_lancedb_path.relative_to(cwd)
                    rag = hr_client.HaikuRAG(
                        db_path=cfg.rag_lancedb_path,
                        config=cfg.haiku_rag_config,
                        read_only=True,
                    )
                    count = _count_rag_documents(rag)
                    if count == "error":
                        room_rag_errors = errors.setdefault(
                            "rag_count", {}
                        ).setdefault(room_config.id, {})
                        room_rag_errors[source] = "count failed"
                    tc_print(f"   - {source:20}: {str(db_path):30} {count}")
                tc_print()
        tc_line()

    return errors


@app.command("rooms")
def audit_rooms(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List rooms defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_rooms_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _invalid_completions(
    the_installation: installation.Installation,
) -> dict:
    errors = {}

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs

    for compl_config in available_completions.values():
        try:
            models.Completion.from_config(compl_config)
        except Exception as exc:
            errors.setdefault("completions", {})[compl_config.id] = str(exc)

    return errors


def _audit_completions_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the completions section (rule header + per-completion entry)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured completions")
    tc_line()

    errors = _invalid_completions(the_installation)
    invalid_completions = errors.get("completions", {})

    available_completions = the_installation._config.completion_configs
    for compl_config in available_completions.values():
        tc_print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        exc = invalid_completions.get(compl_config.id)
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        else:
            tc_print("  OK")
        tc_line()

    return errors


@app.command("completions")
def audit_completions(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List completions defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_completions_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _iter_quiz_configs(the_installation):
    for q_path in the_installation._config.quizzes_paths:
        for q_file in q_path.glob("*.json"):
            yield (
                q_path,
                q_file,
                config_quizzes.QuizConfig(
                    id="check",
                    question_file=str(q_file),
                ),
            )


def _invalid_quizzes(the_installation: installation.Installation) -> dict:
    errors = {}

    for q_path, q_file, q_config in _iter_quiz_configs(the_installation):
        try:
            q_config.get_questions()
        except Exception as exc:
            q_error = f"{exc}"
            quizzes_errors = errors.setdefault("quizzes", {})
            q_path_errors = quizzes_errors.setdefault(str(q_path), {})
            q_path_errors[q_file.name] = q_error

    return errors


def _audit_quizzes_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the quizzes section (rule header + per-file OK / Invalid)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured quizzes")
    tc_line()

    errors = _invalid_quizzes(the_installation)
    invalid_quizzes = errors.get("quizzes", {})

    seen_path = None
    for q_path, q_file, _q_config in _iter_quiz_configs(the_installation):
        if q_path != seen_path:
            tc_print(f"Quiz path: {q_path}")
            seen_path = q_path

        tc_print(f"- Question file: {q_file.name}")
        exc = invalid_quizzes.get(str(q_path), {}).get(q_file.name)

        if exc:
            tc_print(f"  Invalid quiz file: {exc}")
        else:
            tc_print("  OK")
        tc_line()

    return errors


@app.command("quizzes")
def audit_quizzes(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List quizzes defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_quizzes_section(ctx, installation_path)
    _emit_errors(errors, quiet)


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
) -> dict:
    """Print the skills section (rule header + configured + filesystem)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

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


@app.command("skills")
def audit_skills(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List skills defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_skills_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _load_logging_config(the_installation):
    """Return parsed Python-logging YAML, or ``None`` when none is configured.

    Raises ``yaml.YAMLError`` or ``OSError`` if the configured file cannot
    be opened or parsed.
    """
    pyl_config = the_installation._config.logging_config_file
    if pyl_config is None:
        return None
    with pyl_config.open() as f:
        return yaml.safe_load(f)


def _invalid_logging(the_installation: installation.Installation) -> dict:
    try:
        _load_logging_config(the_installation)
    except (yaml.YAMLError, OSError) as exc:
        return {"logging": str(exc)}
    return {}


def _audit_logging_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the Python-logging section (rule header + config or defaults)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Python logging")
    tc_line()

    errors = _invalid_logging(the_installation)

    pyl_config = the_installation._config.logging_config_file
    if pyl_config is None:
        tc_print("OK (defaults)")
        return errors

    tc_print(f"Logging config: {pyl_config}")
    exc = errors.get("logging")
    if exc is not None:
        tc_print(exc)
    else:
        logging_config = _load_logging_config(the_installation)
        tc_print(logging_config)
        tc_print(
            f"Headers map: {the_installation._config.logging_headers_map}",
        )
        tc_print(
            f"Claims map: {the_installation._config.logging_claims_map}",
        )
        tc_print("OK")
    return errors


@app.command("logging")
def audit_logging(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Show the Python-logging config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logging_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _audit_logfire_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:
    """Print the Logfire section (rule header + config or defaults)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Logfire")
    tc_line()

    l_config = the_installation._config.logfire_config
    if l_config is not None:
        tc_print(l_config.as_yaml)
        tc_print("OK")
    else:
        tc_print("OK (defaults)")
    return {}


@app.command("logfire")
def audit_logfire(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """Show the Logfire config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logfire_section(ctx, installation_path)
    _emit_errors(errors, quiet)
