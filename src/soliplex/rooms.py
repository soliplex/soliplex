
import fastapi
from fastapi import responses
from fastapi import security

from . import auth
from . import installation
from . import models
from . import util

router = fastapi.APIRouter()


@util.logfire_span("GET /v1/rooms")
@router.get("/v1/rooms")
async def get_rooms(
    request: fastapi.Request,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
) -> models.ConfiguredRooms:
    user = auth.authenticate(the_installation, token)
    room_configs = the_installation.get_room_configs(user)

    def _key(item):
        key, value = item
        return value.sort_key

    rc_items = sorted(room_configs.items(), key=_key)

    return {
        room_id: models.Room.from_config(room)
        for room_id, room in rc_items
    }


@util.logfire_span("GET /v1/rooms/{room_id}")
@router.get("/v1/rooms/{room_id}")
async def get_room(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
) -> models.Room:
    user = auth.authenticate(the_installation, token)
    room_configs = the_installation.get_room_configs(user)

    try:
        room_config = room_configs[room_id]
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {room_id}",
        ) from None

    return models.Room.from_config(room_config)


@util.logfire_span("GET /v1/rooms/{room_id}/bg_image")
@router.get(
    "/v1/rooms/{room_id}/bg_image",
    response_class=responses.FileResponse,
)
async def get_room_bg_image(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation =
        installation.depend_the_installation,
    token: security.HTTPAuthorizationCredentials =
        auth.oauth2_predicate,
):
    user = auth.authenticate(the_installation, token)
    room_configs = the_installation.get_room_configs(user)

    try:
        room_config = room_configs[room_id]
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404, detail=f"No such room: {room_id}",
        ) from None

    logo_image = room_config.get_logo_image()

    if logo_image is None:
        raise fastapi.HTTPException(
            status_code=404, detail="No image for room",
        )

    return str(logo_image)
