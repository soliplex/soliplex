"""Configuration to extend / replace routes for the FastAPI application"""

import dataclasses
import pathlib
import typing

import fastapi

from . import _utils
from . import exceptions as config_exc

APP_ROUTERS_BY_GROUP_NAME = {
    # "group_name": (router, router_name, **kw)
}


class AppRoutingGroupAlreadyExists(ValueError):
    def __init__(self, group_name):
        self.group_name = group_name
        super().__init__(f"App routing group {group_name} already exists")


class UnknownAppRoutingGroup(KeyError):
    def __init__(self, group_name, existing_group_names):
        self.group_name = group_name
        self.existing_group_names = existing_group_names
        super().__init__(
            f"App routing group {group_name} does not exist "
            f"(existing group names: {','.join(existing_group_names)})"
        )


class AppRouterOperationKindMismatch(ValueError):
    def __init__(self, found_kind, expected_kind):
        self.found_kind = found_kind
        self.expected_kind = expected_kind
        super().__init__(
            "App router operation kind mismatch: "
            f"found '{found_kind}', expected '{expected_kind}'"
        )


@dataclasses.dataclass(kw_only=True)
class APIRouterKwargs:
    prefix: str | None = "/api"
    tags: list[str] | None = None
    dependencies: list[_utils.DottedName] | None = None

    default_response_class: _utils.DottedName | None = None
    deprecated: bool | None = None

    @property
    def _all_router_kwargs(self) -> dict[str, typing.Any]:
        return {
            "prefix": self.prefix,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "default_response_class": self.default_response_class,
            "deprecated": self.deprecated,
        }

    @property
    def router_kwargs(self) -> dict[str, typing.Any]:
        return {
            key: value
            for key, value in self._all_router_kwargs.items()
            if value is not None
        }


@dataclasses.dataclass(kw_only=True)
class _AppRouterOperationBase:
    kind: typing.ClassVar[str]
    group_name: str

    @classmethod
    def _check_kind(cls, kind):
        if kind not in (None, cls.kind):
            raise AppRouterOperationKindMismatch(kind, cls.kind)

    @classmethod
    def from_yaml(cls, config_dict, config_path):
        try:
            kind = config_dict.pop("kind", None)
            cls._check_kind(kind)
            config_dict["_config_path"] = config_path
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                f"app_router_op:{cls.kind}",
                config_dict,
            ) from exc

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return {
            "kind": self.kind,
            "group_name": self.group_name,
        }


@dataclasses.dataclass(kw_only=True)
class AddAppRouter(_AppRouterOperationBase, APIRouterKwargs):
    """Add a new router config for a group name"""

    kind: typing.ClassVar[str] = "add"
    router_name: _utils.DottedName  # importable
    replace_existing: bool = False

    # Set in '_AppRouterOperationBase.from_yaml' above
    _config_path: pathlib.Path = None

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        non_default_value_kwargs = {
            key: value
            for key, value in self._all_router_kwargs.items()
            if key in _API_ROUTER_KWARG_DEFAULTS
            and value != _API_ROUTER_KWARG_DEFAULTS[key]
        }
        return (
            super().as_yaml
            | {
                "router_name": self.router_name,
                "replace_existing": self.replace_existing,
            }
            | non_default_value_kwargs
        )

    def apply(self):
        registry = APP_ROUTERS_BY_GROUP_NAME

        if self.group_name in registry and not self.replace_existing:
            raise AppRoutingGroupAlreadyExists(self.group_name)

        router = _utils._from_dotted_name(self.router_name)
        registry[self.group_name] = (
            router,
            self.router_name,
            self.router_kwargs,
        )


@dataclasses.dataclass(kw_only=True)
class DeleteAppRouter(_AppRouterOperationBase):
    """Delete an existing router config for a group name"""

    kind: typing.ClassVar[str] = "delete"
    require_existing: bool = True

    # Set in '_AppRouterOperationBase.from_yaml' above
    _config_path: pathlib.Path = None

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return super().as_yaml | {
            "require_existing": self.require_existing,
        }

    def apply(self):
        found = APP_ROUTERS_BY_GROUP_NAME.pop(self.group_name, None)

        if found is None and self.require_existing:
            existing_group_names = list(APP_ROUTERS_BY_GROUP_NAME)
            raise UnknownAppRoutingGroup(
                self.group_name,
                existing_group_names,
            )


@dataclasses.dataclass(kw_only=True)
class ClearAppRouters:
    """Delete an existing router config for a group name"""

    kind: typing.ClassVar[str] = "clear"

    # Set in 'from_yaml' below
    _config_path: pathlib.Path = None

    @classmethod
    def _check_kind(cls, kind):
        if kind not in (None, cls.kind):
            raise AppRouterOperationKindMismatch(kind, cls.kind)

    @classmethod
    def from_yaml(cls, config_dict, config_path):
        try:
            kind = config_dict.pop("kind", None)
            cls._check_kind(kind)
            config_dict["_config_path"] = config_path
            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                f"app_router_op:{cls.kind}",
                config_dict,
            ) from exc

    @property
    def as_yaml(self) -> dict[str, typing.Any]:
        return {"kind": self.kind}

    def apply(self):
        APP_ROUTERS_BY_GROUP_NAME.clear()


AppRouterOperations = AddAppRouter | DeleteAppRouter | ClearAppRouters


APP_ROUTER_OPERATIONS_BY_KIND = {
    AddAppRouter.kind: AddAppRouter,
    DeleteAppRouter.kind: DeleteAppRouter,
    ClearAppRouters.kind: ClearAppRouters,
}


_API_ROUTER_KWARG_DEFAULTS = {
    field.name: field.default for field in dataclasses.fields(APIRouterKwargs)
}

_DEFAULT_KWARGS = APIRouterKwargs().router_kwargs


_DEFAULT_ROUTER_NAMES = {
    "views": "soliplex.views.router",
    "agui": "soliplex.views.agui.router",
    "authn": "soliplex.views.authn.router",
    "authz": "soliplex.views.authz.router",
    "completions": "soliplex.views.completions.router",
    "room_file_uploads": "soliplex.views.room_file_uploads.router",
    "thread_file_uploads": "soliplex.views.thread_file_uploads.router",
    "sandbox_workdirs": "soliplex.views.sandbox_workdirs.router",
    "installation": "soliplex.views.installation.router",
    "log_ingest": "soliplex.views.log_ingest.router",
    "quizzes": "soliplex.views.quizzes.router",
    "rooms": "soliplex.views.rooms.router",
    "stats": "soliplex.views.stats.router",
}


def register_default_routers():
    for group_name, router_name in _DEFAULT_ROUTER_NAMES.items():
        router = _utils._from_dotted_name(router_name)
        APP_ROUTERS_BY_GROUP_NAME[group_name] = (
            router,
            router_name,
            _DEFAULT_KWARGS,
        )


def add_registered_routers(app: fastapi.FastAPI) -> None:
    for (
        router,
        _module_name,
        include_router_kwargs,
    ) in APP_ROUTERS_BY_GROUP_NAME.values():
        app.include_router(router, **include_router_kwargs)
