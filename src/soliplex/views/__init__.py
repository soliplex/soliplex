from __future__ import annotations

import fastapi
from fastapi import responses
from fastapi import security

from soliplex import authn as authn_module
from soliplex import installation as installation_module
from soliplex import loggers
from soliplex import util

router = fastapi.APIRouter()

depend_the_installation = installation_module.depend_the_installation
Installation = installation_module.Installation
HTTPAuthorizationCredentials = security.HTTPAuthorizationCredentials


async def get_the_user_claims(
    the_installation: Installation = depend_the_installation,
    token: HTTPAuthorizationCredentials = authn_module.oauth2_predicate,
) -> authn_module.UserClaims:
    return authn_module.authenticate(
        the_installation=the_installation,
        token=token,
    )


depend_the_user_claims = fastapi.Depends(get_the_user_claims)


async def get_the_unauth_logger(
    request: fastapi.Request,
    the_installation: Installation = depend_the_installation,
) -> loggers.LogWrapper:
    return loggers.LogWrapper(
        loggers.AUTHN_LOGGER_NAME,
        headers=request.headers,
    )


depend_the_unauth_logger = fastapi.Depends(get_the_unauth_logger)


async def get_the_logger(
    request: fastapi.Request,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
    the_user_claims: authn_module.UserClaims = depend_the_user_claims,
) -> loggers.LogWrapper:
    extras = {
        "claims": the_user_claims,
    }

    room_id = request.path_params.get("room_id")

    if room_id is not None:
        extras["room_id"] = room_id

    return the_unauth_logger.bind(
        loggers.SOLIPLEX_LOGGER_NAME,
        **extras,
    )


depend_the_logger = fastapi.Depends(get_the_logger)


#   'process_control' canary
@util.logfire_span("GET /ok")
@router.get(
    "/ok", response_class=responses.PlainTextResponse, tags=["process"]
)
async def health_check() -> str:
    """Check that the server is up and running.

    Primarily for use within a process composer environment.
    """
    return "OK"


# testing and validation

CHECK_HEADERS_VALUE_TYPE = str | None | dict[str, str]


@util.logfire_span("GET /check-headers")
@router.get("/check-headers", tags=["debug"])
async def check_headers(
    request: fastapi.Request,
) -> dict[str, CHECK_HEADERS_VALUE_TYPE]:  # pragma: NO COVER
    """Dump request headers for debugging"""
    return_to = "https://google.com"
    redirect_uri = request.url_for("health_check")
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    # redirect_uri = redirect_uri.replace(netloc=redirect_uri.netloc + '/api')
    return {
        "X-Forwarded-For": request.headers.get("x-forwarded-for"),
        "X-Forwarded-Proto": request.headers.get("x-forwarded-proto"),
        "X-Forwarded-Host": request.headers.get("x-forwarded-host"),
        "X-Forwarded-Port": request.headers.get("x-forwarded-port"),
        "X-Real-IP": request.headers.get("x-real-ip"),
        "Host": request.headers.get("host"),
        "redirect_uri": str(redirect_uri),
        "headers": request.headers,
    }
