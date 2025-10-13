import os

import fastapi
import jwt
import starlette.config

from authlib.integrations import starlette_client
from authlib.integrations.httpx_client import AsyncOAuth2Client
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from fastapi import security

from soliplex import installation

TOKEN_CHECK_INTERVAL = timedelta(minutes=15)


depend_the_installation = installation.depend_the_installation


oauth2_scheme = security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
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


def authenticate(
    the_installation: installation.Installation,
    token: str,
):
    # See #316
    if the_installation.auth_disabled:
        return {"name": "Phreddy Phlyntstone", "email": "phreddy@example.com"}

    if token is None:
        raise fastapi.HTTPException(
            status_code=401, detail="JWT validation failed (no token)"
        )

    for auth_system in the_installation.oidc_auth_system_configs:
        payload = validate_access_token(
            token,
            auth_system.token_validation_pem,
        )
        if payload is not None:
            return payload

    raise fastapi.HTTPException(
        status_code=401, detail="JWT validation failed (invalid token)"
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


async def refresh_token(oauth_app, refresh_token: str):
    # Load provider metadata to get token_endpoint
    metadata = await oauth_app.load_server_metadata()
    token_endpoint = metadata["token_endpoint"]

    async with AsyncOAuth2Client(
        client_id=oauth_app.client_id,
        client_secret=oauth_app.client_secret,
    ) as client:
        new_token = await client.refresh_token(
            token_endpoint,
            refresh_token=refresh_token,
        )
    return new_token


async def get_current_user(
        request: Request,
        the_installation: installation.Installation = depend_the_installation):
    """Retrieve current user, refreshing token if needed"""

    if the_installation.auth_disabled:
        return {"name": "Phreddy Phlyntstone", "email": "phreddy@example.com"}

    user = request.session.get("user")
    token = request.session.get("token")
    if not user or not token:
        raise HTTPException(401, "Not authenticated")

    now = datetime.now(timezone.utc)
    expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)

    # If token expired → refresh
    if now >= expires_at:
        if not token.get("refresh_token"):
            request.session.clear()
            raise HTTPException(401, "Session expired; please re-login")

        oauth = get_oauth(the_installation)
        system = token.get("system")
        oauth_app = oauth.create_client(system)

        new_token = await refresh_token(oauth_app, token["refresh_token"])

        # update session
        token["access_token"] = new_token["access_token"]
        token["expires_at"] = new_token["expires_at"]
        token["refresh_token"] = new_token.get("refresh_token", token["refresh_token"])
        request.session["token"] = token

    return user
