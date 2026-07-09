import os
import pathlib
from types import SimpleNamespace
from unittest import mock

import pytest
import typer

from soliplex.cli import serve

ADMIN_EMAIL = "admin@example.com"
WORKERS = 4
UDS_PATH = "/run/soliplex.sock"
SOCKET_FD = 7
FORWARDED_ALLOW_IPS = "*"
APP_FACTORY_NAME = "my.module:factory"


def _serve_kwargs(installation_path, **overrides):
    """Build a full keyword set for a direct 'serve.serve(...)' call.

    The command is a Typer command, but the underlying function is a plain
    callable. Driving it directly (rather than through 'CliRunner') is the
    only way to exercise the callable-injection branches: '--app-maker'
    cannot carry a callable over the command line, and a string there would
    raise 'TypeError' when invoked.
    """
    kwargs = dict(
        ctx=None,
        installation_path=installation_path,
        no_auth_mode=False,
        insecure_session_cookie=False,
        add_admin_user=None,
        host=serve.DEFAULT_HOST,
        port=serve.DEFAULT_PORT,
        uds=None,
        fd=None,
        reload=None,
        reload_dirs=[],
        reload_includes=[],
        workers=None,
        log_config=None,
        log_level=None,
        access_log=None,
        proxy_headers=None,
        forwarded_allow_ips=None,
        app_factory_name=None,
        app_maker=None,
    )
    kwargs.update(overrides)
    return kwargs


@pytest.fixture
def patched_serve():
    """Patch the command's external collaborators and isolate 'os.environ'.

    'get_installation' returns a mock whose '_logging_config_file' is 'None'
    by default (the "no installation-level logging config" branch); tests
    that need the opposite reassign it. 'os.environ' is cleared so the
    private '_SOLIPLEX_*' contract writes are deterministic to assert.
    """
    inst = mock.Mock()
    inst._config._logging_config_file = None

    with (
        mock.patch.object(serve.uvicorn, "run") as uvicorn_run,
        mock.patch.object(
            serve.cli_util, "get_installation", return_value=inst
        ) as get_installation,
        mock.patch.object(serve.main, "create_app") as create_app,
        mock.patch.dict("os.environ", {}, clear=True),
    ):
        yield SimpleNamespace(
            uvicorn_run=uvicorn_run,
            get_installation=get_installation,
            create_app=create_app,
            installation=inst,
        )


def test_serve_add_admin_user_removed_exits(patched_serve, tmp_path):
    kwargs = _serve_kwargs(
        tmp_path / "installation.yaml",
        add_admin_user=ADMIN_EMAIL,
    )

    with pytest.raises(typer.Exit) as exc_info:
        serve.serve(**kwargs)

    assert exc_info.value.exit_code == 1
    patched_serve.get_installation.assert_not_called()
    patched_serve.create_app.assert_not_called()
    patched_serve.uvicorn_run.assert_not_called()


def test_serve_direct_default_uses_create_app(patched_serve, tmp_path):
    i_path = tmp_path / "installation.yaml"
    kwargs = _serve_kwargs(i_path)

    serve.serve(**kwargs)

    patched_serve.create_app.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=False,
        log_config_file=None,
    )
    assert "_SOLIPLEX_INSECURE_SESSION_COOKIE" not in os.environ
    patched_serve.uvicorn_run.assert_called_once_with(
        patched_serve.create_app.return_value,
        host=serve.DEFAULT_HOST,
        port=serve.DEFAULT_PORT,
        ws=serve.WEBSOCKETS_SANSIO,
    )


def test_serve_direct_honors_explicit_app_maker(patched_serve, tmp_path):
    i_path = tmp_path / "installation.yaml"
    app_maker = mock.Mock()
    kwargs = _serve_kwargs(i_path, app_maker=app_maker)

    serve.serve(**kwargs)

    app_maker.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=False,
        log_config_file=None,
    )
    patched_serve.create_app.assert_not_called()
    patched_serve.uvicorn_run.assert_called_once_with(
        app_maker.return_value,
        host=serve.DEFAULT_HOST,
        port=serve.DEFAULT_PORT,
        ws=serve.WEBSOCKETS_SANSIO,
    )


def test_serve_direct_uses_installation_logging_config(
    patched_serve, tmp_path
):
    # No '--log-config' on the command line, but the installation carries
    # its own logging config -> it is forwarded to Uvicorn.
    i_path = tmp_path / "installation.yaml"
    log_path = pathlib.Path("/etc/soliplex/logging.yaml")
    patched_serve.installation._config._logging_config_file = log_path
    patched_serve.installation._config.logging_config_file = log_path
    kwargs = _serve_kwargs(i_path)

    serve.serve(**kwargs)

    patched_serve.uvicorn_run.assert_called_once_with(
        patched_serve.create_app.return_value,
        host=serve.DEFAULT_HOST,
        port=serve.DEFAULT_PORT,
        ws=serve.WEBSOCKETS_SANSIO,
        log_config=str(log_path),
    )


def test_serve_reload_both_directory_factory(patched_serve, tmp_path):
    # 'tmp_path' is a real directory, so the 'is_dir()' branch watches it
    # directly; 'BOTH' also adds the 'soliplex' package directory.
    kwargs = _serve_kwargs(tmp_path, reload=serve.ReloadOption.BOTH)

    serve.serve(**kwargs)

    patched_serve.create_app.assert_not_called()
    assert os.environ["_SOLIPLEX_INSTALLATION_PATH"] == str(tmp_path)
    assert "_SOLIPLEX_NO_AUTH_MODE" not in os.environ
    assert "_SOLIPLEX_LOG_CONFIG_FILE" not in os.environ
    assert "_SOLIPLEX_INSECURE_SESSION_COOKIE" not in os.environ

    args, call_kwargs = patched_serve.uvicorn_run.call_args
    assert args == ("soliplex.main:create_app_from_environment",)
    assert call_kwargs["factory"] is True
    assert call_kwargs["reload"] is serve.ReloadOption.BOTH
    assert str(tmp_path) in call_kwargs["reload_dirs"]
    assert call_kwargs["reload_includes"] == ["*.yaml", "*.yml", "*.txt"]
    assert call_kwargs["host"] == serve.DEFAULT_HOST
    assert call_kwargs["port"] == serve.DEFAULT_PORT
    assert call_kwargs["ws"] == serve.WEBSOCKETS_SANSIO


def test_serve_reload_config_file_watches_parent_dir(patched_serve, tmp_path):
    # A non-directory installation path -> watch its parent. 'CONFIG' (not
    # 'PYTHON'/'BOTH') does not add the 'soliplex' package directory.
    i_file = tmp_path / "installation.yaml"
    kwargs = _serve_kwargs(i_file, reload=serve.ReloadOption.CONFIG)

    serve.serve(**kwargs)

    args, call_kwargs = patched_serve.uvicorn_run.call_args
    assert args == ("soliplex.main:create_app_from_environment",)
    assert call_kwargs["reload"] is serve.ReloadOption.CONFIG
    assert call_kwargs["reload_dirs"] == [str(tmp_path)]
    assert call_kwargs["reload_includes"] == ["*.yaml", "*.yml", "*.txt"]


def test_serve_workers_factory_with_all_options(patched_serve, tmp_path):
    # The workers path is a factory path even without '--reload'. Set every
    # optional Uvicorn knob and both other '_SOLIPLEX_*' env writes, plus an
    # explicit app-factory name (so the default is not substituted).
    i_file = tmp_path / "installation.yaml"
    log_cfg = tmp_path / "logging.yaml"
    kwargs = _serve_kwargs(
        i_file,
        workers=WORKERS,
        no_auth_mode=True,
        log_config=log_cfg,
        uds=UDS_PATH,
        fd=SOCKET_FD,
        log_level=serve.LogLevelOption.DEBUG,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=FORWARDED_ALLOW_IPS,
        app_factory_name=APP_FACTORY_NAME,
    )

    serve.serve(**kwargs)

    assert os.environ["_SOLIPLEX_INSTALLATION_PATH"] == str(i_file)
    assert os.environ["_SOLIPLEX_NO_AUTH_MODE"] == "Y"
    assert os.environ["_SOLIPLEX_LOG_CONFIG_FILE"] == str(log_cfg)

    args, call_kwargs = patched_serve.uvicorn_run.call_args
    assert args == (APP_FACTORY_NAME,)
    assert call_kwargs["factory"] is True
    assert call_kwargs["reload"] is None
    assert call_kwargs["uds"] == UDS_PATH
    assert call_kwargs["fd"] == SOCKET_FD
    assert call_kwargs["workers"] == WORKERS
    assert call_kwargs["log_level"] is serve.LogLevelOption.DEBUG
    assert call_kwargs["log_config"] == str(log_cfg)
    assert call_kwargs["access_log"] is False
    assert call_kwargs["proxy_headers"] is True
    assert call_kwargs["forwarded_allow_ips"] == FORWARDED_ALLOW_IPS


def test_serve_direct_insecure_session_cookie(patched_serve, tmp_path):
    # '--insecure-session-cookie' on the direct path turns off the cookie's
    # Secure flag via the private env var read in-process by
    # 'soliplex.main.app_with_session'.
    i_path = tmp_path / "installation.yaml"
    kwargs = _serve_kwargs(i_path, insecure_session_cookie=True)

    serve.serve(**kwargs)

    assert os.environ["_SOLIPLEX_INSECURE_SESSION_COOKIE"] == "Y"
    patched_serve.create_app.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=False,
        log_config_file=None,
    )


def test_serve_factory_insecure_session_cookie(patched_serve, tmp_path):
    # On the factory path the flag is forwarded through the private
    # '_SOLIPLEX_*' env contract to 'create_app_from_environment'.
    i_file = tmp_path / "installation.yaml"
    kwargs = _serve_kwargs(
        i_file,
        workers=WORKERS,
        insecure_session_cookie=True,
    )

    serve.serve(**kwargs)

    assert os.environ["_SOLIPLEX_INSECURE_SESSION_COOKIE"] == "Y"
    args, _call_kwargs = patched_serve.uvicorn_run.call_args
    assert args == ("soliplex.main:create_app_from_environment",)
