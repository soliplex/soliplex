"""LTI 1.3 nonce and state management

Encodes {nonce, platform_id} into the OIDC 'state' parameter using
a signed token.  This avoids session cookies entirely, sidestepping
SameSite=Lax issues with the cross-site POST in the LTI launch flow.
"""

from __future__ import annotations

import secrets
import time

from soliplex import mcp_auth

LTI_STATE_SALT = "lti-state"
LTI_STATE_MAX_AGE = 600  # 10 minutes

# Maximum number of seen-nonce records to keep in memory. When the
# cache exceeds this, the oldest entries are evicted regardless of
# whether they've expired. 10k @ ~64B/key gives ~640KB worst case,
# which comfortably absorbs realistic LTI launch traffic before the
# 10-minute TTL would otherwise sweep stale entries.
_SEEN_NONCE_LIMIT = 10_000

# Module-level cache of nonces that have already been redeemed via
# `consume_nonce`. Single-process / single-instance only; for HA
# replicas this needs to be a shared cache (Redis). See B3 plan.
_seen_nonces: dict[str, float] = {}


def consume_nonce(nonce: str) -> bool:
    """Mark *nonce* as redeemed. Returns False on replay.

    On first call with a given nonce, records its expiry timestamp
    (now + LTI_STATE_MAX_AGE) and returns True. On any subsequent
    call within the TTL it returns False — the caller should reject
    the request as a replay.

    Expired entries are swept lazily on each call. The cache is
    bounded at `_SEEN_NONCE_LIMIT`; when exceeded, oldest entries
    are dropped first.
    """
    now = time.time()

    expired = [k for k, exp in _seen_nonces.items() if exp <= now]
    for k in expired:
        del _seen_nonces[k]

    if nonce in _seen_nonces:
        return False

    if len(_seen_nonces) >= _SEEN_NONCE_LIMIT:
        oldest = sorted(_seen_nonces.items(), key=lambda kv: kv[1])
        overflow = len(_seen_nonces) - _SEEN_NONCE_LIMIT + 1
        for k, _ in oldest[:overflow]:
            del _seen_nonces[k]

    _seen_nonces[nonce] = now + LTI_STATE_MAX_AGE
    return True


def generate_nonce() -> str:
    return secrets.token_urlsafe(32)


def encode_state(
    secret_key: str,
    *,
    nonce: str,
    platform_id: str,
) -> str:
    """Sign nonce + platform_id into a URL-safe state token"""
    return mcp_auth.generate_url_safe_token(
        secret_key,
        LTI_STATE_SALT,
        nonce=nonce,
        platform_id=platform_id,
    )


def decode_state(
    secret_key: str,
    state: str,
    max_age: int = LTI_STATE_MAX_AGE,
) -> tuple[str, str] | None:
    """Validate and extract (nonce, platform_id) from state token

    Returns None on failure (bad signature, expired, tampered).
    """
    payload = mcp_auth.validate_url_safe_token(
        secret_key,
        LTI_STATE_SALT,
        state,
        max_age=max_age,
    )
    if payload is None:
        return None
    nonce = payload.get("nonce")
    platform_id = payload.get("platform_id")
    if nonce is None or platform_id is None:
        return None
    return nonce, platform_id
