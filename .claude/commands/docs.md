Perform a comprehensive documentation gap analysis for the docsV2 directory.

## Instructions

Execute a minimum of 3 passes to identify documentation gaps across ALL 55 documentation files.

### Pass 1: Inventory & Recent Changes
1. Run `git log --oneline -20` to see recent commits
2. List all files in `docsV2/` directory (currently 55 files)
3. Identify which documentation areas might be affected by recent changes

### Pass 2: Deep Verification by Section

Compare each documentation section against its implementation:

**Reference Section**
- `docsV2/reference/cli.md` → `src/soliplex/cli.py`
- `docsV2/reference/config-schema.md` → `src/soliplex/config.py`
- `docsV2/reference/server-api.md` → `src/soliplex/views/` (OpenAPI)

**Developer Guide - API**
- `docsV2/developer-guide/api/models.md` → `src/soliplex/models.py`
- `docsV2/developer-guide/api/rest-endpoints.md` → `src/soliplex/views/`
- `docsV2/developer-guide/api/agui-protocol.md` → `src/soliplex/agui/`

**Developer Guide - Agents**
- `docsV2/developer-guide/agents/configuration.md` → `src/soliplex/agents.py`
- `docsV2/developer-guide/agents/factory-agents.md` → `src/soliplex/agents.py`
- `docsV2/developer-guide/agents/tools.md` → `src/soliplex/tools.py`
- `docsV2/developer-guide/agents/streaming.md` → `src/soliplex/agui/`

**Developer Guide - RAG**
- `docsV2/developer-guide/rag/database.md` → haiku-rag integration
- `docsV2/developer-guide/rag/tools.md` → `src/soliplex/tools.py`
- `docsV2/developer-guide/rag/citations.md` → `src/soliplex/agui/features.py`

**Developer Guide - MCP**
- `docsV2/developer-guide/mcp/server.md` → `src/soliplex/mcp_server.py`
- `docsV2/developer-guide/mcp/client.md` → `src/soliplex/mcp_client.py`

**Developer Guide - Flutter**
- `docsV2/developer-guide/flutter/architecture.md` → `src/flutter/lib/`
- `docsV2/developer-guide/flutter/widgets.md` → `src/flutter/lib/widgets/`

**Admin Guide - Configuration**
- `docsV2/admin-guide/configuration/installation.md` → `src/soliplex/config.py`
- `docsV2/admin-guide/configuration/agents.md` → `src/soliplex/agents.py`
- `docsV2/admin-guide/configuration/rooms.md` → `src/soliplex/config.py`
- `docsV2/admin-guide/configuration/rag.md` → haiku-rag config
- `docsV2/admin-guide/configuration/secrets.md` → `src/soliplex/secrets.py`
- `docsV2/admin-guide/configuration/environment.md` → `src/soliplex/config.py`
- `docsV2/admin-guide/configuration/oidc.md` → `src/soliplex/auth.py`
- `docsV2/admin-guide/configuration/quizzes.md` → `src/soliplex/views/quizzes.py`
- `docsV2/admin-guide/configuration/meta.md` → `src/soliplex/installation.py`

**Admin Guide - Deployment**
- `docsV2/admin-guide/deployment/docker.md` → `Dockerfile`, `docker-compose.yaml`
- `docsV2/admin-guide/deployment/production.md` → deployment configs
- `docsV2/admin-guide/deployment/monitoring.md` → logging config

**Getting Started**
- `docsV2/getting-started/quickstart.md` → `example/` configs
- `docsV2/getting-started/installation.md` → `pyproject.toml`, README
- `docsV2/getting-started/first-chat.md` → example configs

**User Guide**
- `docsV2/user-guide/rooms.md` → Flutter app, config
- `docsV2/user-guide/rag-search.md` → `src/soliplex/tools.py`
- `docsV2/user-guide/keyboard-shortcuts.md` → `src/flutter/lib/`

**Contributing**
- `docsV2/contributing/development-setup.md` → `pyproject.toml`, CLAUDE.md
- `docsV2/contributing/code-style.md` → ruff config, Flutter analysis

**Troubleshooting**
- `docsV2/troubleshooting/debugging.md` → logging, error handling

Look for:
- Undocumented features, endpoints, or models
- Documented features that no longer exist
- Incorrect examples or code snippets
- Missing configuration options
- Outdated version numbers

### Pass 3: Cross-Reference Validation
- Verify `mkdocsV2.yml` navigation matches actual files in `docsV2/`
- Check for any legacy docs in `docs/` that should be migrated to `docsV2/`
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