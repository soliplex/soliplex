---
name: soliplex-docs
description: "Soliplex documentation: how to install, configure, run, and use Soliplex -- a self-hosted RAG/AI system with a FastAPI backend, Flutter client, and terminal UI. Covers configuration (rooms, agents, completions, RAG, OIDC, skills, quizzes, AG-UI features), server setup and CLI, environment variables, secrets, Docker deployment, RAG database setup, and client usage. Use when answering questions about installing, configuring, operating, or troubleshooting Soliplex."
license: MIT
compatibility: "The documentation itself needs no special environment. The bundled scripts/skill_versions.py is a uv PEP 723 script (Python 3.12+): run it with 'uv run scripts/skill_versions.py ...', which provisions the 'soliplex-skills' library from PyPI on first use. Network access to pypi.org and api.github.com / github.com is required (honors GITHUB_TOKEN / GH_TOKEN)."
metadata:
  source: https://github.com/soliplex/soliplex
---

# Soliplex documentation

This skill bundles the full Soliplex documentation. Use it to answer questions about installing, configuring, operating, or troubleshooting Soliplex.

## How to use this skill

1. Scan the **Documentation map** below and pick the entries whose topic matches the question.
2. Read the matching file(s) under `references/` (they preserve the site's structure and cross-links).
3. Answer strictly from the documentation. If the docs do not cover it, say so rather than guessing.

## Checking for updates

This skill is a point-in-time snapshot (see `metadata` above). To see what has been published and whether a newer build exists, run the bundled helper with `uv` (the first run fetches the small `soliplex-skills` library it depends on):

```bash
# List published versions (rolling builds + release snapshots)
uv run scripts/skill_versions.py list

# Show what changed upstream since this copy was built
uv run scripts/skill_versions.py diff latest

# Compare any two published versions (see 'list' for tags)
uv run scripts/skill_versions.py diff docs-2026.05.20-abc1234 docs-2026.05.29-def5678

# Upgrade this copy in place to the newest build (or a given tag)
uv run scripts/skill_versions.py upgrade
```

The **Documentation map** below is regenerated from the site nav at build time.
