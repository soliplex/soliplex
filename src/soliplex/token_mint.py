"""Signed URL-safe tokens:  MCP room tokens and service tokens"""

from __future__ import annotations

import time
import typing
import uuid

from itsdangerous import url_safe as id_url_safe

from soliplex import loggers

ServiceTokenClaims = dict[str, typing.Any]

SERVICE_TOKEN_SALT = "soliplex.authn.service-token"
SERVICE_TOKEN_RESERVED_CLAIMS = ("iat", "exp")


class ServiceTokenError(ValueError):
    """Base for errors raised while minting a service token"""


class ReservedClaim(ServiceTokenError):
    def __init__(self, claim: str):
        self.claim = claim
        super().__init__(
            f"Service token claims may not include '{claim}': "
            f"it is set when minting"
        )


class InvalidLifetime(ServiceTokenError):
    def __init__(self, expires_in: int):
        self.expires_in = expires_in
        super().__init__(
            f"Service token lifetime must be positive: {expires_in}"
        )


def generate_url_safe_token(secret_key: str, salt: str, **kw) -> str:
    """Generate a signed token for a given context

    'secret_key':
        Key use for symmetric encryption of the token.

    'salt':
        the "context" for the token (e.g., a room ID), to prevent reuse
        of tokens generated for other contexts.

    'kw':
        the values to be encoded into the token.

    Returns:
        a URL-safe string representation of the token, signed using our
        secret key.  The token will contain a timestamp, which can be used
        to verify token age (see 'validate_url_safe_token').
    """
    serializer = id_url_safe.URLSafeTimedSerializer(
        secret_key=secret_key,
        salt=salt,
    )
    return serializer.dumps(kw)


def validate_url_safe_token(
    secret_key: str, salt: str, token: str, max_age: int = None
) -> dict:
    """Validate a signed token for a given context

    'secret_key':
        Key use for symmetric encryption of the token.

    'salt':
        the "context" for the token (e.g., a room ID), to prevent reuse of
        tokens generated for other contexts.

    'token':
        the generated URL-safe token (see 'generate_url_safe_token')

    'max_age':
        the maximum age, in seconds, for the token.

    Returns
        a dict unpacked after verifying the token's signature.
        using our secret key;  if the token cannot be verified, returns
        'None'.
    """
    serializer = id_url_safe.URLSafeTimedSerializer(
        secret_key=secret_key,
        salt=salt,
    )

    ok, found = serializer.loads_unsafe(token, max_age=max_age)

    if ok:
        return found


def mint_service_token(
    secret_key: str,
    claims: ServiceTokenClaims,
    *,
    expires_in: int,
) -> str:
    """Return a signed service token holding 'claims'

    The token's claims are 'claims' plus 'iat' (the current time) and
    'exp' ('iat' plus 'expires_in' seconds).  If 'claims' holds no 'sub',
    the token's 'sub' is a random UUID.

    Raises:

    - 'ReservedClaim' if 'claims' holds one of
      'SERVICE_TOKEN_RESERVED_CLAIMS'.
    - 'InvalidLifetime' if 'expires_in' is not positive.
    """
    for claim in SERVICE_TOKEN_RESERVED_CLAIMS:
        if claim in claims:
            raise ReservedClaim(claim)

    if expires_in <= 0:
        raise InvalidLifetime(expires_in)

    iat = int(time.time())
    to_sign = {
        "sub": str(uuid.uuid4()),
        **claims,
        "iat": iat,
        "exp": iat + expires_in,
    }

    return generate_url_safe_token(secret_key, SERVICE_TOKEN_SALT, **to_sign)


def load_service_token(
    secret_key: str,
    token: str,
) -> tuple[ServiceTokenClaims | None, str | None]:
    """Return '(claims, None)' from service token 'token' if valid.

    Return '(None, reason)' if not:
    - the signature does not verify;
    - the claims hold no numeric 'exp';
    - the 'exp' has expired.
    """
    claims = validate_url_safe_token(secret_key, SERVICE_TOKEN_SALT, token)

    if claims is None:
        return None, loggers.AUTHN_SERVICE_TOKEN_BAD_SIGNATURE

    exp = claims.get("exp")

    if not isinstance(exp, int | float):
        return None, loggers.AUTHN_SERVICE_TOKEN_BAD_ENVELOPE

    if exp <= time.time():
        return None, loggers.AUTHN_SERVICE_TOKEN_EXPIRED

    return claims, None
