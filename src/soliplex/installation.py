import contextlib
import dataclasses
import os
import pathlib

import fastapi
import pydantic_ai
from ag_ui import core as agui_core
from haiku.rag import config as hr_config
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import authz as authz_package
from soliplex import config
from soliplex import mcp_server
from soliplex import secrets
from soliplex.agui import persistence as agui_persistence
from soliplex.authz import schema as authz_schema

ProviderURL = str | None
ProviderModelNames = set[str]
ProviderTypeInfo = dict[ProviderURL, ProviderModelNames]
ProviderInfoMap = dict[config.LLMProviderType, ProviderTypeInfo]


@dataclasses.dataclass
class Installation:
    _config: config.InstallationConfig

    def get_secret(self, secret_name) -> str:
        secret_config = self._config.secrets_map[secret_name]
        return secrets.get_secret(secret_config)

    def resolve_secrets(self):
        secrets.resolve_secrets(self._config.secrets)

    def get_environment(self, key, default=None) -> str:
        return self._config.get_environment(key, default)

    def resolve_environment(self):
        self._config.resolve_environment()

    @property
    def haiku_rag_config(self) -> hr_config.AppConfig:
        return self._config.haiku_rag_config

    @property
    def all_agent_configs(self) -> config.AgentConfigMap:
        """Return a mapping by ID of all defined agent configs"""
        found: config.AgentConfigMap = {}

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

        ollama_url_info = found.get(config.LLMProviderType.OLLAMA)

        if ollama_url_info is not None:
            no_url_models = ollama_url_info.pop(None, set())
            base_url = self.get_environment("OLLAMA_BASE_URL")
            base_url_models = ollama_url_info.get(base_url, set())
            ollama_url_info[base_url] = base_url_models | no_url_models

        return found

    def get_all_models(self) -> set[str]:
        models = set()

        for _ac_id, ac in self.all_agent_configs.items():
            if model_name := getattr(ac, "model_name", None):
                models.add(model_name)

        # Models from haiku.rag config
        hr = self.haiku_rag_config
        for section in (hr.embeddings, hr.qa, hr.reranking, hr.research):
            if not section or not section.model:
                continue
            models.add(section.model.name)

        # Models from environment variables (both config and OS)
        model_env_vars = (
            "DEFAULT_AGENT_MODEL",
            "EMBEDDINGS_MODEL",
            "QA_MODEL",
        )
        for env_var in model_env_vars:
            if model_name := self.get_environment(env_var):
                models.add(model_name)
            if model_name := os.environ.get(env_var):
                models.add(model_name)

        return models

    @property
    def thread_persistence_dburi_sync(self) -> str:
        return self._config.thread_persistence_dburi_sync

    @property
    def thread_persistence_dburi_async(self) -> str:
        return self._config.thread_persistence_dburi_async

    @property
    def room_authz_dburi_sync(self) -> str:
        return self._config.room_authz_dburi_sync

    @property
    def room_authz_dburi_async(self) -> str:
        return self._config.room_authz_dburi_async

    @property
    def auth_disabled(self):
        return len(self._config.oidc_auth_system_configs) == 0

    @property
    def oidc_auth_system_configs(self) -> list[config.OIDCAuthSystemConfig]:
        return self._config.oidc_auth_system_configs

    async def get_room_configs(
        self,
        *,
        user: dict,
        the_room_authz: authz_package.RoomAuthorization = None,
    ) -> dict[str, config.RoomConfig]:
        """Return room configs available to the user"""
        configs = self._config.room_configs

        if the_room_authz is not None:
            allowed = await the_room_authz.filter_room_ids(
                configs.keys(),
                user_token=user,
            )
            configs = {
                room_id: room_config
                for room_id, room_config in configs.items()
                if room_id in allowed
            }

        return configs

    async def get_room_config(
        self,
        *,
        room_id: str,
        user: dict,
        the_room_authz: authz_package.RoomAuthorization = None,
    ) -> config.RoomConfig:
        """Return a room configs IFF available to the user"""
        if the_room_authz is not None:
            if not await the_room_authz.check_room_access(
                room_id=room_id,
                user_token=user,
            ):
                raise KeyError(room_id)

        return self._config.room_configs[room_id]

    async def get_completion_configs(
        self,
        *,
        user: dict,
    ) -> dict[str, config.CompletionConfig]:
        return self._config.completion_configs

    async def get_completion_config(
        self,
        *,
        completion_id: str,
        user: dict,
    ) -> config.CompletionConfig:
        return self._config.completion_configs[completion_id]

    def get_agent_by_id(
        self,
        agent_id: str,
    ) -> pydantic_ai.Agent:
        return agents.get_agent_from_configs(
            self._config.agent_configs_map[agent_id],
            {},
            {},
        )

    async def get_agent_for_room(
        self,
        *,
        room_id: str,
        user: dict,
        the_room_authz: authz_package.RoomAuthorization = None,
    ) -> pydantic_ai.Agent:
        room_config = await self.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )

        return agents.get_agent_from_configs(
            room_config.agent_config,
            room_config.tool_configs,
            room_config.mcp_client_toolset_configs,
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
        return agents.get_agent_from_configs(
            completion_config.agent_config,
            completion_config.tool_configs,
            completion_config.mcp_client_toolset_configs,
        )

    async def get_agent_deps_for_room(
        self,
        *,
        room_id: str,
        user: dict,
        the_room_authz: authz_package.RoomAuthorization = None,
        run_agent_input: agui_core.RunAgentInput = None,
    ) -> pydantic_ai.Agent:
        room_config = await self.get_room_config(
            room_id=room_id,
            user=user,
            the_room_authz=the_room_authz,
        )

        kwargs = {}

        return agents.AgentDependencies(
            the_installation=self,
            user=user,
            tool_configs=room_config.tool_configs,
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
) -> config.InstallationConfig:
    return request.state.the_installation


depend_the_installation = fastapi.Depends(get_the_installation)


async def lifespan(
    app: fastapi.FastAPI,
    installation_path: pathlib.Path,
    no_auth_mode: bool = False,
):
    i_config = config.load_installation(installation_path)

    if no_auth_mode:
        del i_config.oidc_paths[:]

    i_config.reload_configurations()
    the_installation = Installation(i_config)
    the_installation.resolve_secrets()
    the_installation.resolve_environment()

    tp_engine = sqla_asyncio.create_async_engine(
        the_installation.thread_persistence_dburi_async
    )
    async with tp_engine.begin() as tp_connection:
        await tp_connection.run_sync(
            agui_persistence.Base.metadata.create_all,
        )

    ra_engine = sqla_asyncio.create_async_engine(
        the_installation.thread_persistence_dburi_async
    )
    async with ra_engine.begin() as ra_connection:
        await ra_connection.run_sync(
            authz_schema.Base.metadata.create_all,
        )

    context = {
        "the_installation": the_installation,
        "threads_engine": tp_engine,
        "room_authz_engine": ra_engine,
    }

    async with contextlib.AsyncExitStack() as stack:
        mcp_apps = mcp_server.setup_mcp_for_rooms(the_installation)

        for mcp_name, mcp_app in mcp_apps.items():
            mcp_lifespan = mcp_app.lifespan(app)
            await stack.enter_async_context(mcp_lifespan)
            app.mount(f"/mcp/{mcp_name}", mcp_app, name=f"mcp_{mcp_name}")

        yield context

    await tp_engine.dispose()
    await ra_engine.dispose()
