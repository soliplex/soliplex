from __future__ import annotations

import asyncio
import pathlib
import sys
import warnings

import typer
import yaml
from haiku.rag import client as hr_client
from skills_ref import validator as skill_validator
from typer.core import TyperGroup

from soliplex import installation
from soliplex import models
from soliplex import secrets
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.config import installation as config_installation
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rag as config_rag

the_console = cli_util.the_console


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


AUDIT_HELP = "Audit the installation configuration"


_QUIET_OPTION = typer.Option(
    False,
    "-q",
    "--quiet",
    help="Show only errors",
)


def _quiet_console_funcs(quiet):
    """Return ``(line, rule, print, print_exception)`` callables.

    When ``quiet`` is true the returned callables are no-ops, suppressing
    human-focused output.
    """
    if quiet:
        noop = lambda *args, **kwargs: None  # noqa E731
        return noop, noop, noop, noop
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


class _AuditGroup(TyperGroup):
    """Default to the 'installation' subcommand when none is given.

    Allows 'soliplex-cli audit <path>' as shorthand for
    'soliplex-cli audit installation <path>'.
    """

    def parse_args(self, ctx, args):
        for i, token in enumerate(args):
            if token.startswith("-"):
                continue
            if token not in self.commands:
                args = [*args[:i], "installation", *args[i:]]
            break
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="audit",
    help=AUDIT_HELP,
    cls=_AuditGroup,
    no_args_is_help=True,
)


@app.callback()
def _audit_callback(
    ctx: typer.Context,
    quiet: bool = _QUIET_OPTION,
):
    ctx.obj = {"quiet": quiet}


@app.command(
    "installation",
    help=AUDIT_HELP,
)
def audit_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )
    errors = {}

    tc_line, tc_rule, tc_print, tc_print_exception = _quiet_console_funcs(
        quiet
    )

    tc_line()
    tc_rule("Checking secrets")
    tc_line()
    missing = _missing_secrets(the_installation)
    errors |= missing

    if missing:
        tc_print("Missing secrets")
        for secret_name in missing["missing_secrets"]:
            tc_print(f"- {secret_name}")
    else:
        tc_print("OK")

    tc_line()
    tc_rule("Checking environment")
    tc_line()
    missing = _missing_env_vars(the_installation)
    errors |= missing

    if missing:
        tc_line()
        tc_print("Missing environment variables")
        for env_var in missing["missing_env_vars"]:
            tc_print(f"- {env_var}")
    else:
        tc_print("OK")

    # Check that conversion to models doesn't raise
    tc_line()
    tc_rule("Validating installation model")
    tc_line()
    try:
        models.Installation.from_config(the_installation._config)
    except Exception as exc:
        errors["installation_model"] = str(exc)

        tc_print(exc)
    else:
        tc_print("OK")

    tc_line()
    tc_rule("Validating OIDC authentication systems")
    tc_line()
    invalid = _invalid_oidc_auth_providers(the_installation)
    errors |= invalid

    oidc_configs = the_installation.oidc_auth_system_configs
    invalid_providers = invalid.get("oidc", {})

    for oidc_config in oidc_configs:
        tc_print(f"OIDC system: {oidc_config.id}")
        exc = invalid_providers.get(oidc_config.id)
        if exc is not None:
            tc_print(exc)
        else:
            tc_print("OK")
        tc_line()

    tc_line()
    tc_rule("Validating rooms")
    tc_line()
    invalid = _invalid_rooms(the_installation)
    errors |= invalid
    invalid_rooms = invalid.get("room", {})

    rag_invalid = _invalid_room_rag_dbs(the_installation)
    errors |= rag_invalid
    rag_invalid_rooms = rag_invalid.get("rag", {})

    room_configs = the_installation._config.room_configs

    for room_config in room_configs.values():
        tc_line()
        tc_print(f"Room: {room_config.id}")
        exc = invalid_rooms.get(room_config.id)
        if exc is not None:
            tc_print(exc)
        else:
            tc_print("OK")

        per_room = rag_invalid_rooms.get(room_config.id, {})
        candidates = list(_iter_room_rag_candidates(room_config))

        if candidates:
            tc_line()
            tc_print("  Haiku Rag DBs")

            for source, _cfg in candidates:
                tc_print(f"  - {source} RAG DB")
                exc = per_room.get(source)
                if exc is not None:
                    tc_print(f"    {exc}")
                else:
                    tc_print("    OK")

    tc_line()
    tc_rule("Validating completions")
    tc_line()
    completion_configs = the_installation._config.completion_configs
    invalid = _invalid_completions(the_installation)
    errors |= invalid
    invalid_completions = invalid.get("completions", {})

    for compl_config in completion_configs.values():
        tc_print(f"Completion: {compl_config.id}")
        exc = invalid_completions.get(compl_config.id)
        if exc is not None:
            tc_print(f"  {exc}")
        else:
            tc_print("  OK")
        tc_line()

    tc_line()
    tc_rule("Validating quizzes")
    tc_line()
    for q_path in the_installation._config.quizzes_paths:
        tc_print(f"Quizzes path: {q_path}")
        for q_file in q_path.glob("*.json"):
            tc_print(f"- Question file stem: {q_file.stem}")
            q_config = config_quizzes.QuizConfig(
                id="check",
                question_file=str(q_file),
            )
            try:
                q_config.get_questions()
            except Exception as exc:
                q_error = f"  Invalid quiz file: {exc}"
                errors.setdefault("quiz", {})[q_file] = q_error

                tc_print(q_error)
            else:
                tc_print("  OK")
        tc_line()

    tc_line()
    tc_rule("Validating Python logging")
    tc_line()
    pyl_config = the_installation._config.logging_config_file
    if pyl_config is not None:
        tc_print(f"Logging config: {pyl_config}")
        try:
            with pyl_config.open() as f:
                logging_config = yaml.safe_load(f)
        except yaml.YAMLError as y_exc:
            errors["logging"] = str(y_exc)

            tc_print_exception()

        except OSError as os_exc:
            errors["logging"] = str(os_exc)

            tc_print_exception()
        else:
            tc_print(logging_config)
            tc_print(
                f"Headers map: {the_installation._config.logging_headers_map}",
            )
            tc_print(
                f"Claims map: {the_installation._config.logging_claims_map}",
            )
            tc_print("OK")
    else:
        tc_print("OK (defaults)")
    tc_line()

    tc_line()
    tc_rule("Validating skills")
    tc_line()
    skills_errors = {}

    for skills_path in the_installation._config.filesystem_skills_paths:
        tc_print(f"Filesystem skills path: {skills_path}")
        for skill_path in _find_skill_paths(skills_path):
            tc_print(f"- {skill_path.name}")
            skill_errors = skill_validator.validate(skill_path)
            if skill_errors:
                sk_errors = skills_errors.setdefault(skill_path, [])
                for error in skill_errors:
                    sk_errors.append(str(error))

                    tc_print(f"  {error}")
            else:
                tc_print("  OK")
        tc_line()

    if skills_errors:
        errors["skills"] = skills_errors

    tc_line()
    tc_rule("Validating Logfire config")
    tc_line()
    l_config = the_installation._config.logfire_config
    if l_config is not None:
        tc_print(l_config.as_yaml)
        tc_print("OK")
    else:
        tc_print("OK (defaults)")
    tc_line()

    _emit_errors(errors, quiet)


def _missing_secrets(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = exc.secret_names.split(",")
        return {"missing_secrets": missing}
    return {}


@app.command("secrets")
def audit_secrets(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List secrets defined in the installation"""
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )
    errors = {}

    missing = _missing_secrets(the_installation)
    errors |= missing

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured secrets")
    tc_line()

    missing_names = set(missing.get("missing_secrets", ()))
    for secret_config in the_installation._config.secrets:
        flag = (
            "MISSING" if secret_config.secret_name in missing_names else "OK"
        )
        tc_print(f"- {secret_config.secret_name:25} {flag}")

    tc_print()

    _emit_errors(errors, quiet)


def _missing_env_vars(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        missing = exc.env_vars.split(",")
        return {"missing_env_vars": missing}
    return {}


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
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )
    errors = _missing_env_vars(the_installation)
    if errors:
        missing = set(errors["missing_env_vars"])
    else:
        missing = set()

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured environment variables")
    tc_line()

    errors = {}
    if missing:
        errors["missing_env_vars"] = sorted(missing)

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


@app.command("oidc")
def audit_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )
    errors = {}
    invalid = _invalid_oidc_auth_providers(the_installation)
    errors |= invalid

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured OIDC Auth Providers")
    tc_line()

    invalid_providers = invalid.get("oidc", {})

    for oidc_config in the_installation.oidc_auth_system_configs:
        tc_print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        tc_print(f"  {oidc_config.server_url}")
        exc = invalid_providers.get(oidc_config.id)
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        tc_line()

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


@app.command("rooms")
def audit_rooms(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List rooms defined in the installation"""
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Rooms")
    tc_line()

    errors = {}
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


@app.command("completions")
def audit_completions(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List completions defined in the installation"""
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )
    errors = {}
    invalid = _invalid_completions(the_installation)
    errors |= invalid

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Completions")
    tc_line()

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs
    invalid_completions = invalid.get("completions", {})

    for compl_config in available_completions.values():
        tc_print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        exc = invalid_completions.get(compl_config.id)
        if exc is not None:
            tc_print(f"  ERROR: {exc}")
        else:
            tc_print("  OK")
        tc_line()

    _emit_errors(errors, quiet)


@app.command("skills")
def audit_skills(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List skills defined in the installation"""
    quiet = ctx.obj["quiet"]
    the_installation = cli_util.get_installation(
        installation_path,
        auditing=True,
    )

    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Skills")
    tc_line()

    errors = {}

    available_skills = the_installation._config.skill_configs
    for skill_name, skill_config in available_skills.items():
        tc_print(f"- [ {skill_config.kind}:{skill_name}  ]")
        skill_errors = getattr(skill_config, "errors", None)
        if skill_errors:
            errors.setdefault("skills", {})[skill_name] = [
                str(e) for e in skill_errors
            ]
            tc_print("  Validation errors:")
            for error in skill_errors:
                tc_print(f"  - {error}")
        else:
            tc_print(f"  {skill_config.description}")
        tc_line()

    _emit_errors(errors, quiet)
