"""Test-only middleware for config_middleware tests."""

import inspect
import typing

from soliplex.config import installation as config_installation


class _Wrapped:
    def __init__(self, app: typing.Any, i_config=None, **kwargs):
        self.app = app
        self.i_config = i_config
        self.kwargs = kwargs
        caller_info = inspect.stack()[1]
        self.name = caller_info[3]


def null_app_factory(app):
    return _Wrapped(app)


def w_iconfig_app_factory(
    app,
    *,
    installation_config: config_installation.InstallationConfig,
):
    return _Wrapped(app, i_config=installation_config)


def w_extra_params_app_factory(
    app,
    **extra_params,
):
    return _Wrapped(app, **extra_params)
