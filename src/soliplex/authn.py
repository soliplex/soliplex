"""Soliplex authentication support"""

import typing

import fastapi
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import security

from soliplex import installation

UserClaims = dict[str, typing.Any]

oauth2_scheme = security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
)
oauth2_predicate = fastapi.Depends(oauth2_scheme)


_oauth = None

JWT_VALIDATION_NO_TOKEN = "JWT validation failed (no token)"
JWT_VALIDATION_INVALID_TOKEN = "JWT validation failed (invalid token)"


def get_oauth(
    the_installation: installation.Installation,
) -> starlette_client.OAuth:
    global _oauth

    if _oauth is None:
        config_data = {}  # Or use .env
        config = starlette.config.Config(environ=config_data)
        _oauth = starlette_client.OAuth(config)

        for auth_system in the_installation.oidc_auth_system_configs:
            auth_system_kwargs = auth_system.oauth_client_kwargs
            _oauth.register(**auth_system_kwargs)

    return _oauth


def authenticate(
    the_installation: installation.Installation,
    token: str,
) -> UserClaims:
    # See #316
    if the_installation.auth_disabled:
        return installation.NO_AUTH_MODE_USER_TOKEN

    if token is None:
        raise fastapi.HTTPException(
            status_code=401,
            detail=JWT_VALIDATION_NO_TOKEN,
        )

    for auth_system in the_installation.oidc_auth_system_configs:
        payload = validate_access_token(
            token,
            auth_system.token_validation_pem,
        )
        if payload is not None:
            return payload

    raise fastapi.HTTPException(
        status_code=401,
        detail=JWT_VALIDATION_INVALID_TOKEN,
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
