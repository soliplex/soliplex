
import fastapi
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import auth
from soliplex import installation
from soliplex import util

router = fastapi.APIRouter()

@router.get("/login")
async def get_login(
    the_installation: installation.Installation=
        installation.depend_the_installation,
):
    return {
        "systems": [
            {
                "id": auth_system.id,
                "title": auth_system.title,
            } for auth_system in the_installation.oidc_auth_system_configs
        ]
    }


@util.logfire_span("GET /login/{system}")
@router.get("/login/{system}")
async def get_login_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation=
        installation.depend_the_installation,
):
    if auth.auth_disabled(the_installation):
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
@router.get("/auth/{system}")
async def get_auth_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation=
        installation.depend_the_installation,
):
    if auth.auth_disabled(the_installation):
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
            status_code=401,
            detail=f"JWT validation failed {e}"
        ) from None

    access_token = tokendict["access_token"]
    auth.authenticate(the_installation, access_token)

    refresh_token = tokendict["refresh_token"]
    expires_in = tokendict["expires_in"]
    refresh_expires_in = tokendict["refresh_expires_in"]

    # NB: explicitly putting the "query parameters" after the URL,
    # even if the url ends with an anchor tag (support GoRouter)
    return_to = request.query_params.get("return_to", "/")
    return_to += f"?token={access_token}"
    return_to += f"&refresh_token={refresh_token}"
    return_to += f"&expires_in={expires_in}"
    return_to += f"&refresh_expires_in={refresh_expires_in}"
    return responses.RedirectResponse(return_to)
