from __future__ import annotations  # forward refs in typing decls

import dataclasses
import enum
import functools
import inspect
import pathlib
import typing
from collections import abc
from urllib import parse as url_parse

from pydantic_ai import tools as ai_tools

from . import _utils
from . import exceptions as config_exc
from . import rag as config_rag

# ============================================================================
#   Tool configuration types
# ============================================================================


FunctionSchema = ai_tools._function_schema.FunctionSchema


class ToolRequirementConflict(ValueError):
    def __init__(self, tool_name, _config_path):
        self.tool_name = tool_name
        self._config_path = _config_path
        super().__init__(
            f"Tool {tool_name} requires both context and tool config "
            f"(configured in {_config_path}"
        )


class ToolRequires(enum.StrEnum):
    FASTAPI_CONTEXT = "fastapi_context"
    TOOL_CONFIG = "tool_config"
    BARE = "bare"


@dataclasses.dataclass(kw_only=True)
class AIToolParams:
    """Parameters to be passed to 'pydantic_ai.tools.Tool' ctor

    See its docstring for semantics.
    """

    takes_ctx: bool | None = None
    max_retries: int | None = None
    name: str | None = None
    description: str | None = None
    docstring_format: ai_tools.DocstringFormat = None
    require_parameter_descriptions: bool = None
    strict: bool | None = None
    sequential: bool = None
    requires_approval: bool = None
    metadata: dict[str, typing.Any] | None = None
    timeout: float | None = None

    # Set via 'from_yaml'
    _config_path: pathlib.Path = None

    # These dotted names are resolved inside 'as_aitool_ctor_kwargs'
    _prepare: _utils.DottedName | None = None
    _args_validator: _utils.DottedName | None = None
    _schema_generator: _utils.DottedName | None = None
    _function_schema: _utils.DottedName | None = None

    @classmethod
    def from_yaml(
        cls,
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict["_config_path"] = config_path

            prepare = config_dict.pop("prepare", None)
            if prepare is not None:
                config_dict["_prepare"] = prepare

            args_validator = config_dict.pop("args_validator", None)
            if args_validator is not None:
                config_dict["_args_validator"] = args_validator

            schema_generator = config_dict.pop("schema_generator", None)
            if schema_generator is not None:
                config_dict["_schema_generator"] = schema_generator

            function_schema = config_dict.pop("function_schema", None)
            if function_schema is not None:
                config_dict["_function_schema"] = function_schema

            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path, "aitoolparams", config_dict
            ) from exc

    @property
    def prepare(self) -> ai_tools.ToolPrepareFunc | None:
        if self._prepare is not None:
            return _utils._from_dotted_name(self._prepare)
        else:
            return None

    @property
    def args_validator(self) -> ai_tools.ArgsValidatorFunc | None:
        if self._args_validator is not None:
            return _utils._from_dotted_name(self._args_validator)
        else:
            return None

    @property
    def schema_generator(self) -> type[ai_tools.GenerateJsonSchema] | None:
        if self._schema_generator is not None:
            return _utils._from_dotted_name(self._schema_generator)
        else:
            return None

    @property
    def function_schema(self) -> FunctionSchema | None:
        if self._function_schema is not None:
            return _utils._from_dotted_name(self._function_schema)
        else:
            return None

    @property
    def as_yaml(self) -> dict:
        candidates = {
            "takes_ctx": self.takes_ctx,
            "max_retries": self.max_retries,
            "name": self.name,
            "description": self.description,
            "docstring_format": self.docstring_format,
            "require_parameter_descriptions": (
                self.require_parameter_descriptions
            ),
            "strict": self.strict,
            "sequential": self.sequential,
            "requires_approval": self.requires_approval,
            "metadata": self.metadata,
            "timeout": self.timeout,
            "prepare": self._prepare,
            "args_validator": self._args_validator,
            "schema_generator": self._schema_generator,
            "function_schema": self._function_schema,
        }

        return {
            key: value
            for key, value in candidates.items()
            if value is not None
        }

    @property
    def as_aitool_ctor_kwargs(self) -> dict[str, typing.Any]:
        candidates = {
            "takes_ctx": self.takes_ctx,
            "max_retries": self.max_retries,
            "name": self.name,
            "description": self.description,
            "docstring_format": self.docstring_format,
            "require_parameter_descriptions": (
                self.require_parameter_descriptions
            ),
            "strict": self.strict,
            "sequential": self.sequential,
            "requires_approval": self.requires_approval,
            "metadata": self.metadata,
            "timeout": self.timeout,
            "prepare": self.prepare,
            "args_validator": self.args_validator,
            "schema_generator": self.schema_generator,
            "function_schema": self.function_schema,
        }

        return {
            key: value
            for key, value in candidates.items()
            if value is not None
        }


@dataclasses.dataclass(kw_only=True)
class ToolConfig:
    tool_name: _utils.DottedName
    allow_mcp: bool = False
    agui_feature_names: tuple[str] = ()
    _ai_tool_params: AIToolParams | None = None

    _tool: abc.Callable[..., typing.Any] = None

    # Set in 'from_yaml' below
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            agui_feature_names = config_dict.pop("agui_feature_names", ())
            config_dict["agui_feature_names"] = tuple(agui_feature_names)

            ai_tool_params = config_dict.pop("ai_tool_params", None)
            if ai_tool_params is not None:
                config_dict["_ai_tool_params"] = AIToolParams.from_yaml(
                    config_path=config_path,
                    config_dict=ai_tool_params,
                )

            return cls(**config_dict)
        except config_exc.FromYamlException:  # pragma: NO COVER
            raise

        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path, "toolconfig", config_dict
            ) from exc

    @property
    def kind(self):
        _, kind = self.tool_name.rsplit(".", 1)
        return kind

    @property
    def tool_id(self):
        return self.kind

    @property
    def tool(self):
        if self._tool is None:
            self._tool = _utils._from_dotted_name(self.tool_name)

        return self._tool

    @property
    def tool_description(self) -> str:
        return inspect.getdoc(self.tool)

    @property
    def tool_requires(self) -> ToolRequires | None:
        tool_params = inspect.signature(self.tool).parameters

        if "ctx" in tool_params and "tool_config" in tool_params:
            raise ToolRequirementConflict(self.tool_name, self._config_path)

        if "ctx" in tool_params:
            return ToolRequires.FASTAPI_CONTEXT
        elif "tool_config" in tool_params:
            return ToolRequires.TOOL_CONFIG
        else:
            return ToolRequires.BARE

    @property
    def ai_tool_params(self) -> dict[str, typing.Any]:
        if self._ai_tool_params is not None:
            return self._ai_tool_params.as_aitool_ctor_kwargs
        else:
            return {}

    @property
    def tool_with_config(self) -> abc.Callable[..., typing.Any]:
        if self.tool_requires == ToolRequires.TOOL_CONFIG:
            tool_func_sig = inspect.signature(self.tool)
            wo_tc_sig = tool_func_sig.replace(
                parameters=[
                    param
                    for param in tool_func_sig.parameters.values()
                    if param.name != "tool_config"
                ]
            )
            tool_w_config = functools.update_wrapper(
                functools.partial(self.tool, tool_config=self),
                self.tool,
            )
            tool_w_config.__signature__ = wo_tc_sig

            return tool_w_config
        else:
            return self.tool

    def get_extra_parameters(self) -> dict:
        return {}


SDTC_TOOL_NAME = "soliplex.tools.rag.search_documents"
_, SDTC_TOOL_KIND = SDTC_TOOL_NAME.rsplit(".", 1)


@dataclasses.dataclass(kw_only=True)
class SearchDocumentsToolConfig(ToolConfig, config_rag._RAGConfigBase):
    kind: str = SDTC_TOOL_KIND
    tool_name: str = SDTC_TOOL_NAME

    search_documents_limit: int = 5

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            instance = cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "sdtc",
                config_dict,
            ) from exc

        return instance

    def get_extra_parameters(self) -> dict:
        local = {
            "search_documents_limit": self.search_documents_limit,
        }
        return (
            super().get_extra_parameters()
            | config_rag._RAGConfigBase.get_extra_parameters(self)
            | local
        )


TOOL_CONFIG_CLASSES_BY_TOOL_NAME = {
    klass.tool_name: klass
    for klass in [
        SearchDocumentsToolConfig,
    ]
}


ToolConfigMap = dict[str, ToolConfig]


def extract_tool_configs(
    installation_config: InstallationConfig,  # noqa F821 cycle
    config_path: pathlib.Path,
    config_dict: dict,
) -> ToolConfigMap:
    tool_configs = {}

    for t_config in config_dict.pop("tools", ()):
        tool_name = t_config.get("tool_name")
        tc_class = TOOL_CONFIG_CLASSES_BY_TOOL_NAME.get(tool_name, ToolConfig)

        tool_config = tc_class.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=t_config,
        )
        tool_configs[tool_config.kind] = tool_config

    return tool_configs


@dataclasses.dataclass(kw_only=True)
class Stdio_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which runs as a subprocess"""

    kind: typing.ClassVar[str] = "stdio"
    command: str
    args: list[str] = _utils._default_list_field()

    env: dict[str, str] = _utils._default_dict_field()
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path,
                "stdio_mcptc",
                config_dict,
            ) from exc

    @property
    def toolset_params(self) -> dict:
        return {
            "command": self.command,
            "args": self.args,
            "env": self.env,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        env_map = {
            key: self._installation_config.get_secret(value)
            for (key, value) in self.env.items()
        }
        return {
            "command": self.command,
            "args": self.args,
            "env": env_map,
            "allowed_tools": self.allowed_tools,
        }


@dataclasses.dataclass(kw_only=True)
class HTTP_MCP_ClientToolsetConfig:
    """Configure an MCP client toolset which makes calls over streaming HTTP"""

    kind: typing.ClassVar[str] = "http"
    url: str
    headers: dict[str, typing.Any] = _utils._default_dict_field()

    query_params: dict[str, str] = _utils._default_dict_field()
    allowed_tools: list[str] = None

    # set in 'from_yaml' class factory
    _installation_config: InstallationConfig = (  # noqa F821 cycle
        _utils._no_repr_no_compare_none()
    )
    _config_path: pathlib.Path = None

    @classmethod
    def from_yaml(
        cls,
        installation_config: InstallationConfig,  # noqa F821 cycle
        config_path: pathlib.Path,
        config_dict: dict[str, typing.Any],
    ):
        try:
            config_dict["_installation_config"] = installation_config
            config_dict["_config_path"] = config_path

            return cls(**config_dict)
        except Exception as exc:
            raise config_exc.FromYamlException(
                config_path, "http_mcptc", config_dict
            ) from exc

    @property
    def toolset_params(self) -> dict:
        return {
            "url": self.url,
            "headers": self.headers,
            "query_params": self.query_params,
            "allowed_tools": self.allowed_tools,
        }

    @property
    def tool_kwargs(self) -> dict:
        url = self.url

        headers = {
            key: self._installation_config.interpolate_secrets(value)
            for (key, value) in self.headers.items()
        }

        if self.query_params:
            qp = {
                key: self._installation_config.get_secret(value)
                for (key, value) in self.query_params.items()
            }
            qs = url_parse.urlencode(qp)
            url = f"{url}?{qs}"

        return {
            "url": url,
            "headers": headers,
            "allowed_tools": self.allowed_tools,
        }


MCP_TOOLSET_CONFIG_CLASSES_BY_KIND = {
    "stdio": Stdio_MCP_ClientToolsetConfig,
    "http": HTTP_MCP_ClientToolsetConfig,
}


def extract_mcp_client_toolset_configs(
    installation_config: InstallationConfig,  # noqa F821 cycle
    config_path: pathlib.Path,
    config_dict: dict,
):
    mcp_client_toolset_configs = {}

    for mcp_name, mcp_client_toolset_config in config_dict.pop(
        "mcp_client_toolsets", {}
    ).items():
        kind = mcp_client_toolset_config.pop("kind")
        mcp_config_klass = MCP_TOOLSET_CONFIG_CLASSES_BY_KIND[kind]
        mcp_client_toolset_configs[mcp_name] = mcp_config_klass.from_yaml(
            installation_config=installation_config,
            config_path=config_path,
            config_dict=mcp_client_toolset_config,
        )

    return mcp_client_toolset_configs


MCP_ClientToolsetConfig = (
    Stdio_MCP_ClientToolsetConfig | HTTP_MCP_ClientToolsetConfig
)

MCP_ClientToolsetConfigMap = dict[str, MCP_ClientToolsetConfig]


@dataclasses.dataclass(kw_only=True)
class NoArgsMCPWrapper:
    func: abc.Callable[..., typing.Any]
    tool_config: ToolConfig

    def __call__(self):
        return self.func(tool_config=self.tool_config)


@dataclasses.dataclass(kw_only=True)
class WithQueryMCPWrapper:
    func: abc.Callable[..., typing.Any]
    tool_config: ToolConfig

    def __call__(self, query):
        return self.func(query, tool_config=self.tool_config)


MCP_TOOL_CONFIG_WRAPPERS_BY_TOOL_NAME = {}
