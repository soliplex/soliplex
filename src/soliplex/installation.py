import dataclasses

import fastapi
import pydantic_ai

from soliplex import agents
from soliplex import config
from soliplex import convos


@dataclasses.dataclass
class Installation:
    _config: config.InstallationConfig

    @property
    def oidc_auth_system_configs(self) -> list[config.OIDCAuthSystemConfig]:
        return self._config.oidc_auth_system_configs

    def get_room_configs(
        self, user: dict,
    ) -> dict[str, config.RoomConfig]:
        return self._config.room_configs

    def get_room_config(
        self, room_id, user: dict,
    ) -> config.RoomConfig:
        return self._config.room_configs[room_id]

    def get_completion_configs(
        self, user: dict,
    ) -> dict[str, config.CompletionConfig]:
        return self._config.completion_configs

    def get_completion_config(
        self, completion_id, user: dict,
    ) -> config.CompletionConfig:
        return self._config.completion_configs[completion_id]

    def get_agent_for_room(
        self, room_id: str, user: dict,
    ) -> pydantic_ai.Agent:
        room_config = self.get_room_config(room_id, user)
        return agents.get_agent_from_configs(
            room_config.agent_config,
            room_config.tool_configs,
            room_config.mcp_client_toolset_configs,
        )


async def get_the_installation(
    request: fastapi.Request,
) -> config.InstallationConfig:
    return request.state.the_installation

depend_the_installation = fastapi.Depends(get_the_installation)


async def lifespan(app: fastapi.FastAPI, installation_path):
    i_config = config.load_installation(installation_path)
    i_config.reload_configurations()
    the_installation = Installation(i_config)
    the_convos = convos.Conversations()

    context = {
        "the_installation": the_installation,
        "the_convos": the_convos,
    }

    yield context
