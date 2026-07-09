from __future__ import annotations  # forward refs in typing decls

import dataclasses
import inspect
import typing

import fastapi

from soliplex.config import installation as config_installation

from . import _utils

_no_repr = _utils._no_repr
_default_dict_field = _utils._default_dict_field


@typing.runtime_checkable
class MiddlewareFactoryNoIconfig(typing.Protocol):
    """Protocol for middelware factory without installation config"""

    def __call__(
        self,
        app: fastapi.FastAPI,
        **extra_params,
    ) -> fastapi.FastAPI: ...


@typing.runtime_checkable
class MiddlewareFactoryWithIConfig(typing.Protocol):
    """Protocol for middelware factory without installation config"""

    def __call__(
        self,
        app: fastapi.FastAPI,
        *,
        installation_config: config_installation.InstallationConfig,
        **extra_params,
    ) -> fastapi.FastAPI: ...


MiddlewareFactory = MiddlewareFactoryNoIconfig | MiddlewareFactoryWithIConfig


@dataclasses.dataclass(kw_only=True)
class MiddlewareConfig:
    """Registered middleware

    'app_factory'
        dotted name of a factory returning a middleware instance, wrapped
        around an existing ASGI application (or other middleware).

    'extra_params':
        dict parsed from other keys in the YAML for the middleware.

    Example usage:

        Without a factory needing an 'InstallationConfig':
        ```
        factory = functools.partial(
            _utils._from_dotted_name(mw_config.app_factory),
            **mw_config.extra_params,
        )
        app = factory(app)
        ```

        With a factory needing an 'InstallationConfig':
        ```
        factory = functools.partial(
            _utils._from_dotted_name(mw_config.app_factory),
            installation_config=i_config,
            **mw_config.extra_params,
        )
        app = factory(app)
        ```
    """

    name: str
    app_factory: MiddlewareFactory
    extra_params: dict[str, typing.Any] = _default_dict_field()

    @property
    def needs_iconfig(self):
        argspec = inspect.getfullargspec(self.app_factory)
        return "installation_config" in argspec.kwonlyargs

    @classmethod
    def from_yaml(cls, yaml_config: dict):
        app_factory = yaml_config["app_factory"]
        yaml_config["app_factory"] = _utils._from_dotted_name(app_factory)
        return cls(**yaml_config)


def compose_middleware_stack(
    app,
    installation_config: config_installation.InstallationConfig,
    to_compose: list[MiddlewareConfig],
):
    composed = app
    composing = to_compose[:]

    while composing:
        mw_config = composing.pop()
        if mw_config.needs_iconfig:
            composed = mw_config.app_factory(
                composed,
                installation_config=installation_config,
                **mw_config.extra_params,
            )
        else:
            composed = mw_config.app_factory(
                composed,
                **mw_config.extra_params,
            )

    return composed
