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

## Managing this skill's version

`scripts/skill_versions.py` lists, diffs, and upgrades published builds of this
skill against its GitHub releases. It is a small
[PEP 723](https://peps.python.org/pep-0723/) helper backed by the shared
[`soliplex-skills`](https://soliplex.github.io/soliplex-skills/) library, so run
it with `uv` (the first run fetches that library):

```bash
uv run scripts/skill_versions.py list              # published versions, newest first
uv run scripts/skill_versions.py diff [TAG]         # installed vs a published build (default: latest)
uv run scripts/skill_versions.py upgrade [TAG]      # install a published build in place (default: latest)
```

Two kinds of versions are published. **Release** builds are snapshots attached
to tagged software releases (`v…`) — stable milestones that only change when a
release is cut. **Rolling** builds (`template-skill-YYYY.MM.DD-<sha>`) are
continuous per-build snapshots, tagged with the build date and short commit
hash; the `template-skill-latest` pointer always tracks the newest one, so the
default `latest` target for `diff`/`upgrade` means "the current tip of the
rolling line." `list` shows both newest first (marking the installed copy and
the `latest` pointer); narrow it with `list --kind release` or
`list --kind rolling`. To stay on stable milestones rather than the rolling
tip, pass an explicit `v…` `TAG` to `diff`/`upgrade`.

Set `GITHUB_TOKEN`/`GH_TOKEN` to raise the GitHub API rate limit. The helper
needs network access to PyPI (to provision `soliplex-skills` on first run) and
to `api.github.com`/`github.com`.

The **Documentation map** below is regenerated from the site nav at build time.
