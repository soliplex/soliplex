# Installation Environment

The `environment` section configures non-secret values used by various
portions of the Soliplex application.  Application code should use the
`Installation.get_environment` API to fetch configured values, rather than
using `os.environ`.

## Environment Entries

The `environment` section consists of a list of mappings, each with
keys `name` and `value`.

```yaml
environment:
  - name: "ENV_VAR_NAME"
    value: "ENV_VAR_VALUE"
```

## Bare-String Environment Entries

As an alternative, an item in the list can be a bare string:  such an
entry corresponds exactly to a mapping with `name: "<bare string` and
no `value`.

This configuration:

```yaml
environment:
  - "ENV_VAR_NAME"
```

is exactly equivalent to this one:

```yaml
environment:
  - name: "ENV_VAR_NAME"
```

## Resolving Environment Entry Values

When resolving environment entry values after an installation configuration,
Soliplex will use values from the following sources, in order of
precedence:

- Value explicitly configured in the installation
- Value from an `.env` file located in the installation directory
- Value from the OS environment

If the `InstallationConfig.disable_dotenv` flag is set to `True`, then
Soliplex use these sources, in order of precedence:

- Value explicitly configured in the installation
- Value from the OS environment

See the [server environment](../server/environment.md) page for examples
of configuring operating system environment variables (versus this page,
which explains how they are used within the Soliplex configuration).

## Checking Configured Environment Values

The `soliplex-cli` application has a sub-command, `audit environment`.
It loads the configuration, attempts to resolve any values not found, and
reports them.  For example:

```bash
$ soliplex-cli audit environment example/installation.yaml

─────────────────────── Configured environment variables ───────────────────────

- OLLAMA_BASE_URL          : MISSING
- INSTALLATION_PATH        : file:.
- RAG_LANCE_DB_PATH        : file:../db/rag
- LOGFIRE_ENVIRONMENT      : container
- LOGFIRE_SERVICE_NAME     : soliplex

```
