"""LTI 1.3 External Tool Provider views"""

from __future__ import annotations

import json
import urllib.parse

import fastapi
from fastapi import responses as fastapi_responses

from soliplex import installation
from soliplex import loggers
from soliplex.lti import nonce as lti_nonce
from soliplex.lti import platform as lti_platform
from soliplex.lti import session as lti_session
from soliplex.lti import validation as lti_validation

router = fastapi.APIRouter(prefix="/lti", tags=["lti"])

depend_the_installation = installation.depend_the_installation


def _embed_safe_json(payload: dict) -> str:
    """Serialise *payload* for safe embedding in an HTML <script> tag.

    The ``</`` -> ``<\\/`` rewrite prevents a ``</script>`` substring
    from ever appearing inside the JSON block and terminating the
    enclosing tag prematurely. JSON consumers ignore the backslash
    inside string literals, so the parsed value is unchanged.
    """
    return json.dumps(payload).replace("</", "<\\/")


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

    if not lti_nonce.consume_nonce(nonce):
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_NONCE_REPLAY,
        )

    lti_platforms = the_installation.lti_platform_configs
    platform = lti_platform.find_platform_by_id(lti_platforms, platform_id)

    if platform is None:
        raise fastapi.HTTPException(
            status_code=400,
            detail=loggers.LTI_UNKNOWN_PLATFORM,
        )

    try:
        payload = await lti_validation.validate_id_token(
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
        platform.id,
    )

    base_url = str(request.base_url).rstrip("/")
    if show_picker:
        config_json = _embed_safe_json(
            {
                "token": session_token,
                "base": base_url,
                "default_room": room_id,
            }
        )
        html = _PICKER_CHAT_PAGE.format(config_json=config_json)
    else:
        config_json = _embed_safe_json(
            {
                "room": room_id,
                "token": session_token,
                "base": base_url,
            }
        )
        html = _CHAT_PAGE.format(config_json=config_json)

    # CSP: defence-in-depth around the iframe-embedded chat page.
    # 'unsafe-inline' is required today because all <script>/<style>
    # blocks are inline; a follow-up could introduce per-request CSP
    # nonces to drop that. cdn.jsdelivr.net is allowed for marked.js
    # only, and the script tag carries an SRI hash (see _MARKED_CDN).
    csp = "; ".join(
        [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
            "style-src 'self' 'unsafe-inline'",
            "connect-src 'self'",
            "img-src 'self' data:",
            f"frame-ancestors {platform.issuer}",
        ]
    )
    return fastapi_responses.HTMLResponse(
        html,
        headers={"Content-Security-Policy": csp},
    )


# ----------------------------------------------------------------
#   HTML / CSS / JS templates (inline, served by the routes above)
# ----------------------------------------------------------------


_CHAT_STYLES = """\
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:system-ui,sans-serif;height:100vh;
  display:flex;flex-direction:column;background:#fafafa}}
#chat{{flex:1;display:flex;flex-direction:column;min-height:0}}
#room-header{{padding:.5rem 1rem;background:#fff;
  border-bottom:1px solid #e0e0e0;font-weight:600;
  color:#333;font-size:.9rem;display:none}}
#msgs{{flex:1;overflow-y:auto;padding:1rem}}
.m{{margin:.5rem 0;padding:.75rem 1rem;border-radius:.75rem;
  max-width:80%;word-wrap:break-word;line-height:1.5}}
.m.u{{background:#0070f3;color:#fff;margin-left:auto;
  white-space:pre-wrap}}
.m.a{{background:#fff;border:1px solid #e0e0e0}}
.m.a.s{{opacity:.7}}
.m.err{{background:#fee;border:1px solid #c00;color:#900}}
.m.a table{{border-collapse:collapse;width:100%;margin:.5rem 0;
  font-size:.85rem}}
.m.a th,.m.a td{{border:1px solid #ddd;padding:.4rem .6rem;
  text-align:left}}
.m.a th{{background:#f5f5f5;font-weight:600}}
.m.a code{{background:#f5f5f5;padding:.15rem .35rem;
  border-radius:.25rem;font-size:.85em}}
.m.a pre{{background:#f5f5f5;padding:.75rem;border-radius:.5rem;
  overflow-x:auto;margin:.5rem 0}}
.m.a pre code{{background:none;padding:0}}
.m.a p{{margin:.4rem 0}}
.m.a ul,.m.a ol{{margin:.4rem 0;padding-left:1.5rem}}
#bar{{display:flex;padding:.5rem;border-top:1px solid #e0e0e0;
  gap:.5rem;background:#fff}}
#bar input{{flex:1;padding:.6rem;border:1px solid #ccc;
  border-radius:.5rem;font-size:.95rem}}
#bar button{{padding:.6rem 1.2rem;background:#0070f3;color:#fff;
  border:none;border-radius:.5rem;cursor:pointer;
  font-size:.95rem}}
#bar button:disabled{{opacity:.5;cursor:not-allowed}}
"""

_CHAT_BODY = """\
<div id="room-header"></div>
<div id="msgs"></div>
<div id="bar">
  <input id="txt" type="text"
         placeholder="Ask something…"
         autocomplete="off" />
  <button id="btn" onclick="send()">Send</button>
</div>
"""

_CHAT_SCRIPT = """\
let threadId = null;
let currentRunId = null;
let agState = {{}};
let messages = [];
let userSeq = 0;
let asstSeq = 0;
let busy = false;

function renderMd(text) {{
  if (typeof marked !== "undefined") {{
    return marked.parse(text);
  }}
  const d = document.createElement("div");
  d.textContent = text;
  return d.innerHTML;
}}

function addEl(cls, text, id) {{
  const c = document.getElementById("msgs");
  let el = id ? document.getElementById(id) : null;
  if (!el) {{
    el = document.createElement("div");
    el.className = "m " + cls;
    if (id) el.id = id;
    c.appendChild(el);
  }}
  if (cls.includes("u") || cls.includes("err")) {{
    el.textContent = text;
  }} else {{
    el.innerHTML = renderMd(text);
  }}
  c.scrollTop = c.scrollHeight;
  return el;
}}

function setEnabled(v) {{
  busy = !v;
  document.getElementById("btn").disabled = !v;
  document.getElementById("txt").disabled = !v;
}}

async function api(path, body) {{
  const r = await fetch(BASE + "/api/v1/rooms/" + ROOM + path, {{
    method: "POST",
    headers: {{
      "Authorization": "Bearer " + TOKEN,
      "Content-Type": "application/json"
    }},
    body: JSON.stringify(body)
  }});
  if (!r.ok) throw new Error("HTTP " + r.status);
  return r;
}}

async function ensureThread() {{
  if (threadId) return;
  const r = await api("/agui", {{}});
  const d = await r.json();
  threadId = d.thread_id;
  const runIds = Object.keys(d.runs);
  currentRunId = runIds[0];
  const ri = d.runs[currentRunId].run_input;
  if (ri && ri.state) agState = ri.state;
}}

async function createRun() {{
  const r = await api("/agui/" + threadId, {{}});
  const d = await r.json();
  currentRunId = d.run_id;
}}

async function send() {{
  if (busy) return;
  const input = document.getElementById("txt");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  setEnabled(false);

  try {{
    await ensureThread();

    userSeq++;
    const uid = "user_" + String(userSeq).padStart(3, "0");
    messages.push({{id: uid, role: "user", content: text}});
    addEl("u", text);

    if (userSeq > 1) await createRun();

    const mid = "ai-" + currentRunId;
    const el = addEl("a s", "…", mid);
    let acc = "";

    const resp = await fetch(
      BASE + "/api/v1/rooms/" + ROOM
        + "/agui/" + threadId + "/" + currentRunId,
      {{
        method: "POST",
        headers: {{
          "Authorization": "Bearer " + TOKEN,
          "Content-Type": "application/json"
        }},
        body: JSON.stringify({{
          threadId: threadId,
          runId: currentRunId,
          state: agState,
          messages: messages,
          tools: [],
          context: [],
          forwardedProps: {{}}
        }})
      }}
    );

    if (!resp.ok) throw new Error("HTTP " + resp.status);

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";

    while (true) {{
      const {{done, value}} = await reader.read();
      if (done) break;
      buf += decoder.decode(value, {{stream: true}});
      const lines = buf.split("\\n");
      buf = lines.pop();
      for (const line of lines) {{
        if (!line.startsWith("data:")) continue;
        try {{
          const ev = JSON.parse(line.slice(5).trim());
          if (ev.type === "TEXT_MESSAGE_CONTENT" && ev.delta) {{
            acc += ev.delta;
            el.innerHTML = renderMd(acc);
            el.className = "m a s";
            document.getElementById("msgs").scrollTop =
              document.getElementById("msgs").scrollHeight;
          }}
          if (ev.type === "RUN_FINISHED") {{
            el.className = "m a";
          }}
          if (ev.type === "RUN_ERROR") {{
            el.className = "m err";
            el.textContent = ev.message || "Run error";
          }}
        }} catch (_) {{}}
      }}
    }}

    if (!acc) acc = el.textContent;
    el.className = el.className.replace(" s", "");
    asstSeq++;
    const aid = "assistant_"
      + String(asstSeq).padStart(3, "0");
    messages.push({{id: aid, role: "assistant", content: acc}});

  }} catch (err) {{
    addEl("err", "Error: " + err.message);
  }} finally {{
    setEnabled(true);
    document.getElementById("txt").focus();
  }}
}}

document.getElementById("txt")
  .addEventListener("keydown", function(e) {{
    if (e.key === "Enter" && !e.shiftKey) {{
      e.preventDefault();
      send();
    }}
  }});
"""

# Pinned marked.js (15.0.7) + SRI hash so a CDN compromise can't
# silently swap in arbitrary JS inside the LTI iframe. Recompute the
# hash when bumping the version:
#   curl -sL https://cdn.jsdelivr.net/npm/marked@<VER>/marked.min.js \
#     | openssl dgst -sha384 -binary | openssl base64 -A
_MARKED_CDN = (
    "<script "
    'src="https://cdn.jsdelivr.net/npm/marked@15.0.7/marked.min.js" '
    'integrity="sha384-H+hy9ULve6xfxRkWIh/YOtvDdpXgV2fmAGQk'
    'IDTxIgZwNoaoBal14Di2YTMR6MzR" '
    'crossorigin="anonymous"></script>'
)

_CHAT_PAGE = (
    """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">
<title>Soliplex Chat</title>
"""
    + _MARKED_CDN
    + """
<style>
"""
    + _CHAT_STYLES
    + """\
</style>
</head>
<body>
<div id="chat">
"""
    + _CHAT_BODY
    + """\
</div>
<script id="lti-config" type="application/json">{config_json}</script>
<script>
const _cfg = JSON.parse(
  document.getElementById("lti-config").textContent
);
let ROOM = _cfg.room;
const TOKEN = _cfg.token;
const BASE = _cfg.base;
"""
    + _CHAT_SCRIPT
    + """\
</script>
</body>
</html>
"""
)

_PICKER_STYLES = """\
#picker{{padding:1.5rem;overflow-y:auto}}
#picker h2{{margin-bottom:1rem;font-size:1.25rem;color:#333}}
.room-grid{{display:grid;
  grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:1rem}}
.room-card{{background:#fff;border:1px solid #e0e0e0;
  border-radius:.75rem;padding:1.25rem;cursor:pointer;
  transition:border-color .15s,box-shadow .15s}}
.room-card:hover{{border-color:#0070f3;
  box-shadow:0 2px 8px rgba(0,112,243,.15)}}
.room-card h3{{font-size:1rem;margin-bottom:.4rem;color:#111}}
.room-card p{{font-size:.85rem;color:#555;margin-bottom:.6rem;
  line-height:1.4}}
.chips{{display:flex;flex-wrap:wrap;gap:.35rem}}
.chip{{font-size:.75rem;background:#eef4ff;color:#0070f3;
  padding:.2rem .6rem;border-radius:1rem}}
#picker .empty{{color:#777;font-style:italic}}
#picker .error{{color:#900;background:#fee;padding:.75rem;
  border-radius:.5rem}}
#picker .error button{{margin-top:.5rem;padding:.4rem .8rem;
  background:#0070f3;color:#fff;border:none;
  border-radius:.4rem;cursor:pointer}}
.loader{{text-align:center;padding:2rem;color:#777}}
"""

_PICKER_CHAT_PAGE = (
    """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">
<title>Soliplex</title>
"""
    + _MARKED_CDN
    + """
<style>
"""
    + _CHAT_STYLES
    + _PICKER_STYLES
    + """\
#chat{{display:none}}
</style>
</head>
<body>
<div id="picker">
  <div class="loader">Loading rooms…</div>
</div>
<div id="chat">
"""
    + _CHAT_BODY
    + """\
</div>
<script id="lti-config" type="application/json">{config_json}</script>
<script>
const _cfg = JSON.parse(
  document.getElementById("lti-config").textContent
);
let ROOM = "";
const TOKEN = _cfg.token;
const BASE = _cfg.base;
const DEFAULT_ROOM = _cfg.default_room;

function selectRoom(roomId, roomName) {{
  ROOM = roomId;
  document.getElementById("picker").style.display = "none";
  document.getElementById("chat").style.display = "flex";
  if (roomName) {{
    const hdr = document.getElementById("room-header");
    hdr.textContent = roomName;
    hdr.style.display = "block";
  }}
  document.getElementById("txt").focus();
}}

async function loadRooms() {{
  const picker = document.getElementById("picker");
  try {{
    const r = await fetch(BASE + "/api/v1/rooms", {{
      headers: {{"Authorization": "Bearer " + TOKEN}}
    }});
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    const entries = Object.entries(data);
    if (entries.length === 0) {{
      picker.innerHTML =
        '<p class="empty">No rooms are available for your '
        + 'account. Contact your administrator.</p>';
      return;
    }}
    if (entries.length === 1) {{
      selectRoom(entries[0][0],
        entries[0][1].name || entries[0][0]);
      return;
    }}
    let html = "<h2>Select a room</h2><div class=\\"room-grid\\">";
    for (const [rid, room] of entries) {{
      const desc = room.description
        ? "<p>" + escHtml(room.description) + "</p>" : "";
      let chips = "";
      if (room.suggestions && room.suggestions.length) {{
        chips = '<div class="chips">'
          + room.suggestions.slice(0, 2)
              .map(s => '<span class="chip">'
                + escHtml(s) + '</span>').join("")
          + "</div>";
      }}
      const label = escHtml(room.name || rid);
      html += '<div class="room-card" onclick="selectRoom(\\\''
        + escHtml(rid) + '\\\',\\\'' + label + '\\\')">'
        + "<h3>" + escHtml(room.name || rid) + "</h3>"
        + desc + chips + "</div>";
    }}
    html += "</div>";
    picker.innerHTML = html;
  }} catch (err) {{
    picker.innerHTML =
      '<div class="error">Could not load rooms: '
      + escHtml(err.message)
      + '<br><button onclick="loadRooms()">Retry</button>'
      + '</div>';
  }}
}}

function escHtml(s) {{
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}}

loadRooms();

"""
    + _CHAT_SCRIPT
    + """\
</script>
</body>
</html>
"""
)
