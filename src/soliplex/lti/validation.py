"""LTI 1.3 id_token validation"""

from __future__ import annotations

import anyio
import jwt

# LTI 1.3 claim URIs
LTI_CLAIM_MESSAGE_TYPE = (
    "https://purl.imsglobal.org/spec/lti/claim/message_type"
)
LTI_CLAIM_VERSION = "https://purl.imsglobal.org/spec/lti/claim/version"
LTI_CLAIM_DEPLOYMENT_ID = (
    "https://purl.imsglobal.org/spec/lti/claim/deployment_id"
)
LTI_CLAIM_CONTEXT = "https://purl.imsglobal.org/spec/lti/claim/context"
LTI_CLAIM_TARGET_LINK_URI = (
    "https://purl.imsglobal.org/spec/lti/claim/target_link_uri"
)

LTI_VERSION = "1.3.0"
LTI_RESOURCE_LINK_REQUEST = "LtiResourceLinkRequest"


class LTIValidationError(ValueError):
    _default: str = ""

    def __init__(self, msg=None):
        super().__init__(msg or self._default)


class LTITokenExpired(LTIValidationError):
    _default = "LTI id_token has expired"


class LTIInvalidNonce(LTIValidationError):
    _default = "LTI nonce mismatch"


class LTIInvalidVersion(LTIValidationError):
    def __init__(self, *, expected, got):
        super().__init__(f"Expected LTI version {expected!r}, got {got!r}")


class LTIInvalidMessageType(LTIValidationError):
    def __init__(self, *, expected, got):
        super().__init__(f"Expected message type {expected!r}, got {got!r}")


# Module-level cache of PyJWKClient instances keyed by JWKS URL.
# Each client's internal `cache_keys=True` cache is then preserved
# across requests (instead of being thrown away with the client when
# validation returns, which is what happened before this was cached).
# JWKS-rotation cadence is presumed slower than process restart; if
# that ever changes, add a TTL or external invalidation hook.
_jwks_clients: dict[str, jwt.PyJWKClient] = {}
_jwks_lock: anyio.Lock | None = None


async def _get_jwks_client(key_set_url: str) -> jwt.PyJWKClient:
    """Return the cached PyJWKClient for *key_set_url*, creating it
    on first request. The lock prevents two concurrent first-request
    coroutines from racing to construct duplicate clients."""
    if key_set_url in _jwks_clients:
        return _jwks_clients[key_set_url]
    global _jwks_lock
    if _jwks_lock is None:
        _jwks_lock = anyio.Lock()
    async with _jwks_lock:
        if key_set_url not in _jwks_clients:
            _jwks_clients[key_set_url] = jwt.PyJWKClient(
                key_set_url, cache_keys=True
            )
    return _jwks_clients[key_set_url]


async def validate_id_token(
    id_token: str,
    *,
    key_set_url: str,
    issuer: str,
    client_id: str,
    expected_nonce: str,
) -> dict:
    """Validate an LTI 1.3 id_token and return the payload.

    Raises LTIValidationError subclasses on failure. The JWKS fetch
    (which ``PyJWKClient`` performs with blocking ``urllib.request``
    on first key lookup) is offloaded to a worker thread so the
    event loop is not stalled during launch.
    """
    jwks_client = await _get_jwks_client(key_set_url)

    signing_key = await anyio.to_thread.run_sync(
        jwks_client.get_signing_key_from_jwt, id_token
    )

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
