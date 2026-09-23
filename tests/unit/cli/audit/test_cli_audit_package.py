from __future__ import annotations

from unittest import mock

import pytest

from soliplex.cli import audit as cli_audit


@pytest.mark.parametrize(
    "w_args, exp_args",
    [
        ((), ["all"]),
        (["-q"], ["-q", "all"]),
        (["all"], ["all"]),
        (["-q", "all"], ["-q", "all"]),
        (["other", "w_arg"], ["other", "w_arg"]),
        (["-q", "other", "w_arg"], ["-q", "other", "w_arg"]),
        (["-q", "path"], ["-q", "all", "path"]),
        (["path"], ["all", "path"]),
    ],
)
@mock.patch("soliplex.cli.audit.typer_core.TyperGroup.parse_args")
def test__auditgroup_parse_args(parse_args, ctx, w_args, exp_args):
    all_command = mock.Mock(spec_set=())
    other_command = mock.Mock(spec_set=())
    ag = cli_audit._AuditGroup(
        commands={"all": all_command, "other": other_command},
    )

    found = ag.parse_args(ctx, w_args)

    assert found is parse_args.return_value
    parse_args.assert_called_once_with(ctx, exp_args)


@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test__audit_callback(configure_logging, ctx, w_quiet):
    w_quiet_kw = {"quiet": w_quiet}

    cli_audit._audit_callback(ctx, cli_log_config=None, **w_quiet_kw)

    assert ctx.obj["quiet"] == w_quiet
    configure_logging.assert_called_once_with(None)


@mock.patch("soliplex.cli.cli_util._configure_cli_logging")
def test_cli_log_config_from_env(
    configure_logging, scratch_installation, cli_runner, tmp_path
):
    # 'audit room-authz' (like 'audit admin-users') reads security objects
    # through the authz policy, so it emits security-object-read audit
    # records -- hence the group's '--cli-log-config' option, backed by
    # 'SOLIPLEX_CLI_LOG_CONFIG' via Typer's 'envvar='. Verify the env value
    # reaches the callback as a Path. Regression guard.
    cfg = tmp_path / "audit-logging.yaml"
    cfg.write_text("version: 1\n")

    result = cli_runner.invoke(
        cli_audit.app,
        ["room-authz", str(scratch_installation.path)],
        env={"SOLIPLEX_CLI_LOG_CONFIG": str(cfg)},
    )

    assert result.exit_code == 0
    # The group callback (which runs first) forwards the env-derived Path;
    # the '_authz_session' safety net then calls it again with no argument.
    assert configure_logging.call_args_list[0] == mock.call(cfg)


@pytest.mark.parametrize("w_errors", [False, True])
@pytest.mark.parametrize("w_quiet", [False, True])
@mock.patch("soliplex.cli.audit._common._emit_errors")
@mock.patch("soliplex.cli.audit.ollama._audit_ollama_section")
@mock.patch("soliplex.cli.audit.logfire._audit_logfire_section")
@mock.patch("soliplex.cli.audit.logging._audit_logging_section")
@mock.patch("soliplex.cli.audit.skills._audit_skills_section")
@mock.patch("soliplex.cli.audit.quizzes._audit_quizzes_section")
@mock.patch("soliplex.cli.audit.completions._audit_completions_section")
@mock.patch("soliplex.cli.audit.room_authz._audit_room_authz_section")
@mock.patch("soliplex.cli.audit.admin_users._audit_admin_users_section")
@mock.patch("soliplex.cli.audit.databases._audit_databases_section")
@mock.patch("soliplex.cli.audit.rooms._audit_rooms_section")
@mock.patch("soliplex.cli.audit.oidc._audit_oidc_section")
@mock.patch("soliplex.cli.audit.environment._audit_environment_section")
@mock.patch("soliplex.cli.audit.secrets._audit_secrets_section")
@mock.patch("soliplex.cli.audit.installation._audit_installation_section")
def test_audit_all(
    _audit_installation_section,
    _audit_secrets_section,
    _audit_environment_section,
    _audit_oidc_section,
    _audit_rooms_section,
    _audit_databases_section,
    _audit_admin_users_section,
    _audit_room_authz_section,
    _audit_completions_section,
    _audit_quizzes_section,
    _audit_skills_section,
    _audit_logging_section,
    _audit_logfire_section,
    _audit_ollama_section,
    _emit_errors,
    ctx,
    installation_path,
    w_quiet,
    w_errors,
):
    ctx.obj["quiet"] = w_quiet

    if w_errors:
        _audit_installation_section.return_value = {"installation": None}
        _audit_secrets_section.return_value = {"secrets": None}
        _audit_environment_section.return_value = {"environment": None}
        _audit_oidc_section.return_value = {"oidc": None}
        _audit_rooms_section.return_value = {"rooms": None}
        _audit_databases_section.return_value = {"databases": None}
        _audit_admin_users_section.return_value = {"admin_users": None}
        _audit_room_authz_section.return_value = {"room_authz": None}
        _audit_completions_section.return_value = {"completions": None}
        _audit_quizzes_section.return_value = {"quizzes": None}
        _audit_skills_section.return_value = {"skills": None}
        _audit_logging_section.return_value = {"logging": None}
        _audit_logfire_section.return_value = {"logfire": None}
        _audit_ollama_section.return_value = {"ollama": None}

        expected = {
            "installation": None,
            "secrets": None,
            "environment": None,
            "oidc": None,
            "rooms": None,
            "databases": None,
            "admin_users": None,
            "room_authz": None,
            "completions": None,
            "quizzes": None,
            "skills": None,
            "logging": None,
            "logfire": None,
            "ollama": None,
        }
    else:
        _audit_installation_section.return_value = {}
        _audit_secrets_section.return_value = {}
        _audit_environment_section.return_value = {}
        _audit_oidc_section.return_value = {}
        _audit_rooms_section.return_value = {}
        _audit_databases_section.return_value = {}
        _audit_admin_users_section.return_value = {}
        _audit_room_authz_section.return_value = {}
        _audit_completions_section.return_value = {}
        _audit_quizzes_section.return_value = {}
        _audit_skills_section.return_value = {}
        _audit_logging_section.return_value = {}
        _audit_logfire_section.return_value = {}
        _audit_ollama_section.return_value = {}

        expected = {}

    cli_audit.audit_all(ctx, installation_path)

    _emit_errors.assert_called_once_with(expected, w_quiet)

    _audit_installation_section.assert_called_once_with(ctx, installation_path)
    _audit_secrets_section.assert_called_once_with(ctx, installation_path)
    _audit_environment_section.assert_called_once_with(ctx, installation_path)
    _audit_oidc_section.assert_called_once_with(ctx, installation_path)
    _audit_rooms_section.assert_called_once_with(ctx, installation_path)
    _audit_admin_users_section.assert_called_once_with(ctx, installation_path)
    _audit_room_authz_section.assert_called_once_with(ctx, installation_path)
    _audit_completions_section.assert_called_once_with(ctx, installation_path)
    _audit_quizzes_section.assert_called_once_with(ctx, installation_path)
    _audit_skills_section.assert_called_once_with(ctx, installation_path)
    _audit_logging_section.assert_called_once_with(ctx, installation_path)
    _audit_logfire_section.assert_called_once_with(ctx, installation_path)
    _audit_ollama_section.assert_called_once_with(ctx, installation_path)
