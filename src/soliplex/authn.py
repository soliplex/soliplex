"""Soliplex authentication support"""

import typing

import fastapi
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import security

from soliplex import installation
from soliplex import loggers
from soliplex.config import authsystem as config_authsystem

UserClaims = dict[str, typing.Any]

oauth2_scheme = security.OAuth2PasswordBearer(
    tokenUrl="token",
    auto_error=False,
)
oauth2_predicate = fastapi.Depends(oauth2_scheme)


_oauth = None

JWT_VALIDATION_NO_TOKEN = "JWT validation failed (no token)"
JWT_VALIDATION_INVALID_TOKEN = "JWT validation failed (invalid token)"


def _get_authsystem_config(
    *,
    the_installation: installation.Installation,
    logger: loggers.LogWrapper,
    system: str,
) -> config_authsystem.OIDCAuthSystemConfig:
    """Return the indicated authsystem config

    Raise a 404 if the system is in no-auth mode, or if the named
    authsystem config is not found.
    """
    msg = loggers.AUTHN_NO_AUTH_MODE

    for config in the_installation.oidc_auth_system_configs:
        msg = loggers.AUTHN_UNKNOWN_AUTHSYSTEM

        if config.id == system:
            return config

    logger.error(msg)
    raise fastapi.HTTPException(
        status_code=404,
        detail=msg,
    )


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
    logger: loggers.LogWrapper,
    token: str,
) -> UserClaims:
    # See #316
    if the_installation.auth_disabled:
        return installation.NO_AUTH_MODE_USER_TOKEN

    if token is None:
        logger.info(loggers.AUTHN_JWT_NOT_SET)
        raise fastapi.HTTPException(
            status_code=401,
            detail=JWT_VALIDATION_NO_TOKEN,
        )

    errors = {}  # accumulated; only reported if all systems miss

    for auth_system in the_installation.oidc_auth_system_configs:
        payload, msg = validate_access_token(
            token,
            auth_system,
        )
        if payload is not None:
            return payload

        errors[auth_system.id] = msg

    for oidc_system_id, msg in errors.items():
        logger.error(
            loggers.AUTHN_JWT_INVALID,
            oidc_system_id=oidc_system_id,
            reason=msg,
        )

    raise fastapi.HTTPException(
        status_code=401,
        detail=JWT_VALIDATION_INVALID_TOKEN,
    )


def validate_access_token(
    token: str,
    auth_system: config_authsystem.OIDCAuthSystemConfig,
) -> tuple[dict | None, str | None, int | None]:
    """Return '(payload, None)'  if successful

    Return '(None, msg)' if failed.
    """
    payload = msg = None
    try:
        payload = jwt.decode(
            token,
            auth_system.token_validation_pem,
            algorithms=["RS256"],
            issuer=auth_system.issuer,
            options={
                "verify_aud": False,
                "require": ["exp", "iat", "iss", "sub"],
            },
        )
    except jwt.InvalidIssuerError:
        msg = loggers.AUTHN_JWT_PARSE_INVALID_ISS
    except jwt.InvalidSignatureError:
        msg = loggers.AUTHN_JWT_PARSE_INVALID_SIG
    except jwt.MissingRequiredClaimError as exc:
        msg = f"{loggers.AUTHN_JWT_PARSE_REQUIRED_CLAIM}:{exc.claim}"
    except jwt.ExpiredSignatureError:
        msg = loggers.AUTHN_JWT_PARSE_EXPIRED_SIG
    except jwt.InvalidTokenError:
        msg = loggers.AUTHN_JWT_PARSE_OTHER

    if msg is not None:
        return None, msg

    if payload.get("azp") not in auth_system.accepted_azp_list:
        return None, loggers.AUTHN_JWT_BIND_AZP

    for claim, expected in auth_system.required_claims.items():
        if payload.get(claim) != expected:
            return None, f"{loggers.AUTHN_JWT_BIND_CLAIM}:{claim}"

    return payload, None
