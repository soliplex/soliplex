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
