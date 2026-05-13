"""LTI session token management and user claims extraction"""

from __future__ import annotations

from soliplex import mcp_auth
from soliplex.lti import LTI_CLAIM_RESOURCE_LINK
from soliplex.lti import LTI_CLAIM_ROLES

LTI_SESSION_SALT = "lti-session"


def claims_from_lti_payload(payload: dict) -> dict:
    """Extract Soliplex UserClaims from a validated LTI payload"""
    email = payload.get("email", "")
    given_name = payload.get("given_name", "")
    family_name = payload.get("family_name", "")
    name = payload.get("name", "")
    sub = payload.get("sub", "")

    roles = payload.get(LTI_CLAIM_ROLES, [])
    resource_link = payload.get(LTI_CLAIM_RESOURCE_LINK, {})

    return {
        "sub": sub,
        "email": email or sub,
        "given_name": given_name,
        "family_name": family_name,
        "name": (name or f"{given_name} {family_name}".strip() or sub),
        "preferred_username": email or sub,
        "lti_roles": roles,
        "lti_resource_link_id": resource_link.get("id", ""),
    }


def mint_session_token(
    secret_key: str,
    user_claims: dict,
    room_id: str,
    platform_id: str,
) -> str:
    """Create a signed LTI session token.

    ``platform_id`` is embedded as ``_platform_id`` so that the
    auth layer can look up the issuing platform's ``session_ttl``
    on validation (rather than trying every platform's TTL and
    accepting the longest one).
    """
    payload = dict(user_claims) | {
        "_room_id": room_id,
        "_platform_id": platform_id,
    }
    return mcp_auth.generate_url_safe_token(
        secret_key,
        LTI_SESSION_SALT,
        **payload,
    )


def peek_platform_id(secret_key: str, token: str) -> str | None:
    """Return the ``_platform_id`` from a token, or None if invalid.

    Validates the HMAC signature but does not enforce ``max_age`` —
    the caller looks up the platform first, then re-validates with
    the platform-specific TTL via ``validate_session_token``.
    """
    # max_age=None on itsdangerous skips age check while keeping
    # signature verification.
    claims = mcp_auth.validate_url_safe_token(
        secret_key,
        LTI_SESSION_SALT,
        token,
        max_age=None,
    )
    if claims is None:
        return None
    return claims.get("_platform_id")


def validate_session_token(
    secret_key: str,
    token: str,
    max_age: int,
) -> dict | None:
    """Validate an LTI session token.

    Returns UserClaims on success, None on failure. Strips the
    internal ``_room_id`` / ``_platform_id`` fields so the returned
    claims dict carries only user-facing identity.
    """
    claims = mcp_auth.validate_url_safe_token(
        secret_key,
        LTI_SESSION_SALT,
        token,
        max_age=max_age,
    )
    if claims is None:
        return None
    claims.pop("_room_id", None)
    claims.pop("_platform_id", None)
    return claims
