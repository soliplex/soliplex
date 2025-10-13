import dataclasses

import fastapi
from authlib.integrations import starlette_client
from datetime import datetime, timedelta
from fastapi import responses
from fastapi import security

from soliplex import auth
from soliplex import installation
from soliplex import models
from soliplex import util

router = fastapi.APIRouter()

depend_the_installation = installation.depend_the_installation


@router.get("/login")
async def get_login(
    the_installation: installation.Installation = depend_the_installation,
) -> models.ConfiguredOIDCAuthSystems:
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
@router.get("/login/{system}")
async def get_login_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
):
    if the_installation.auth_disabled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )

    oauth = auth.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    redirect_uri = request.url_for("get_auth_system", system=system)

    for auth_system in the_installation.oidc_auth_system_configs:
        if auth_system.id == system and auth_system.include_return_to:
            return_to = request.query_params.get("return_to", "/")
            redirect_uri = redirect_uri.replace_query_params(return_to=return_to)

    redirect_uri = util.strip_default_port(redirect_uri)

    found = await oauth_app.authorize_redirect(request, redirect_uri)
    return found


@util.logfire_span("GET /auth/{system}")
@router.get("/auth/{system}")
async def get_auth_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
):
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

    try:
        id_token = await oauth_app.parse_id_token(request, tokendict)
    except Exception:
        id_token = None

    try:
        userinfo = await oauth_app.userinfo(token=tokendict)
    except Exception:
        userinfo = {}

    profile = userinfo or id_token or tokendict.get("userinfo", {})

    request.session["user"] = {
        "sub": profile.get("sub"),
        "email": profile.get("email"),
        "name": profile.get("name"),
    }

    request.session["token"] = {
        "system": system,
        "access_token": tokendict["access_token"],
        "refresh_token": tokendict.get("refresh_token"),
        "expires_at": tokendict.get("expires_at") or (
            datetime.utcnow() + timedelta(seconds=tokendict.get("expires_in", 3600))
        ).isoformat()
    }

    return_to = request.query_params.get("return_to", "/")
    return responses.RedirectResponse(return_to)


@util.logfire_span("GET /user_info")
@router.get("/user_info")
async def get_user_info(
    the_installation: installation.Installation = depend_the_installation,
    token: security.HTTPAuthorizationCredentials = auth.oauth2_predicate,
) -> models.UserInfo:
    if the_installation.auth_disabled:
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )

    return await auth.authenticate(the_installation, token)
