# AI Skills

Skills are a newer implementation for defining extension points
to an LLM system.

See:

- [AI Skills specificzation](https://agentskills.io/specification)
- [Haiku SKills](https://ggozad.github.io/haiku.skills/)

A Soliplex installation currently supports kinds of skills:

- Filesystem-based skills are loaded from directories containing a
  `SKILLS.md` spec file.

- Python entrypoint skills are loaded using Python's package entrypoint
  mechanism.

## Configuring Filesystem Skill Search Paths

At the installation level, define the directories to be searched for
`SKILLS.md` spec files using the
[`filesystem_skills_paths` entry](installation.md#filesystem-skill-paths)
in the installation configuration file.

Discovered filesystem skills can be queried using the
`InstallationConfig.available_filesystem_skill_configs` attribute.

## Configuring Entrypoint Skills

Entrypoint skills are loaded automatically.  There is currently no
option to configure or suppress this feature.

Discovered entrypoint skills can be queried using the
`InstallationConfig.available_entrypoint_skill_configs` attribute.

## Enabling Available Skills

Skills discovered using either of these mechanisms are "available",
but not enabled by default.  To enable one or more skills, use the
[`skill_configs` stanza](installation.md#enabling-skill-configurations)
in the installation configuration file.

## Configuring Room-Specific Skills

Soliplex provides two custom skill configuration types, based on the
skills defined in `haiku.rag.skills.rag` and `haiku.rag.skills.rlm`.
Because these skills require additional parameters available in
a room configuration, they are defined using the
[`skill_configs` stanza](rooms.md#skill-configuration)
of the room configuration's `skills` entry.
