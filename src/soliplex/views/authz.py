"""Soliplex authentication views"""

import fastapi

from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["authorization"])

depend_the_installation = installation.depend_the_installation
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_user_claims = views.depend_the_user_claims


@util.logfire_span("GET /v1/rooms/{room_id}/authz")
@router.get(
    "/v1/rooms/{room_id}/authz",
    summary="Get authorization policy for a room",
)
async def get_room_authz(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.RoomPolicy | None:
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    try:
        room_policy = await the_authz_policy.get_room_policy(
            room_id=room_id,
            user_token=the_user_claims,
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
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.RoomPolicy | None:
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    await the_authz_policy.update_room_policy(
        room_id=room_id,
        room_policy=room_policy,
        user_token=the_user_claims,
    )

    return fastapi.Response(status_code=204)


@util.logfire_span("DELETE /v1/rooms/{room_id}/authz")
@router.delete(
    "/v1/rooms/{room_id}/authz",
    summary="Delete authorization policy for a room",
)
async def delete_room_authz(
    request: fastapi.Request,
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.RoomPolicy | None:
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    await the_authz_policy.delete_room_policy(
        room_id=room_id,
        user_token=the_user_claims,
    )

    return fastapi.Response(status_code=204)


@util.logfire_span("GET /v1/installation/authz")
@router.get(
    "/v1/installation/authz",
    summary="Get authorization config for installation and its rooms",
)
async def get_installation_authz(
    request: fastapi.Request,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
) -> models.InstallationAuthorization:
    if not await the_authz_policy.check_admin_access(the_user_claims):
        raise fastapi.HTTPException(
            status_code=403,
            detail="Admin access required",
        ) from None

    admin_user_emails = await the_authz_policy.list_admin_users()

    room_policies = {
        room_id: await the_authz_policy.get_room_policy(
            room_id=room_id,
            user_token=the_user_claims,
        )
        for room_id in await the_installation.get_room_configs(
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
        )
    }

    return models.InstallationAuthorization(
        admin_user_emails=admin_user_emails,
        room_policies={
            room_id: room_policy if room_policy is not None else None
            for room_id, room_policy in room_policies.items()
        },
    )
