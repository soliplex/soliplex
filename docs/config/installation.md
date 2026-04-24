# Installation Configuration

## Installation ID

A required field, to allow quick disambiguation between alternative
configurations.

```yaml
id: "soliplex-example"
```

## Installation Metaconfiguration

The `meta` section allows you to register custom "kinds" of entities (tool
configurations, MCP client toolset configurations, etc.), such that you
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
- GitHub secrets
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

**Note:** this configuration is distinct from adding variables to
the operating system environment: see [this page](../server/environment.md)
for that topic.

## `haiku.rag` Configuration File

The `haiku_rag_config_file` entry points to a YAML file containing
configuration values for the `haiku.rag` client

If not configured explicitly, the installation configuration expects to
find this file in the same directory, with the default name `haiku.rag.yaml`.

Please see the `haiku.rag` configuration
[docs](https://ggozad.github.io/haiku.rag/configuration/) for details
on how to configure the `haiku.rag` client used by Soliplex.

## Agent Configurations

An installation can declare agent configurations (which are normally bound
to rooms / completions) at the top-level, such that they can be
looked up by ID from Python code using `the_installation.get_agent_by_id`.

```yaml
agent_configs:

  - id: "ollama_gpt_oss"
    model_name: "gpt-oss:20b"
    system_prompt: |
      You are an expert AI assistant specializing in information retrieval.
      ...

```

Please see [this page](agents.md) for details on configuring agents.
In addition to the values described there, note that the `id` element is
required here.

## Thread Persistence DBURI

An installation can define two DBURIs for the database used to store
AG-UI threads, runs, events, etc.

### Synchronous DBURI

One DBURI is for sync usage, e.g.  within console scripts.  Examples:

- `sqlite://`
- `postgresql+psycopg2://user:<password>@dbhost/dbname`

### Asynchronous DBURI

The other DBURI is for async usage, e.g. within the Soliplex server
process.  Examples:

- `sqlite+aiosqlite://`
- `postgresql+asyncpg://user:<password>@dbhost/dbname`

This DBURI must be compatible with SQLAlchemy's [asyncio extension](
https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
Dialects known to work include:

- [`aiosqlite`](https://aiosqlite.omnilib.dev/en/stable/index.html)
- [`asyncpg`](https://magicstack.github.io/asyncpg/current/)

### Default configuration

By default, Soliplex configures thread persistence using in-memory DBURIS:

- For sync use, `sqlite` (DBURI `sqlite://`)
- For async use, `aiosqlite` (DBURI `sqlite+aiosqlite://`)

The default configuration is equivalent to this explicit YAML:

```yaml
thread_persistence_dburi:
  sync: "sqlite://"
  async: "sqlite+aiosqlite://"
```

### Database passwords as secrets

For DBURIs requiring authentication, we would rather not expose the
password in plain-text configuration.  In this case, we can define a
Soliplex secret (read [here](./secrets.md)), and use that secret in the DBURI.

```yaml
secrets:
    - secret_name: MY_DBURI_SECRET
      # Configure sources here
...

thread_persistence_dburi:
  sync: "postgresql+psycopg2://user:secret:MY_DBURI_SECRET@dbhost/dbname"
  async: "postgresql+asyncpg://user:secret:MY_DBURI_SECRET@dbhost/dbname"
```

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
'./oidc', just as though we had configured:

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

## Filesystem Skill Paths

The `filesystem_skills_paths` stanza specifies one or more filesystem paths to
search for AI Skill configurations.

Please see [this page](skills.md) for documentation on AI skills.

Each path can be either:

- a directory containing its own `SKILLS.md` file:  this
  directory will be mapped as a single skill.

- a directory whose immediate subdirectories will be treated as skills
  IFF they contain a `SKILLS.md` file.

Non-absolute paths will be evaluated relative to the installation directory.

The order of entries in the `filesystem_skills_paths` list controls which
skill configuration is used for any conflict on skill name:  filesystem
skills found earlier in the list "win" over later ones with the same name.

By default, Soliplex loads skill configurations found under the path
'./skills', just as though we had configured:

```yaml
filesystem_skills_paths:
  - "./skills"
```

To disable filesystem skill discovery, list a single, "null" path, e.g.:

```yaml
filesystem_skills_paths:
  -
```

## Enabling Skill Configurations

To enable discovered filesystem or entrypoint skills, add them to the
`skill_configs` stanza of the installation configuration.  E.g.:

```yaml
skill_configs:
  - skill_name: "bare-bones"
    kind: "filesystem"
  - skill_name: "image-generation"
    kind: "entrypoint"
```

Discovered skills which are not mentioned in this stanza cannot be
referenced by other parts of the configuration, e.g. rooms.

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

The `completion_paths` stanza specifies one or more filesystem paths to
search for completion configs.

Please see [this page](completions.md) for details on how to configure
these providers.

Each path can be either:

- a directory containing its own `completion_config.yaml` file:  this
  directory will be mapped as a single completion.

- a directory whose immediate subdirectories will be treated as
  completions IFF they contain a `completion_config.yaml` file.

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

## Logfire Configuration

See the [Soliplex logfire configuration](logfire.md) page.
