"""LTI 1.3 id_token validation"""

from __future__ import annotations

import jwt

# LTI 1.3 claim URIs
LTI_CLAIM_MESSAGE_TYPE = (
    "https://purl.imsglobal.org/spec/lti/claim/message_type"
)
LTI_CLAIM_VERSION = "https://purl.imsglobal.org/spec/lti/claim/version"
LTI_CLAIM_DEPLOYMENT_ID = (
    "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
)
LTI_CLAIM_RESOURCE_LINK = (
    "https://purl.imsglobal.org/spec/lti/claim/resource_link"
)
LTI_CLAIM_ROLES = "https://purl.imsglobal.org/spec/lti/claim/roles"
LTI_CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
LTI_CLAIM_TARGET_LINK_URI = (
    "https://purl.imsglobal.org/spec/lti/claim/target_link_uri"
)

LTI_VERSION = "1.3.0"
LTI_RESOURCE_LINK_REQUEST = "LtiResourceLinkRequest"


class LTIValidationError(ValueError):
    pass


class LTITokenExpired(LTIValidationError):
    _default = "LTI id_token has expired"

    def __init__(self, msg=None):
        super().__init__(msg or self._default)


class LTIInvalidNonce(LTIValidationError):
    _default = "LTI nonce mismatch"

    def __init__(self, msg=None):
        super().__init__(msg or self._default)


class LTIInvalidVersion(LTIValidationError):
    def __init__(self, *, expected, got):
        super().__init__(f"Expected LTI version {expected!r}, got {got!r}")


class LTIInvalidMessageType(LTIValidationError):
    def __init__(self, *, expected, got):
        super().__init__(f"Expected message type {expected!r}, got {got!r}")


def _fetch_jwks(key_set_url: str) -> jwt.PyJWKClient:
    """Return a caching PyJWKClient for the platform JWKS"""
    return jwt.PyJWKClient(key_set_url, cache_keys=True)


def validate_id_token(
    id_token: str,
    *,
    key_set_url: str,
    issuer: str,
    client_id: str,
    expected_nonce: str,
    jwks_client: jwt.PyJWKClient | None = None,
) -> dict:
    """Validate an LTI 1.3 id_token and return the payload.

    Raises LTIValidationError subclasses on failure.
    """
    if jwks_client is None:
        jwks_client = _fetch_jwks(key_set_url)

    signing_key = jwks_client.get_signing_key_from_jwt(id_token)

    try:
        payload = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=issuer,
            options={
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": False,
            },
            leeway=30,
        )
    except jwt.ExpiredSignatureError as exc:
        raise LTITokenExpired() from exc
    except jwt.InvalidTokenError as exc:
        raise LTIValidationError(str(exc)) from exc

    if payload.get("nonce") != expected_nonce:
        raise LTIInvalidNonce()

    version = payload.get(LTI_CLAIM_VERSION)
    if version != LTI_VERSION:
        raise LTIInvalidVersion(expected=LTI_VERSION, got=version)

    msg_type = payload.get(LTI_CLAIM_MESSAGE_TYPE)
    if msg_type != LTI_RESOURCE_LINK_REQUEST:
        raise LTIInvalidMessageType(
            expected=LTI_RESOURCE_LINK_REQUEST,
            got=msg_type,
        )

    return payload
