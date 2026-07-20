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

Soliplex also provides native capability configuration types for RAG,
analysis, and sandbox execution. Because these capabilities require
room-specific parameters, they are defined using the
[`skill_configs` stanza](rooms.md#skill-configuration)
of the room configuration's `skills` entry.
