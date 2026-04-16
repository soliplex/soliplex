"""LTI session token management and user claims extraction"""

from __future__ import annotations

from soliplex import mcp_auth
from soliplex.lti import validation as lti_validation

LTI_SESSION_SALT = "lti-session"


def claims_from_lti_payload(payload: dict) -> dict:
    """Extract Soliplex UserClaims from a validated LTI payload"""
    email = payload.get("email", "")
    given_name = payload.get("given_name", "")
    family_name = payload.get("family_name", "")
    name = payload.get("name", "")
    sub = payload.get("sub", "")

    roles = payload.get(lti_validation.LTI_CLAIM_ROLES, [])
    resource_link = payload.get(lti_validation.LTI_CLAIM_RESOURCE_LINK, {})

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
) -> str:
    """Create a signed LTI session token"""
    payload = dict(user_claims) | {"_room_id": room_id}
    return mcp_auth.generate_url_safe_token(
        secret_key,
        LTI_SESSION_SALT,
        **payload,
    )


def validate_session_token(
    secret_key: str,
    token: str,
    max_age: int,
) -> dict | None:
    """Validate an LTI session token.

    Returns UserClaims on success, None on failure.
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
    return claims
