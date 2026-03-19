import asyncio
import enum
import json
import os
import pathlib
import typing
import warnings
from importlib import metadata as importlib_metadata

import requests
import typer
import uvicorn
import uvicorn.config
import yaml
from haiku.rag import client as hr_client
from rich import console
from skills_ref import validator as skill_validator

import soliplex
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import main
from soliplex import models
from soliplex import ollama
from soliplex import secrets
from soliplex import util
from soliplex.authz import schema as authz_schema
from soliplex.config import installation as config_installation
from soliplex.config import quizzes as config_quizzes
from soliplex.config import rag as config_rag


class ReloadOption(enum.StrEnum):
    CONFIG = "config"
    PYTHON = "python"
    BOTH = "both"


class LogLevelOption(enum.StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


the_cli = typer.Typer(
    context_settings={
        "help_option_names": ["-h", "--help"],
    },
    no_args_is_help=True,
    add_completion=False,
)

the_console = console.Console()


def version_callback(value: bool):
    if value:
        gitmeta = util.GitMetadata(pathlib.Path.cwd())
        v = importlib_metadata.version("soliplex")
        the_console.print(f"Installed soliplex version: {v}")
        the_console.print(f"Soliplex git tag          : {gitmeta.git_tag}")
        the_console.print(f"Soliplex git branch       : {gitmeta.git_branch}")
        the_console.print(f"Soliplex git hash         : {gitmeta.git_hash}")
        raise typer.Exit()


installation_path_type = typing.Annotated[
    pathlib.Path,
    typer.Argument(
        envvar="SOLIPLEX_INSTALLATION_PATH",
        help="Soliplex installation path",
    ),
]


def get_installation(
    installation_path: pathlib.Path,
) -> installation.Installation:
    if installation_path.is_dir():
        installation_path = installation_path / "installation.yaml"
    i_config = config_installation.load_installation(installation_path)
    i_config.reload_configurations()
    return installation.Installation(i_config)


@the_cli.callback()
def app(
    _version: bool = typer.Option(
        False,
        "-v",
        "--version",
        callback=version_callback,
        help="Show version and exit",
    ),
):
    """soliplex CLI - RAG system"""


reload_option: ReloadOption = typer.Option(
    None,
    "-r",
    "--reload",
    help="Reload on file changes",
)


reload_dirs_option: list[pathlib.Path] = typer.Option(
    [],
    "--reload-dirs",
    help="Additional directories to be monitored for reload",
)


reload_includes_option: list[str] = typer.Option(
    [],
    "--reload-includes",
    help="Additional glob patterns for files to be montored for reload",
)


log_config_option: pathlib.Path = typer.Option(
    None,
    "--log-config",
    help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
)


log_level_option: LogLevelOption = typer.Option(
    None, "--log-level", help="Log level"
)

app_factory_name_option = typer.Option(None, hidden=True)
app_maker_option = typer.Option(None, hidden=True)


@the_cli.command(
    "serve",
)
def serve(
    ctx: typer.Context,
    installation_path: installation_path_type,
    no_auth_mode: bool = typer.Option(
        False,
        "--no-auth-mode",
        help="""\
Disable OIDC authentication providers

Incompatible with '--add-admin-user'.
""",
    ),
    add_admin_user: str | None = typer.Option(
        None,
        "--add-admin-user",
        help="""\
Add an admin user to the authorization database

Incompatible with '--no-auth-mode'.
""",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "-h",
        "--host",
        help="Bind socket to this host",
    ),
    port: int = typer.Option(
        8000,
        "-p",
        "--port",
        help="Port number",
    ),
    uds: str = typer.Option(
        None,
        "--uds",
        help="Bind to a Unix domain socket",
    ),
    fd: int = typer.Option(
        None,
        "--fd",
        help="Bind to socket from this file descriptor",
    ),
    reload: ReloadOption = reload_option,
    reload_dirs: list[pathlib.Path] = reload_dirs_option,
    reload_includes: list[str] = reload_includes_option,
    workers: int = typer.Option(
        None,
        "--workers",
        envvar="WEB_CONCURRENCY",
        help="Number of worker processes. Defaults to the "
        "$WEB_CONCURRENCY environment variable if available, or 1. "
        "Not valid with --reload.",
    ),
    log_config: pathlib.Path = log_config_option,
    log_level: LogLevelOption = log_level_option,
    access_log: bool | None = typer.Option(
        None,
        "--access-log",
        help="Enable/Disable access log",
    ),
    proxy_headers: bool = typer.Option(
        None,
        "--proxy-headers",
        help="Enable/Disable X-Forwarded-Proto, X-Forwarded-For "
        "to populate url scheme and remote address info.",
    ),
    forwarded_allow_ips: str = typer.Option(
        None,
        "--forwarded-allow-ips",
        envvar="FORWARDED_ALLOW_IPS",
        help="Comma separated list of IP Addresses, IP Networks, or "
        "literals (e.g. UNIX Socket path) to trust with proxy headers. "
        "Defaults to the $FORWARDED_ALLOW_IPS environment "
        "variable if available, or '127.0.0.1'. "
        "The literal '*' means trust everything.",
    ),
    app_factory_name=app_factory_name_option,
    app_maker=app_maker_option,
):
    """Run the Soliplex server"""
    if no_auth_mode and (add_admin_user is not None):
        the_console.rule("Incompatible CLI arguments")
        the_console.print(
            "'--no-auth-mode' and '--add-admin-user- are incompatible."
        )
        raise typer.Exit()

    # Temporary, to permit updating logging config if not passed on CLI.
    the_installation = get_installation(installation_path)
    i_config = the_installation._config

    if reload in (ReloadOption.PYTHON, ReloadOption.BOTH):
        reload_dirs.extend(soliplex.__path__)

    if reload in (ReloadOption.CONFIG, ReloadOption.BOTH):
        if installation_path.is_dir():
            reload_dirs.append(installation_path)
        else:
            reload_dirs.append(installation_path.parent)

        reload_includes.append("*.yaml")
        reload_includes.append("*.yml")
        reload_includes.append("*.txt")

    uvicorn_kw = {
        "host": host,
        "port": port,
        "ws": "websockets-sansio",
    }

    if uds is not None:
        uvicorn_kw["uds"] = uds

    if fd is not None:
        uvicorn_kw["fd"] = fd

    if workers is not None:
        uvicorn_kw["workers"] = workers

    if log_level is not None:
        uvicorn_kw["log_level"] = log_level

    if log_config is not None:
        uvicorn_kw["log_config"] = str(log_config)
    elif i_config._logging_config_file is not None:
        uvicorn_kw["log_config"] = str(i_config.logging_config_file)

    if access_log is not None:
        uvicorn_kw["access_log"] = access_log

    if proxy_headers is not None:
        uvicorn_kw["proxy_headers"] = proxy_headers

    if forwarded_allow_ips is not None:
        uvicorn_kw["forwarded_allow_ips"] = forwarded_allow_ips

    reload_dirs = [str(rd) for rd in reload_dirs]

    if reload or workers:
        # Work around uvicorn's aversion to passing arguments to the app
        # factory.
        #
        # N.B.:  The environment variables set here are a private contract
        #        between this command and the
        #        'soliplex.main.create_app_from_environment'
        #        function:  do not try setting them yourself, either
        #        directly or via a '.env' file.
        os.environ["_SOLIPLEX_INSTALLATION_PATH"] = str(installation_path)

        if no_auth_mode:
            os.environ["_SOLIPLEX_NO_AUTH_MODE"] = "Y"

        if log_config is not None:  # pass to the app, disable Uvicorn.
            os.environ["_SOLIPLEX_LOG_CONFIG_FILE"] = str(log_config)

        if add_admin_user is not None:
            os.environ["_SOLIPLEX_ADD_ADMIN_USER"] = add_admin_user

        if app_factory_name is None:
            app_factory_name = "soliplex.main:create_app_from_environment"

        uvicorn.run(
            app_factory_name,
            factory=True,
            reload=reload,
            reload_dirs=reload_dirs,
            reload_includes=reload_includes,
            **uvicorn_kw,
        )
    else:
        if app_maker is None:
            app_maker = main.create_app

        app = app_maker(
            installation_path=installation_path,
            no_auth_mode=no_auth_mode,
            log_config_file=log_config,
            add_admin_user=add_admin_user,
        )
        uvicorn.run(app, **uvicorn_kw)


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


@the_cli.command(
    "check-config",
)
def check_config(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Check that secrets / env vars can be resolved"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Checking secrets")
    the_console.line()
    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound as exc:
        the_console.print("Missing secrets")
        for secret_name in exc.secret_names.split(","):
            the_console.print(f"- {secret_name}")
    else:
        the_console.print("OK")

    the_console.line()
    the_console.rule("Checking environment")
    the_console.line()
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        the_console.line()
        the_console.print("Missing environment variables")
        for env_var in exc.env_vars.split(","):
            the_console.print(f"- {env_var}")
    else:
        the_console.print("OK")

    # Check that conversion to models doesn't raise
    the_console.line()
    the_console.rule("Validating installation model")
    the_console.line()
    try:
        models.Installation.from_config(the_installation._config)
    except Exception as exc:
        the_console.print(exc)
    else:
        the_console.print("OK")

    the_console.line()
    the_console.rule("Validating OIDC authentication systems")
    the_console.line()
    oidc_configs = the_installation._config.oidc_auth_system_configs
    for oidc_config in oidc_configs:
        the_console.print(f"OIDC system: {oidc_config.id}")
        try:
            models.OIDCAuthSystem.from_config(oidc_config)
        except Exception as exc:
            the_console.print(exc)
        else:
            the_console.print("OK")
        the_console.line()

    the_console.line()
    the_console.rule("Validating room models")
    the_console.line()
    room_configs = the_installation._config.room_configs
    for room_config in room_configs.values():
        the_console.print(f"Room: {room_config.id}")
        try:
            models.Room.from_config(room_config)
        except Exception as exc:
            the_console.print(exc)
        else:
            the_console.print("OK")
        the_console.line()

        if isinstance(room_config.agent_config, config_rag._RAGConfigBase):
            the_console.print("- Checking agent RAG DB")
            try:
                room_config.agent_config.rag_lancedb_path  # noqa B018
            except Exception as exc:
                the_console.print(exc)
            else:
                the_console.print("  OK")
            the_console.line()

        room_skills = room_config.skills

        if room_skills is not None:
            for s_name, s_config in room_skills.skill_configs.items():
                if isinstance(s_config, config_rag._RAGConfigBase):
                    the_console.print(f"- Checking skill RAG DB: {s_name}")
                    try:
                        s_config.rag_lancedb_path  # noqa B018
                    except Exception as exc:
                        the_console.print(exc)
                    else:
                        the_console.print("  OK")
                    the_console.line()

        for tool_config in room_config.tool_configs.values():
            if isinstance(tool_config, config_rag._RAGConfigBase):
                the_console.print(
                    f"- Checking tool RAG DB: {tool_config.tool_name}"
                )
                try:
                    tool_config.rag_lancedb_path  # noqa B018
                except Exception as exc:
                    the_console.print(exc)
                else:
                    the_console.print("  OK")
                the_console.line()

    the_console.line()
    the_console.rule("Validating completion models")
    the_console.line()
    completion_configs = the_installation._config.completion_configs

    for compl_config in completion_configs.values():
        the_console.print(f"Completion: {compl_config.id}")
        try:
            models.Completion.from_config(compl_config)
        except Exception as exc:
            the_console.print(exc)
        else:
            the_console.print("OK")
        the_console.line()

    the_console.line()
    the_console.rule("Validating quizzes")
    the_console.line()
    for q_path in the_installation._config.quizzes_paths:
        the_console.print(f"Quizzes path: {q_path}")
        for q_file in q_path.glob("*.json"):
            the_console.print(f"- Question file stem: {q_file.stem}")
            q_config = config_quizzes.QuizConfig(
                id="check",
                question_file=str(q_file),
            )
            try:
                q_config.get_questions()
            except Exception as exc:
                the_console.print(f"  Invalid quiz file: {exc}")
            else:
                the_console.print("  OK")
        the_console.line()

    the_console.line()
    the_console.rule("Validating Python logging")
    the_console.line()
    pyl_config = the_installation._config.logging_config_file
    if pyl_config is not None:
        the_console.print(f"Logging config: {pyl_config}")
        try:
            with pyl_config.open() as f:
                logging_config = yaml.safe_load(f)
        except yaml.YAMLError:
            the_console.print_exception()
        except OSError:
            the_console.print_exception()
        else:
            the_console.print(logging_config)
            the_console.print(
                f"Headers map: {the_installation._config.logging_headers_map}",
            )
            the_console.print(
                f"Claims map: {the_installation._config.logging_claims_map}",
            )
            the_console.print("OK")
    else:
        the_console.print("OK (defaults)")
    the_console.line()

    the_console.line()
    the_console.rule("Validating skills")
    the_console.line()
    for skills_path in the_installation._config.filesystem_skills_paths:
        the_console.print(f"Filesystem skills path: {skills_path}")
        for skill_path in _find_skill_paths(skills_path):
            the_console.print(f"- {skill_path.name}")
            errors = skill_validator.validate(skill_path)
            if errors:
                for error in errors:
                    the_console.print(f"  {error}")
            else:
                the_console.print("  OK")
        the_console.line()

    the_console.line()
    the_console.rule("Validating Logfire config")
    the_console.line()
    l_config = the_installation._config.logfire_config
    if l_config is not None:
        the_console.print(l_config.as_yaml)
        the_console.print("OK")
    else:
        the_console.print("OK (defaults)")
    the_console.line()


@the_cli.command(
    "list-secrets",
)
def list_secrets(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List secrets defined in the installation"""
    the_installation = get_installation(installation_path)
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


@the_cli.command(
    "list-environment",
)
def list_environment(
    ctx: typer.Context,
    installation_path: installation_path_type,
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
    the_installation = get_installation(installation_path)
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


@the_cli.command(
    "list-oidc-auth-providers",
)
def list_oidc_auth_providers(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List OIDC Auth Providers defined in the installation"""
    the_installation = get_installation(installation_path)

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


@the_cli.command(
    "list-rooms",
)
def list_rooms(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List rooms defined in the installation"""
    the_installation = get_installation(installation_path)
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


@the_cli.command(
    "list-completions",
)
def list_completions(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List completions defined in the installation"""
    the_installation = get_installation(installation_path)

    the_console.line()
    the_console.rule("Configured Completions")
    the_console.line()

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_completions = the_installation._config.completion_configs
    for compl_config in available_completions.values():
        the_console.print(f"- [ {compl_config.id} ] {compl_config.name}: ")
        the_console.line()


@the_cli.command(
    "list-skills",
)
def list_skills(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """List skills defined in the installation"""
    the_installation = get_installation(installation_path)

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


@the_cli.command(
    "config",
)
def config_as_yaml(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Export the installatin config as YAML"""
    the_installation = get_installation(installation_path)

    try:
        the_installation.resolve_secrets()
    except secrets.SecretsNotFound:
        pass

    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars:
        pass

    exported_yaml = yaml.dump(
        the_installation._config.as_yaml,
        sort_keys=False,
    )

    the_console.print(f"#{'-' * 78}")
    the_console.print(f"# Source: {installation_path}")
    the_console.print(f"#{'-' * 78}")
    the_console.print(exported_yaml)


def _check_ram_dburi(dburi: str, command: str):
    if dburi == config_installation.SYNC_MEMORY_ENGINE_URL:
        the_console.rule("Authorization DB is RAM-based")
        the_console.print(f"'{command}' is a no-op with a RAM-based database")
        raise typer.Exit()


def _dump_admin_users(session):
    with session:
        admin_users = [
            admin_user.email
            for admin_user in session.query(
                authz_schema.AdminUser,
            )
        ]
    print(json.dumps({"admin_users": admin_users}))


@the_cli.command(
    "list-admin-users",
)
def list_admin_users(
    ctx: typer.Context,
    installation_path: installation_path_type,
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Show admin users defined in the installation's authz database."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "list-admin-users")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)
    _dump_admin_users(session)


@the_cli.command(
    "clear-admin-users",
)
def clear_admin_users(
    ctx: typer.Context,
    installation_path: installation_path_type,
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Clear admin user from the installation's authz database."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "clear-admin-users")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        for admin_user in session.query(authz_schema.AdminUser):
            session.delete(admin_user)
        session.commit()

        _dump_admin_users(session)


@the_cli.command(
    "add-admin-user",
)
def add_admin_user(
    ctx: typer.Context,
    installation_path: installation_path_type,
    admin_user_email: str,
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Add an admin user to the installation's authz database."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "add-admin-user")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        admin_user = authz_schema.AdminUser(email=admin_user_email)
        session.add(admin_user)
        session.commit()

        _dump_admin_users(session)


def _dump_room_policy(session, room_id):
    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        if policy is None:
            to_dump = policy
        else:
            to_dump = policy.as_model.model_dump()
            to_dump["default_allow_deny"] = str(to_dump["default_allow_deny"])

            for dump_ae in to_dump["acl_entries"]:
                dump_ae["allow_deny"] = str(dump_ae["allow_deny"])

    print(json.dumps(to_dump))


@the_cli.command(
    "show-room-authz",
)
def show_room_authz(
    ctx: typer.Context,
    installation_path: installation_path_type,
    room_id: str,
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Show room ACL entries defined in the installation's authz database."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "show-room-authz")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    _dump_room_policy(session, room_id)


@the_cli.command(
    "clear-room-authz",
)
def clear_room_authz(
    ctx: typer.Context,
    installation_path: installation_path_type,
    room_id: str,
    make_room_private: bool = typer.Option(
        False,
        "--make-room-private",
        help="Make room private",
    ),
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Show room ACL entries defined in the installation's authz database."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "clear-room-authz")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        before_entries = len(session.query(authz_schema.ACLEntry).all())

        if policy is not None:
            # for acl_entry in policy.acl_entries:
            #    session.delete(acl_entry)
            should_remove = len(policy.acl_entries)

            session.delete(policy)
            session.commit()

        after_entries = len(session.query(authz_schema.ACLEntry).all())
        assert after_entries == before_entries - should_remove

        if make_room_private:
            policy = authz_schema.RoomPolicy(room_id=room_id)
            session.add(policy)
            session.commit()

    _dump_room_policy(session, room_id)


@the_cli.command(
    "add-room-user",
)
def add_room_user(
    ctx: typer.Context,
    installation_path: installation_path_type,
    room_id: str,
    user_email: str,
    skip_ram_db_check: bool = typer.Option(
        False,
        "-s",
        "--skip-ram-db-check",
        help="Skip check for RAM-based DB",
    ),
):
    """Add a user to the ACL for a room."""
    the_installation = get_installation(installation_path)
    dburi = the_installation.authorization_dburi_sync

    if not skip_ram_db_check:
        _check_ram_dburi(dburi, "add-room-user")

    session = authz_schema.get_session(engine_url=dburi, init_schema=True)

    with session:
        policy = (
            session.query(
                authz_schema.RoomPolicy,
            )
            .where(
                authz_schema.RoomPolicy.room_id == room_id,
            )
            .first()
        )

        if policy is None:
            policy = authz_schema.RoomPolicy(room_id=room_id)
            session.add(policy)
            session.commit()

        existing_acls = [
            acl_entry
            for acl_entry in policy.acl_entries
            if acl_entry.email == user_email
        ]
        for to_remove in existing_acls:
            session.delete(to_remove)
        session.commit()

        new_acl = authz_schema.ACLEntry(
            room_policy=policy,
            allow_deny=authz_package.AllowDeny.ALLOW,
            email=user_email,
        )
        session.add(new_acl)
        session.commit()

    _dump_room_policy(session, room_id)


@the_cli.command(
    "agui-feature-schemas",
)
def agui_feature_schemas(
    ctx: typer.Context,
    installation_path: installation_path_type,
):
    """Export the installatin config as YAML"""
    the_installation = get_installation(installation_path)

    feature_schemas = {
        feature.name: {
            "source": str(feature.source),
            "json_schema": feature.json_schema,
        }
        for feature in the_installation._config.agui_features
    }

    print(json.dumps(feature_schemas))


@the_cli.command(
    "pull-models",
)
def pull_models(
    ctx: typer.Context,
    installation_path: installation_path_type,
    ollama_url: str = typer.Option(
        None,
        "-u",
        "--ollama-url",
        help=(
            "Ollama API base URL (defaults to 'OLLAMA_BASE_URL' from "
            "installation enviroment)"
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "-n",
        "--dry-run",
        help="Show which models would be pulled without actually pulling them",
    ),
):
    """Pull Ollama models referenced in the installation configuration"""

    def on_status(msg, is_error=False):
        style = "red" if is_error else None
        the_console.print(f"  {msg}", style=style)

    the_console.line()
    the_console.rule("Scanning for Ollama models")
    the_console.line()

    the_installation = get_installation(installation_path)
    the_installation.resolve_environment()
    all_provider_info = the_installation.all_provider_info
    ollama_url_models = all_provider_info["ollama"]

    if ollama_url is not None:
        ollama_url_models = {
            ollama_url: ollama_url_models.get(ollama_url, set())
        }

    for url, model_names in ollama_url_models.items():
        if not model_names:
            the_console.rule(f"No Ollama models for URL: {url}")
            the_console.line()

        else:
            rest_api = ollama.REST_API(url)

            the_console.rule(f"Pulling Ollama models for URL: {url}")
            the_console.line()
            the_console.print(
                f"Found {len(model_names)} unique Ollama model(s)"
            )
            the_console.line()

            for model_name in sorted(model_names):
                the_console.print(f"  - {model_name}")

            if not dry_run:
                success_count = 0

                for model_name in sorted(model_names):
                    the_console.print(f"\nPulling: {model_name}")

                    try:
                        result = rest_api.pull_model(model_name, stream=False)
                        status_text = result["status"]
                    except requests.RequestException as exc:
                        on_status(str(exc.args), True)
                    except KeyError:
                        on_status("No status returned", True)
                    else:
                        on_status(status_text, False)
                        success_count += 1

                the_console.line()
                the_console.rule(
                    f"Pulled {success_count}/{len(model_names)} model(s) "
                    "successfully"
                )
                the_console.line()


if __name__ == "__main__":
    the_cli()
