import contextlib
import dataclasses
import pathlib

import fastapi
import pydantic_ai
from ag_ui import core as agui_core
from haiku.rag import config as hr_config
from haiku.rag.graph import agui as hr_agui
from sqlalchemy.ext import asyncio as sqla_asyncio

from soliplex import agents
from soliplex import config
from soliplex import mcp_server
from soliplex import secrets
from soliplex.agui import persistence as agui_persistence


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
    def thread_persistence_dburi_sync(self) -> str:
        return self._config.thread_persistence_dburi_sync

    @property
    def thread_persistence_dburi_async(self) -> str:
        return self._config.thread_persistence_dburi_async

    @property
    def auth_disabled(self):
        return len(self._config.oidc_auth_system_configs) == 0

    @property
    def oidc_auth_system_configs(self) -> list[config.OIDCAuthSystemConfig]:
        return self._config.oidc_auth_system_configs

    def get_room_configs(
        self,
        user: dict,
    ) -> dict[str, config.RoomConfig]:
        return self._config.room_configs

    def get_room_config(
        self,
        room_id,
        user: dict,
    ) -> config.RoomConfig:
        return self._config.room_configs[room_id]

    def get_completion_configs(
        self,
        user: dict,
    ) -> dict[str, config.CompletionConfig]:
        return self._config.completion_configs

    def get_completion_config(
        self,
        completion_id,
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

    def get_agent_for_room(
        self,
        room_id: str,
        user: dict,
    ) -> pydantic_ai.Agent:
        room_config = self.get_room_config(room_id, user)
        return agents.get_agent_from_configs(
            room_config.agent_config,
            room_config.tool_configs,
            room_config.mcp_client_toolset_configs,
        )

    def get_agent_for_completion(
        self,
        completion_id: str,
        user: dict,
    ) -> pydantic_ai.Agent:
        completion_config = self.get_completion_config(completion_id, user)
        return agents.get_agent_from_configs(
            completion_config.agent_config,
            completion_config.tool_configs,
            completion_config.mcp_client_toolset_configs,
        )

    def get_agent_deps_for_room(
        self,
        room_id: str,
        user: dict,
        run_agent_input: agui_core.RunAgentInput = None,
    ) -> pydantic_ai.Agent:
        room_config = self.get_room_config(room_id, user)

        kwargs = {}

        if run_agent_input is not None:
            kwargs["agui_emitter"] = hr_agui.AGUIEmitter(
                thread_id=run_agent_input.thread_id,
                run_id=run_agent_input.run_id,
                use_deltas=True,
            )

        return agents.AgentDependencies(
            the_installation=self,
            user=user,
            tool_configs=room_config.tool_configs,
            **kwargs,
        )

    def get_agent_deps_for_completion(
        self,
        completion_id: str,
        user: dict,
        run_agent_input: agui_core.RunAgentInput = None,
    ) -> pydantic_ai.Agent:
        completion_config = self.get_completion_config(completion_id, user)

        kwargs = {}

        if run_agent_input is not None:
            kwargs["agui_emitter"] = hr_agui.AGUIEmitter(
                thread_id=run_agent_input.thread_id,
                run_id=run_agent_input.run_id,
                use_deltas=False,
            )

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

    engine = sqla_asyncio.create_async_engine(
        the_installation.thread_persistence_dburi_async
    )
    async with engine.begin() as connection:
        await connection.run_sync(agui_persistence.Base.metadata.create_all)

    context = {
        "the_installation": the_installation,
        "threads_engine": engine,
    }

    async with contextlib.AsyncExitStack() as stack:
        mcp_apps = mcp_server.setup_mcp_for_rooms(the_installation)

        for mcp_name, mcp_app in mcp_apps.items():
            mcp_lifespan = mcp_app.lifespan(app)
            await stack.enter_async_context(mcp_lifespan)
            app.mount(f"/mcp/{mcp_name}", mcp_app, name=f"mcp_{mcp_name}")

        yield context

    await engine.dispose()
