"""Soliplex authorization views"""

import fastapi

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["authorization"])

depend_the_installation = installation.depend_the_installation
depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


def get_the_authz_logger(
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> loggers.LogWrapper:
    return the_logger.bind(loggers.AUTHZ_LOGGER_NAME)


depend_the_authz_logger = fastapi.Depends(get_the_authz_logger)


@util.logfire_span("GET /v1/rooms/{room_id}/authz")
@router.get(
    "/v1/rooms/{room_id}/authz",
    summary="Get authorization policy for a room",
)
async def get_room_authz(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> models.RoomPolicy | None:
    the_authz_logger.debug(loggers.AUTHZ_GET_ROOM_POLICY)

    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_READ,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

    room_policy = await the_room_authz.get_room_policy(
        room_id=room_id,
    )

    return room_policy


@util.logfire_span("POST /v1/rooms/{room_id}/authz")
@router.post(
    "/v1/rooms/{room_id}/authz",
    summary="Update authorization policy for a room",
)
async def post_room_authz(
    room_id: str,
    room_policy: models.RoomPolicy,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> models.RoomPolicy | None:
    the_authz_logger.debug(loggers.AUTHZ_POST_ROOM_POLICY)

    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_UPDATE,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

    await the_room_authz.update_room_policy(
        room_id=room_id,
        room_policy=room_policy,
    )

    return fastapi.Response(status_code=204)


@util.logfire_span("DELETE /v1/rooms/{room_id}/authz")
@router.delete(
    "/v1/rooms/{room_id}/authz",
    summary="Delete authorization policy for a room",
)
async def delete_room_authz(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> models.RoomPolicy | None:
    the_authz_logger.debug(loggers.AUTHZ_DELETE_ROOM_POLICY)

    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_ROOM_POLICY,
        action=loggers.AUDIT_ACTION_DELETE,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

    await the_room_authz.delete_room_policy(
        room_id=room_id,
    )

    return fastapi.Response(status_code=204)


@util.logfire_span("GET /v1/installation/authz")
@router.get(
    "/v1/installation/authz",
    summary="Get authorization config for installation and its rooms",
)
async def get_installation_authz(
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_room_authz: authz.RoomAuthorizationPolicy = depend_the_room_authz,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> models.InstallationAuthorization:
    the_authz_logger.debug(loggers.AUTHZ_GET_INSTALLATION_AUTHZ)

    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_INSTALLATION_AUTHZ,
        action=loggers.AUDIT_ACTION_READ,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        ) from None

    discriminators = await the_admin_users.list_admin_user_discriminators()

    room_policies = {
        room_id: await the_room_authz.get_room_policy(
            room_id=room_id,
        )
        for room_id in await the_installation.get_room_configs(
            user=the_user_claims,
            the_room_authz=the_room_authz,
            the_logger=the_authz_logger,
        )
    }

    return models.InstallationAuthorization(
        admin_user_discriminators=discriminators,
        room_policies={
            room_id: room_policy if room_policy is not None else None
            for room_id, room_policy in room_policies.items()
        },
    )
