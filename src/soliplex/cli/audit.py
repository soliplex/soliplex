from __future__ import annotations

import asyncio
import pathlib
import sys
import warnings

import requests
import typer
import yaml
from haiku.rag import client as hr_client
from skills_ref import validator as skill_validator
from typer import core as typer_core

from soliplex import authz
from soliplex import installation
from soliplex import models
from soliplex import ollama
from soliplex import secrets
from soliplex.cli import cli_util
from soliplex.cli import types
from soliplex.config import agui as config_agui
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
    cli_log_config: pathlib.Path | None = cli_util.CLI_LOG_CONFIG_OPTION,
):
    cli_util._configure_cli_logging(cli_log_config)
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
    errors |= _audit_admin_users_section(ctx, installation_path)
    errors |= _audit_room_authz_section(ctx, installation_path)
    errors |= _audit_completions_section(ctx, installation_path)
    errors |= _audit_quizzes_section(ctx, installation_path)
    errors |= _audit_skills_section(ctx, installation_path)
    errors |= _audit_logging_section(ctx, installation_path)
    errors |= _audit_logfire_section(ctx, installation_path)
    errors |= _audit_ollama_section(ctx, installation_path)

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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
    """List secrets defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_secrets_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _missing_env_vars(the_installation: installation.Installation) -> dict:
    try:
        the_installation.resolve_environment()
    except config_installation.MissingEnvVars as exc:
        return {"missing_env_vars": exc.failed}
    return {}


def _audit_environment_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    *,
    verbose: bool = False,
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
    """List OIDC Auth Providers defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_oidc_section(ctx, installation_path)
    _emit_errors(errors, quiet)


async def _async_count(rag):
    with warnings.catch_warnings():
        async with rag as rag_a:
            return await rag_a.count_documents()


def _count_rag_documents(rag: hr_client.HaikuRAG):
    """Return ``(display, error)`` for the RAG document count.

    On success, ``error`` is ``None``. On failure, ``error`` carries the
    exception message so the caller can record it in the audit report.
    """
    try:
        count = asyncio.run(_async_count(rag))
    except Exception as exc:
        return f"ERROR: {exc}", str(exc)

    return f"{count} documents", None


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


def _invalid_room_agui_features(
    the_installation: installation.Installation,
) -> dict:
    feature_errors: dict[str, list[str]] = {}
    registry = config_agui.AGUI_FEATURES_BY_NAME

    for room_config in the_installation._config.room_configs.values():
        missing = [
            name
            for name in room_config.agui_feature_names
            if name not in registry
        ]
        if missing:
            feature_errors[room_config.id] = missing

    if feature_errors:
        return {"agui_features": feature_errors}
    return {}


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
) -> dict:  # pragma NO COVER UI ONLY
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

    feature_invalid = _invalid_room_agui_features(the_installation)
    errors |= feature_invalid
    feature_invalid_rooms = feature_invalid.get("agui_features", {})

    # Deliberately bypass auth check done by 'get_room_configs' here.
    available_rooms = the_installation._config.room_configs

    for room_config in available_rooms.values():
        tc_print(f"- [ {room_config.id} ] {room_config.name}: ")
        tc_print(f"  {room_config.description}")

        room_exc = invalid_rooms.get(room_config.id)
        if room_exc is not None:
            tc_print(f"  ERROR: {room_exc}")

        room_features = room_config.agui_feature_names
        if room_features:
            unregistered = set(feature_invalid_rooms.get(room_config.id, ()))
            tc_print()
            tc_print("   AG-UI features")
            for feature_name in room_features:
                flag = "UNREGISTERED" if feature_name in unregistered else "OK"
                tc_print(f"   - {feature_name:30}: {flag}")
            tc_print()

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
                    rag = hr_client.HaikuRAG(
                        db_path=cfg.rag_lancedb_path,
                        config=cfg.haiku_rag_config,
                        read_only=True,
                    )
                    count_display, count_error = _count_rag_documents(rag)
                    if count_error is not None:
                        room_rag_errors = errors.setdefault(
                            "rag_count", {}
                        ).setdefault(room_config.id, {})
                        room_rag_errors[source] = count_error
                    tc_print(
                        f"   - {source:20}: "
                        f"{str(cfg.rag_lancedb_path):30} {count_display}"
                    )
                tc_print()
        tc_line()

    return errors


@app.command("rooms")
def audit_rooms(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
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


async def _list_room_policies(dburi):
    async with cli_util._room_authz_policy(dburi) as policy:
        return await policy.list_room_policies()


async def _list_admin_discriminators(dburi):
    async with cli_util._admin_user_policy(dburi) as policy:
        return await policy.list_admin_user_discriminators()


def _room_policies(the_installation) -> tuple[list, str | None]:
    """Return ``(policies, error)`` for the stored room policies.

    ``policies`` holds the unchecked policy models read via
    'RoomAuthorizationPolicy.list_room_policies' and ``error`` is ``None``
    on success. A RAM-based authz DB can hold no persisted rows, so it
    short-circuits to ``([], None)`` without touching the database.

    When the database itself cannot be reached -- e.g. its DBURI names a
    Postgres server that isn't listening -- ``policies`` is empty and
    ``error`` carries the exception message, so the audit can report the
    unreachable DB instead of dying on the traceback.
    """
    dburi = the_installation.authorization_dburi_async

    if dburi in cli_util._RAM_DBURIS:
        return [], None

    try:
        return list(asyncio.run(_list_room_policies(dburi))), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _room_authz_groups(the_installation, room_policies):
    """Bucket configured rooms by authorization state; collect stale rows.

    ``room_policies`` is the policy list from '_room_policies'.
    """
    configured = sorted(the_installation._config.room_configs)

    policies = {
        policy.room_id: policy.default_allow_deny for policy in room_policies
    }

    configured_set = set(configured)
    default, public, private = [], [], []
    for room_id in configured:
        if room_id not in policies:
            default.append(room_id)
        elif policies[room_id] == authz.AllowDeny.ALLOW:
            public.append(room_id)
        else:
            private.append(room_id)

    stale = sorted(rid for rid in policies if rid not in configured_set)

    return {
        "default": default,
        "public": public,
        "private": private,
        "stale": stale,
    }


def _invalid_acl_json_paths(room_policies) -> dict:
    """Collect ACL entries whose stored 'json_path' fails to validate.

    ``room_policies`` is the policy list from '_room_policies' -- the
    unchecked models, which tolerate entries that would fail
    'policy.as_model'. Each surfaced 'json_path' is re-validated against
    the currently-loaded JSONPath environment. Typically an entry lands
    here when it was authored under a meta-config that registered filter
    functions which are no longer present.

    Returns a dict mapping 'room_id' to a list of '(json_path, error)'
    pairs.
    """
    invalid: dict = {}
    for policy in room_policies:
        for entry in policy.acl_entries:
            if entry.json_path is None:
                continue
            try:
                authz.validate_json_path(entry.json_path)
            except authz.InvalidJSONPath as exc:
                invalid.setdefault(policy.room_id, []).append(
                    (entry.json_path, str(exc)),
                )
    return invalid


def _audit_room_authz_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the room-authz section (rule header + four buckets)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured rooms by authorization state")
    tc_line()

    room_policies, db_error = _room_policies(the_installation)
    if db_error is not None:
        tc_print(f"ERROR: authorization database unreachable: {db_error}")
        tc_line()
        return {"room_authz": {"unreachable": db_error}}

    groups = _room_authz_groups(the_installation, room_policies)

    for label, room_ids in (
        (
            "Default (no policy row -- public to authenticated users)",
            groups["default"],
        ),
        ("Public (policy row, default ALLOW)", groups["public"]),
        ("Private (policy row, default DENY)", groups["private"]),
    ):
        tc_print(f"{label}:")
        if room_ids:
            for room_id in room_ids:
                tc_print(f"  - {room_id}")
        else:
            tc_print("  (none)")
        tc_line()

    tc_print("Stale (policy row exists for unconfigured room):")
    if groups["stale"]:
        for room_id in groups["stale"]:
            tc_print(f"  - {room_id}  STALE")
    else:
        tc_print("  (none)")
    tc_line()

    invalid_acls = _invalid_acl_json_paths(room_policies)
    tc_print("ACL entries with invalid JSONPath:")
    if invalid_acls:
        for room_id in sorted(invalid_acls):
            for json_path, error in invalid_acls[room_id]:
                tc_print(f"  - {room_id}: {json_path}  ({error})")
    else:
        tc_print("  (none)")
    tc_line()

    sub_errors: dict = {}
    if groups["stale"]:
        sub_errors["stale_rooms"] = groups["stale"]
    if invalid_acls:
        sub_errors["invalid_acls"] = invalid_acls

    errors: dict = {}
    if sub_errors:
        errors["room_authz"] = sub_errors
    return errors


def _admin_user_json_paths(
    the_installation,
) -> tuple[list[str], str | None]:
    """Return ``(json_paths, error)`` for the stored admin rows.

    ``json_paths`` holds every stored 'AdminUser.json_path', in insertion
    order, read via 'AdminUserPolicy.list_admin_user_discriminators';
    ``error`` is ``None`` on success. A RAM-based authz DB can hold no
    persisted rows, so it short-circuits to ``([], None)`` without
    touching the database.

    When the database itself cannot be reached -- e.g. its DBURI names a
    Postgres server that isn't listening -- ``json_paths`` is empty and
    ``error`` carries the exception message, so the audit can report the
    unreachable DB instead of dying on the traceback.
    """
    dburi = the_installation.authorization_dburi_async

    if dburi in cli_util._RAM_DBURIS:
        return [], None

    try:
        return list(asyncio.run(_list_admin_discriminators(dburi))), None
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"


def _invalid_admin_user_json_paths(
    json_paths,
) -> list[tuple[str, str]]:
    """Collect admin entries whose 'json_path' fails to validate.

    Same intent as '_invalid_acl_json_paths' but for the 'AdminUser'
    table: a row typically lands here when it was authored under a
    meta-config that registered filter functions which are no longer
    present. ``json_paths`` is the list from '_admin_user_json_paths'.

    Returns a list of '(json_path, error)' pairs.
    """
    invalid: list[tuple[str, str]] = []
    for json_path in json_paths:
        try:
            authz.validate_json_path(json_path)
        except authz.InvalidJSONPath as exc:
            invalid.append((json_path, str(exc)))
    return invalid


def _audit_admin_users_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the admin-users section (rule header + listing + invalid)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured admin users")
    tc_line()

    json_paths, db_error = _admin_user_json_paths(the_installation)
    if db_error is not None:
        tc_print(f"ERROR: authorization database unreachable: {db_error}")
        tc_line()
        return {"admin_users": {"unreachable": db_error}}

    tc_print(f"Admin users ({len(json_paths)}):")
    if json_paths:
        for json_path in json_paths:
            parsed = authz.parse_token_field_json_path(json_path)
            if parsed is not None:
                field, value = parsed
                tc_print(f"  - {field}={value}")
            else:
                tc_print(f"  - json_path={json_path}")
    else:
        tc_print("  (none)")
    tc_line()

    invalid = _invalid_admin_user_json_paths(json_paths)
    tc_print("Admin users with invalid JSONPath:")
    if invalid:
        for json_path, error in invalid:
            tc_print(f"  - {json_path}  ({error})")
    else:
        tc_print("  (none)")
    tc_line()

    errors: dict = {}
    if invalid:
        errors["admin_users"] = {"invalid_json_paths": invalid}
    return errors


@app.command("admin-users")
def audit_admin_users(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List configured admin users and flag any with invalid JSONPath.

    Each stored 'AdminUser.json_path' is re-validated against the
    currently-loaded JSONPath environment. An entry whose query no
    longer compiles (e.g. because the meta-config filter function it
    referenced has been removed) is reported as an audit error.
    """
    quiet = ctx.obj["quiet"]
    errors = _audit_admin_users_section(ctx, installation_path)
    _emit_errors(errors, quiet)


@app.command("room-authz")
def audit_room_authz(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
):  # pragma NO COVER command
    """List rooms by authorization status.

    Buckets: 'default' (no policy row), 'public' (policy with
    default_allow_deny=ALLOW), 'private' (policy with
    default_allow_deny=DENY), 'stale' (policy row exists in the
    authorization database for a room that isn't configured in the
    YAML). A non-empty 'stale' bucket is reported as an audit error.
    """
    quiet = ctx.obj["quiet"]
    errors = _audit_room_authz_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _audit_completions_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
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
    with pyl_config.open(encoding="utf-8") as f:
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
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
    """Show the Python-logging config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logging_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _audit_logfire_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
) -> dict:  # pragma NO COVER UI ONLY
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
):  # pragma NO COVER command
    """Show the Logfire config defined in the installation"""
    quiet = ctx.obj["quiet"]
    errors = _audit_logfire_section(ctx, installation_path)
    _emit_errors(errors, quiet)


def _unresponsive_ollama_models(rest_api, model_names) -> dict:
    """Return ``{model_name: error}`` for models that fail to respond.

    Sends a minimal chat-completion request to each name in
    ``model_names`` (which should already be present on the server) and
    records those that raise a network error or non-2xx response. The
    result is empty when every model responds.
    """
    unresponsive: dict[str, str] = {}

    for model_name in model_names:
        try:
            rest_api.chat_completion(model_name)
        except requests.RequestException as exc:
            unresponsive[model_name] = str(exc.args)

    return unresponsive


def _missing_ollama_models(
    the_installation: installation.Installation,
    *,
    check_responsive: bool = False,
) -> dict:
    """Return per-URL info about Ollama models on each server.

    Each value may carry ``{"unreachable": str}`` (the server refused
    the connection or returned an HTTP error), ``{"missing_models":
    [str, ...]}`` (the server is reachable but missing one or more
    models the installation references), and -- when ``check_responsive``
    is set -- ``{"unresponsive_models": {name: error}}`` (a model is
    installed but failed to answer a minimal chat-completion request).
    """
    ollama_url_models = the_installation.all_provider_info.get("ollama", {})
    per_url: dict[str, dict] = {}

    for url, required in ollama_url_models.items():
        if not required:
            continue

        rest_api = ollama.REST_API(url)

        try:
            response = rest_api.get_available_models()
        except requests.RequestException as exc:
            per_url[url] = {"unreachable": str(exc.args)}
            continue

        available = {entry["name"] for entry in response.get("models", ())}
        missing = sorted(required - available)

        url_info: dict = {}
        if missing:
            url_info["missing_models"] = missing

        if check_responsive:
            unresponsive = _unresponsive_ollama_models(
                rest_api,
                sorted(required & available),
            )
            if unresponsive:
                url_info["unresponsive_models"] = unresponsive

        if url_info:
            per_url[url] = url_info

    if per_url:
        return {"ollama": per_url}
    return {}


def _audit_ollama_section(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    *,
    check_responsive: bool = False,
) -> dict:  # pragma NO COVER UI ONLY
    """Print the Ollama section (rule header + per-URL availability check)."""
    quiet = ctx.obj["quiet"]
    the_installation = _get_installation(ctx, installation_path)
    tc_line, tc_rule, tc_print, _ = _quiet_console_funcs(quiet)

    tc_line()
    tc_rule("Configured Ollama URLs")
    tc_line()

    ollama_url_models = the_installation.all_provider_info.get("ollama", {})
    errors = _missing_ollama_models(
        the_installation,
        check_responsive=check_responsive,
    )
    per_url = errors.get("ollama", {})

    if not ollama_url_models:
        tc_print("No Ollama URLs referenced by the installation.")
        tc_line()
        return errors

    for url in sorted(ollama_url_models):
        tc_print(f"- {url}")
        url_errors = per_url.get(url, {})
        unreachable = url_errors.get("unreachable")
        missing = url_errors.get("missing_models")
        unresponsive = url_errors.get("unresponsive_models")
        if unreachable is not None:
            tc_print(f"  ERROR: {unreachable}")
        else:
            if missing:
                tc_print(f"  MISSING: {', '.join(missing)}")
                tc_print(
                    "  Run 'soliplex-cli ollama pull' to pull missing models.",
                )
            if unresponsive:
                tc_print(
                    f"  UNRESPONSIVE: {', '.join(sorted(unresponsive))}",
                )
                for model_name in sorted(unresponsive):
                    tc_print(f"    - {model_name}: {unresponsive[model_name]}")
            if not missing and not unresponsive:
                tc_print("  OK")
        tc_line()

    return errors


@app.command("ollama")
def audit_ollama(
    ctx: typer.Context,
    installation_path: types.installation_path_type,
    check_responsive: bool = typer.Option(
        False,
        "-r",
        "--check-responsive",
        help=(
            "Also confirm each installed model answers a minimal "
            "chat-completion request (slower; contacts each model)"
        ),
    ),
):  # pragma NO COVER command
    """Compare configured Ollama models against each server's available set"""
    quiet = ctx.obj["quiet"]
    errors = _audit_ollama_section(
        ctx,
        installation_path,
        check_responsive=check_responsive,
    )
    _emit_errors(errors, quiet)
