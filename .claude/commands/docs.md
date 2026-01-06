Perform a comprehensive documentation gap analysis for the docs directory.

## Instructions

Execute a minimum of 3 passes to identify documentation gaps across all documentation files.

### Pass 1: Inventory & Recent Changes
1. Run `git log --oneline -20` to see recent commits
2. List all files in `docs/` directory
3. Identify which documentation areas might be affected by recent changes

### Pass 2: Deep Verification by Section

Compare each documentation section against its implementation:

**Reference Section**
- `docs/reference/cli.md` → `src/soliplex/cli.py`, `src/soliplex/tui/`
- `docs/reference/config-schema.md` → `src/soliplex/config.py`
- `docs/reference/server-api.md` → `src/soliplex/views/` (OpenAPI)

**Developer Guide - API**
- `docs/developer-guide/api/models.md` → `src/soliplex/models.py`
- `docs/developer-guide/api/rest-endpoints.md` → `src/soliplex/views/`
- `docs/developer-guide/api/agui-protocol.md` → `src/soliplex/agui/`

**Developer Guide - Agents**
- `docs/developer-guide/agents/configuration.md` → `src/soliplex/agents.py`
- `docs/developer-guide/agents/factory-agents.md` → `src/soliplex/agents.py`
- `docs/developer-guide/agents/tools.md` → `src/soliplex/tools.py`
- `docs/developer-guide/agents/streaming.md` → `src/soliplex/agui/`

**Developer Guide - RAG**
- `docs/developer-guide/rag/database.md` → haiku-rag integration
- `docs/developer-guide/rag/tools.md` → `src/soliplex/tools.py`
- `docs/developer-guide/rag/citations.md` → `src/soliplex/agui/features.py`

**Developer Guide - MCP**
- `docs/developer-guide/mcp/server.md` → `src/soliplex/mcp_server.py`
- `docs/developer-guide/mcp/client.md` → `src/soliplex/mcp_client.py`

**Developer Guide - Flutter**
- `docs/developer-guide/flutter/architecture.md` → `src/flutter/lib/`
- `docs/developer-guide/flutter/widgets.md` → `src/flutter/lib/widgets/`

**Admin Guide - Configuration**
- `docs/admin-guide/configuration/installation.md` → `src/soliplex/config.py`
- `docs/admin-guide/configuration/agents.md` → `src/soliplex/agents.py`
- `docs/admin-guide/configuration/rooms.md` → `src/soliplex/config.py`
- `docs/admin-guide/configuration/rag.md` → haiku-rag config
- `docs/admin-guide/configuration/secrets.md` → `src/soliplex/secrets.py`
- `docs/admin-guide/configuration/environment.md` → `src/soliplex/config.py`
- `docs/admin-guide/configuration/oidc.md` → `src/soliplex/auth.py`
- `docs/admin-guide/configuration/quizzes.md` → `src/soliplex/views/quizzes.py`
- `docs/admin-guide/configuration/meta.md` → `src/soliplex/installation.py`
- `docs/admin-guide/configuration/completions.md` → `src/soliplex/views/completions.py`
- `docs/admin-guide/configuration/filesystem-layout.md` → filesystem structure

**Admin Guide - Authentication**
- `docs/admin-guide/authentication/index.md` → `src/soliplex/auth.py`

**Admin Guide - Deployment**
- `docs/admin-guide/deployment/docker.md` → `Dockerfile`, `docker-compose.yaml`
- `docs/admin-guide/deployment/production.md` → deployment configs
- `docs/admin-guide/deployment/monitoring.md` → logging config

**Getting Started**
- `docs/getting-started/quickstart.md` → `example/` configs
- `docs/getting-started/installation.md` → `pyproject.toml`, README
- `docs/getting-started/first-chat.md` → example configs

**User Guide**
- `docs/user-guide/rooms.md` → Flutter app, config
- `docs/user-guide/rag-search.md` → `src/soliplex/tools.py`
- `docs/user-guide/keyboard-shortcuts.md` → `src/flutter/lib/`

**Contributing**
- `docs/contributing/development-setup.md` → `pyproject.toml`, CLAUDE.md
- `docs/contributing/code-style.md` → ruff config, Flutter analysis

**Troubleshooting**
- `docs/troubleshooting/debugging.md` → logging, error handling

Look for:
- Undocumented features, endpoints, or models
- Documented features that no longer exist
- Incorrect examples or code snippets
- Missing configuration options
- Outdated version numbers

### Pass 3: Cross-Reference Validation
- Verify `mkdocs.yml` navigation matches actual files in `docs/`
- Verify internal documentation links work
- Check index.md files have accurate section overviews

### Output
Present findings as a prioritized gap analysis:

**Critical**: Features that exist but are completely undocumented
**High**: Significant gaps or incorrect information
**Medium**: Minor improvements or enhancements

For each gap, include:
- File path (both docs and implementation)
- Specific issue description
- Recommended fix

Ask before making any changes. User will review the analysis and decide what to implement.