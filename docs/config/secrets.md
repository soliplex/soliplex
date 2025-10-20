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

A secret source which uses a filesystme path can be configured so:

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


## Secrets wihout Sources

Secrets which list no sources are treated as though the were configured
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

# Checking Configured Secrets

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

```
