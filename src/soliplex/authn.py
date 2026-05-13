"""Soliplex authentication support"""

import logging
import typing

import fastapi
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import security

from soliplex import installation

_logger = logging.getLogger(__name__)

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

    # Try LTI session tokens
    lti_platforms = the_installation.lti_platform_configs
    if lti_platforms:
        from soliplex.lti import platform as lti_platform
        from soliplex.lti import session as lti_session

        try:
            secret_key = the_installation.get_secret("LTI_SESSION_SECRET")
        except KeyError:
            secret_key = None

        if secret_key is not None:
            # Peek at the token to find the platform that minted it,
            # then validate with that platform's session_ttl only.
            # Trying every platform's TTL in a loop would let a token
            # issued by a short-TTL platform be accepted after expiry
            # by a long-TTL platform.
            platform_id = lti_session.peek_platform_id(secret_key, token)
            if platform_id is not None:
                platform = lti_platform.find_platform_by_id(
                    lti_platforms, platform_id
                )
                if platform is not None:
                    claims = lti_session.validate_session_token(
                        secret_key,
                        token,
                        max_age=platform.session_ttl,
                    )
                    if claims is not None:
                        return claims
            else:
                # Legacy bridge: token minted before S1 added
                # _platform_id.  Validate with the most conservative
                # TTL across all platforms so a legacy token cannot
                # outlive the shortest configured TTL.  Remove this
                # branch after the warning below goes silent for a
                # full deploy cycle.
                conservative_ttl = min(p.session_ttl for p in lti_platforms)
                claims = lti_session.validate_session_token(
                    secret_key,
                    token,
                    max_age=conservative_ttl,
                )
                if claims is not None:
                    _logger.warning(
                        "Accepted legacy LTI session token without "
                        "_platform_id (sub=%r); re-launch will mint "
                        "a current token.",
                        claims.get("sub", "<unknown>"),
                    )
                    return claims

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
