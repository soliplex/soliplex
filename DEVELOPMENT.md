# Development Guide

This guide is for developers working on the Soliplex backend and TUI. If
you only want to *run* Soliplex, see the [Quickstart](README.md#quickstart)
instead.

This repository contains the **Python backend and TUI only**. The Flutter
frontend lives in a sibling repo at
<https://github.com/soliplex/frontend> with its own tooling.

> [AGENTS.md](AGENTS.md) and [CLAUDE.md](CLAUDE.md) are condensed,
> agent-facing versions of this guide. If you change a workflow here,
> update those too.

## Getting started

Prerequisites:

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (used for everything -- do not use `pip`)

Set up a working tree:

```bash
git clone git@github.com:soliplex/soliplex.git
cd soliplex

# Install the project and its dev dependencies
uv sync --group dev

# Configure environment (edit .env with your settings)
cp .env.example .env
```

Run all Python commands through `uv run` so they use the project
environment.

## Running locally

```bash
# Start a dev server against the minimal example (no auth)
uv run soliplex-cli serve example/minimal.yaml --no-auth-mode

# Validate a configuration before serving it
uv run soliplex-cli audit example/minimal.yaml
```

The minimal example uses Ollama and expects `OLLAMA_BASE_URL` to be set
(in your shell or `.env`). The server listens on `http://localhost:8000`
by default. Run `uv run soliplex-cli --help` for the full command list,
and see the [`soliplex-cli` reference](docs/server/cli.md) for every
subcommand and option.

### Entry points

- `soliplex-cli` -- backend CLI (serve, config audits, admin users,
  model pulls, ...)
- `soliplex-tui` -- terminal UI client
- `soliplex-tui-serve` -- TUI server

## Repository structure

Most modules are self-explanatory from their filenames (`ls src/soliplex/`
for the full layout). The non-obvious ones:

- `agui/` -- AG-UI protocol (threads, runs, persistence)
- `authz/` -- authorization policy engine
- `config/` -- YAML config parsing (16 modules; `installation.py` is the
  top-level entry)
- `tools/` -- agent tools (RAG, feedback, file uploads)
- `agents.py` -- Pydantic AI agent creation
- `completions.py` -- OpenAI-compatible streaming endpoint (not just
  LLM-level completions)
- `installation.py` -- installation lifespan, admin bootstrap, and global
  state management
- `main.py` -- FastAPI app factory (`create_app`)
- `tests/unit/` -- unit tests; mirrors `src/soliplex/`
- `tests/functional/` -- tests requiring an LLM (skipped by default)
- `example/` -- sample configs (rooms, completions, oidc, quizzes, skills)
- `schemas/` -- AG-UI feature JSON schemas

Useful files:

- `pyproject.toml` -- dependencies, scripts, and tool configuration
- `src/soliplex/config/installation.py` -- master config parsing
- `src/soliplex/main.py` -- FastAPI app factory
- `example/installation.yaml` -- full config example
- `example/minimal.yaml` -- minimal config for development
- `.env.example` -- environment variable reference

## Code style

- Line length: 79 characters
- Single-line imports, enforced via isort (through ruff)
- Ruff rule sets: `F`, `E`, `B`, `U`, `I`, `PD`, `TRY`, `PT`
- Target version: Python 3.13

```bash
# Check lint and formatting
uv run ruff check
uv run ruff format --check

# Auto-fix lint and formatting
uv run ruff check --fix
uv run ruff format
```

## Pre-commit hooks

(Optional) To automate linting for code style and other checks
that run in CI run automatically before every commit, install the
[pre-commit](https://pre-commit.com/) hooks.

```bash
uv run pre-commit install

# Optionally run every hook against the whole tree once
uv run pre-commit run --all-files
```

The configured hooks (see `.pre-commit-config.yaml`) enforce:

- **ruff-check** -- lint Python sources (auto-fixing where possible).
- **ruff-format** -- format Python sources.
- **pymarkdown** -- lint Markdown files.
- **agentskills-validate** -- validate the published `soliplex-docs` agent
  skill, using the `agentskills` console script from the `soliplex-skills`
  dev dependency. Runs only when something under `skills/soliplex-docs/`
  changes.
- **lint-textio** -- reject text file IO in `src/soliplex/` that passes no
  explicit `encoding=` and so falls back to the host locale encoding
  (`cp1252` on a typical Windows host); see `scripts/lint_textio.py`, which
  also runs standalone.
- **lint-textio-self-test** -- run `scripts/lint_textio.py --self-test`
  whenever that script itself is touched. The self-test guards the guard:
  a check that has silently stopped matching anything would otherwise pass
  by finding no violations, so it runs before the check proper (in CI too
  -- see `.github/workflows/python-lint.yaml`).
- **actionlint** -- lint GitHub Actions workflow files.
- **check-toml** / **check-yaml** -- validate TOML and YAML syntax.
- **gitleaks** -- scan for committed secrets.
- **pip-audit** -- scan dependencies for known vulnerabilities (runs when
  `pyproject.toml`, `uv.lock`, or `.pre-commit-config.yaml` changes).
- **debug-statements** -- reject leftover `pdb` / `breakpoint()` calls.
- **trailing-whitespace** / **end-of-file-fixer** -- normalize whitespace
  and trailing newlines.
- **check-merge-conflict** -- reject unresolved merge-conflict markers.
- **no-commit-to-branch** -- block direct commits to `main` / `master`.

## Testing

- Unit tests live in `tests/unit/`, mirroring the `src/soliplex/`
  structure.
- 100% branch coverage is enforced via pytest-cov
  (`--cov-fail-under=100`). Coverage is measured over four targets (see
  `addopts` in `pyproject.toml`): `src/soliplex`, `tests/unit`, `scripts`,
  and `skills/soliplex-docs/scripts` -- the test suite and the helper
  scripts are held to the same 100% bar as `src/`.
- Those targets are spelled as *paths* rather than importable names, and
  need to stay that way. `soliplex` is a namespace package (there is no
  `src/soliplex/__init__.py`), and coverage cannot enumerate a namespace
  package by walking the filesystem: given `--cov=soliplex` it reports only
  the modules that were imported during the run, so a module no test
  imports never appears in the report and never trips the threshold. A path
  target is walked, and unexecuted files under it are reported at 0%.
- `[tool.coverage.run]` `omit` is consequently the one place that decides
  what is exempt from the threshold. It lists `scripts/lint_textio.py`,
  which runs its own `--self-test` during lint, and `src/soliplex/tui/*`,
  since the TUI is deliberately untested. Everything else under
  `src/soliplex/` has to reach 100%, so new code there cannot slip past the
  gate by simply having no test import it.
- `--cov-fail-under=100` is set in `addopts`, so it applies to every
  `pytest` invocation rather than only to full runs. Any subset -- one
  file, one test, the functional suite -- needs `--no-cov`, or the run
  fails on the coverage threshold whatever the tests themselves did.
- Async tests use pytest-asyncio.
- Functional tests in `tests/functional/` require a running LLM and are
  skipped by default (marker: `needs_llm`).

```bash
# Run the unit tests (100% coverage required)
uv run pytest

# Run a single file or test ('--no-cov': see below)
uv run pytest --no-cov tests/unit/test_agents.py
uv run pytest --no-cov tests/unit/test_agents.py::test_name

# Run tests for a sub-package, measuring coverage only for the target
# (can help finding implicitly-covered items):
uv run pytest --cov-reset --cov soliplex.agui tests/unit/agui

# Run functional tests (require a running LLM)
uv run pytest --no-cov tests/functional/ -m needs_llm
```

### Running tests in parallel

`pytest-xdist` is a dev dependency, but no `-n` is baked into `addopts`, so
a plain `uv run pytest` is serial. Parallelism is opt-in, and it is only
safe for the unit suite:

```bash
# Unit tests, in parallel (see below for choosing '-n')
uv run pytest -n 8

# Functional tests -- serial, deliberately: no '-n'
uv run pytest --no-cov -m "not needs_llm" tests/functional/
```

Choosing a value for `-n`: start from `nproc` and take about half the
logical cores -- `-n 8` on a 16-core box, `-n 4` on an 8-core one. Two
things push the useful number below one-worker-per-core. Each worker pays a
fixed cost to start up and collect the suite before it runs anything, so
the marginal worker buys less and less; and a run that saturates every core
leaves nothing for the editor, browser, or language server you are using
meanwhile. Half is a starting point rather than a rule -- the best value
depends on the machine, so if a run feels slow, time a couple of values and
keep the winner.

`-n auto` asks xdist for one worker per logical core. That is the right
choice when the core count is not known ahead of time, which is exactly
CI's situation: `.github/workflows/python-test.yaml` runs the unit suite
with `-n auto` so the same workflow adapts to whatever runner size GitHub
provides. On a machine whose core count you do know, prefer an explicit
number.

The functional suite has to stay serial. Its tests share on-disk state and
module-scoped application fixtures -- `test_sandbox_workdirs.py`, for
instance, creates a sandbox workdir tree keyed by a constant `ROOM_ID` and
`rmtree`s it on teardown -- so xdist workers would race, and tear down
directories still in use by their peers. CI runs the functional tests in
their own step with no `-n`.

Coverage is unaffected by `-n`: pytest-cov collects each worker's data and
merges it, so a parallel run enforces the same 100% threshold as a serial
one.

## Configuration system

- Configuration is YAML-based and hierarchical, parsed under
  `src/soliplex/config/`. The top-level entry is `InstallationConfig` in
  `config/installation.py`.
- Config classes are dataclasses with a `from_yaml` classmethod.
- Each config dataclass carries `_installation_config` and `_config_path`
  as private fields, so nested configs can resolve environment variables,
  secrets, and paths relative to the config file without threading that
  context through every `from_yaml` call.
- Environment variables are resolved via `Installation.get_environment()`.
- Secrets are resolved through a configurable source chain (environment
  variables, files, subprocess, random generation) in `config/secrets.py`.

The full configuration reference is in [docs/config/](docs/config/).

## Common tasks

### Adding a tool

1. Create or modify a tool module in `src/soliplex/tools/`.
2. Tool functions are async and accept `RunContext[AgentDependencies]`.
3. If the tool needs configuration, add a `ToolConfig` subclass in
   `config/tools.py`.
4. Register it in `TOOL_CONFIG_CLASSES_BY_TOOL_NAME` (in `config/tools.py`
   and `config/meta.py`).
5. Reference the tool in a room configuration under `agent.tools`.

### Adding a room

1. Create `example/rooms/<room_id>/room_config.yaml`.
2. Required fields: `id`, `name`, `description`, `agent`.
3. Optionally add `prompt.txt` for an external system prompt.

### Adding an API endpoint

1. Create or modify a router in `src/soliplex/views/`.
2. Register the router in `main.py` with the appropriate prefix.
3. Add unit tests achieving 100% branch coverage.

## Architecture overview

- The FastAPI app is created via `create_app()` in `main.py`.
- Rooms contain agents, each with tools, skills, and an LLM provider
  configuration.
- The AG-UI protocol handles the thread/run lifecycle with SSE event
  streaming.
- Authorization is handled by a policy engine in `authz/`.
- The MCP server exposes Soliplex tools; the MCP client consumes external
  tool servers.
- Authentication is via OIDC/JWT in `authn.py`.
- Public API models are defined in `models.py`.

## Key dependencies

See `pyproject.toml` for authoritative version constraints.

- FastAPI / Uvicorn -- REST API and ASGI server
- pydantic-ai-slim[google] -- agent framework
- haiku.rag-slim -- RAG functionality
- FastMCP -- Model Context Protocol
- ag-ui-protocol -- AG-UI event protocol
- SQLModel / aiosqlite -- database ORM

## Environment variables

See `.env.example` for the full reference. Key variables:

- `OLLAMA_BASE_URL` -- Ollama server URL (without the `/v1` suffix)
- `OPENAI_API_KEY` / `GEMINI_API_KEY` -- LLM provider keys
- `SOLIPLEX_URL_SAFE_TOKEN_SECRET` -- MCP token secret (auto-generated if
  unset)
- `LOGFIRE_TOKEN` -- Pydantic Logfire token (optional)

## Documentation

Detailed configuration and usage docs are in [docs/](docs/), published as a
[Zensical site](https://soliplex.github.io/soliplex/). Example
configurations are in [example/](example/).

## Releasing `soliplex` to PyPI

Soliplex distributions get pushed to [PyPI](https://pypi.org) via a GitHub
workflow action, defined in `.github/workflows/pypi.yaml`. This workflow
is triggered by publishing a GitHub release, typically from a pre-existing
signed tag.

### Minor releases

Minor releases typically indicate new features (a la <https://semver.org>).

1. For each "minor" release, e.g. `v0.47`, the developer first creates
   a release branch (in the example case, `v0.47.x`), with an associated
   new [Git worktree](https://git-scm.com/docs/git-worktree):

   ```bash
   git worktree add -b v0.47.x ../soliplex-v0.47.x
   ```

2. In the new worktree, the developer captures a git log since the previous
   minor release:

   ```bash
   cd ../soliplex-v0.47.x
   git log v0.46..HEAD > ../soliplex-v0.47.txt
   ```

   and edits it into a condensed, human-focused change log, dropping
   any changes backported to previous patch releases (e.g., in `v0.46.1`,
   etc.).

   ```bash
   "$EDITOR" ../soliplex-v0.47.txt
   ```

3. The developer then prepares the new release, editing the version
   in `pyproject.toml` (no `v` prefix, e.g. `version = "0.47"`)
   and then synchronizing the `uv` lock file:

   ```bash
   uv sync --all-groups
   ```

   and committing the release prep changes:

   ```bash
   git commit pyproject.toml uv.lock -m "chore: prep 'v0.47' release"
   ```

4. The developer then creates a signed tag using the changelog created
   in step #2:

   ```bash
   git tag -s -F ../soliplex-v0.47.txt v0.47
   ```

   and pushes the new branch and tag to GitHub:

   ```bash
   git push origin v0.47.x v0.47
   ```

5. The developer then visits the GitHub page for the new tag in the browser
   (in this case, <https://github.com/soliplex/soliplex/releases/tag/v0.47>)
   and clicks the "Create release from tag" button.

   After filling in the "Release title" value (e.g.,
   `soliplex v0.47: <terse summary>`), the developer pastes the changelog
   text into the "Describe this release" textarea, and submits the form.

### Patch releases

Patch releases typically indicate bug fixes (a la <https://semver.org>).

1. After merging a bugfix PR to `main`, the developer backports
   the fix onto the most recent minor release branch inside its worktree
   using [`git cherry-pick`](https://git-scm.com/docs/git-cherry-pick).

   In the worktree for `main`, where the bugfix branch was created:

   ```bash
   git checkout main && git fetch --prune origin && git merge origin/main
   git log # verify the PR squash-merge hash
   ```

   In the release branch worktree:

   ```bash
   cd ../soliplex-v0.47.x
   git cherry-pick <pr-squash-merge-release-hash>
   ```

2. Once all bugfix PRs to be released have been merged and backported, the
   developer creates a new changelog using `git log`, using as the base
   either the most recent patch release for the branch (e.g. `v0.47.2`
   when making a new `v0.47.3` release), or the minor release tag if
   making the first patch release (i.e., `v0.47` when making the `v0.47.1`
   release):

   ```bash
   git log <base-tag>..v0.47.x > ../soliplex-v0.47.<patch#>.txt
   "$EDITOR" ../soliplex-v0.47.<patch#>.txt
   ```

3. The developer then creates a patch release tag in the release branch
   worktree:

   ```bash
   cd ../soliplex-v0.47.x
   "$EDITOR" pyproject.toml  # 'version = "0.47.<patch#>"'
   uv sync --all-groups
   git commit pyproject.toml uv.lock -m "chore: prep 'v0.47.<patch#>' release"
   git tag -s -F ../soliplex-v0.47.<patch#>.txt v0.47.<patch#>
   ```

   and pushes the tag / branch to GitHub:

   ```bash
   git push origin v0.47.x v0.47.<patch#>
   ```

4. The developer then makes a GitHub release from the new tag, exactly as
   for the minor release tag above.
