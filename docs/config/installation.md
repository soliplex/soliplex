# Installation Configuration

## Installation ID

A required field, to allow quick disambiguation between alternative
configurations.

```yaml
id: "soliplex-example"
```
## Installation Metaconfiguration

The `meta` section allows you to register custom "kinds" of entities (tool
configurations, MCP client toolset configurations, etc., such that you
can use them within your own configurations (e.g., to register a configuration
class for use with a custom tool in a given room).

```yaml
meta:
```

See [this page](meta.md) for documentation on the meta-configuration schema.

## Secrets

```yaml
secrets:
```

Secrets are values used to authenticate access to different resources or
APIs.

The may be kept in an external store, such as:

- ASW secret store
- Github secrets
- Docker Compose secrets files
- The user keyring

See [this page](secrets.md) for documentation on configuring installation
secrets.

## Environment

The `environment` section configures non-secret values used by various
portions of the Soliplex application.  Application code should use the
`Installation.get_environment` API to fetch configured values, rather than
using `os.environ`.

```yaml
environment:
```

See [this page](environment.md) for documentation on configuring the
installation environment.

## Agent Configurations

An installation can declare agent configurations (which are normally bound
to rooms / completions) at the top-level, such that they can be
looked up by by ID from Python code using `the_installation.get_agent_by_id`.

```yaml
agent_configs:

  - id: "ollama_gpt_oss"
    model_name: "gpt-oss:20b"
    system_prompt: |
      You are an expert AI assistant specializing in information retrieval.
      ...

```
Plese see [this page](agents.md) for details on configuring agents.
In addition to the values described there, note that the `id` element is
required here.

## OIDC Auth Provider Paths

The `oidc_paths` element specifies one or more filesystem paths to be
searched for OIDC provider configs.

Please see [this page](oidc_providers.md) for details on how to configure
these providers.

```yaml

oidc_paths:
  - "/path/to/oidc/config/dir"
```

Non-absolute paths will be evaluated relative to the installation directory.

By default, Soliplex loads provider configurations found under the path
'./oicd', just as though we had configured:

```yaml
oidc_paths:
  - "./oidc"
```

To disable authentication, list a single, "null" path, e.g.:
```yaml
oidc_paths:
  -
```
Or else run 'soliplex-cli serve --no-auth-mode'

## Room Configuration Paths

The `room_paths` element specify one or more filesystem paths to
search for room configs.

Please see [this page](rooms.md) for details on how to configure
these providers.

Each path can be either:

- a directory containing its own `room_config.yaml` file:  this directory
  will be mapped as a single room.

- a directory whose immediate subdirectories will be treated as rooms
  IFF they contain a `room_config.yaml` file.

Non-absolute paths are evaluated relative to the installation directory.

The order of `room_paths` in this list controls which room configuration
is used for any conflict on room ID:  rooms found earlier in the list
"win" over later ones with the same ID.

By default, Soliplex loads room configurations found under the path './rooms',
just as though we had configured:

```yaml
room_paths:
  - "./rooms"
```
To disable all rooms, list a single, "null" path, e.g.:

```yaml
room_paths:
   -
```

## Completion Configuration Paths

The `completion_paths` entry specifies one or more filesystem paths to
search for completion configs.

Please see [this page](completions.md) for details on how to configure
these providers.

Each path can be either:

- a directory containing its own `completion_config.yaml` file:  this
  directory will be mapped as a single completion.

- a directory whose immediate subdirectories will be treated as rooms
  IFF they contain a `room_config.yaml` file.

Non-absolute paths will be evaluated relative to the installation directory.

The order of entries in the `completion_paths` list controls which completion
configuration is used for any conflict on completion ID:  completions
found earlier in the list "win" over later ones with the same ID.

By default, Soliplex loads completion configurations found under the path
'./completions', just as though we had configured:

```yaml
completion_paths:
  - "./completions"
```

To disable all completions, list a single, "null" path, e.g.:
```yaml
completion_paths:
  -
```
