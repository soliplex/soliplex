"""Soliplex authentication support"""

import os
import time
import typing

import fastapi
import itsdangerous
import jwt
import starlette.config
from authlib.integrations import starlette_client
from fastapi import security

from soliplex import installation
from soliplex import loggers
from soliplex import token_mint
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
SERVICE_TOKEN_VALIDATION_INVALID_TOKEN = (
    "Service token validation failed (invalid token)"
)

INSECURE_COOKIES_ENV_VAR = "_SOLIPLEX_INSECURE_SESSION_COOKIE"

AUTHN_COOKIE_NAME = "soliplex_authn"
AUTHN_COOKIE_SALT = "soliplex.authn.cookie"
AUTHN_COOKIE_SECRET_NAME = "SESSION_MIDDLEWARE_TOKEN"
AUTHN_COOKIE_ALWAYS_CLAIMS = ("sub",)
# Browsers reject cookies whose name+value exceeds 4096 bytes (RFC 6265bis;
# enforced by Chrome and Firefox, and no more generous in Safari in
# practice).  'soliplex_authn' consumes 14 of them, leaving the round 4000
# as the budget for the serialized value alone.
AUTHN_COOKIE_MAX_SIZE = 4000

SERVICE_TOKEN_SECRET_NAME = "URL_SAFE_TOKEN_SECRET"


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

    claims, service_token_reason = token_mint.load_service_token(
        the_installation.get_secret(SERVICE_TOKEN_SECRET_NAME),
        token,
    )
    if claims is not None:
        return claims

    if service_token_reason != loggers.AUTHN_SERVICE_TOKEN_BAD_SIGNATURE:
        # The signature verified, so the token is a service token:
        # report the error accordingly.
        logger.error(
            loggers.AUTHN_SERVICE_TOKEN_INVALID,
            reason=service_token_reason,
        )
        raise fastapi.HTTPException(
            status_code=401,
            detail=SERVICE_TOKEN_VALIDATION_INVALID_TOKEN,
        )

    for oidc_system_id, msg in errors.items():
        logger.error(
            loggers.AUTHN_JWT_INVALID,
            oidc_system_id=oidc_system_id,
            reason=msg,
        )

    logger.error(
        loggers.AUTHN_SERVICE_TOKEN_INVALID,
        reason=service_token_reason,
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


def secure_cookies() -> bool:
    """Should Soliplex's cookies carry the 'Secure' attribute?

    'True' unless the '_SOLIPLEX_INSECURE_SESSION_COOKIE' environment
    variable is 'Y'.
    """
    return os.environ.get(INSECURE_COOKIES_ENV_VAR) != "Y"


def _authn_cookie_serializer(
    the_installation: installation.Installation,
) -> itsdangerous.URLSafeSerializer:
    secret_key = the_installation.get_secret(AUTHN_COOKIE_SECRET_NAME)
    return itsdangerous.URLSafeSerializer(secret_key, salt=AUTHN_COOKIE_SALT)


def set_authn_cookie(
    response: fastapi.Response,
    *,
    the_installation: installation.Installation,
    auth_system: config_authsystem.OIDCAuthSystemConfig,
    claims: UserClaims,
    logger: loggers.LogWrapper,
) -> bool:
    """Set the signed authn cookie on 'response'

    The cookie holds the claims named in 'AUTHN_COOKIE_ALWAYS_CLAIMS' and
    in 'auth_system.cookie_claims' (those present in 'claims'), and
    expires at 'claims["exp"]'.  Returns True when the cookie was set.

    A value larger than 'AUTHN_COOKIE_MAX_SIZE' is logged as an error,
    and the cookie is cleared from the response rather than set:  the
    browser ignores an oversized 'Set-Cookie' entirely (see
    'AUTHN_COOKIE_MAX_SIZE'), so merely not setting it would leave
    whatever 'soliplex_authn' cookie the browser already holds --
    possibly left by a different visitor's sign-in -- authorizing the
    wrong person until it expires.
    """
    names = (*AUTHN_COOKIE_ALWAYS_CLAIMS, *auth_system.cookie_claims)
    selected = {name: claims[name] for name in names if name in claims}
    envelope = (auth_system.id, claims["exp"], selected)
    value = _authn_cookie_serializer(the_installation).dumps(envelope)

    cookie_set = len(value) <= AUTHN_COOKIE_MAX_SIZE

    if cookie_set:
        response.set_cookie(
            AUTHN_COOKIE_NAME,
            value,
            max_age=max(int(claims["exp"] - time.time()), 0),
            path="/",
            secure=secure_cookies(),
            httponly=True,
            samesite="lax",
        )
    else:
        logger.error(loggers.AUTHN_COOKIE_TOO_LARGE, size=len(value))
        clear_authn_cookie(response)

    return cookie_set


def clear_authn_cookie(response: fastapi.Response):
    """Remove the authn cookie via 'response'"""
    response.delete_cookie(
        AUTHN_COOKIE_NAME,
        path="/",
        secure=secure_cookies(),
        httponly=True,
        samesite="lax",
    )


def load_authn_cookie(
    the_installation: installation.Installation,
    value: str,
) -> tuple[UserClaims | None, None | str]:
    """Return '(claims, None)' from authn cookie's 'value' if valid.

    Return '(None, reason)' if not:
    - the signature does not verify;
    - 'value' is not a well formed '(authsystem_id, exp, claims)' envelope;
    - the unpacked 'exp' has expired;
    - the unpacked 'authsystem_id' matches no configured auth system.
    """
    try:
        envelope = _authn_cookie_serializer(the_installation).loads(value)
    except itsdangerous.BadSignature:
        return None, loggers.AUTHN_COOKIE_BAD_SIGNATURE

    try:
        authsystem_id, exp, claims = envelope
    except ValueError:
        return None, loggers.AUTHN_COOKIE_BAD_ENVELOPE

    if exp <= time.time():
        return None, loggers.AUTHN_COOKIE_EXPIRED

    authsystem_map = {
        auth_system.id
        for auth_system in the_installation.oidc_auth_system_configs
    }
    if authsystem_id not in authsystem_map:
        return None, loggers.AUTHN_COOKIE_UNKNOWN_IDP

    return claims, None
