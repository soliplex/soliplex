# Skills Configuration Guide

This guide explains the Soliplex skill configuration system introduced in PR #664, which replaces the legacy `haiku_chat` module with a pluggable architecture.

## Overview

Skills extend a room's agent with specialized capabilities. There are three types:

| Type | `kind` value | Source | Description |
|------|-------------|--------|-------------|
| Filesystem | `"filesystem"` | `SKILL.md` files on disk | Custom skills defined as markdown instructions |
| Entrypoint | `"entrypoint"` | Python package entrypoints | Skills distributed via pip packages |
| Haiku RAG | `"haiku.rag.skills.rag"` | Built into `haiku.rag-slim` | Retrieval-Augmented Generation for document search/QA |
| Haiku RLM | `"haiku.rag.skills.rlm"` | Built into `haiku.rag-slim` | RAG with Language Model reasoning |

## Configuration Architecture

Skills are configured at two levels:

### 1. Installation Level (`installation.yaml`)

Define which skills are **available** globally:

```yaml
# Paths to search for filesystem skills
filesystem_skills_paths:
  - "./skills"

# Enable specific discovered skills
skill_configs:
  - skill_name: "bare-bones"
    kind: "filesystem"
  - skill_name: "my-custom-skill"
    kind: "filesystem"
```

### 2. Room Level (`room_config.yaml`)

Define which skills a room **uses**:

```yaml
skills:
  # Optional: override the model used for skill execution
  model_name: "gpt-oss:latest"

  # Reference installation-level skills by name
  skill_names:
    - "bare-bones"
    - "my-custom-skill"

  # Define room-specific skills inline
  skill_configs:
    - skill_name: "rag"
      kind: "haiku.rag.skills.rag"
      rag_lancedb_stem: "rag"
```

## Creating a Filesystem Skill

### Directory Structure

```
skills/
└── my-skill/
    └── SKILL.md
```

### Minimum `SKILL.md`

```markdown
---
name: my-skill
description: A brief description of what this skill does
---

Instructions for the AI agent when this skill is active.
These instructions are injected into the agent's context.
```

### Full `SKILL.md` with all fields

```markdown
---
name: my-skill
description: A brief description of what this skill does
license: MIT
compatibility: ">=0.32"
metadata:
  author: your-name
  version: "1.0.0"
---

Detailed instructions for the AI agent.

You can use markdown formatting here. The agent will receive
these instructions as part of its system context.
```

**Important**: Do NOT include `allowed_tools` in the SKILL.md frontmatter. This field is managed internally by the skills framework and will cause a conflict if specified manually.

## Configuring RAG Skills

RAG skills connect a room to a LanceDB vector database for document retrieval.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `skill_name` | string | Unique name for this skill instance |
| `kind` | string | Must be `"haiku.rag.skills.rag"` |
| `rag_lancedb_stem` | string | Name stem for the LanceDB directory (e.g., `"rag"` → `{RAG_LANCE_DB_PATH}/rag.lancedb`) |

**Note**: `rag_lancedb_stem` resolves relative to the `RAG_LANCE_DB_PATH` environment variable configured in your installation YAML. Ensure this variable points to a valid directory containing your indexed LanceDB databases.

### Alternative: Override Path

Instead of `rag_lancedb_stem`, you can specify an absolute or relative path:

```yaml
skill_configs:
  - skill_name: "rag"
    kind: "haiku.rag.skills.rag"
    rag_lancedb_override_path: "../custom/db/path"
```

You must specify exactly one of `rag_lancedb_stem` or `rag_lancedb_override_path`.

### Room-Level RAG Config Override

Place a `haiku.rag.yaml` file in the room directory to override global RAG settings:

```
rooms/
└── my-room/
    ├── room_config.yaml
    └── haiku.rag.yaml      # Optional: room-level RAG overrides
```

## Mixing Skill Types

A room can use multiple skill types simultaneously:

```yaml
# room_config.yaml
skills:
  # Filesystem skills from installation
  skill_names:
    - "code-review"
    - "data-analysis"

  # RAG skill defined inline
  skill_configs:
    - skill_name: "rag"
      kind: "haiku.rag.skills.rag"
      rag_lancedb_stem: "rag"
```

This produces a room with 3 skills: two filesystem skills (via `skill_names`) and one RAG skill (via `skill_configs`).

## Validation

### Check configuration

```bash
soliplex-cli check-config example/minimal.yaml
```

### List available skills

```bash
soliplex-cli list-skills example/minimal.yaml
```

### Verify via API

```bash
curl http://localhost:8000/api/v1/rooms/{room_id} | python -m json.tool
```

The response includes a `skills` object with each skill's `source`, `description`, and `state_type_schema`.

## Known Limitations

- **Duplicate `skill_name` values**: If two entries in `skill_configs` share the same `skill_name`, the last one silently wins. No warning is logged.
- **`rag_features` and `background_context`**: These fields from the legacy `haiku_chat` module are **not yet supported** in the new skill system. Remove them from your room configs.
- **`allowed_tools` in SKILL.md**: Do not include `allowed_tools` in filesystem skill frontmatter — it conflicts with the upstream parser.

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `MissingSkillNames` | Room references a skill not in installation config | Add the skill to `skill_configs` in installation YAML |
| `RagDbExactlyOneOfStemOrOverride` | Neither or both of `rag_lancedb_stem`/`rag_lancedb_override_path` set | Specify exactly one |
| `RagDbFileNotFound` | LanceDB directory doesn't exist | Run document indexing first, or check `RAG_LANCE_DB_PATH` env var |
| `KeyError` on skill `kind` | Invalid `kind` value | Use one of: `filesystem`, `entrypoint`, `haiku.rag.skills.rag`, `haiku.rag.skills.rlm` |

## Migration from `haiku_chat`

If upgrading from the legacy `haiku_chat` module:

1. Remove any `ChatAgentConfig` references from `meta.agent_configs`
2. Remove `soliplex.haiku_chat.ChatAgentConfig` from meta config
3. Replace chat agent configs with standard `AgentConfig` using `template_id`
4. Add RAG skills to room configs using the new `skills:` block:
   ```yaml
   skills:
     skill_configs:
       - skill_name: "rag"
         kind: "haiku.rag.skills.rag"
         rag_lancedb_stem: "rag"
   ```
5. **Remove** any `rag_features` or `background_context` keys from room configs (not yet supported)
6. Bump `haiku.rag-slim` to `>= 0.32.3, < 0.33` in your dependencies
