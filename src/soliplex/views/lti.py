"""LTI 1.3 External Tool Provider views"""

from __future__ import annotations

import urllib.parse

import fastapi
from fastapi import responses as fastapi_responses

from soliplex import installation
from soliplex import loggers
from soliplex.lti import nonce as lti_nonce
from soliplex.lti import platform as lti_platform
from soliplex.lti import session as lti_session
from soliplex.lti import validation as lti_validation
from soliplex.views.lti_templates import _CHAT_PAGE
from soliplex.views.lti_templates import _PICKER_CHAT_PAGE

router = fastapi.APIRouter(prefix="/lti", tags=["lti"])

depend_the_installation = installation.depend_the_installation


# ----------------------------------------------------------------
#   Helpers
# ----------------------------------------------------------------


def _get_lti_secret(the_installation):
    try:
        return the_installation.get_secret("LTI_SESSION_SECRET")
    except KeyError:
        raise fastapi.HTTPException(
            status_code=500,
            detail=loggers.LTI_SECRET_NOT_CONFIGURED,
        ) from None


# ----------------------------------------------------------------
#   Endpoints
# ----------------------------------------------------------------


@router.get(
    "/jwks",
    summary="LTI JWKS endpoint",
)
async def get_lti_jwks() -> dict:
    """Return Soliplex JSON Web Key Set (empty in Phase 1)"""
    return {"keys": []}


async def _read_params(
    request: fastapi.Request,
) -> dict[str, str]:
    """Read params from query string (GET) or form (POST)"""
    if request.method == "POST":
        form = await request.form()
        return dict(form)
    return dict(request.query_params)


@router.api_route(
    "/login",
    methods=["GET", "POST"],
    summary="LTI OIDC login initiation",
)
async def lti_login(
    request: fastapi.Request,
    the_installation: (installation.Installation) = depend_the_installation,
):
    """Handle OIDC third-party login initiation from an LTI
    platform.

    Validates iss/client_id, encodes nonce+platform_id into
    a signed state token, and redirects to the platform's
    auth endpoint.
    """
    params = await _read_params(request)

    iss = params.get("iss")
    client_id = params.get("client_id")
    login_hint = params.get("login_hint", "")
    lti_message_hint = params.get("lti_message_hint", "")

    lti_platforms = the_installation.lti_platform_configs

    try:
        platform = lti_platform.find_platform(
            lti_platforms,
            issuer=iss,
            client_id=client_id,
        )
    except lti_platform.UnknownLTIPlatform:
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_UNKNOWN_PLATFORM,
        ) from None

    secret_key = _get_lti_secret(the_installation)
    nonce = lti_nonce.generate_nonce()
    state = lti_nonce.encode_state(
        secret_key,
        nonce=nonce,
        platform_id=platform.id,
    )

    redirect_uri = str(request.url_for("lti_launch"))

    auth_params = urllib.parse.urlencode(
        {
            "scope": "openid",
            "response_type": "id_token",
            "client_id": platform.client_id,
            "redirect_uri": redirect_uri,
            "login_hint": login_hint,
            "lti_message_hint": lti_message_hint,
            "state": state,
            "response_mode": "form_post",
            "nonce": nonce,
            "prompt": "none",
        }
    )

    auth_url = f"{platform.auth_login_url}?{auth_params}"
    return fastapi_responses.RedirectResponse(
        auth_url,
        status_code=302,
    )


@router.post(
    "/launch",
    name="lti_launch",
    summary="LTI launch endpoint",
)
async def lti_launch(
    request: fastapi.Request,
    the_installation: (installation.Installation) = depend_the_installation,
):
    """Receive and validate the LTI id_token from a platform.

    On success, renders the chat page with an embedded session
    token.
    """
    form = await request.form()
    id_token = form.get("id_token")
    state = form.get("state")

    if id_token is None or state is None:
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_INVALID_LAUNCH,
        )

    secret_key = _get_lti_secret(the_installation)
    decoded = lti_nonce.decode_state(secret_key, state)

    if decoded is None:
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_INVALID_LAUNCH,
        )

    nonce, platform_id = decoded

    lti_platforms = the_installation.lti_platform_configs
    platform = lti_platform.find_platform_by_id(lti_platforms, platform_id)

    if platform is None:
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_UNKNOWN_PLATFORM,
        )

    try:
        payload = lti_validation.validate_id_token(
            id_token,
            key_set_url=platform.key_set_url,
            issuer=platform.issuer,
            client_id=platform.client_id,
            expected_nonce=nonce,
        )
    except lti_validation.LTIValidationError as exc:
        raise fastapi.HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    deployment_id = payload.get(lti_validation.LTI_CLAIM_DEPLOYMENT_ID)
    try:
        lti_platform.check_deployment(platform, deployment_id)
    except lti_platform.InvalidLTIDeployment as exc:
        raise fastapi.HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    target_link_uri = payload.get(lti_validation.LTI_CLAIM_TARGET_LINK_URI)
    context = payload.get(lti_validation.LTI_CLAIM_CONTEXT, {})
    course_id = context.get("id") if isinstance(context, dict) else None

    room_id = lti_platform.resolve_room_id(
        platform,
        target_link_uri=target_link_uri,
        course_id=course_id,
    )

    show_picker = (
        platform.show_room_picker and room_id == platform.default_room_id
    )

    user_claims = lti_session.claims_from_lti_payload(payload)
    session_token = lti_session.mint_session_token(
        secret_key,
        user_claims,
        "" if show_picker else room_id,
    )

    base_url = str(request.base_url).rstrip("/")
    if show_picker:
        html = _PICKER_CHAT_PAGE.format(
            session_token=session_token,
            base_url=base_url,
            default_room_id=room_id,
        )
    else:
        html = _CHAT_PAGE.format(
            room_id=room_id,
            session_token=session_token,
            base_url=base_url,
        )

    return fastapi_responses.HTMLResponse(
        html,
        headers={
            "Content-Security-Policy": (f"frame-ancestors {platform.issuer}"),
        },
    )
