import dataclasses

import fastapi

from soliplex import config


@dataclasses.dataclass
class Installation:
    _config: config.InstallationConfig

    @property
    def oidc_auth_system_configs(self) -> list[config.OIDCAuthSystemConfig]:
        return self._config.oidc_auth_system_configs

    def get_room_configs(self, _user) -> dict[str, config.RoomConfig]:
        return self._config.room_configs

    def get_completion_configs(
        self, _user
    ) -> dict[str, config.CompletionConfig]:
        return self._config.completion_configs


async def get_the_installation(
    request: fastapi.Request,
) -> config.InstallationConfig:
    return request.state.the_installation

depend_the_installation = fastapi.Depends(get_the_installation)


async def lifespan(app: fastapi.FastAPI, installation_path):
    i_config = config.load_installation(installation_path)
    i_config.reload_configurations()
    the_installation = Installation(i_config)

    context = {
        "the_installation": the_installation,
    }

    yield context
