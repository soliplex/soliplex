from unittest import mock
from urllib import parse as urllib_parse

import fastapi
import pytest
from authlib.integrations import starlette_client
from fastapi import responses

from soliplex import installation
from soliplex import loggers
from soliplex import models
from soliplex.config import authsystem as config_authsystem
from soliplex.views import authn as authn_views

USER_NAME = "phreddy"
GIVEN_NAME = "Phred"
FAMILY_NAME = "Phlyntstone"
EMAIL = "phreddy@example.com"

AUTH_USER_CLAIMS = {
    "preferred_username": USER_NAME,
    "given_name": GIVEN_NAME,
    "family_name": FAMILY_NAME,
    "email": EMAIL,
}


REQUEST_URL = "http://test.example.com"
OTHER_ALLOWED_URL = "http://other.example.com"
BENIGN_ALLOWED_URL = "https://benign.example.com"


@pytest.mark.parametrize(
    "url, exp_scheme, exp_netloc",
    [
        ("", "", ""),
        ("/", "", ""),
        ("http://example.com", "http", "example.com"),
        ("http://example.COM", "http", "example.com"),
        ("https://Example.com", "https", "example.com"),
        (REQUEST_URL, "http", "test.example.com"),
        (OTHER_ALLOWED_URL, "http", "other.example.com"),
        (BENIGN_ALLOWED_URL, "https", "benign.example.com"),
    ],
)
def test__scheme_netloc(url, exp_scheme, exp_netloc):

    found_scheme, found_netloc = authn_views._scheme_netloc(url)

    assert found_scheme == exp_scheme
    assert found_netloc == exp_netloc


@pytest.mark.parametrize(
    "host, expected",
    [
        ("localhost", True),
        ("myapp.localhost", True),
        ("otherhost", False),
        ("127.0.0.1", True),
        ("127.8.9.10", True),
        ("::1", True),
        ("127.8", False),
    ],
)
def test__is_loopback(host, expected):

    found = authn_views._is_loopback(host)

    assert found is expected


_RT = authn_views.ReturnTo
_CONTROL_CHARS_MALFORMED = [(chr(i), _RT.MALFORMED) for i in range(32)]


@pytest.mark.parametrize(
    "return_to, expected",
    [
        ("", _RT.MALFORMED),
        (" /", _RT.MALFORMED),
        ("/ ", _RT.MALFORMED),
        ("/\foo", _RT.MALFORMED),  # backsplash hack
        ("\0x7F", _RT.MALFORMED),  # DEL
    ]
    + _CONTROL_CHARS_MALFORMED
    + [
        ("http://evil.example/", _RT.MALFORMED),
        ("evil.com", _RT.MALFORMED),
        ("http://127.1/", _RT.MALFORMED),
        ("foo/bar", _RT.MALFORMED),
        ("./x", _RT.MALFORMED),
        ("../x", _RT.MALFORMED),
        ("?x=1", _RT.MALFORMED),
        ("#/auth/callback", _RT.MALFORMED),
        ("ftp://example.com", _RT.MALFORMED),
        ("json:null", _RT.MALFORMED),
        ("http:evil.com", _RT.MALFORMED),
        ("https:evil.com", _RT.MALFORMED),
    ]
    + [
        ("http://localhost:9999/", _RT.UNLISTED),
        ("http://app.localhost:3000/", _RT.UNLISTED),
        ("http://127.0.0.1:9999/", _RT.UNLISTED),
        ("http://127.8.9.10/", _RT.UNLISTED),
        ("http://[::1]:9999/", _RT.UNLISTED),
        ("https://evil.example", _RT.UNLISTED),
        ("https://unlisted.example.com", _RT.UNLISTED),
    ]
    + [
        ("/", _RT.TRUSTED),
        ("/another/place", _RT.TRUSTED),
        ("/ask_me?anything=1", _RT.TRUSTED),
        ("/borken#yes", _RT.TRUSTED),
        (REQUEST_URL, _RT.TRUSTED),
        (f"{REQUEST_URL}/somewhere/else", _RT.TRUSTED),
        (OTHER_ALLOWED_URL, _RT.TRUSTED),
        (BENIGN_ALLOWED_URL, _RT.TRUSTED),
    ],
)
def test__classify_return_to(return_to, expected):
    request = mock.create_autospec(
        fastapi.Request,
        url=urllib_parse.urlparse(REQUEST_URL),
    )
    allowed_frontend_origins = [
        OTHER_ALLOWED_URL,
        BENIGN_ALLOWED_URL,
    ]

    found = authn_views._classify_return_to(
        return_to,
        request,
        allowed_frontend_origins,
    )

    assert found is expected


def raises_httpexc(match, code) -> pytest.raises:
    def _check(exc):
        return exc.status_code == code

    return pytest.raises(fastapi.HTTPException, match=match, check=_check)


@pytest.mark.anyio
async def test_get_login(with_auth_systems):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.oidc_auth_system_configs = with_auth_systems
    the_unauth_logger = mock.create_autospec(loggers.LogWrapper)

    found = await authn_views.get_login(
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    with_auth_systems_map = {asys.id: asys for asys in with_auth_systems}

    for (f_key, f_val), (e_key, e_val) in zip(
        sorted(found.items()),
        sorted(with_auth_systems_map.items()),
        strict=True,
    ):
        assert isinstance(f_val, models.OIDCAuthSystem)
        assert f_key == e_key
        assert f_val.title == e_val.title

    the_unauth_logger.debug.assert_called_once_with(loggers.AUTHN_GET_LOGIN)


DEFAULT_RETURN_TO = "/"
OTHER_RETURN_TO = "/another/path"
UNLISTED_RETURN_TO = "https://unlisted.example.com/#/auth/callback"
UNLISTED_ORIGIN = "https://unlisted.example.com"
TEST_PROMPT = "test prompt"
TEST_SYSTEM = "test_oauth_appname"
TEST_CSRF_TOKEN = "test-csrf-token"
TEST_SERVER_NAME = "Test Server"
TEST_AUTHSYSTEM_TITLE = "Test Auth System"
REQUEST_HOST = "test.example.com"
FORM_ACTION = "http://test.example.com/api/login/test_oauth_appname/confirm"
UFOP = config_authsystem.UnlistedFrontendOriginPolicy
RETURN_TO_KEY = f"soliplex.authn.{TEST_SYSTEM}.return_to"
PENDING_KEY = f"soliplex.authn.{TEST_SYSTEM}.pending"
_raises_badrequest = raises_httpexc(loggers.AUTHN_BAD_REQUEST, 400)

HOSTILE_KW = {
    "server_name": "Soli<b>plex",
    "auth_system_title": "Keycloak & co",
    "origin": 'https://evil-"><script>.example',
    "form_action": FORM_ACTION,
    "csrf_token": 'tok"en',
}


def _make_request(query: dict | None = None, session: dict | None = None):
    return fastapi.Request(
        scope={
            "type": "http",
            "scheme": "http",
            "server": (REQUEST_HOST, 80),
            "path": f"/api/login/{TEST_SYSTEM}",
            "headers": [(b"host", REQUEST_HOST.encode("ascii"))],
            "query_string": urllib_parse.urlencode(query or {}).encode(),
            "session": {} if session is None else session,
        }
    )


def _make_authsystem_config(temp_dir, **kwargs):
    return config_authsystem.OIDCAuthSystemConfig(
        id=TEST_SYSTEM,
        title=TEST_AUTHSYSTEM_TITLE,
        server_url="https://idp.example.com/realms/test",
        token_validation_pem="PEM",
        client_id="test-client",
        _config_path=temp_dir / "config.yaml",
        **kwargs,
    )


def test__return_to_session_key():
    found = authn_views._return_to_session_key(TEST_SYSTEM)

    assert found == RETURN_TO_KEY


def test__pending_session_key():
    found = authn_views._pending_session_key(TEST_SYSTEM)

    assert found == PENDING_KEY


@pytest.mark.parametrize(
    "return_to, expected",
    [
        ("https://example.com/path?q=1#frag", "https://example.com"),
        ("https://user:pw@example.com/", "https://example.com"),
        ("https://allowed.example@evil.example/", "https://evil.example"),
        ("https://EXAMPLE.com:8443/", "https://example.com:8443"),
        ("https://bücher.example/", "https://xn--bcher-kva.example"),
        ("http://[::1]:8080/", "http://[::1]:8080"),
    ],
)
def test__display_origin(return_to, expected):
    found = authn_views._display_origin(return_to)

    assert found == expected


@pytest.mark.parametrize(
    "return_to",
    [
        "https:evil.example",
        "https://example.com:notaport/",
        "https://example.com:99999/",
        "https://a..b/",
        f"https://{'x' * 64}.example/",
    ],
)
def test__display_origin_raises(return_to):
    with pytest.raises(ValueError, match="https"):
        authn_views._display_origin(return_to)


@pytest.mark.parametrize(
    "w_configured, w_in_oidc_folder, exp_name",
    [
        (False, False, "packaged"),
        (False, True, "in_oidc_folder"),
        (True, False, "configured"),
        (True, True, "configured"),
    ],
)
def test__consent_template_path(
    temp_dir,
    w_configured,
    w_in_oidc_folder,
    exp_name,
):
    configured = temp_dir / "elsewhere.html.mako"
    in_oidc_folder = temp_dir / authn_views.CONSENT_TEMPLATE_FILENAME
    if w_in_oidc_folder:
        in_oidc_folder.write_text("in folder", encoding="utf-8")
    asc = _make_authsystem_config(
        temp_dir,
        consent_template_path=configured if w_configured else None,
    )
    exp_path = {
        "packaged": authn_views._PACKAGED_CONSENT_TEMPLATE,
        "in_oidc_folder": in_oidc_folder,
        "configured": configured,
    }[exp_name]

    found = authn_views._consent_template_path(asc)

    assert found == exp_path


def test__render_template_escapes(temp_dir):
    template_path = temp_dir / "t.html.mako"
    template_path.write_text("<p>${origin}</p>", encoding="utf-8")

    found = authn_views._render_template(template_path, origin="<script>")

    assert found == "<p>&lt;script&gt;</p>"


def test__render_template_strict_undefined(temp_dir):
    template_path = temp_dir / "t.html.mako"
    template_path.write_text("<p>${origin}</p>", encoding="utf-8")

    with pytest.raises(NameError, match="origin"):
        authn_views._render_template(template_path)


@pytest.mark.parametrize("w_cancelled", [False, True])
def test__render_template_packaged(w_cancelled):
    found = authn_views._render_template(
        authn_views._PACKAGED_CONSENT_TEMPLATE,
        cancelled=w_cancelled,
        **HOSTILE_KW,
    )

    assert found.startswith("<!doctype html>")
    assert "<script>" not in found
    assert "Soli&lt;b&gt;plex" in found
    assert ("Sign-in cancelled" in found) is w_cancelled
    assert ('value="tok&#34;en"' in found) is not w_cancelled


@pytest.mark.parametrize(
    "template_text, exp_html, exp_logged",
    [
        ("<p>${origin}</p>", "<p>ORIGIN</p>", False),
        ("<p>${nonesuch}</p>", None, True),
        ("<p>${origin</p>", None, True),
    ],
)
def test__consent_response(temp_dir, template_text, exp_html, exp_logged):
    template_path = temp_dir / "consent.html.mako"
    template_path.write_text(template_text, encoding="utf-8")
    asc = _make_authsystem_config(
        temp_dir, consent_template_path=template_path
    )
    logger = mock.create_autospec(loggers.LogWrapper)
    kwargs = HOSTILE_KW | {"origin": "ORIGIN", "cancelled": False}
    if exp_html is None:
        exp_html = authn_views._render_template(
            authn_views._PACKAGED_CONSENT_TEMPLATE, **kwargs
        )

    found = authn_views._consent_response(
        authsystem_config=asc,
        logger=logger,
        **kwargs,
    )

    assert isinstance(found, responses.HTMLResponse)
    assert found.body.decode("utf-8") == exp_html
    for key, value in authn_views._CONSENT_HEADERS.items():
        assert found.headers[key] == value
    assert "form-action" not in found.headers["content-security-policy"]
    if exp_logged:
        logger.exception.assert_called_once_with(
            loggers.AUTHN_CONSENT_TEMPLATE_FAILED
        )
    else:
        logger.exception.assert_not_called()


def test__bad_request():
    logger = mock.create_autospec(loggers.LogWrapper)

    found = authn_views._bad_request(logger, "testing", extra_field="value")

    assert isinstance(found, fastapi.HTTPException)
    assert found.status_code == 400
    assert found.detail == "testing"
    logger.error.assert_called_once_with("testing", extra_field="value")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "prompt, exp_auth_params",
    [
        (None, {}),
        (TEST_PROMPT, {"prompt": TEST_PROMPT}),
    ],
)
@mock.patch("soliplex.util.strip_default_port")
@mock.patch("soliplex.authn.get_oauth")
async def test__redirect_to_idp(
    get_oauth,
    strip_default_port,
    prompt,
    exp_auth_params,
):
    the_installation = mock.create_autospec(installation.Installation)
    logger = mock.create_autospec(loggers.LogWrapper)
    cc = get_oauth.return_value.create_client
    ar = cc.return_value.authorize_redirect = mock.AsyncMock()
    request = _make_request()
    ruf = request.url_for = mock.Mock(spec_set=())

    found = await authn_views._redirect_to_idp(
        request,
        the_installation=the_installation,
        logger=logger,
        system=TEST_SYSTEM,
        return_to=OTHER_RETURN_TO,
        prompt=prompt,
    )

    assert found is ar.return_value
    assert request.session == {RETURN_TO_KEY: OTHER_RETURN_TO}
    ruf.assert_called_once_with("get_auth_system", system=TEST_SYSTEM)
    # No 'return_to' query on the 'redirect_uri':  it is registered exactly.
    strip_default_port.assert_called_once_with(ruf.return_value)
    ar.assert_awaited_once_with(
        request,
        strip_default_port.return_value,
        **exp_auth_params,
    )
    get_oauth.assert_called_once_with(the_installation)
    cc.assert_called_once_with(TEST_SYSTEM)
    logger.debug.assert_called_once_with(loggers.AUTHN_GET_LOGIN_SYSTEM)


@pytest.fixture
def the_unauth_logger():
    return mock.create_autospec(loggers.LogWrapper)


@pytest.fixture
def login_asc():
    asc = mock.create_autospec(config_authsystem.OIDCAuthSystemConfig)
    asc.title = TEST_AUTHSYSTEM_TITLE
    asc.allowed_frontend_origins = []
    asc.unlisted_frontend_origin = UFOP.CONSENT_REQUIRED
    return asc


@pytest.mark.anyio
@mock.patch("soliplex.views.authn._redirect_to_idp")
@mock.patch("soliplex.views.authn._classify_return_to")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_login_system_malformed(
    _get_authsystem_config,
    _classify_return_to,
    _redirect_to_idp,
    the_unauth_logger,
    login_asc,
):
    _get_authsystem_config.return_value = login_asc
    _classify_return_to.return_value = _RT.MALFORMED
    request = _make_request({"return_to": "//evil.com"})

    with _raises_badrequest:
        await authn_views.get_login_system(
            request=request,
            system=TEST_SYSTEM,
            the_installation=mock.create_autospec(installation.Installation),
            the_unauth_logger=the_unauth_logger,
        )

    assert request.session == {}
    _redirect_to_idp.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_qs_dict, exp_return_to, exp_prompt",
    [
        ({}, DEFAULT_RETURN_TO, None),
        ({"return_to": OTHER_RETURN_TO}, OTHER_RETURN_TO, None),
        ({"prompt": TEST_PROMPT}, DEFAULT_RETURN_TO, TEST_PROMPT),
        (
            {"return_to": OTHER_RETURN_TO, "prompt": TEST_PROMPT},
            OTHER_RETURN_TO,
            TEST_PROMPT,
        ),
    ],
)
@mock.patch("soliplex.views.authn._redirect_to_idp")
@mock.patch("soliplex.views.authn._classify_return_to")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_login_system_trusted(
    _get_authsystem_config,
    _classify_return_to,
    _redirect_to_idp,
    the_unauth_logger,
    login_asc,
    w_qs_dict,
    exp_return_to,
    exp_prompt,
):
    the_installation = mock.create_autospec(installation.Installation)
    bound_logger = the_unauth_logger.bind.return_value
    _get_authsystem_config.return_value = login_asc
    _classify_return_to.return_value = _RT.TRUSTED
    request = _make_request(w_qs_dict)

    found = await authn_views.get_login_system(
        request=request,
        system=TEST_SYSTEM,
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert found is _redirect_to_idp.return_value
    _redirect_to_idp.assert_awaited_once_with(
        request,
        the_installation=the_installation,
        logger=bound_logger,
        system=TEST_SYSTEM,
        return_to=exp_return_to,
        prompt=exp_prompt,
    )
    _classify_return_to.assert_called_once_with(
        exp_return_to,
        request,
        login_asc.allowed_frontend_origins,
    )
    _get_authsystem_config.assert_called_once_with(
        the_installation=the_installation,
        logger=bound_logger,
        system=TEST_SYSTEM,
    )
    the_unauth_logger.bind.assert_called_once_with(oidc_system=TEST_SYSTEM)


@pytest.mark.anyio
@mock.patch("soliplex.views.authn._consent_response")
@mock.patch("soliplex.views.authn._classify_return_to")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_login_system_unlisted_denied(
    _get_authsystem_config,
    _classify_return_to,
    _consent_response,
    the_unauth_logger,
    login_asc,
):
    bound_logger = the_unauth_logger.bind.return_value
    login_asc.unlisted_frontend_origin = UFOP.DENY_ALL
    _get_authsystem_config.return_value = login_asc
    _classify_return_to.return_value = _RT.UNLISTED
    request = _make_request({"return_to": UNLISTED_RETURN_TO})

    with raises_httpexc(loggers.AUTHN_UNLISTED_ORIGIN_DENIED, 400):
        await authn_views.get_login_system(
            request=request,
            system=TEST_SYSTEM,
            the_installation=mock.create_autospec(installation.Installation),
            the_unauth_logger=the_unauth_logger,
        )

    assert request.session == {}
    _consent_response.assert_not_called()
    bound_logger.error.assert_called_once_with(
        loggers.AUTHN_UNLISTED_ORIGIN_DENIED,
        return_to=UNLISTED_RETURN_TO,
    )


@pytest.mark.anyio
@mock.patch("soliplex.views.authn._consent_response")
@mock.patch("soliplex.views.authn._classify_return_to")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_login_system_unlisted_undisplayable(
    _get_authsystem_config,
    _classify_return_to,
    _consent_response,
    the_unauth_logger,
    login_asc,
):
    _get_authsystem_config.return_value = login_asc
    _classify_return_to.return_value = _RT.UNLISTED
    request = _make_request({"return_to": "https:evil.example"})

    with _raises_badrequest:
        await authn_views.get_login_system(
            request=request,
            system=TEST_SYSTEM,
            the_installation=mock.create_autospec(installation.Installation),
            the_unauth_logger=the_unauth_logger,
        )

    assert request.session == {}
    _consent_response.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_server_name, exp_server_name",
    [
        (None, REQUEST_HOST),
        (TEST_SERVER_NAME, TEST_SERVER_NAME),
    ],
)
@mock.patch("secrets.token_urlsafe", return_value=TEST_CSRF_TOKEN)
@mock.patch("soliplex.views.authn._consent_response")
@mock.patch("soliplex.views.authn._classify_return_to")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_login_system_unlisted_consent(
    _get_authsystem_config,
    _classify_return_to,
    _consent_response,
    token_urlsafe,
    the_unauth_logger,
    login_asc,
    w_server_name,
    exp_server_name,
):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation._config = mock.Mock(server_name=w_server_name)
    bound_logger = the_unauth_logger.bind.return_value
    _get_authsystem_config.return_value = login_asc
    _classify_return_to.return_value = _RT.UNLISTED
    request = _make_request(
        {"return_to": UNLISTED_RETURN_TO, "prompt": TEST_PROMPT}
    )
    ruf = request.url_for = mock.Mock(return_value=FORM_ACTION)

    found = await authn_views.get_login_system(
        request=request,
        system=TEST_SYSTEM,
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert found is _consent_response.return_value
    assert request.session == {
        PENDING_KEY: {
            "return_to": UNLISTED_RETURN_TO,
            "prompt": TEST_PROMPT,
            "csrf_token": TEST_CSRF_TOKEN,
        },
    }
    _consent_response.assert_called_once_with(
        authsystem_config=login_asc,
        logger=bound_logger,
        server_name=exp_server_name,
        auth_system_title=TEST_AUTHSYSTEM_TITLE,
        origin=UNLISTED_ORIGIN,
        form_action=FORM_ACTION,
        csrf_token=TEST_CSRF_TOKEN,
        cancelled=False,
    )
    ruf.assert_called_once_with(
        "post_login_system_confirm", system=TEST_SYSTEM
    )
    token_urlsafe.assert_called_once_with(32)
    bound_logger.info.assert_called_once_with(
        loggers.AUTHN_CONSENT_REQUESTED,
        origin=UNLISTED_ORIGIN,
    )


PENDING = {
    "return_to": UNLISTED_RETURN_TO,
    "prompt": TEST_PROMPT,
    "csrf_token": TEST_CSRF_TOKEN,
}


@pytest.mark.anyio
@pytest.mark.parametrize(
    "w_session, w_csrf_token, w_decision",
    [
        pytest.param({}, TEST_CSRF_TOKEN, "continue", id="no-pending"),
        pytest.param(
            {PENDING_KEY: PENDING}, "wrong-token", "continue", id="bad-token"
        ),
        pytest.param(
            {PENDING_KEY: PENDING}, TEST_CSRF_TOKEN, "bogus", id="bad-decision"
        ),
    ],
)
@mock.patch("soliplex.views.authn._consent_response")
@mock.patch("soliplex.views.authn._redirect_to_idp")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_post_login_system_confirm_invalid(
    _get_authsystem_config,
    _redirect_to_idp,
    _consent_response,
    the_unauth_logger,
    login_asc,
    w_session,
    w_csrf_token,
    w_decision,
):
    _get_authsystem_config.return_value = login_asc
    request = _make_request(session=dict(w_session))

    with raises_httpexc(loggers.AUTHN_CONSENT_INVALID, 400):
        await authn_views.post_login_system_confirm(
            request=request,
            system=TEST_SYSTEM,
            csrf_token=w_csrf_token,
            decision=w_decision,
            the_installation=mock.create_autospec(installation.Installation),
            the_unauth_logger=the_unauth_logger,
        )

    # Consumed even when the confirmation fails:  no replay.
    assert request.session == {}
    _redirect_to_idp.assert_not_called()
    _consent_response.assert_not_called()


@pytest.mark.anyio
@mock.patch("soliplex.views.authn._redirect_to_idp")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_post_login_system_confirm_continue(
    _get_authsystem_config,
    _redirect_to_idp,
    the_unauth_logger,
    login_asc,
):
    the_installation = mock.create_autospec(installation.Installation)
    bound_logger = the_unauth_logger.bind.return_value
    _get_authsystem_config.return_value = login_asc
    request = _make_request(session={PENDING_KEY: dict(PENDING)})

    found = await authn_views.post_login_system_confirm(
        request=request,
        system=TEST_SYSTEM,
        csrf_token=TEST_CSRF_TOKEN,
        decision="continue",
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert found is _redirect_to_idp.return_value
    assert PENDING_KEY not in request.session
    _redirect_to_idp.assert_awaited_once_with(
        request,
        the_installation=the_installation,
        logger=bound_logger,
        system=TEST_SYSTEM,
        return_to=UNLISTED_RETURN_TO,
        prompt=TEST_PROMPT,
    )
    bound_logger.info.assert_called_once_with(
        loggers.AUTHN_CONSENT_CONFIRMED,
        return_to=UNLISTED_RETURN_TO,
    )


@pytest.mark.anyio
@mock.patch("soliplex.views.authn._consent_response")
@mock.patch("soliplex.views.authn._redirect_to_idp")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_post_login_system_confirm_cancel(
    _get_authsystem_config,
    _redirect_to_idp,
    _consent_response,
    the_unauth_logger,
    login_asc,
):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation._config = mock.Mock(server_name=TEST_SERVER_NAME)
    bound_logger = the_unauth_logger.bind.return_value
    _get_authsystem_config.return_value = login_asc
    request = _make_request(session={PENDING_KEY: dict(PENDING)})

    found = await authn_views.post_login_system_confirm(
        request=request,
        system=TEST_SYSTEM,
        csrf_token=TEST_CSRF_TOKEN,
        decision="cancel",
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert found is _consent_response.return_value
    assert request.session == {}
    _redirect_to_idp.assert_not_called()
    _consent_response.assert_called_once_with(
        authsystem_config=login_asc,
        logger=bound_logger,
        server_name=TEST_SERVER_NAME,
        auth_system_title=TEST_AUTHSYSTEM_TITLE,
        origin=UNLISTED_ORIGIN,
        form_action="",
        csrf_token="",
        cancelled=True,
    )
    bound_logger.info.assert_called_once_with(
        loggers.AUTHN_CONSENT_CANCELLED,
        return_to=UNLISTED_RETURN_TO,
    )


@pytest.mark.parametrize(
    "return_to, exp_url",
    [
        ("/", "/#?a=1&b=two"),
        ("/path", "/path#?a=1&b=two"),
        ("/path?q=x", "/path?q=x#?a=1&b=two"),
        ("/#", "/#?a=1&b=two"),
        ("/#/auth/callback", "/#/auth/callback?a=1&b=two"),
        ("/?q=x#/auth/callback", "/?q=x#/auth/callback?a=1&b=two"),
        ("/#/auth/callback?", "/#/auth/callback?a=1&b=two"),
        ("/#/auth/callback?c=3", "/#/auth/callback?c=3&a=1&b=two"),
        ("/#/auth/callback?c=3&", "/#/auth/callback?c=3&a=1&b=two"),
        (
            "https://example.com/#/auth/callback",
            "https://example.com/#/auth/callback?a=1&b=two",
        ),
    ],
)
def test__with_callback_params(return_to, exp_url):
    params = {"a": "1", "b": "two"}

    found = authn_views._with_callback_params(return_to, params)

    assert found == exp_url


TOKENDICT = {
    "access_token": "TOKEN",
    "refresh_token": "RTOKEN",
    "expires_in": "EXPIRES_IN",
}
EXP_QS = "token=TOKEN&refresh_token=RTOKEN&expires_in=EXPIRES_IN"
TOKENDICT_W_ID_TOKEN = {**TOKENDICT, "id_token": "IDTOKEN"}
EXP_QS_W_ID_TOKEN = f"{EXP_QS}&id_token=IDTOKEN"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "return_to, exp_location",
    [
        pytest.param(DEFAULT_RETURN_TO, f"/#?{EXP_QS}", id="default"),
        pytest.param(OTHER_RETURN_TO, f"/another/path#?{EXP_QS}", id="path"),
        pytest.param(
            "/#/authn/callback", f"/#/authn/callback?{EXP_QS}", id="hash"
        ),
        pytest.param(
            UNLISTED_RETURN_TO,
            f"{UNLISTED_ORIGIN}/#/auth/callback?{EXP_QS}",
            id="absolute-w-hash",
        ),
    ],
)
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_auth_system(
    _get_authsystem_config,
    auth_fn,
    get_oauth,
    the_unauth_logger,
    return_to,
    exp_location,
):
    the_installation = mock.create_autospec(installation.Installation)
    bound_logger = the_unauth_logger.bind.return_value
    cc = get_oauth.return_value.create_client
    aat = cc.return_value.authorize_access_token = mock.AsyncMock(
        return_value=TOKENDICT,
    )
    # A 'return_to' in the query string is ignored.
    request = _make_request(
        {"return_to": "https://evil.example/"},
        session={RETURN_TO_KEY: return_to},
    )

    response = await authn_views.get_auth_system(
        request=request,
        system=TEST_SYSTEM,
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert isinstance(response, responses.RedirectResponse)
    assert response.status_code == 307
    assert response.headers["location"] == exp_location
    assert request.session == {}
    aat.assert_awaited_once_with(request)
    auth_fn.assert_called_once_with(the_installation, bound_logger, "TOKEN")
    cc.assert_called_once_with(TEST_SYSTEM)
    bound_logger.debug.assert_called_once_with(loggers.AUTHN_JWT_VALID)
    _get_authsystem_config.assert_called_once_with(
        the_installation=the_installation,
        logger=bound_logger,
        system=TEST_SYSTEM,
    )
    the_unauth_logger.bind.assert_called_once_with(oidc_system=TEST_SYSTEM)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "tokendict, exp_location",
    [
        pytest.param(TOKENDICT, f"/#?{EXP_QS}", id="wo_id_token"),
        pytest.param(
            TOKENDICT_W_ID_TOKEN, f"/#?{EXP_QS_W_ID_TOKEN}", id="w_id_token"
        ),
    ],
)
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_auth_system_id_token(
    _get_authsystem_config,
    auth_fn,
    get_oauth,
    the_unauth_logger,
    tokendict,
    exp_location,
):
    the_installation = mock.create_autospec(installation.Installation)
    cc = get_oauth.return_value.create_client
    cc.return_value.authorize_access_token = mock.AsyncMock(
        return_value=tokendict,
    )
    request = _make_request(session={RETURN_TO_KEY: DEFAULT_RETURN_TO})

    response = await authn_views.get_auth_system(
        request=request,
        system=TEST_SYSTEM,
        the_installation=the_installation,
        the_unauth_logger=the_unauth_logger,
    )

    assert response.headers["location"] == exp_location


@pytest.mark.anyio
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_auth_system_wo_session_return_to(
    _get_authsystem_config,
    get_oauth,
    the_unauth_logger,
):
    request = _make_request({"return_to": OTHER_RETURN_TO})

    with raises_httpexc(loggers.AUTHN_NO_RETURN_TO, 400):
        await authn_views.get_auth_system(
            request=request,
            system=TEST_SYSTEM,
            the_installation=mock.create_autospec(installation.Installation),
            the_unauth_logger=the_unauth_logger,
        )

    # The authorization code is never exchanged, so no tokens exist.
    get_oauth.assert_not_called()


@pytest.mark.anyio
@pytest.mark.parametrize("w_error", ["aat", "authenticate"])
@mock.patch("soliplex.authn.get_oauth")
@mock.patch("soliplex.authn.authenticate")
@mock.patch("soliplex.authn._get_authsystem_config")
async def test_get_auth_system_w_error(
    _get_authsystem_config,
    auth_fn,
    get_oauth,
    the_unauth_logger,
    w_error,
):
    the_installation = mock.create_autospec(installation.Installation)
    bound_logger = the_unauth_logger.bind.return_value
    aat = (
        get_oauth.return_value.create_client.return_value.authorize_access_token
    ) = mock.AsyncMock(  # noqa: E501
        return_value=TOKENDICT,
    )
    if w_error == "aat":
        aat.side_effect = starlette_client.OAuthError("testing")
    else:
        auth_fn.side_effect = fastapi.HTTPException(status_code=401)
    request = _make_request(session={RETURN_TO_KEY: OTHER_RETURN_TO})

    with raises_httpexc(None, 401):
        await authn_views.get_auth_system(
            request=request,
            system=TEST_SYSTEM,
            the_installation=the_installation,
            the_unauth_logger=the_unauth_logger,
        )

    if w_error == "aat":
        bound_logger.exception.assert_called_once_with(
            loggers.AUTHN_JWT_INVALID
        )
    else:  # Details logged by 'authenticate'
        bound_logger.error.assert_called_once_with(loggers.AUTHN_JWT_INVALID)


@pytest.mark.anyio
@pytest.mark.parametrize("w_auth_disabled", [False, True])
async def test_get_user_info(w_auth_disabled):
    the_installation = mock.create_autospec(installation.Installation)
    the_installation.auth_disabled = w_auth_disabled
    the_logger = mock.create_autospec(loggers.LogWrapper)

    if w_auth_disabled:
        with pytest.raises(fastapi.HTTPException) as exc:
            await authn_views.get_user_info(
                the_installation=the_installation,
                the_user_claims=AUTH_USER_CLAIMS,
                the_logger=the_logger,
            )

        assert exc.value.status_code == 404
        assert exc.value.detail == loggers.AUTHN_NO_AUTH_MODE

        the_logger.error.assert_called_once_with(loggers.AUTHN_NO_AUTH_MODE)

    else:
        found = await authn_views.get_user_info(
            the_installation=the_installation,
            the_user_claims=AUTH_USER_CLAIMS,
            the_logger=the_logger,
        )

        assert found == models.UserProfile(**AUTH_USER_CLAIMS)

        the_logger.debug.assert_called_once_with(loggers.AUTHN_GET_USER_INFO)
