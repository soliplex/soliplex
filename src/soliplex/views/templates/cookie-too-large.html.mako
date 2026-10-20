## Packaged default for the page telling a user their sign-in could not
## complete because the provider's credentials do not fit the authn
## cookie.  Served with HTTP 500, only for 'delivery=cookie' sign-ins.
## See 'soliplex.views.authn._cookie_error_response'.
##
## Copy this file to 'cookie-too-large.html.mako' in an 'oidc' folder to
## restyle it.  Rendered with 'default_filters=["h"]' and
## 'strict_undefined=True': every '${...}' is HTML-escaped, and every
## variable below is always passed.
##
##   server_name        -- installation 'server_name', else the host
##   auth_system_title  -- the auth system's 'title'
##
## The response's Content-Security-Policy blocks scripts and external
## resources: keep styles inline, and embed any images as 'data:' URIs.
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Sign-in problem - ${server_name}</title>
<style>
  :root {
    --bg: #f6f7f9;
    --card: #ffffff;
    --text: #1d2330;
    --muted: #5b6475;
    --border: #d9dde5;
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
  .notice {
    margin: 1rem 0;
    padding: 0.75rem;
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 6px;
  }
</style>
</head>
<body>
<main>
  <h1>Sign-in could not be completed</h1>
  <p class="provider">using ${auth_system_title}</p>
  <p class="notice">
    The credentials from this provider don't fit in the browser cookie
    which ${server_name} uses to recognize signed-in visitors.
  </p>
  <p>
    Please report this to the operator of ${server_name}.  The error is
    also recorded in the server's logs.
  </p>
  <p>You can close this page.</p>
</main>
</body>
</html>
