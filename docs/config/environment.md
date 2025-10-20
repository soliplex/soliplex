# Installation Environment

The `environment` section configures non-secret values used by various
portions of the Soliplex application.  Application code should use the
`Installation.get_environment` API to fetch configured values, rather than
using `os.environ`.

## Environment Entries

The section consists of a list of mappings, each with keys `name` and
`value`.

```yaml
environment:
  - name: "ENV_VAR_NAME"
    value: "ENV_VAR_VALUE"
```

## Unconfigured Environment Entries

If the `value` key is missing, the Soliplex application will
attempt to resolve it using `os.environ` during startup.

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

# Checking Configured Environment Values

The `soliplex-cli` application has a sub-command, `list-environment`.
It loads the configuration, attempts to resolve any values not found, and
reports them:

```bash
$ soliplex-cli list-environment example/installation.yaml 

─────────────────────── Configured environment variables ───────────────────────

- OLLAMA_BASE_URL          : MISSING
- DEFAULT_AGENT_MODEL      : qwen3:latest
- EMBEDDINGS_PROVIDER      : ollama
- EMBEDDINGS_MODEL         : mxbai-embed-large
- EMBEDDINGS_VECTOR_DIM    : 1024
- QA_PROVIDER              : ollama
- QA_MODEL                 : qwen3:latest
- RERANK                   : false
- INSTALLATION_PATH        : file:.
- RAG_LANCE_DB_PATH        : file:../db/rag
- LOGFIRE_ENVIRONMENT      : container
- LOGFIRE_SERVICE_NAME     : soliplex

```
