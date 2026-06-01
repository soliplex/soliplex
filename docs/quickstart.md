# Quickstart

The fastest way to stand up and run your own Soliplex is to let a
skills-compatible AI agent (e.g. Claude Code, Codex, Copilot) do it for you.
Soliplex publishes two [Agent Skills](https://agentskills.io/) that teach
your agent how to deploy and operate it -- no need to clone or build the
backend yourself.

## The two skills

- **`soliplex-template`** scaffolds a complete, runnable Docker Compose stack
  (nginx, the Soliplex backend, the Flutter frontend, an ingester, Postgres,
  and a TUI). It prompts for the parameters you care about -- project name,
  host ports, your Ollama URL, models, version pins, auth mode -- and writes
  out the full project. It is published from
  [soliplex/soliplex-template](https://github.com/soliplex/soliplex-template).
- **`soliplex-docs`** is this documentation, packaged as a skill, so your
  agent can answer questions about installing, configuring, and operating
  your deployment straight from the official docs. See the
  [Documentation Skill](docs-skill.md) page for how it is built, versioned,
  and kept up to date.

## Install the skills

Each skill is a tarball that unpacks into a `soliplex-template/` or
`soliplex-docs/` directory. Install them by unpacking both into whichever
directory your agent scans for skills. The directory differs per agent:

| Agent | Per user | Per project |
|-------|----------|-------------|
| [Claude Code](https://code.claude.com/docs/en/skills) | `~/.claude/skills` | `.claude/skills` |
| [OpenAI Codex](https://developers.openai.com/codex/skills/) | `~/.agents/skills` | `.agents/skills` |
| [GitHub Copilot](https://code.visualstudio.com/docs/copilot/customization/agent-skills) | `~/.copilot/skills` | `.github/skills` |

Point `SKILLS_DIR` at the row that matches your agent (the example below uses
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

To install into a project instead -- for example a Codex project -- set
`SKILLS_DIR=.agents/skills` and rerun the `curl` commands.

The table covers the common cases; consult your agent's documentation (linked
above) for the authoritative list of locations it scans. Both skills bundle a
`scripts/skill_versions.py` helper to list published builds and upgrade in
place; see the [Documentation Skill](docs-skill.md) page for details.

## Use the skills

Start your agent in the directory where you want the deployment to live and
ask it to scaffold a stack -- for example, *"Use the soliplex-template skill
to set up a new Soliplex deployment."* The skill walks you through the
parameters and generates the project; then `docker compose up` brings it
online (the frontend defaults to <http://localhost:9000>).

Ask the same agent configuration or operations questions and it will answer
from the `soliplex-docs` skill -- for example, *"Use the soliplex-docs skill
to answer questions about configuring or operating a Soliplex installation,"*
and then *"How do I add a new room?"*

## Other paths

The skills-based path is the recommended way to get started. To deploy or
develop Soliplex by hand instead, see:

- [Prerequisites](prerequisites.md) -- system requirements and an
  installation checklist.
- [Server Setup](server/index.md) -- install the backend from a source
  checkout and run it.
- [Docker Deployment](docker.md) -- run the stack with Docker Compose
  yourself.
