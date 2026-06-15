import fastapi

from soliplex import agui as agui_package
from soliplex import authn
from soliplex import authz as authz_package
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["stats"])

depend_the_installation = installation.depend_the_installation
depend_the_authz = authz_package.depend_the_authz_policy
depend_the_threads = agui_package.depend_the_threads
depend_the_user_claims = views.depend_the_user_claims
depend_the_logger = views.depend_the_logger


@util.logfire_span("GET /v1/stats/rooms")
@router.get("/v1/stats/rooms")
async def get_rooms_stats(
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> dict[str, models.RoomStats]:
    """Return last-activity stats for each room the user can access.

    One entry per room the authorization policy currently grants the
    user ('get_room_configs'); last_activity is null for a room they
    have no runs in. A room they were de-authorized from drops out.
    """
    the_logger.debug(loggers.STATS_GET_ROOMS_STATS)

    user_name = the_user_claims.get("preferred_username", "<unknown>")

    room_configs = await the_installation.get_room_configs(
        user=the_user_claims,
        the_authz_policy=the_authz_policy,
        the_logger=the_logger,
    )

    activity_by_room = await the_threads.get_rooms_last_activity(
        user_name=user_name,
    )

    return {
        room_id: models.RoomStats(
            room_id=room_id,
            last_activity=activity_by_room.get(room_id),
        )
        for room_id in room_configs
    }


@util.logfire_span("GET /v1/stats/rooms/{room_id}")
@router.get("/v1/stats/rooms/{room_id}")
async def get_room_stats(
    room_id: str,
    the_installation: installation.Installation = depend_the_installation,
    the_authz_policy: authz_package.AuthorizationPolicy = depend_the_authz,
    the_threads: agui_package.ThreadStorage = depend_the_threads,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.RoomStats:
    """Return last-activity stats for a single room.

    The room-access check rejects unknown or inaccessible rooms with a
    404; last_activity is null when the user has no runs there.
    """
    the_logger.debug(loggers.STATS_GET_ROOM_STATS)

    try:
        await the_installation.get_room_config(
            room_id=room_id,
            user=the_user_claims,
            the_authz_policy=the_authz_policy,
            the_logger=the_logger,
        )
    except KeyError:
        # An authz denial is logged by 'get_room_config'; a genuinely
        # missing room is not, so log the lookup failure here either way.
        the_logger.exception(loggers.ROOM_UNKNOWN_ROOM_ID, room_id)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.ROOM_UNKNOWN_ROOM_ID % room_id,
        ) from None

    user_name = the_user_claims.get("preferred_username", "<unknown>")

    last_activity = await the_threads.get_room_last_activity(
        user_name=user_name,
        room_id=room_id,
    )

    return models.RoomStats(room_id=room_id, last_activity=last_activity)
