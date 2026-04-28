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


class _AuditGroup(TyperGroup):
    """Default to the 'installation' subcommand when none is given.

    Allows 'soliplex-cli audit <path>' as shorthand for
    'soliplex-cli audit installation <path>'.
    """

    def parse_args(self, ctx, args):
        first_positional = next(
            (a for a in args if not a.startswith("-")),
            None,
        )
        if (
            first_positional is not None
            and first_positional not in self.commands
        ):
            args = ["installation", *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    name="audit",
    help=AUDIT_HELP,
    cls=_AuditGroup,
    no_args_is_help=True,
)


@app.command(
    "installation",
    help=AUDIT_HELP,
)
def audit_installation(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    quiet: bool = typer.Option(
        False,
        "-q",
        "--quiet",
        help="Show only errors",
    ),
):
    the_installation = cli_util.get_installation(installation_path)

    errors = {}

    if quiet:
        tc_line = lambda *args: None  # noqa E731
        tc_rule = lambda *args: None  # noqa E731
        tc_print = lambda *args: None  # noqa E731
    else:
        tc_line = the_console.line
        tc_rule = the_console.rule
        tc_print = the_console.print
        tc_print_exception = the_console.print_exception

    tc_line()
    tc_rule("Checking secrets")
    tc_line()
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = exc.secret_names.split(",")
        errors["missing_secrets"] = missing

        tc_print("Missing secrets")
        for secret_name in missing:
            tc_print(f"- {secret_name}")
    else:
        tc_print("OK")

    tc_line()
    tc_rule("Checking environment")
    tc_line()
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        missing = exc.env_vars.split(",")
        errors["missing_env_vars"] = missing

        tc_line()
        tc_print("Missing environment variables")
        for env_var in exc.env_vars.split(","):
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
    oidc_configs = the_installation._config.oidc_auth_system_configs
    for oidc_config in oidc_configs:
        tc_print(f"OIDC system: {oidc_config.id}")
        try:
            models.OIDCAuthSystem.from_config(oidc_config)
        except Exception as exc:
            errors.setdefault("oidc", {})[oidc_config.id] = str(exc)

            tc_print(exc)
        else:
            tc_print("OK")
        tc_line()

    tc_line()
    tc_rule("Validating room models")
    tc_line()
    room_configs = the_installation._config.room_configs
    rag_errors = {}

    def _rag_error(room_config, which, exc):
        rag_room = rag_errors.setdefault(room_config.id, {})
        rag_room[which] = str(exc)

    for room_config in room_configs.values():
        tc_print(f"Room: {room_config.id}")
        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            errors.setdefault("room", {})[room_config.id] = str(exc)

            tc_print(exc)
        else:
            tc_print("OK")
        tc_line()

        if isinstance(room_config.agent_config, config_rag._RAGConfigBase):
            tc_print("- Checking agent RAG DB")
            try:
                room_config.agent_config.rag_lancedb_path  # noqa B018
            except Exception as exc:
                _rag_error(room_config, "agent", exc)

                tc_print(exc)
            else:
                tc_print("  OK")
            tc_line()

        room_skills = room_config.skills

        if room_skills is not None:
            for s_name, s_config in room_skills.skill_configs.items():
                if isinstance(s_config, config_rag._RAGConfigBase):
                    tc_print(f"- Checking skill RAG DB: {s_name}")
                    try:
                        s_config.rag_lancedb_path  # noqa B018
                    except Exception as exc:
                        _rag_error(room_config, f"skill-{s_name}", exc)

                        tc_print(exc)
                    else:
                        tc_print("  OK")
                    tc_line()

        for tool_config in room_config.tool_configs.values():
            if isinstance(tool_config, config_rag._RAGConfigBase):
                t_name = tool_config.tool_name
                tc_print(f"- Checking tool RAG DB: {t_name}")
                try:
                    tool_config.rag_lancedb_path  # noqa B018
                except Exception as exc:
                    _rag_error(room_config, f"tool-{t_name}", exc)

                    tc_print(exc)
                else:
                    tc_print("  OK")
                tc_line()

    if rag_errors:
        errors["rag"] = rag_errors

    tc_line()
    tc_rule("Validating completion models")
    tc_line()
    completion_configs = the_installation._config.completion_configs

    for compl_config in completion_configs.values():
        tc_print(f"Completion: {compl_config.id}")
        try:
            models.Completion.from_config(compl_config)
        except Exception as exc:
            errors.setdefault("completion", {})[compl_config.id] = str(exc)

            tc_print(exc)
        else:
            tc_print("OK")
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

    if errors:
        if quiet:
            the_console.print_json(data=errors)
        sys.exit(-1)


@app.command("secrets")
def audit_secrets(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List secrets defined in the installation"""
    the_installation = cli_util.get_installation(installation_path)
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        missing = set(exc.secret_names.split(","))
    else:
        missing = set()

    the_console.line()
    the_console.rule("Configured secrets")
    the_console.line()

    for secret_config in the_installation._config.secrets:
        flag = "MISSING" if secret_config.secret_name in missing else "OK"
        the_console.print(f"- {secret_config.secret_name:25} {flag}")

    the_console.print()


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
    the_installation = cli_util.get_installation(installation_path)
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        missing = set(exc.env_vars.split(","))
    else:
        missing = set()

    the_console.line()
    the_console.rule("Configured environment variables")
    the_console.line()

    for key, value in the_installation._config.environment.items():
        if key in missing:
            value = "MISSING"

        the_console.print(f"- {key:25}: {value}")

        if verbose:
            for i_source, source in enumerate(
                the_installation.get_environment_sources(key)
            ):
                mark = " " if i_source else "*"
                the_console.print(
                    f"  {mark}{str(source.source_type):24}: {source.value}"
                )

        the_console.print()

    the_console.print()


@app.command("oidc")
def audit_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    the_installation = cli_util.get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured OIDC Auth Providers")
    the_console.line()

    for oidc_config in the_installation.oidc_auth_system_configs:
        the_console.print(f"- [ {oidc_config.id} ] {oidc_config.title}: ")
        the_console.print(f"  {oidc_config.server_url}")
        the_console.line()


async def _async_count(rag):
    with warnings.catch_warnings():
        return await rag.count_documents()


def _count_rag_documents(rag: hr_client.HaikuRAG):
    try:
        count = asyncio.run(_async_count(rag))
    except Exception:
        return "error"

    return f"{count} documents"


@app.command("rooms")
def audit_rooms(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List rooms defined in the installation"""
    the_installation = cli_util.get_installation(installation_path)
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars:
        pass

    the_console.line()
    the_console.rule("Configured Rooms")
    the_console.line()

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs
    cwd = pathlib.Path.cwd()

    for room_config in available_rooms.values():
        the_console.print(f"- [ {room_config.id} ] {room_config.name}: ")
        the_console.print(f"  {room_config.description}")
        try:
            hrc_kws = list(
                room_config.list_haiku_rag_client_kw(include_source=True)
            )
        except config_rag.RagDbFileNotFound as exc:
            the_console.log("   Invalid Haiku Rag configs")
            the_console.print(str(exc))
        else:
            if hrc_kws:
                the_console.print()
                the_console.print("   Haiku Rag DBs")
                for hr_client_kw in hrc_kws:
                    source = hr_client_kw.pop("source")
                    db_path = hr_client_kw["db_path"].relative_to(cwd)
                    rag = hr_client.HaikuRAG(**hr_client_kw)
                    count = _count_rag_documents(rag)
                    the_console.print(
                        f"   - {source:20}: {str(db_path):30} {count}"
                    )
                    the_console.print()
        the_console.line()


@app.command("completions")
def audit_completions(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List completions defined in the installation"""
    the_installation = cli_util.get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured Completions")
    the_console.line()

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs
    for compl_config in available_completions.values():
        the_console.print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        the_console.line()


@app.command("skills")
def audit_skills(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):
    """List skills defined in the installation"""
    the_installation = cli_util.get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured Skills")
    the_console.line()

    available_skills = the_installation._config.skill_configs
    for skill_name, skill_config in available_skills.items():
        the_console.print(f"- [ {skill_config.kind}:{skill_name}  ]")
        errors = getattr(skill_config, "errors", None)
        if errors:
            the_console.print("  Validation errors:")
            for error in errors:
                the_console.print(f"  - {error}")
        else:
            the_console.print(f"  {skill_config.description}")
        the_console.line()
