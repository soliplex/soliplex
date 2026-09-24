# AI Skills

Soliplex loads instruction-only [Agent Skills](https://agentskills.io/)
as native Pydantic AI capabilities.

See:

- [Agent Skills specification](https://agentskills.io/specification)

Filesystem-based skills are loaded from directories containing a
`SKILL.md` specification file.

## Configuring Filesystem Skill Search Paths

At the installation level, define the directories to be searched for
`SKILL.md` spec files using the
[`filesystem_skills_paths` entry](installation.md#filesystem-skill-paths)
in the installation configuration file.

Discovered filesystem skills can be queried using the
`InstallationConfig.available_filesystem_skill_configs` attribute.

## Selecting Available Skills

All discovered skills are enabled by default. To restrict an installation
to selected skills, use the
[`skill_configs` stanza](installation.md#selecting-skill-configurations)
in the installation configuration file.

## Configuring Room-Specific Skills

Soliplex also provides native capability configuration types for RAG and
sandbox execution. Because these capabilities require
room-specific parameters, they are defined using the
[`skill_configs` stanza](rooms.md#skill-configuration)
of the room configuration's `skills` entry.

### `bwrap_sandbox`

```yaml
skills:
  skill_configs:
    - kind: "bwrap_sandbox"
      environment: "pandas-only"
      execution_timeout_seconds: 60.0
      max_output_chars: 20000
```

- `environment` (optional, default `bare`) -- the sandbox environment every
  execution in this room runs in, named after a subdirectory of the
  installation's
  [`environments_path`](installation.md#sandbox-configuration). The model
  does not select it.

- `execution_timeout_seconds` / `max_output_chars` (optional) -- override
  the installation's
  [`sandbox_config`](installation.md#sandbox-configuration) values for this
  room. Omit either to inherit, which keeps the room following a later
  change to the installation default.

- `volumes` (optional) -- extra host directories to mount, keyed by the name
  they take under `/sandbox/volumes`:

  ```yaml
      volumes:
        reference:
          host_path: /srv/reference
          writable: false
  ```
