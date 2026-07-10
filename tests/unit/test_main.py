import functools
import pathlib
from unittest import mock

import pytest
from fastapi.middleware import cors as fastapi_mw_cors
from starlette.middleware import sessions as starlette_mw_sessions

from soliplex import main

LOG_CONFIG_FILE_PATH = "/path/to/logging.yaml"
EXPLICIT_INST_PATH = "/explicit"
TOKEN = "DEADBEEF"


@pytest.fixture(scope="module", params=[False, True])
def no_auth_mode_kwargs(request):
    kw = {"no_auth_mode": request.param}
    return kw


@pytest.fixture(scope="module", params=[None, LOG_CONFIG_FILE_PATH])
def log_config_file_kwargs(request):
    kw = {}

    if request.param is not None:
        kw["log_config_file"] = request.param

    return kw


def test_curry_lifespan(
    no_auth_mode_kwargs,
    log_config_file_kwargs,
):
    exp_path = EXPLICIT_INST_PATH

    exp_no_auth_mode = no_auth_mode_kwargs["no_auth_mode"]

    if log_config_file_kwargs:
        exp_log_config_file = log_config_file_kwargs["log_config_file"]
    else:
        exp_log_config_file = None

    found = main.curry_lifespan(
        installation_path=EXPLICIT_INST_PATH,
        **no_auth_mode_kwargs,
        **log_config_file_kwargs,
    )

    assert isinstance(found, functools.partial)

    assert found.keywords == {
        "installation_path": pathlib.Path(exp_path),
        "no_auth_mode": exp_no_auth_mode,
        "log_config_file": exp_log_config_file,
    }


@mock.patch("fastapi.FastAPI")
@mock.patch("contextlib.asynccontextmanager")
def test_app_with_lifespan(acm, fapi):
    lifespan = mock.Mock(spec_set=())

    found = main.app_with_lifespan(lifespan)

    assert found is fapi.return_value
    assert found.state.agui_background_tasks == set()

    fapi.assert_called_once_with(lifespan=acm.return_value)
    acm.assert_called_once_with(lifespan)


def test_app_with_cors():
    app = mock.Mock(spec_set=["add_middleware"])
    extra_params = {
        "allow_origins": ["*"],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }

    found = main.app_with_cors(app, **extra_params)

    assert found is app
    app.add_middleware.assert_called_once_with(
        fastapi_mw_cors.CORSMiddleware,
        **extra_params,
    )


@pytest.mark.parametrize(
    "env, exp_https_only",
    [
        ({}, True),
        ({"_SOLIPLEX_INSECURE_SESSION_COOKIE": "Y"}, False),
    ],
)
def test_app_with_session(env, exp_https_only):
    app = mock.Mock(spec_set=["add_middleware"])
    installation_config = mock.Mock(spec_set=["get_secret"])
    installation_config.get_secret.return_value = TOKEN

    with mock.patch.dict("os.environ", env, clear=True):
        found = main.app_with_session(
            app,
            installation_config=installation_config,
        )

    assert found is app
    installation_config.get_secret.assert_called_once_with(
        "secret:SESSION_MIDDLEWARE_TOKEN",
    )
    app.add_middleware.assert_called_once_with(
        starlette_mw_sessions.SessionMiddleware,
        secret_key=TOKEN.encode("ascii"),
        https_only=exp_https_only,
        same_site="lax",
    )


def test_default_middleware_stack():
    found = main.default_middleware_stack()

    session_mw, cors_mw = found
    assert session_mw.name == "session"
    assert session_mw.app_factory is main.app_with_session
    assert session_mw.extra_params == {}
    assert cors_mw.name == "cors"
    assert cors_mw.app_factory is main.app_with_cors
    assert cors_mw.extra_params == {
        "allow_origins": ["*"],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


def _loaded_installation(w_configured_stack):
    """Build a mock 'InstallationConfig' with a controllable stack.

    When 'w_configured_stack' is true the config carries an explicit
    'middleware_stack'; otherwise it is empty (so 'create_app' falls back to
    'default_middleware_stack').
    """
    configured_stack = [mock.Mock(name="configured_mw")]
    inst = mock.Mock(spec_set=["middleware_stack"])
    inst.middleware_stack = configured_stack if w_configured_stack else []
    return inst


@pytest.mark.parametrize("w_configured_stack", [False, True])
@pytest.mark.parametrize("w_log_config_file", [None, LOG_CONFIG_FILE_PATH])
@pytest.mark.parametrize("w_no_auth_mode", [False, True])
def test_create_app_with_explicit_overrides(
    w_no_auth_mode,
    w_log_config_file,
    w_configured_stack,
):
    kwargs = {}

    if w_log_config_file is not None:
        kwargs["log_config_file"] = w_log_config_file

    loaded_installation = _loaded_installation(w_configured_stack)
    i_path = pathlib.Path(EXPLICIT_INST_PATH)
    curry_lifespan = mock.Mock(spec_set=())
    app_with_lifespan = mock.Mock(spec_set=())
    compose_middleware_stack = mock.Mock(spec_set=())
    default_middleware_stack = mock.Mock(spec_set=())

    with (
        mock.patch.object(
            main.config_middleware,
            "compose_middleware_stack",
            compose_middleware_stack,
        ),
        mock.patch.object(
            main, "default_middleware_stack", default_middleware_stack
        ),
        mock.patch.object(
            main.config_installation,
            "load_installation",
            return_value=loaded_installation,
        ) as load_installation,
    ):
        found = main.create_app(
            installation_path=i_path,
            no_auth_mode=w_no_auth_mode,
            curry_lifespan=curry_lifespan,
            app_with_lifespan=app_with_lifespan,
            **kwargs,
        )

    assert found is compose_middleware_stack.return_value
    load_installation.assert_called_once_with(i_path)

    if w_configured_stack:
        exp_stack = loaded_installation.middleware_stack
        default_middleware_stack.assert_not_called()
    else:
        exp_stack = default_middleware_stack.return_value
        default_middleware_stack.assert_called_once_with()

    compose_middleware_stack.assert_called_once_with(
        app_with_lifespan.return_value,
        loaded_installation,
        exp_stack,
    )
    app_with_lifespan.assert_called_once_with(curry_lifespan.return_value)
    curry_lifespan.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=w_no_auth_mode,
        log_config_file=w_log_config_file,
    )


@pytest.mark.parametrize("w_configured_stack", [False, True])
@pytest.mark.parametrize("w_log_config_file", [None, LOG_CONFIG_FILE_PATH])
@pytest.mark.parametrize("w_no_auth_mode", [False, True])
def test_create_app_wo_explicit_overrides(
    w_no_auth_mode,
    w_log_config_file,
    w_configured_stack,
):
    kwargs = {}

    if w_log_config_file is not None:
        kwargs["log_config_file"] = w_log_config_file

    loaded_installation = _loaded_installation(w_configured_stack)
    i_path = pathlib.Path(EXPLICIT_INST_PATH)
    curry_lifespan = mock.Mock(spec_set=())
    app_with_lifespan = mock.Mock(spec_set=())
    compose_middleware_stack = mock.Mock(spec_set=())
    default_middleware_stack = mock.Mock(spec_set=())

    with (
        mock.patch.multiple(
            "soliplex.main",
            curry_lifespan=curry_lifespan,
            app_with_lifespan=app_with_lifespan,
            default_middleware_stack=default_middleware_stack,
        ),
        mock.patch.object(
            main.config_middleware,
            "compose_middleware_stack",
            compose_middleware_stack,
        ),
        mock.patch.object(
            main.config_installation,
            "load_installation",
            return_value=loaded_installation,
        ) as load_installation,
    ):
        found = main.create_app(
            installation_path=i_path,
            no_auth_mode=w_no_auth_mode,
            **kwargs,
        )

    assert found is compose_middleware_stack.return_value
    load_installation.assert_called_once_with(i_path)

    if w_configured_stack:
        exp_stack = loaded_installation.middleware_stack
        default_middleware_stack.assert_not_called()
    else:
        exp_stack = default_middleware_stack.return_value
        default_middleware_stack.assert_called_once_with()

    compose_middleware_stack.assert_called_once_with(
        app_with_lifespan.return_value,
        loaded_installation,
        exp_stack,
    )
    app_with_lifespan.assert_called_once_with(curry_lifespan.return_value)
    curry_lifespan.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=w_no_auth_mode,
        log_config_file=w_log_config_file,
    )


@pytest.mark.parametrize("w_log_config_file", [None, LOG_CONFIG_FILE_PATH])
@pytest.mark.parametrize("w_no_auth_mode", [False, True])
@mock.patch("soliplex.main.create_app")
def test_create_app_from_environment(
    create_app,
    temp_dir,
    w_no_auth_mode,
    w_log_config_file,
):
    i_path = temp_dir / "installation.yaml"

    env_patch = {"_SOLIPLEX_INSTALLATION_PATH": str(i_path)}

    if w_no_auth_mode:
        env_patch["_SOLIPLEX_NO_AUTH_MODE"] = "Y"

    if w_log_config_file:
        env_patch["_SOLIPLEX_LOG_CONFIG_FILE"] = w_log_config_file

    with mock.patch.dict("os.environ", clear=True, **env_patch):
        found = main.create_app_from_environment()

    assert found is create_app.return_value
    create_app.assert_called_once_with(
        installation_path=i_path,
        no_auth_mode=w_no_auth_mode,
        log_config_file=w_log_config_file,
    )
