"""Soliplex authentication views"""

import dataclasses
from urllib import parse as urlparse

import fastapi
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import authn
from soliplex import authz
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views

router = fastapi.APIRouter(tags=["authentication"])

depend_the_installation = installation.depend_the_installation
depend_the_admin_users = views.depend_the_admin_user_policy
depend_the_user_claims = views.depend_the_user_claims
depend_the_unauth_logger = views.depend_the_unauth_logger
depend_the_logger = views.depend_the_logger


@router.get("/login", summary="Get available OIDC auth providers")
async def get_login(
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
) -> models.ConfiguredOIDCAuthSystems:
    """Describe configured OIDC Authentication providers"""
    # Remove `_installation_config` to avoid infinite recursion
    the_unauth_logger.debug(loggers.AUTHN_GET_LOGIN)
    auth_system_copies = [
        dataclasses.replace(auth_system, _installation_config=None)
        for auth_system in the_installation.oidc_auth_system_configs
    ]

    return {
        auth_system.id: models.OIDCAuthSystem.from_config(auth_system)
        for auth_system in auth_system_copies
    }


@util.logfire_span("GET /login/{system}")
@router.get(
    "/login/{system}",
    summary="Initiate OIDC token auth flow with a provider",
)
async def get_login_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
):
    """Initiate token auth flow with the specified OIDC auth provider"""
    bound_logger = the_unauth_logger.bind(oidc_system=system)

    if the_installation.auth_disabled:
        bound_logger.error(loggers.AUTHN_NO_AUTH_MODE)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.AUTHN_NO_AUTH_MODE,
        )

    return_to = request.query_params.get("return_to", "/")
    redirect_uri = request.url_for("get_auth_system", system=system)
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    redirect_uri = util.strip_default_port(redirect_uri)

    auth_params = {}
    prompt = request.query_params.get("prompt")
    if prompt is not None:
        auth_params["prompt"] = prompt

    oauth = authn.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    found = await oauth_app.authorize_redirect(
        request, redirect_uri, **auth_params
    )
    bound_logger.debug(loggers.AUTHN_GET_LOGIN_SYSTEM)
    return found


@util.logfire_span("GET /auth/{system}")
@router.get(
    "/auth/{system}",
    summary="Complete token auth flow with an auth provider",
)
async def get_auth_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
):
    """Complete the OIDC token auth flow with the specified provider

    On success, redirect to client-specified URL.
    """
    bound_logger = the_unauth_logger.bind(oidc_system=system)

    if the_installation.auth_disabled:
        bound_logger.error(loggers.AUTHN_NO_AUTH_MODE)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.AUTHN_NO_AUTH_MODE,
        )

    oauth = authn.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    try:
        tokendict = await oauth_app.authorize_access_token(request)
    except starlette_client.OAuthError:
        bound_logger.exception(loggers.AUTHN_JWT_INVALID)
        raise fastapi.HTTPException(
            status_code=401,
            detail=loggers.AUTHN_JWT_INVALID,
        ) from None

    access_token = tokendict["access_token"]

    try:
        authn.authenticate(the_installation, access_token)
    except fastapi.HTTPException:
        bound_logger.exception(loggers.AUTHN_JWT_INVALID)
        raise
    else:
        bound_logger.debug(loggers.AUTHN_JWT_VALID)

    refresh_token = tokendict["refresh_token"]
    expires_in = tokendict["expires_in"]

    # Handle hash-based routing (e.g., /#/auth/callback)
    # Query params must be placed before the hash fragment for Flutter to see
    # them
    return_to = request.query_params.get("return_to", "/")

    components = urlparse.urlparse(return_to)
    qs = urlparse.urlencode(
        dict(
            token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
        )
    )
    return_to = urlparse.urlunparse(
        (
            components.scheme,
            components.netloc,
            components.path,
            components.params,
            qs,
            components.fragment,
        )
    )

    return responses.RedirectResponse(return_to)


@util.logfire_span("GET /user_info")
@router.get("/user_info", summary="Get user profile")
async def get_user_info(
    the_installation: installation.Installation = depend_the_installation,
    the_admin_users: authz.AdminUserPolicy = depend_the_admin_users,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.UserProfile:
    """Return the profile of the authenticated user

    Carries 'is_admin' so a client can paint the administrator-only
    affordances it has rather than showing controls that 403 on use.

    Note for clients: this endpoint 404s outright when the installation
    runs with authentication disabled, so "no profile" there means
    single-user development, not "not an administrator". Treating it as
    the latter would leave the label management tab uneditable locally.
    """
    if the_installation.auth_disabled:
        the_logger.error(loggers.AUTHN_NO_AUTH_MODE)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.AUTHN_NO_AUTH_MODE,
        )

    the_logger.debug(loggers.AUTHN_GET_USER_INFO)

    is_admin = await the_admin_users.check_admin_access(
        the_user_claims,
        resource=loggers.AUDIT_RESOURCE_USER_PROFILE,
        action=loggers.AUDIT_ACTION_READ,
    )

    return models.UserProfile.from_user_claims(
        the_user_claims,
        is_admin=is_admin,
    )
