"""Soliplex authentication views"""

import dataclasses
import enum
import ipaddress
import pathlib
import secrets
import typing
from urllib import parse as urllib_parse

import fastapi
from authlib.integrations import starlette_client
from fastapi import responses
from mako import template as mako_template

from soliplex import authn
from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex import util
from soliplex import views
from soliplex.config import authsystem as config_authsystem

router = fastapi.APIRouter(tags=["authentication"])

depend_the_installation = installation.depend_the_installation
depend_the_user_claims = views.depend_the_user_claims
depend_the_unauth_logger = views.depend_the_unauth_logger
depend_the_logger = views.depend_the_logger


def _scheme_netloc(url: str) -> tuple[str, str]:
    scheme, netloc = urllib_parse.urlparse(url)[:2]
    return scheme, netloc.lower()


def _is_loopback(host: str) -> bool:
    """Is 'host' one browsers treat as the local machine?"""
    if host == "localhost" or host.endswith(".localhost"):
        return True

    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:  # a name, not an address literal
        return False


class ReturnTo(enum.StrEnum):
    MALFORMED = "malformed"
    UNLISTED = "unlisted"
    TRUSTED = "trusted"


# No backsplash, DEL, or control chars
_EVIL_CHARS = frozenset("\\\x7f") | {chr(i) for i in range(32)}

# No other non-relative schemes allowed.
_ALLOWED_SCHEMES = frozenset(("http", "https"))


def _classify_return_to(
    return_to: str,
    request: fastapi.Request,
    allowed_frontend_origins: list[str],
) -> ReturnTo:
    """Does the client-supplied 'return_to' belong an allowed origin?

    - relative paths
    - the request origin itself
    - one of the authsystem configs allowed origins
    """
    if (
        not return_to
        or _EVIL_CHARS & set(return_to)
        or return_to != return_to.strip()
    ):
        return ReturnTo.MALFORMED

    (scheme, netloc) = _scheme_netloc(return_to)

    if not scheme and not netloc:
        if return_to.startswith("/"):
            return ReturnTo.TRUSTED
        else:
            return ReturnTo.MALFORMED

    if scheme and not netloc:
        return ReturnTo.MALFORMED

    if scheme not in _ALLOWED_SCHEMES:
        return ReturnTo.MALFORMED

    trusted = {
        (request.url.scheme, request.url.netloc.lower()),
        *(_scheme_netloc(afo) for afo in allowed_frontend_origins),
    }

    if (scheme, netloc) in trusted:
        return ReturnTo.TRUSTED

    host = urllib_parse.urlsplit(return_to).hostname

    # 'http' but not in the 'trusted' check must only be loopback.
    if scheme == "http" and not _is_loopback(host):
        return ReturnTo.MALFORMED

    return ReturnTo.UNLISTED


CONSENT_TEMPLATE_FILENAME = "consent.html.mako"
_PACKAGED_CONSENT_TEMPLATE = (
    pathlib.Path(__file__).parent / "templates" / CONSENT_TEMPLATE_FILENAME
)

# No 'form-action': browsers apply it to the redirect which follows the
# form's POST, which would block the redirect to the IdP.
_CONSENT_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "frame-ancestors 'none'"
    ),
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
}


def _return_to_session_key(system: str) -> str:
    """Session key for the 'return_to' accepted for 'system'"""
    return f"soliplex.authn.{system}.return_to"


def _pending_session_key(system: str) -> str:
    """Session key for a sign-in awaiting the user's confirmation"""
    return f"soliplex.authn.{system}.pending"


def _display_origin(return_to: str) -> str:
    """Return the origin of 'return_to', for showing to the user

    Omit any userinfo, which could otherwise pose as the host, and show an
    internationalized host name in punycode.

    Raise 'ValueError' if the host is missing, or if it or the port cannot
    be shown.
    """
    parsed = urllib_parse.urlsplit(return_to)

    if not parsed.hostname:
        raise ValueError(return_to)

    try:
        host = parsed.hostname.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(return_to) from exc

    if ":" in host:  # IPv6 literal
        host = f"[{host}]"

    try:
        port = parsed.port
    except ValueError as exc:  # not an integer in range
        raise ValueError(return_to) from exc

    port = f":{port}" if port is not None else ""

    return f"{parsed.scheme}://{host}{port}"


def _consent_template_path(
    authsystem_config: config_authsystem.OIDCAuthSystemConfig,
) -> pathlib.Path:
    """Find the template for the page confirming an unlisted origin

    - the auth system's 'consent_template_path', if configured
    - else 'consent.html.mako' in the auth system's 'oidc' folder, if present
    - else the packaged default
    """
    if authsystem_config.consent_template_path is not None:
        return authsystem_config.consent_template_path

    in_oidc_folder = (
        authsystem_config._config_path.parent / CONSENT_TEMPLATE_FILENAME
    )

    if in_oidc_folder.is_file():
        return in_oidc_folder

    return _PACKAGED_CONSENT_TEMPLATE


def _render_template(template_path: pathlib.Path, **kwargs) -> str:
    template = mako_template.Template(
        filename=str(template_path),
        input_encoding="utf-8",
        default_filters=["h"],
        strict_undefined=True,
    )
    return template.render(**kwargs)


def _consent_response(
    *,
    authsystem_config: config_authsystem.OIDCAuthSystemConfig,
    logger: loggers.LogWrapper,
    **kwargs,
) -> responses.HTMLResponse:
    """Render the consent page, falling back to the packaged template"""
    template_path = _consent_template_path(authsystem_config)

    try:
        html = _render_template(template_path, **kwargs)
    except Exception:
        logger.exception(loggers.AUTHN_CONSENT_TEMPLATE_FAILED)
        html = _render_template(_PACKAGED_CONSENT_TEMPLATE, **kwargs)

    return responses.HTMLResponse(html, headers=_CONSENT_HEADERS)


def _bad_request(
    logger: loggers.LogWrapper, msg: str, **fields
) -> fastapi.HTTPException:
    logger.error(msg, **fields)
    return fastapi.HTTPException(status_code=400, detail=msg)


async def _redirect_to_idp(
    request: fastapi.Request,
    *,
    the_installation: installation.Installation,
    logger: loggers.LogWrapper,
    system: str,
    return_to: str,
    prompt: str | None,
):
    """Remember 'return_to' for the callback, and redirect to the IdP

    The 'redirect_uri' carries no query:  each auth system's client can
    register it exactly with the IdP.
    """
    request.session[_return_to_session_key(system)] = return_to

    redirect_uri = request.url_for("get_auth_system", system=system)
    redirect_uri = util.strip_default_port(redirect_uri)

    auth_params = {}
    if prompt is not None:
        auth_params["prompt"] = prompt

    oauth = authn.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    found = await oauth_app.authorize_redirect(
        request, redirect_uri, **auth_params
    )
    logger.debug(loggers.AUTHN_GET_LOGIN_SYSTEM)
    return found


@router.get("/login", summary="Get available OIDC auth providers")
async def get_login(
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
) -> models.ConfiguredOIDCAuthSystems:
    """Describe configured OIDC Authentication providers"""
    # Remove `_installation_config` to avoid infinite recursion
    the_unauth_logger.debug(loggers.AUTHN_GET_LOGIN)
    auth_system_copies = [
        dataclasses.replace(auth_system, _installation_config=None)
        for auth_system in the_installation.oidc_auth_system_configs
    ]

    return {
        auth_system.id: models.OIDCAuthSystem.from_config(auth_system)
        for auth_system in auth_system_copies
    }


@util.logfire_span("GET /login/{system}")
@router.get(
    "/login/{system}",
    summary="Initiate OIDC token auth flow with a provider",
)
async def get_login_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
):
    """Initiate token auth flow with the specified OIDC auth provider"""
    bound_logger = the_unauth_logger.bind(oidc_system=system)

    authsystem_config = authn._get_authsystem_config(
        the_installation=the_installation,
        logger=bound_logger,
        system=system,
    )

    return_to = request.query_params.get("return_to", "/")
    rt_status = _classify_return_to(
        return_to,
        request,
        authsystem_config.allowed_frontend_origins,
    )

    if rt_status is ReturnTo.MALFORMED:
        raise _bad_request(bound_logger, loggers.AUTHN_BAD_REQUEST)

    prompt = request.query_params.get("prompt")

    if rt_status is ReturnTo.TRUSTED:
        return await _redirect_to_idp(
            request,
            the_installation=the_installation,
            logger=bound_logger,
            system=system,
            return_to=return_to,
            prompt=prompt,
        )

    # ReturnTo.UNLISTED
    policy = authsystem_config.unlisted_frontend_origin

    if policy is config_authsystem.UnlistedFrontendOriginPolicy.DENY_ALL:
        raise _bad_request(
            bound_logger,
            loggers.AUTHN_UNLISTED_ORIGIN_DENIED,
            return_to=return_to,
        )

    try:
        origin = _display_origin(return_to)
    except ValueError:
        raise _bad_request(bound_logger, loggers.AUTHN_BAD_REQUEST) from None

    csrf_token = secrets.token_urlsafe(32)
    request.session[_pending_session_key(system)] = {
        "return_to": return_to,
        "prompt": prompt,
        "csrf_token": csrf_token,
    }
    bound_logger.info(loggers.AUTHN_CONSENT_REQUESTED, origin=origin)

    return _consent_response(
        authsystem_config=authsystem_config,
        logger=bound_logger,
        server_name=(
            the_installation._config.server_name or request.url.hostname
        ),
        auth_system_title=authsystem_config.title,
        origin=origin,
        form_action=str(
            request.url_for("post_login_system_confirm", system=system)
        ),
        csrf_token=csrf_token,
        cancelled=False,
    )


@util.logfire_span("POST /login/{system}/confirm")
@router.post(
    "/login/{system}/confirm",
    summary="Confirm or cancel sign-in for an unlisted frontend origin",
)
async def post_login_system_confirm(
    request: fastapi.Request,
    system: str,
    csrf_token: typing.Annotated[str, fastapi.Form()],
    decision: typing.Annotated[str, fastapi.Form()],
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
):
    """Act on the user's answer to the consent page

    The pending sign-in is consumed either way:  a replayed or stale form
    fails.
    """
    bound_logger = the_unauth_logger.bind(oidc_system=system)

    authsystem_config = authn._get_authsystem_config(
        the_installation=the_installation,
        logger=bound_logger,
        system=system,
    )

    pending = request.session.pop(_pending_session_key(system), None)

    if pending is None or not secrets.compare_digest(
        pending["csrf_token"], csrf_token
    ):
        raise _bad_request(bound_logger, loggers.AUTHN_CONSENT_INVALID)

    if decision == "continue":
        bound_logger.info(
            loggers.AUTHN_CONSENT_CONFIRMED,
            return_to=pending["return_to"],
        )
        return await _redirect_to_idp(
            request,
            the_installation=the_installation,
            logger=bound_logger,
            system=system,
            return_to=pending["return_to"],
            prompt=pending["prompt"],
        )

    if decision != "cancel":
        raise _bad_request(bound_logger, loggers.AUTHN_CONSENT_INVALID)

    bound_logger.info(
        loggers.AUTHN_CONSENT_CANCELLED,
        return_to=pending["return_to"],
    )

    # Never redirect to the unlisted origin, even without tokens.
    return _consent_response(
        authsystem_config=authsystem_config,
        logger=bound_logger,
        server_name=(
            the_installation._config.server_name or request.url.hostname
        ),
        auth_system_title=authsystem_config.title,
        origin=_display_origin(pending["return_to"]),
        form_action="",
        csrf_token="",
        cancelled=True,
    )


def _with_callback_params(return_to: str, params: dict) -> str:
    """Return 'return_to' with 'params' added to its fragment

    The parameters follow a '?' inside the fragment
    ('/#/auth/callback?token=...'), where the web client reads them;
    browsers do not send the fragment to the server.  'return_to' without
    a fragment gets one ('/#?token=...').  Any query string of
    'return_to' is kept unchanged.
    """
    base, _, fragment = return_to.partition("#")
    if "?" not in fragment:
        separator = "?"
    elif fragment.endswith(("?", "&")):
        separator = ""
    else:
        separator = "&"
    qs = urllib_parse.urlencode(params)
    return f"{base}#{fragment}{separator}{qs}"


@util.logfire_span("GET /auth/{system}")
@router.get(
    "/auth/{system}",
    summary="Complete token auth flow with an auth provider",
)
async def get_auth_system(
    request: fastapi.Request,
    system: str,
    the_installation: installation.Installation = depend_the_installation,
    the_unauth_logger: loggers.LogWrapper = depend_the_unauth_logger,
):
    """Complete the OIDC token auth flow with the specified provider

    On success, redirect to client-specified URL, passing 'token',
    'refresh_token', 'expires_in', and (when the provider returns one)
    'id_token' as callback parameters.
    """
    bound_logger = the_unauth_logger.bind(oidc_system=system)

    # For the side effect: 404 if 'system' is unknown or auth is disabled.
    authn._get_authsystem_config(
        the_installation=the_installation,
        logger=bound_logger,
        system=system,
    )

    # Stored by 'get_login_system' (or 'post_login_system_confirm') after
    # it was accepted:  never taken from the query string.
    return_to = request.session.pop(_return_to_session_key(system), None)

    if return_to is None:
        raise _bad_request(bound_logger, loggers.AUTHN_NO_RETURN_TO)

    oauth = authn.get_oauth(the_installation)
    oauth_app = oauth.create_client(system)

    try:
        tokendict = await oauth_app.authorize_access_token(request)
    except starlette_client.OAuthError:
        bound_logger.exception(loggers.AUTHN_JWT_INVALID)
        raise fastapi.HTTPException(
            status_code=401,
            detail=loggers.AUTHN_JWT_INVALID,
        ) from None

    access_token = tokendict["access_token"]

    try:
        authn.authenticate(the_installation, bound_logger, access_token)
    except fastapi.HTTPException:
        bound_logger.error(  # noqa: TRY400 'authenticate' logged details
            loggers.AUTHN_JWT_INVALID,
        )
        raise
    else:
        bound_logger.debug(loggers.AUTHN_JWT_VALID)

    refresh_token = tokendict["refresh_token"]
    expires_in = tokendict["expires_in"]

    callback_params = dict(
        token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    # Absent unless the configured scope includes 'openid'.
    id_token = tokendict.get("id_token")
    if id_token is not None:
        callback_params["id_token"] = id_token

    return_to = _with_callback_params(return_to, callback_params)

    return responses.RedirectResponse(return_to)


@util.logfire_span("GET /user_info")
@router.get("/user_info", summary="Get user profile")
async def get_user_info(
    the_installation: installation.Installation = depend_the_installation,
    the_user_claims: authn.UserClaims = depend_the_user_claims,
    the_logger: loggers.LogWrapper = depend_the_logger,
) -> models.UserProfile:
    """Return the profile of the authenticated user"""
    if the_installation.auth_disabled:
        the_logger.error(loggers.AUTHN_NO_AUTH_MODE)
        raise fastapi.HTTPException(
            status_code=404,
            detail=loggers.AUTHN_NO_AUTH_MODE,
        )

    the_logger.debug(loggers.AUTHN_GET_USER_INFO)
    return models.UserProfile.from_user_claims(the_user_claims)
