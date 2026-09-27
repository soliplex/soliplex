## Packaged default for the page asking a user to confirm an unlisted
## frontend origin before the OIDC sign-in proceeds.  See afsoc-rag#1907.
##
## Copy this file to 'consent.html.mako' in an 'oidc' folder (or point
## 'consent_template_path' at it) to restyle it.  Rendered with
## 'default_filters=["h"]' and 'strict_undefined=True': every '${...}' is
## HTML-escaped, and every variable below is always passed.
##
##   server_name        -- installation 'server_name', else the host
##   auth_system_title  -- the auth system's 'title'
##   origin             -- the unlisted frontend origin (punycode)
##   form_action        -- URL the confirm / cancel form must POST to
##   csrf_token         -- must be posted back as 'csrf_token'
##   cancelled          -- True: render the "cancelled" page instead
##
## The response's Content-Security-Policy blocks scripts and external
## resources: keep styles inline, and embed any images as 'data:' URIs.
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
% if cancelled:
<title>Sign-in cancelled - ${server_name}</title>
% else:
<title>Confirm sign-in - ${server_name}</title>
% endif
<style>
  :root {
    --bg: #f6f7f9;
    --card: #ffffff;
    --text: #1d2330;
    --muted: #5b6475;
    --border: #d9dde5;
    --accent: #1f5fd6;
    --accent-text: #ffffff;
    --warn-bg: #fff6e0;
    --warn-border: #e8c46a;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #14171d;
      --card: #1d2129;
      --text: #e6e9ef;
      --muted: #a1a9b8;
      --border: #343a46;
      --accent: #5b8def;
      --accent-text: #0d1117;
      --warn-bg: #2e2714;
      --warn-border: #7a6224;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 16px;
    background: var(--bg);
    color: var(--text);
    font: 16px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  }
  main {
    width: 100%;
    max-width: 32rem;
    padding: 2rem;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  h1 { margin: 0 0 0.25rem; font-size: 1.375rem; }
  .provider { margin: 0 0 1.5rem; color: var(--muted); }
  .origin {
    margin: 0.75rem 0;
    padding: 0.75rem;
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 6px;
    font: 600 1.0625rem/1.4 ui-monospace, "SFMono-Regular", Menlo,
      Consolas, monospace;
    overflow-wrap: anywhere;
  }
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 1.5rem;
  }
  button {
    flex: 1 1 10rem;
    padding: 0.625rem 1rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--text);
    font: inherit;
    cursor: pointer;
  }
  button.continue {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-text);
    font-weight: 600;
  }
  button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
</style>
</head>
<body>
<main>
% if cancelled:
  <h1>Sign-in cancelled</h1>
  <p class="provider">${server_name}</p>
  <p>No sign-in was sent to the app. You can close this page.</p>
% else:
  <h1>Sign in to ${server_name}</h1>
  <p class="provider">using ${auth_system_title}</p>

  <p>The app at</p>
  <p class="origin">${origin}</p>
  <p>
    is asking to receive your sign-in for this server. It will be able
    to act as you here.
  </p>
  <p>
    <strong>Continue only if you opened that app yourself.</strong>
    If you followed a link you didn't expect, choose Cancel.
  </p>

  <form method="post" action="${form_action}">
    <input type="hidden" name="csrf_token" value="${csrf_token}">
    <div class="actions">
      <button type="submit" name="decision" value="cancel">Cancel</button>
      <button type="submit" name="decision" value="continue"
              class="continue">Continue</button>
    </div>
  </form>
% endif
</main>
</body>
</html>
