"""Soliplex authorization views"""

import typing

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
depend_the_cookie_admin_users = views.depend_the_authn_cookie_admin_user_policy
depend_the_room_authz = views.depend_the_room_authz_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_authn_cookie_claims = views.depend_the_authn_cookie_claims
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


@util.logfire_span("GET /v1/user/authz")
@router.get(
    "/v1/user/authz",
    summary="Get authorization info for the user",
)
async def get_user_authz(
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_authz_logger: loggers.LogWrapper = depend_the_authz_logger,
) -> models.UserAuthorization:
    the_authz_logger.debug(loggers.AUTHZ_GET_USER_AUTHZ)

    is_admin_user = await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_USER_AUTHZ,
        action=loggers.AUDIT_ACTION_READ,
    )

    return models.UserAuthorization(is_admin_user=is_admin_user)


AUTHZ_CHECK_RESOURCE_PATTERN = r"^[A-Za-z0-9_.:-]+$"
AUTHZ_CHECK_USER_HEADER = "X-Soliplex-User"
AUTHZ_CHECK_USER_CLAIMS = ("preferred_username", "email", "sub")


def _soliplex_user_for_header(the_user_claims: authn.UserClaims) -> str | None:
    """Determine a value for the 'X-Soliplex-User' header

    Return the first of 'AUTHZ_CHECK_USER_CLAIMS' present in
    'the_user_claims' whose value is a wire-safe (printable ASCII)
    string;  if no claim is wire-safe, return 'None'.  A claim which a
    quirky IdP emitted as some non-string JSON value fails the gate and
    falls through, like any other non-safe value.
    """
    for claim in AUTHZ_CHECK_USER_CLAIMS:
        value = the_user_claims.get(claim)
        if isinstance(value, str) and value.isascii() and value.isprintable():
            return value

    return None


@util.logfire_span("GET /v1/authz/check/{resource}")
@router.get(
    "/v1/authz/check/{resource}",
    status_code=204,
    response_class=fastapi.Response,
    summary="Check admin access, as an nginx 'auth_request' target",
)
async def get_authz_check(
    resource: typing.Annotated[
        str,
        fastapi.Path(pattern=AUTHZ_CHECK_RESOURCE_PATTERN),
    ],
    the_admin_users: authz.AdminUserPolicy = depend_the_cookie_admin_users,
    the_user_claims: authn.UserClaims = depend_the_authn_cookie_claims,
) -> fastapi.Response:
    """Allow an admin user to reach 'resource' (a label for the audit log)

    The user is identified by the authn cookie set at login.

    On success, the 'X-Soliplex-User' header names the user (see
    '_soliplex_user_for_header').

    Raises:

    - 'fastapi.HTTPException' (401) as 'views.get_the_authn_cookie_claims'.
    - 'fastapi.HTTPException' (403) if the user is not an admin user.
    """
    if not await the_admin_users.check_admin_access(
        the_user_claims,
        resource=resource,
        action=loggers.AUDIT_ACTION_ACCESS,
    ):
        raise fastapi.HTTPException(
            status_code=403,
            detail=loggers.AUTHZ_ADMIN_ACCESS_REQUIRED,
        )

    headers = {}
    user = _soliplex_user_for_header(the_user_claims)
    if user is not None:
        headers[AUTHZ_CHECK_USER_HEADER] = user

    return fastapi.Response(status_code=204, headers=headers)
