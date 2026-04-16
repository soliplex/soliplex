"""LTI chat page HTML templates"""

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
         placeholder="Ask something\u2026"
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
    const el = addEl("a s", "\u2026", mid);
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

_MARKED_CDN = (
    '<script src="https://cdn.jsdelivr.net/npm/'
    'marked@15/marked.min.js"></script>'
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
<script>
const ROOM  = "{room_id}";
const TOKEN = "{session_token}";
const BASE  = "{base_url}";
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
  <div class="loader">Loading rooms\u2026</div>
</div>
<div id="chat">
"""
    + _CHAT_BODY
    + """\
</div>
<script>
let ROOM  = "";
const TOKEN = "{session_token}";
const BASE  = "{base_url}";
const DEFAULT_ROOM = "{default_room_id}";

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
