# ASGI Middleware Stack

The `middleware_stack` section of an installation configuration declares the
ASGI middleware that wraps the Soliplex application. It is an ordered list:
the **first entry is the outermost layer** (it sees a request first and a
response last), and the last entry sits closest to the application.

If you omit `middleware_stack` entirely, Soliplex installs a built-in
[default stack](#default-stack). Providing your own list **replaces** that
default outright, so include session / CORS middleware yourself if you still
want them.

## Middleware factories

Each entry names an `app_factory`: a Python "dotted name" which is imported
and called to wrap the application. A factory receives the application (an
ASGI app, or the middleware wrapping it) as its first positional argument and
returns the wrapped result:

```python
def app_factory(app, **extra_params):
    ...
    return app
```

If a factory declares a keyword-only `installation_config` parameter, it is
passed the resolved [`InstallationConfig`](installation.md) — for example to
look up [secrets](secrets.md) or [environment](environment.md) values:

```python
def app_factory(app, *, installation_config, **extra_params):
    ...
    return app
```

Whether the installation config is injected is detected automatically from
the factory's signature, so `installation_config` must be a real keyword-only
parameter (not absorbed by `**kwargs`).

## Configuration

Each list entry accepts:

- `name`, a string labelling the middleware (for diagnostics).

- `app_factory`, the dotted name of the factory described above.

- `extra_params` (optional), a mapping forwarded to the factory as keyword
  arguments.

Example:

```yaml
middleware_stack:
  - name: "session"
    app_factory: "soliplex.main.app_with_session"
  - name: "cors"
    app_factory: "soliplex.main.app_with_cors"
    extra_params:
      allow_origins: ["*"]
      allow_credentials: true
      allow_methods: ["*"]
      allow_headers: ["*"]
```

## Default stack

When `middleware_stack` is omitted, Soliplex uses
`soliplex.main.default_middleware_stack()`, which is equivalent to the example
above:

- `soliplex.main.app_with_session` (outermost) — adds Starlette's
  `SessionMiddleware`. It reads the `SESSION_MIDDLEWARE_TOKEN` secret from the
  installation config for the cookie's signing key, and marks the cookie
  `Secure` unless the server was started with `--insecure-session-cookie`.

- `soliplex.main.app_with_cors` — adds FastAPI's `CORSMiddleware` with a
  permissive configuration drawn from its `extra_params`.

These two factories double as worked examples of the with- and
without-`installation_config` factory shapes.
