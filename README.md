# Soliplex

An AI-powered Retrieval-Augmented Generation (RAG) system with a modern web interface.

## Overview

Soliplex is a self-hosted, full-stack RAG/AI system: a FastAPI backend
(a thin configuration and authentication layer around
[pydantic-ai](https://ai.pydantic.dev/)), a hardened
[Flutter client](https://github.com/soliplex/frontend), and a terminal UI.

See the [Overview](docs/overview.md) for what Soliplex is, when (and when not)
to use it, how it compares to alternatives, and the full feature and
architecture breakdown.

## Quickstart

The fastest way to stand up and run your own Soliplex is to let a
skills-compatible AI agent (e.g. Claude Code, Codex, Copilot)
do it for you. Soliplex publishes two [Agent Skills](https://agentskills.io/)
that teach your agent how to deploy and operate it -- no need to clone or hack
on this repository:

- **`soliplex-template`** scaffolds a complete, runnable Docker Compose stack
  (nginx, the Soliplex backend, the Flutter frontend, an ingester, Postgres,
  and a TUI). It prompts for the parameters you care about -- project name,
  host ports, your Ollama URL, models, version pins, auth mode -- and writes
  out the full project. Published from
  [soliplex/soliplex-template](https://github.com/soliplex/soliplex-template).

- **`soliplex-docs`** is the full Soliplex documentation, so your agent can
  answer questions about installing, configuring, and operating your
  deployment straight from the official docs. Published from this repository.

### Install the skills

Each skill is a tarball that unpacks into a `soliplex-template/` or
`soliplex-docs/` directory. Install them by unpacking both into whichever
directory your agent scans for skills. The directory differs per agent:

| Agent | Per user | Per project |
|-------|----------|-------------|
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills` | `.claude/skills` |
| [OpenAI Codex](https://developers.openai.com/codex/skills/) | `~/.agents/skills` | `.agents/skills` |
| [GitHub Copilot](https://code.visualstudio.com/docs/copilot/customization/agent-skills) | `~/.copilot/skills` | `.github/skills` |

Point `SKILLS_DIR` at the row that matches your agent (the examples below use
the Claude Code per-user location) and unpack both skills into it:

```bash
SKILLS_DIR=~/.claude/skills
mkdir -p "$SKILLS_DIR"

# Deployment scaffolder
curl -fsSL \
  https://github.com/soliplex/soliplex-template/releases/download/template-skill-latest/soliplex-template-skill.tar.gz \
  | tar xz -C "$SKILLS_DIR"

# Documentation
curl -fsSL \
  https://github.com/soliplex/soliplex/releases/download/docs-latest/soliplex-docs-skill.tar.gz \
  | tar xz -C "$SKILLS_DIR"
```

For example, to install into a Codex project instead:

```bash
SKILLS_DIR=.agents/skills
```

The table covers the common cases; consult your agent's documentation (linked
above) for the authoritative list of locations it scans. Both skills bundle a
`scripts/skill_versions.py` helper to list published builds and upgrade in
place; see [docs/docs-skill.md](docs/docs-skill.md) for details.

### Use the skills

Start your agent in the directory where you want the deployment to live and
ask it to scaffold a stack -- for example, *"Use the soliplex-template skill
to set up a new Soliplex deployment."* The skill walks you through the
parameters and generates the project; then `docker compose up` brings it
online (the frontend defaults to <http://localhost:9000>).

Tell your agent to answer configuration or operations questions about Soliplex
using the `soliplex-docs` skill -- for example, *"Use the soliplex-docs skill
to answer questions about configuring or operating a Soliplex installation."*
and then *"What is a Soliplex installation?"*

> The remainder of this README covers running Soliplex from a source checkout
> and developing on the backend itself. If you only want to *use* Soliplex,
> the two skills above are all you need.

## Running from source

The skills-based [Quickstart](#quickstart) above is the recommended path for
most users. To run Soliplex from a checkout of this repository instead, see:

- [Prerequisites](docs/prerequisites.md) -- system requirements and an
  installation checklist.
- [Server Setup](docs/server/index.md) -- install the backend, run the example
  installations, and start the server.
- [`soliplex-cli` reference](docs/server/cli.md) -- every subcommand and option
  (config audits, serving, admin users, model pulls, ...).
- [RAG Database](docs/rag.md) -- create and populate the LanceDB database the
  examples expect.
- [Client Setup](docs/client.md) -- run the Flutter web client.
- [Docker Deployment](docs/docker.md) -- run the full stack with Docker Compose.

## Documentation

The full documentation set lives in [`docs/`](docs/) and is published as a
[Zensical site](https://soliplex.github.io/soliplex/):

> **Tip:** the same documentation is also available as the `soliplex-docs`
> Agent Skill, so a skills-compatible agent can answer questions straight from
> it -- see the [Quickstart](#quickstart) above.

- [Overview](docs/overview.md)
- [Prerequisites](docs/prerequisites.md)
- [Server Setup](docs/server/index.md) and
  [CLI Reference](docs/server/cli.md)
- [Client Setup](docs/client.md)
- [Docker Deployment](docs/docker.md)
- [RAG Database](docs/rag.md)
- [Documentation Skill](docs/docs-skill.md)
- [Configuration](docs/config/)
- [Usage](docs/usage.md)

## Configuration

Soliplex is configured by a tree of YAML files rooted at an
`installation.yaml`; sample configurations live in the
[`example/`](example/) directory. See the configuration docs:

- [Filesystem Layout](docs/config/filesystem_layout.md),
  [Installation](docs/config/installation.md),
  [Meta](docs/config/meta.md)
- [Rooms](docs/config/rooms.md),
  [Agents](docs/config/agents.md),
  [Completions](docs/config/completions.md)
- [RAG](docs/config/rag.md),
  [Quizzes](docs/config/quizzes.md),
  [AI Skills](docs/config/skills.md),
  [AG-UI Features](docs/config/agui.md)
- [Secrets](docs/config/secrets.md),
  [Environment](docs/config/environment.md),
  [OIDC Authentication](docs/config/oidc_providers.md)
- [Logfire](docs/config/logfire.md),
  [Console logging](docs/config/logging.md),
  [SQLAlchemy DBURIs](docs/config/dburis.md)

## Development

Contributor guidance -- setup, build and test commands, code style, the
configuration system, and how to add tools, rooms, and API endpoints -- lives
in [DEVELOPMENT.md](DEVELOPMENT.md). [AGENTS.md](AGENTS.md) and
[CLAUDE.md](CLAUDE.md) are condensed, agent-facing versions of the same
guidance.

## Related Repositories

- [soliplex/frontend](https://github.com/soliplex/frontend) -- Flutter client (cross-platform mobile/desktop)
- [soliplex/soliplex-template](https://github.com/soliplex/soliplex-template) -- Docker Compose deployment template
- [soliplex/ingester](https://github.com/soliplex/ingester) -- Content ingestion pipeline
- [soliplex/ingester-agents](https://github.com/soliplex/ingester-agents) -- Document ingestion agents
- [soliplex/whitelabel](https://github.com/soliplex/whitelabel) -- Customer white-label appshell template
- [Documentation site](https://soliplex.github.io/soliplex/)

## License

MIT License - Copyright (c) 2025 Enfold Systems, Inc.
