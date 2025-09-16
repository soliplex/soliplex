import os

import fastapi
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import responses
from fastapi import security

from soliplex import installation
from soliplex import util

router = fastapi.APIRouter()


oauth2_scheme = security.OAuth2PasswordBearer(
    tokenUrl="token", auto_error=False,
)
oauth2_predicate = fastapi.Depends(oauth2_scheme)


_session_secret_key: bytes = None

def _get_session_secret_key() -> bytes:
    global _session_secret_key

    if _session_secret_key is None:
        _session_secret_key = os.urandom(16).hex()

    return _session_secret_key


_oauth = None

def get_oauth(
    the_installation: installation.Installation,
) -> starlette_client.OAuth:
    global _oauth

    if _oauth is None:

        config_data = {
            "SESSION_SECRET_KEY": _get_session_secret_key(),
        }

        config = starlette.config.Config(environ=config_data)  # Or use .env

        _oauth = starlette_client.OAuth(config)

        session_secret_key = _get_session_secret_key()
        for auth_system in the_installation.oidc_auth_system_configs:
            auth_system_kwargs = auth_system.oauth_client_kwargs
            auth_system_kwargs["authorize_state"] = session_secret_key

            _oauth.register(**auth_system_kwargs)

    return _oauth


def auth_disabled(
    the_installation: installation.Installation
) -> bool:
    return len(the_installation.oidc_auth_system_configs) == 0


def authenticate(
    the_installation: installation.Installation,
    token: str,
):
    # See #316
    if auth_disabled(the_installation):
        return {"name": "Phreddy Phlyntstone", "email": "phreddy@example.com"}

    if token is None:
        raise fastapi.HTTPException(
            status_code=401,
            detail="JWT validation failed (no token)"
        )

    for auth_system in the_installation.oidc_auth_system_configs:
        payload = validate_access_token(
            token, auth_system.token_validation_pem,
        )
        if payload is not None:
            return payload

    raise fastapi.HTTPException(
        status_code=401,
        detail="JWT validation failed (invalid token)"
    )


def validate_access_token(token, token_validation_pem):
    try:
        return jwt.decode(
            token,
            token_validation_pem,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.InvalidTokenError:
        return None


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
    if auth_disabled(the_installation):
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )
    return_to = request.query_params.get("return_to", "/")
    redirect_uri = request.url_for("get_auth_system", system=system)
    redirect_uri = redirect_uri.replace_query_params(return_to=return_to)
    redirect_uri = util.strip_default_port(redirect_uri)

    oauth = get_oauth(the_installation)
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
    if auth_disabled(the_installation):
        raise fastapi.HTTPException(
            status_code=404,
            detail="system in no-auth mode",
        )

    oauth = get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    try:
        tokendict = await oauth_app.authorize_access_token(request)
    except starlette_client.OAuthError as e:
        raise fastapi.HTTPException(
            status_code=401,
            detail=f"JWT validation failed {e}"
        ) from None

    access_token = tokendict["access_token"]
    authenticate(the_installation, access_token)

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
