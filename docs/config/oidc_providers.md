# OIDC Provider Configuration

The `config.yaml` file in an OIDC provider configuration directory specifies
one or more authentication systems.  Settings at the top level of the file
are defaults, shared by every authentication system it lists:

```yaml
oidc_client_pem_path: "./cacert.pem"
allowed_frontend_origins:
  - "https://chat.example.com"
unlisted_frontend_origin: "consent-required"

auth_systems:

  - id: "myprovider"
    title: "Authenticate with MyProvider"
    server_url: "https://oidc.example.com/"
    client_id: "myprovider-token-service"
    client_secret: ""  # "secret:{MYPROVIDER_CLIENT_SECRET}"
    scope: "openid email profile"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MII..AQAB
        -----END PUBLIC KEY-----
```

## Required Configuration Elements

- `auth_systems` is a list of one or more OIDC provider configurations
  (see below).

## Optional Configuration Elements

Each of these is a default for every entry in `auth_systems`.  An entry
which sets the same key replaces the default:  lists are not merged, so an
entry with `allowed_frontend_origins: []` allows no extra origins, whatever
the top level lists.

- `oidc_client_pem_path` points to a file on the filesystem containing
  the shared CA certificate store.  If not configured, the Soliplex
  application will use systemwide default CA certificates.

- `allowed_frontend_origins`: a list of web frontend origins trusted to
  receive a user's tokens without asking the user first.  See
  [Frontend origins](#frontend-origins) below.

- `unlisted_frontend_origin`: what to do when sign-in is started for a
  frontend origin which is not trusted:  `consent-required` (the default)
  or `deny-all`.  See [Frontend origins](#frontend-origins) below.

- `consent_template_path`: a Mako template for the page asking a user to
  confirm an unlisted frontend origin.  See
  [Customizing the consent page](#customizing-the-consent-page) below.

Relative paths are resolved against the directory holding `config.yaml`.

## Required OIDC Provider Elements

- `id`: a string, should be unique across all configured providers

- `title`: a string, might be displayed by a client

- `server_url`: URL for initiating the token auth flow.

- `token_validation_pem`: a string, the public key used to verify
   the providers tokens.

- `client_id`: a string identifying the client to the provider.

Soliplex always uses PKCE (`S256`) when it exchanges the authorization
code, so the provider must accept a code challenge for this client.
Providers which support PKCE without requiring it (e.g., Keycloak's
default) need no extra configuration.

## Optional OIDC Provider Elements

- `client_secret`: a string;  if not empty, should be in the form
  `"secret:MYPROVIDER_CLIENT_SECRET"`, where the name following the
  `secret:` prefix is the name of a configured installation secret
  (see [this page](secrets.md) for details).

- `scope`: string, an OAuth scope specifier.

- `cookie_claims`: a list of token claim names to copy into the authn
  cookie set at sign-in (default: `email` and `preferred_username`).
  List top-level claim names:  a listed claim is copied whole, including
  any nested values.  The authn cookie is signed, not encrypted:  do
  not list claims you consider sensitive.  See
  [Protecting other services with nginx `auth_request`](#protecting-other-services-with-nginx-auth_request)
  below.

- `oidc_client_pem_path`, `allowed_frontend_origins`,
  `unlisted_frontend_origin`, `consent_template_path`: as above, for this
  provider only, replacing any top-level default.

## Example: defaults and overrides

This file configures two providers.  Only `staff` overrides any defaults:

```yaml
oidc_client_pem_path: "./cacert.pem"
allowed_frontend_origins:
  - "https://chat.example.com"

auth_systems:

  - id: "public"
    title: "Sign in with Example ID"
    server_url: "https://id.example.com/realms/public"
    client_id: "soliplex-public"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MII..AQAB
        -----END PUBLIC KEY-----

  - id: "staff"
    title: "Staff sign-in"
    server_url: "https://sso.example.com/realms/staff"
    client_id: "soliplex-staff"
    client_secret: "secret:STAFF_CLIENT_SECRET"
    token_validation_pem: |
        -----BEGIN PUBLIC KEY-----
        MII..AQAB
        -----END PUBLIC KEY-----
    oidc_client_pem_path: "./staff-cacert.pem"
    allowed_frontend_origins: []
    unlisted_frontend_origin: "deny-all"
```

With this file in `oidc/`, each provider ends up with these settings:

| Setting | `public` | `staff` |
| --- | --- | --- |
| `oidc_client_pem_path` | `oidc/cacert.pem` (default) | `oidc/staff-cacert.pem` |
| `allowed_frontend_origins` | `https://chat.example.com` (default) | none |
| `unlisted_frontend_origin` | `consent-required` (built-in default) | `deny-all` |
| consent template | `oidc/consent.html.mako` if present, else packaged | never shown |

So `public` supports a hosted web client at `https://chat.example.com`
with no prompt, and asks users to confirm any other frontend.  `staff`
accepts only frontends on the backend's own origin, and refuses every
other origin without asking.

## Frontend origins

A web frontend starts sign-in by sending the user's browser to
`/api/login/<id>?return_to=<URL>`.  After the provider signs the user in,
Soliplex redirects the browser to that `return_to` URL, carrying the
user's tokens, so it first decides whether the URL's origin is trusted to
receive them.

These are trusted, with no configuration:

- a path on the backend's own origin, such as `/` (the default);
- an absolute URL on the origin the backend is served from.  This covers
  the standard deployment, where the web frontend and `/api/` are served
  from the same host.  Behind a proxy which terminates TLS, run
  `soliplex-cli serve` with `--proxy-headers` (see
  [the CLI reference](../server/cli.md)); otherwise the backend sees its
  own origin as `http://`, and same-origin sign-ins get the consent page.

Also trusted:  any origin listed in `allowed_frontend_origins`.  List a
frontend served from a different origin than the backend, such as a
hosted web client which connects to more than one backend.  Each entry is
an origin only:  a scheme (`http` or `https`), a host, and an optional
port, with no path.

Any other origin is *unlisted*, and `unlisted_frontend_origin` decides
what happens:

- `consent-required`: Soliplex shows its own page naming the origin, and
  asks the user to confirm before continuing to the provider.  This keeps
  the web client's "connect to any server" feature working, while
  preventing a link from signing a user in silently and sending their
  tokens elsewhere.
- `deny-all`: sign-in fails with an HTTP 400 response.  Use this where
  every legitimate frontend is known and listed.

Some `return_to` values are refused with an HTTP 400 response whatever the
policy:

- a plain `http` URL whose host is not the local machine (`localhost`,
  `*.localhost`, `127.0.0.0/8` or `[::1]`), unless it is the backend's own
  origin or is listed;
- a scheme other than `http` or `https`;
- a relative URL not starting with `/`, or starting with `//`;
- a URL containing a backslash, control characters, or leading or
  trailing whitespace.

## Registering the redirect URI

The provider redirects back to the backend at `/api/auth/<id>`, with no
query string, whichever frontend started the sign-in.  Register that one
URI exactly in the provider's client configuration, for example
`https://soliplex.example.com/api/auth/myprovider`, and avoid wildcards
such as `https://soliplex.example.com/*`.  Adding a frontend never requires
changing the provider's configuration:  frontends are allowed by
`allowed_frontend_origins` here, not by the provider.

## Protecting other services with nginx `auth_request`

A deployment can put other web services (for example, an ingester
dashboard) behind the same nginx as Soliplex, and let Soliplex decide who
reaches them, through nginx's
[`auth_request`](https://nginx.org/en/docs/http/ngx_http_auth_request_module.html).

### The authn cookie

A browser following a link to a proxied service sends no bearer token.
So, whenever a sign-in completes, Soliplex also sets an `HttpOnly`,
`SameSite=Lax` cookie named `soliplex_authn`, with `Path=/`, which the
browser then sends with every request to that host.

- The cookie is signed with the `SESSION_MIDDLEWARE_TOKEN` installation
  secret, but not encrypted:  anyone holding it can read the claims it
  carries.
- It encodes the signing auth system's id, the expiry, the `sub` claim,
  and the claims named in the provider's `cookie_claims`.
- It expires with the access token, and is not renewed when the web
  client refreshes its tokens.
- It is marked `Secure`, unless `soliplex-cli serve` runs with
  `--insecure-session-cookie` for local testing.
- A value larger than 4000 bytes is logged as an error, and the
  cookie is not set:  the browser would not keep it (their 4096-byte
  limit counts name and value, and this cookie's name takes 14 of
  them), and setting it would evict any cookie the visitor already
  holds.  Proxied-service sessions re-login on every request until
  the deployment trims the provider's `cookie_claims`;  a
  `delivery=cookie` sign-in answers with an error page (HTTP 500)
  rather than redirecting.

`POST /api/auth/<id>/logout` clears the cookie.  The web client's own
logout drops only its tokens:  the authn cookie persists until this
endpoint is called or the cookie expires.

### The check endpoint

`GET /api/v1/authz/check/<resource>` answers an `auth_request`
subrequest:

- `204` if the user is an admin user (see
  [`admin-users`](../server/cli.md#admin-users)), with the
  `X-Soliplex-User` header
  naming the user (their `preferred_username`, `email`, or `sub` claim;
  the header is omitted when none of the three is a printable ASCII
  string);
- `401` if the request has no authn cookie, or the cookie does not
  verify or has expired;
- `403` if the user is authenticated, but not an admin user.

It reads only the authn cookie, not a bearer token:  the check answers
for browser navigations, which carry only the cookie, while a client
holding a bearer token authenticates to the proxied service's own API
directly.  The admin check
matches the deployment's admin-user discriminators against the claims
carried by the cookie, so the provider's `cookie_claims` must name every
claim those discriminators reference (`sub` is always carried):
otherwise the check denies users whom it would otherwise admit.

`<resource>` is a label
for the audit log, such as `ingester_control`, made of letters, digits,
`_`, `.`, `:`, and `-`.  In no-auth mode, it answers as the rest of the
API does.

On success, the response's `X-Soliplex-User` header is an unverified
display name, projected onto the proxied request by nginx:  treat it
as a value for logs and interface display, never as an input to
authorization, and never as a record key.  It is trustworthy only in
locations whose `proxy_set_header` overwrites whatever the client
itself sent, so keep the proxied service reachable only through nginx,
and repeat the `proxy_set_header` in every proxied location.

### Signing in from a proxied service

To sign in from a proxied service, send the browser to
`/api/login/<id>?return_to=<path>&delivery=cookie`.  With
`delivery=cookie`, the callback sets the authn cookie and redirects to
`return_to` without appending the user's tokens, which only the Soliplex
web client knows to remove from the address bar.  The default,
`delivery=fragment`, appends the tokens as usual.

For example:

```nginx
location /ingester/ {
    auth_request /_soliplex_authz_check;
    auth_request_set $soliplex_user $upstream_http_x_soliplex_user;
    proxy_set_header X-Soliplex-User $soliplex_user;
    error_page 401 = @soliplex_login;
    proxy_pass http://ingester:8080/;
}

location = /_soliplex_authz_check {
    internal;
    proxy_pass http://soliplex:8000/api/v1/authz/check/ingester_control;
    proxy_pass_request_body off;
    proxy_set_header Content-Length "";
}

location @soliplex_login {
    return 302 /api/login/myprovider?delivery=cookie&return_to=$request_uri;
}
```

The proxied service receives the `soliplex_authn` cookie along with
every other cookie for the host.  To keep it from the service, remove
it in nginx before proxying.

The header's name is nginx's to change, too:  a service expecting,
say, `X-Forwarded-User` takes one line in the same location,

```nginx
proxy_set_header X-Forwarded-User $soliplex_user;
```

and different proxied locations may project the same check under
different names.

The login redirect issued after a lapsed session carries the original
path, but as a `GET` request:  a `POST` submission lost to a lapse is
not replayed after sign-in, and must be re-entered.

Sign-ins which deliver tokens (`delivery=fragment`, the default)
redirect through the same nginx, and an IdP issuing larger tokens can
push the callback's `Location` header past nginx's default
response-header buffer (4k or 8k, one memory page):  nginx logs
`upstream sent too big header`, and the login fails with a 502.
Where the Soliplex API is proxied, size the buffers to the
deployment's largest tokens:

```nginx
proxy_buffer_size 64k;
proxy_buffers 8 64k;
```

`delivery=cookie` logins — the proxied-service flow above — do not
have this problem:  their redirects carry no tokens at all.

## Customizing the consent page

For each provider, Soliplex looks for the consent page's template in this
order:

1. the provider's `consent_template_path`, or the top-level default;
2. a file named `consent.html.mako` in the directory holding
   `config.yaml`;
3. the default template packaged with Soliplex.

To start from the packaged default, copy
`soliplex/views/templates/consent.html.mako` from the installed package
into the OIDC configuration directory as `consent.html.mako`, and edit it.

The template is rendered with [Mako](https://www.makotemplates.org/),
receiving these variables:

- `server_name`: the installation's `server_name`, or the backend's host
  name if none is configured
- `auth_system_title`: the provider's `title`
- `origin`: the unlisted frontend origin, with any internationalized
  host name shown in punycode
- `form_action`: the URL the form must `POST` to
- `csrf_token`: must be posted back in a field named `csrf_token`
- `cancelled`: `True` to render the page shown after the user cancels,
  instead of the prompt

The form must post a field named `decision`, with the value `continue` or
`cancel`, along with `csrf_token`.

Every `${...}` expression is HTML-escaped, and a variable not in the list
above is an error.  If the template fails to render, Soliplex logs the
error and serves the packaged default instead.

The page is served with a `Content-Security-Policy` allowing no scripts
and no external resources.  Keep styles inline, and embed any images as
`data:` URIs.

A Mako template can run arbitrary Python code, so protect the OIDC
configuration directory as you would the rest of the installation's
configuration.
