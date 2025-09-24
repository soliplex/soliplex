import os

import fastapi
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import security

from soliplex import installation

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


def authenticate(
    the_installation: installation.Installation,
    token: str,
):
    # See #316
    if the_installation.auth_disabled:
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
