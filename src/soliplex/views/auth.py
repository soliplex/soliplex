import dataclasses
from urllib import parse as urlparse

import fastapi
from authlib.integrations import starlette_client
from fastapi import responses
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter(tags=["authentication"])

depend_the_installation = installation.depend_the_installation


@router.get("/login", summary="Get available OIDC auth providers")
async def get_login(
    the_installation: installation.Installation = depend_the_installation,
) -> models.ConfiguredOIDCAuthSystems:
    """Describe configured OIDC Authentication providers"""
    # Remove `_installation_config` to avoid infinite recursion
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
):
    """Initiate token auth flow with the specified OIDC auth provider"""
    if the_installation.auth_disabled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )
    return_to = request.query_params.get("return_to", "/")
    redirect_uri = request.url_for("get_auth_system", system=system)
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    redirect_uri = util.strip_default_port(redirect_uri)

    oauth = auth.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    found = await oauth_app.authorize_redirect(request, redirect_uri)
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
):
    """Complete the OIDC token auth flow with the specified provider

    On success, redirect to client-specified URL.
    """
    if the_installation.auth_disabled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )

    oauth = auth.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    try:
        tokendict = await oauth_app.authorize_access_token(request)
    except starlette_client.OAuthError as e:
        raise fastapi.HTTPException(
            status_code=401, detail=f"JWT validation failed {e}"
        ) from None

    access_token = tokendict["access_token"]
    auth.authenticate(the_installation, access_token)

    refresh_token = tokendict["refresh_token"]
    expires_in = tokendict["expires_in"]
    refresh_expires_in = tokendict["refresh_expires_in"]

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
            refresh_expires_in=refresh_expires_in,
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
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.UserInfo:
    """Return the profile of the authenticated user"""
    if the_installation.auth_disabled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )

    return auth.authenticate(the_installation, token)
