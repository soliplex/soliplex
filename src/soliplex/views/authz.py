"""Soliplex authentication views"""

import fastapi
from fastapi import security

from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter(tags=["authorization"])

depend_the_installation = installation.depend_the_installation
depend_the_room_authz = authz_package.depend_the_room_authz


@util.logfire_span("GET /v1/rooms/{room_id}/authz")
@router.get(
    "/v1/rooms/{room_id}/authz",
    summary="Get authorization policy for a room",
)
async def get_room_authz(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.RoomPolicy | None:
    user = authn.authenticate(the_installation, token)

    try:
        room_policy = await the_room_authz.get_room_policy(
            room_id=room_id,
            user_token=user,
        )
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"No such room: {room_id}",
        ) from None

    return room_policy


@util.logfire_span("POST /v1/rooms/{room_id}/authz")
@router.post(
    "/v1/rooms/{room_id}/authz",
    summary="Update authorization policy for a room",
)
async def post_room_authz(
    request: fastapi.Request,
    room_id: str,
    room_policy: models.RoomPolicy,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.RoomPolicy | None:
    user = authn.authenticate(the_installation, token)

    await the_room_authz.update_room_policy(
        room_id=room_id,
        room_policy=room_policy,
        user_token=user,
    )

    return fastapi.Response(status_code=204)


@util.logfire_span("DELTE /v1/rooms/{room_id}/authz")
@router.delete(
    "/v1/rooms/{room_id}/authz",
    summary="Delete authorization policy for a room",
)
async def delete_room_authz(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_room_authz: authz_package.RoomAuthorization = depend_the_room_authz,
    token: security.HTTPAuthorizationCredentials = authn.oauth2_predicate,
) -> models.RoomPolicy | None:
    user = authn.authenticate(the_installation, token)

    await the_room_authz.delete_room_policy(
        room_id=room_id,
        user_token=user,
    )

    return fastapi.Response(status_code=204)
