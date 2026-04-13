# Configuring Installation Secrets

The `secrets` section of an installation configuration contains a list
of secret names, and optionally their configured sources.

The default configuration knows of four types of sources:

- Environment variables
- File paths
- Subprocess commands
- Randomly-generated strings

## Secret Source: Environment Variable

A secret source which uses an environment variable can be configured so:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "env_var"
       env_var_name: "MY_SECRET_ENV_VAR_NAME"
```

## Secret Source: Filesystem Path

A secret source which uses a file system path can be configured so:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "file_path"
       file_path: "/run/secret/my_secret"
```

## Secret Source: Subprocess Command

A secret source which uses a subprocess command can be configured so:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "subprocess"
       command: "/usr/bin/fetch_secret"
       args:
       - "--secret-name=MY_SECRET"
```

## Secret Source: Randomly-Generated String

A secret source which uses generates a random string at process startup
can be configured so:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "random_chars"
       n_chars: 32
```

## Layering Secret Sources

Sources are resolved in the order they are listed, with the first one
returning a value winning.  This example layers an environment variable
source with a random string source:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "env_var"
       env_var_name: "MY_SECRET_ENV_VAR_NAME"
     - kind: "random_chars"
       n_chars: 32
```

## Secrets without Sources

Secrets which list no sources are treated as though they were configured
using an environment variable source with the same name.

This configuration:

```yaml
secrets:
    - secret_name: MY_SECRET
```

is equivalent to:

```yaml
secrets:
   - secret_name: MY_SECRET
     sources:
     - kind: "env_var"
       env_var_name: "MY_SECRET"
```

## Secrets as Bare Strings

An even shorter way to spell the previous configuration:

```yaml
secrets:
   - "MY_SECRET"

```

## Required Secrets

In addition to secrets configured to manage access to external APIs,
the Soliplex server itself depends on two secrets:

### `SESSION_MIDDLEWARE_TOKEN`

This secret is used to encrypt a client's session data (see the
Starlette session middleware
[docs](https://www.starlette.dev/middleware/#sessionmiddleware)).

Its value must be an ASCII hex digest of a random `bytes` object with length
32.  To generate such a value:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If generated this way, the value can be passed into Soliplex via either
an `env_var` source, e.g.:

```yaml
secrets:
  ...
  - name: "SESSION_MIDDLEWARE_TOKEN"
    sources:
      - kind: "env_var"
        env_var_name: "SOLIPLEX_SESSION_MIDDLEWARE_TOKEN"
```

or a `file_path` source, e.g.:

```yaml
secrets:
  ...
  - name: "SESSION_MIDDLEWARE_TOKEN"
    sources:
      - kind: "file_path"
        file_path: "/run/secret/session_middleware_token"
```

The installation configurations in the `example/` directory provider a
fallback `random_chars` source:

```yaml
  - secret_name: "SESSION_MIDDLEWARE_TOKEN"
    sources:
      - kind: "env_var"
        env_var_name: "SOLIPLEX_SESSION_MIDDLEWARE_TOKEN"
      - kind: "random_chars"
```

but this configuration should not be used where sessions must survive
a server restart (the session token will be regenerated), nor when [running
behind a load balancer](../server.md#running-behind-a-load-balancer).

### `URL_SAFE_TOKEN_SECRET`

This secret is used to generate bearer tokens to allow MCP clients to
access a room's MCP-enabled tools.

This value must be an ASCII hex digest of a random `bytes` object with length
32.  To generate such a value:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

If generated this way, the value can be passed into Soliplex via either
an `env_var` source, e.g.:

```yaml
secrets:
  ...
  - name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "SOLIPLEX_URL_SAFE_TOKEN_SECRET"
```

or a `file_path` source, e.g.:

```yaml
secrets:
  ...
  - name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "file_path"
        file_path: "/run/secret/url_safe_token"
```

The installation configurations in the `example/` directory provider a
fallback `random_chars` source:

```yaml
  - secret_name: "URL_SAFE_TOKEN_SECRET"
    sources:
      - kind: "env_var"
        env_var_name: "SOLIPLEX_URL_SAFE_TOKEN_SECRET"
      - kind: "random_chars"
```

but this configuration should not be used where sessions must survive
a server restart (the session token will be regenerated), nor when [running
behind a load balancer](../server.md#running-behind-a-load-balancer).

## Checking Configured Secrets

The `soliplex-cli` application has a sub-command, `list-secrets`.
It loads the configuration, attempts to resolve all the secrets, and
reports those not found.  E.g.:

```bash
$ soliplex-cli list-secrets example/installation.yaml

───────────────────────────── Configured secrets ──────────────────────────────

- LOGFIRE_TOKEN             MISSING
- SMITHERY_AI_API_KEY       MISSING
- SMITHERY_AI_PROFILE       MISSING
- URL_SAFE_TOKEN_SECRET     OK
- SESSION_MIDDLEWARE_TOKEN  OK

```
