import contextlib
import dataclasses
import pathlib
from logging import config as logging_config

import fastapi
import logfire
import pydantic_ai
from ag_ui import core as agui_core
from haiku.rag import config as hr_config
from sqlalchemy import sql as sqla_sql
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import authz as authz_package
from soliplex import loggers
from soliplex import mcp_server
from soliplex import secrets
from soliplex import util
from soliplex.agui import schema as agui_schema
from soliplex.authz import schema as authz_schema
from soliplex.config import agents as config_agents
from soliplex.config import authsystem as config_authsystem
from soliplex.config import completions as config_completions
from soliplex.config import installation as config_installation
from soliplex.config import logfire as config_logfire
from soliplex.config import rooms as config_rooms

ProviderURL = str | None
ProviderModelNames = set[str]
ProviderTypeInfo = dict[ProviderURL, ProviderModelNames]
ProviderInfoMap = dict[config_agents.LLMProviderType, ProviderTypeInfo]


NO_AUTH_MODE_USER_TOKEN = {
    "name": "Phreddy Phlyntstone",
    "email": "phreddy@example.com",
}


@dataclasses.dataclass
class Installation:
    _config: config_installation.InstallationConfig

    def get_secret(self, secret_name) -> str:
        secret_config = self._config.secrets_map[secret_name]
        return secrets.get_secret(secret_config)

    def resolve_secrets(self):
        secrets.resolve_secrets(self._config.secrets)

    def get_environment_sources(
        self, key
    ) -> list[config_installation.EnvironmentSource]:
        return self._config.get_environment_sources(key)

    def get_environment(self, key, default=None) -> str:
        return self._config.get_environment(key, default)

    def resolve_environment(self):
        self._config.resolve_environment()

    def resolve_app_routers(self):
        self._config.resolve_app_routers()

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        return self._config.haiku_rag_config

    @property
    def all_agent_configs(self) -> config_agents.AgentConfigMap:
        """Return a mapping by ID of all defined agent configs"""
        found: config_agents.AgentConfigMap = {}

        for ac in self._config.agent_configs:
            found[ac.id] = ac

        for rc in self._config.room_configs.values():
            found[rc.agent_config.id] = rc.agent_config
            # Models from quiz judge agents
            for quiz in rc.quizzes:
                if quiz.judge_agent:
                    found[quiz.judge_agent.id] = quiz.judge_agent

        for cc in self._config.completion_configs.values():
            found[cc.agent_config.id] = cc.agent_config

        return found

    @property
    def agent_provider_info(self) -> ProviderInfoMap:
        """Return a set of unique provider info across all agent configs"""
        found: ProviderInfoMap = {}

        for agent_config in self.all_agent_configs.values():
            provider_type = getattr(agent_config, "provider_type", None)

            if provider_type is not None:
                type_info = found.setdefault(provider_type, {})
                base_url = agent_config.llm_provider_base_url
                url_models = type_info.setdefault(base_url, set())
                url_models.add(agent_config.model_name)

        return found

    @property
    def haiku_rag_provider_info(self) -> ProviderInfoMap:
        hr = self.haiku_rag_config
        found: ProviderInfoMap = {}

        for section in (hr.embeddings, hr.qa, hr.reranking, hr.research):
            if section and section.model:
                provider_type = section.model.provider
                type_info = found.setdefault(provider_type, {})
                base_url = section.model.base_url
                url_models = type_info.setdefault(base_url, set())
                url_models.add(section.model.name)

        return found

    @property
    def all_provider_info(self) -> ProviderInfoMap:
        found = self.agent_provider_info

        for provider_type, hr_info in self.haiku_rag_provider_info.items():
            ac_info = found.setdefault(provider_type, {})

            for hr_url, hr_models in hr_info.items():
                ac_models = ac_info.get(hr_url, set())
                ac_info[hr_url] = ac_models | hr_models

        ollama_url_info = found.get(config_agents.LLMProviderType.OLLAMA)

        if ollama_url_info is not None:
            no_url_models = ollama_url_info.pop(None, set())
            base_url = self.get_environment("OLLAMA_BASE_URL")
            base_url_models = ollama_url_info.get(base_url, set())
            ollama_url_info[base_url] = base_url_models | no_url_models

        return found

    @property
    def logfire_config(self) -> config_logfire.LogfireConfig | None:
        return self._config.logfire_config

    @property
    def thread_persistence_dburi_sync(self) -> str:
        return self._config.thread_persistence_dburi_sync

    @property
    def thread_persistence_dburi_async(self) -> str:
        return self._config.thread_persistence_dburi_async

    @property
    def authorization_dburi_sync(self) -> str:
        return self._config.authorization_dburi_sync

    @property
    def authorization_dburi_async(self) -> str:
        return self._config.authorization_dburi_async

    @property
    def auth_disabled(self):
        return len(self._config.oidc_auth_system_configs) == 0

    @property
    def oidc_auth_system_configs(
        self,
    ) -> list[config_authsystem.OIDCAuthSystemConfig]:
        return self._config.oidc_auth_system_configs

    async def get_room_configs(
        self,
        *,
        user: dict,
        the_authz_policy: authz_package.AuthorizationPolicy = None,
        the_logger: loggers.LogWrapper = None,
    ) -> config_rooms.RoomConfigMap:
        """Return room configs available to the user"""
        if the_logger is None:
            logger = loggers.LogWrapper(
                loggers.AUTHZ_LOGGER_NAME,
                the_installation=self,
                user=user,
            )
        else:
            logger = the_logger.bind(loggers.AUTHZ_LOGGER_NAME, user=user)

        configs = self._config.room_configs

        if the_authz_policy is not None:
            logger.debug(loggers.AUTHZ_FILTERING_ROOMS)
            allowed = await the_authz_policy.filter_room_ids(
                configs.keys(),
                user_token=user,
            )

            configs = {
                room_id: room_config
                for room_id, room_config in configs.items()
                if room_id in allowed
            }
        else:
            logger.debug(loggers.AUTHZ_NOT_FILTERING_ROOMS)

        return configs

    async def get_room_config(
        self,
        *,
        room_id: str,
        user: dict,
        the_authz_policy: authz_package.AuthorizationPolicy = None,
        the_logger: loggers.LogWrapper = None,
    ) -> config_rooms.RoomConfig:
        """Return a room configs IFF available to the user"""
        if the_logger is None:
            logger = loggers.LogWrapper(
                loggers.AUTHZ_LOGGER_NAME,
                the_installation=self,
                user=user,
            )
        else:
            logger = the_logger.bind(loggers.AUTHZ_LOGGER_NAME, user=user)

        if the_authz_policy is not None:
            if not await the_authz_policy.check_room_access(
                room_id=room_id,
                user_token=user,
            ):
                logger.error(loggers.AUTHZ_ROOM_NOT_AUTHORIZED)
                raise KeyError(room_id)

            logger.debug(loggers.AUTHZ_ROOM_AUTHORIZED)

        return self._config.room_configs[room_id]

    async def get_completion_configs(
        self,
        *,
        user: dict,
    ) -> dict[str, config_completions.CompletionConfig]:
        return self._config.completion_configs

    async def get_completion_config(
        self,
        *,
        completion_id: str,
        user: dict,
    ) -> config_completions.CompletionConfig:
        return self._config.completion_configs[completion_id]

    def get_agent_by_id(
        self,
        agent_id: str,
    ) -> pydantic_ai.Agent:
        return agents.get_agent_from_configs(
            agent_config=self._config.agent_configs_map[agent_id],
            tool_configs={},
            mcp_client_toolset_configs={},
        )

    async def get_agent_for_room(
        self,
        *,
        room_id: str,
        user: dict,
        the_authz_policy: authz_package.AuthorizationPolicy = None,
        the_logger: loggers.LogWrapper = None,
    ) -> pydantic_ai.Agent:
        room_config = await self.get_room_config(
            room_id=room_id,
            user=user,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
        mcpcts_configs = room_config.mcp_client_toolset_configs

        return agents.get_agent_from_configs(
            agent_config=room_config.agent_config,
            tool_configs=room_config.tool_configs,
            mcp_client_toolset_configs=mcpcts_configs,
            skill_toolset_config=room_config.skills,
        )

    async def get_agent_for_completion(
        self,
        *,
        completion_id: str,
        user: dict,
    ) -> pydantic_ai.Agent:
        completion_config = await self.get_completion_config(
            completion_id=completion_id,
            user=user,
        )
        mcpcts_configs = completion_config.mcp_client_toolset_configs

        return agents.get_agent_from_configs(
            agent_config=completion_config.agent_config,
            tool_configs=completion_config.tool_configs,
            mcp_client_toolset_configs=mcpcts_configs,
        )

    async def get_agent_deps_for_room(
        self,
        *,
        room_id: str,
        user: dict,
        the_authz_policy: authz_package.AuthorizationPolicy = None,
        run_agent_input: agui_core.RunAgentInput = None,
        the_logger: loggers.LogWrapper = None,
    ) -> pydantic_ai.Agent:
        room_config = await self.get_room_config(
            room_id=room_id,
            user=user,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )

        kwargs = {}

        thread_id = None
        if run_agent_input is not None:
            thread_id = run_agent_input.thread_id

        return agents.AgentDependencies(
            the_installation=self,
            user=user,
            tool_configs=room_config.tool_configs,
            thread_id=thread_id,
            **kwargs,
        )

    async def get_agent_deps_for_completion(
        self,
        *,
        completion_id: str,
        user: dict,
        run_agent_input: agui_core.RunAgentInput = None,
    ) -> pydantic_ai.Agent:
        completion_config = await self.get_completion_config(
            completion_id=completion_id,
            user=user,
        )

        kwargs = {}

        return agents.AgentDependencies(
            the_installation=self,
            user=user,
            tool_configs=completion_config.tool_configs,
            **kwargs,
        )


async def get_the_installation(
    request: fastapi.Request,
) -> config_installation.InstallationConfig:
    return request.state.the_installation


depend_the_installation = fastapi.Depends(get_the_installation)


def apply_logfire_configuration(
    app: fastapi.FastAPI,
    the_installation: Installation,
    disable_logfire_console=False,
):
    logfire_config = the_installation.logfire_config

    if logfire_config is not None:
        # Disable Logfire's console output if we are sending data to Logfire
        logfire_kw = logfire_config.logfire_config_kwargs | {
            "console": False,
        }
        logfire.configure(**logfire_kw)

        ipydai = logfire_config.instrument_pydantic_ai

        if ipydai is not None:
            logfire.instrument_pydantic_ai(
                **ipydai.instrument_pydantic_ai_kwargs,
            )
        else:
            logfire.instrument_pydantic_ai()

        ifapi = logfire_config.instrument_fast_api

        if ifapi is not None:
            logfire.instrument_fastapi(
                app,
                **ifapi.instrument_fast_api_kwargs,
            )
        else:
            logfire.instrument_fastapi(app, capture_headers=True)
    else:
        # 'if-token-present' means nothing will be sent (and the example
        # will work) if you don't have logfire configured
        logfire_kw = {
            "send_to_logfire": "if-token-present",
        }

        if disable_logfire_console:
            logfire_kw["console"] = False

        logfire.configure(**logfire_kw)
        logfire.instrument_pydantic_ai()
        logfire.instrument_fastapi(app, capture_headers=True)


def add_user_as_admin(connection, *, email):
    insert_stmt = sqla_sql.insert(authz_schema.AdminUser).values(
        email=email,
    )
    connection.execute(insert_stmt)


def add_no_auth_user_as_admin(connection):
    query = sqla_sql.select(authz_schema.AdminUser)
    result = connection.execute(query)
    has_admin_users = result.first() is not None

    if not has_admin_users:
        email = NO_AUTH_MODE_USER_TOKEN["email"]
        add_user_as_admin(connection, email=email)


async def lifespan(
    app: fastapi.FastAPI,
    *,
    installation_path: pathlib.Path,
    no_auth_mode: bool = False,
    log_config_file: str = None,
    add_admin_user: str = None,
):
    i_config = config_installation.load_installation(installation_path)

    if no_auth_mode:
        del i_config.oidc_paths[:]

    i_config.reload_configurations()
    the_installation = Installation(i_config)
    the_installation.resolve_secrets()
    the_installation.resolve_environment()
    the_installation.resolve_app_routers()

    if log_config_file is not None:
        log_config_file = pathlib.Path(log_config_file)
        logging_config_dict = config_installation._load_config_yaml(
            log_config_file
        )
    else:
        logging_config_dict = i_config.logging_config

    if logging_config_dict is not None:
        logging_config.dictConfig(logging_config_dict)
        disable_logfire_console = True
    else:
        disable_logfire_console = False

    apply_logfire_configuration(app, the_installation, disable_logfire_console)

    agui_engine = sqla_asyncio.create_async_engine(
        the_installation.thread_persistence_dburi_async,
        json_serializer=util.serialize_sqla_json,
        pool_pre_ping=True,
    )
    async with agui_engine.begin() as agui_connection:
        await agui_connection.run_sync(
            agui_schema.Base.metadata.create_all,
        )

    authz_engine = sqla_asyncio.create_async_engine(
        the_installation.authorization_dburi_async,
        json_serializer=util.serialize_sqla_json,
        pool_pre_ping=True,
    )
    async with authz_engine.begin() as ra_connection:
        await ra_connection.run_sync(
            authz_schema.Base.metadata.create_all,
        )
        if add_admin_user:
            await ra_connection.run_sync(
                add_user_as_admin,
                email=add_admin_user,
            )
        elif no_auth_mode:
            await ra_connection.run_sync(
                add_no_auth_user_as_admin,
            )

    context = {
        "the_installation": the_installation,
        "threads_engine": agui_engine,
        "authorization_engine": authz_engine,
    }

    async with contextlib.AsyncExitStack() as stack:
        mcp_apps = mcp_server.setup_mcp_for_rooms(the_installation)

        for mcp_name, mcp_app in mcp_apps.items():
            mcp_lifespan = mcp_app.lifespan(app)
            await stack.enter_async_context(mcp_lifespan)
            app.mount(f"/mcp/{mcp_name}", mcp_app, name=f"mcp_{mcp_name}")

        yield context

    await agui_engine.dispose()
    await authz_engine.dispose()
