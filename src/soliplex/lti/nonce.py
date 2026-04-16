"""LTI 1.3 nonce and state management

Encodes {nonce, platform_id} into the OIDC 'state' parameter using
a signed token.  This avoids session cookies entirely, sidestepping
SameSite=Lax issues with the cross-site POST in the LTI launch flow.
"""

from __future__ import annotations

import secrets

from soliplex import mcp_auth

LTI_STATE_SALT = "lti-state"
LTI_STATE_MAX_AGE = 600  # 10 minutes


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
