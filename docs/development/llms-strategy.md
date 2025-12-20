# LLM Documentation Strategy

This document describes the federated documentation strategy for AI agents (Claude Code, Gemini CLI, etc.).

## Overview

Soliplex uses a **federated documentation** approach that separates **discovery** (maps) from **knowledge** (content). This optimizes for local agent context windows by allowing agents to:

1. Load a small map file for navigation (~60 KB total)
2. Selectively load only the content they need (~516 KB total)

**Result**: ~88% context window savings for typical tasks.

## Architecture

```
site/llms.txt (368 B)              ← Entry point
├── llms-project.txt (1.2 KB)      ← Project map (setup, config)
│   └── llms-project-full.txt (42 KB)
├── llms-server.txt (116 B)        ← Server API map (Python)
│   └── llms-server-full.txt (68 KB)
└── llms-client.txt (58 KB)        ← Client API map (Flutter)
    └── llms-client-full.txt (406 KB)
```

### File Types

| Type | Purpose | When to Load |
|------|---------|--------------|
| **Map** (`llms-*.txt`) | Navigation links, class lists | Always - for discovery |
| **Content** (`llms-*-full.txt`) | Complete documentation | On-demand - when diving deep |

### Domains

| Domain | Map | Content | Covers |
|--------|-----|---------|--------|
| **Project** | `llms-project.txt` | `llms-project-full.txt` | Setup, configuration, architecture |
| **Server** | `llms-server.txt` | `llms-server-full.txt` | Python backend, API endpoints |
| **Client** | `llms-client.txt` | `llms-client-full.txt` | Flutter widgets, services, models |

## Building Documentation

### For Local Agents (Recommended)

```bash
DOCS_MODE=absolute ./scripts/build_docs.sh
```

This generates absolute filesystem paths in `llms.txt`, enabling agents to directly read files. This is the default mode.

### For Local Dev Server

```bash
DOCS_MODE=local LOCAL_PORT=8000 ./scripts/build_docs.sh
```

Generates `http://localhost:PORT/` URLs for use with `mkdocs serve`.

### For Remote/Hosted

```bash
DOCS_MODE=remote ./scripts/build_docs.sh
```

Generates full HTTPS URLs for online access (uses `site_url` from mkdocs.yml).

### For Portable Archives

```bash
DOCS_MODE=relative ./scripts/build_docs.sh
```

Generates relative paths for directory-independent archives.

## Agent Workflow

### Recommended Flow

1. **Start**: Read `site/llms.txt` to see available domains
2. **Discover**: Load the relevant map file (e.g., `llms-client.txt`)
3. **Navigate**: Find the specific class/module you need
4. **Deep-dive**: Load the `-full.txt` content file for complete details

### Quick Access (After Local Build)

```
site/llms.txt              → Start here
site/llms-project-full.txt → Architecture, setup, config
site/llms-server-full.txt  → Python API reference
site/llms-client-full.txt  → Flutter/Dart API reference
```

## Domain Selection Guide

| Question Type | Domain | File to Load |
|---------------|--------|--------------|
| "How do I configure...?" | Project | `llms-project-full.txt` |
| "What endpoints exist for...?" | Server | `llms-server-full.txt` |
| "How does the widget...?" | Client | `llms-client-full.txt` |
| "How do I add authentication?" | All | Start with maps, then load relevant content |

## Client API Categories

The client map (`llms-client.txt`) organizes 400+ classes into semantic categories:

- **Core Architecture** - Widget registry, app scaffold
- **AG-UI Protocol** - Event types, protocol handlers
- **Services & State** - Notifiers, managers, Riverpod providers
- **Models & Data** - Domain models, DTOs
- **Network & API** - Transport layer, API clients
- **Authentication** - OIDC, token management
- **UI Components** - Widgets, screens, dialogs
- **Utilities & Misc** - Helpers, extensions

## Validation

Run the validation script to verify the federation strategy:

```bash
uv run python scripts/validate_llms_strategy.py
```

This checks:
- Context efficiency (maps < 15% of content)
- Link integrity (all map links resolve)
- Completeness (no missing sections)

## Maintenance

### Adding New Documentation

1. Add markdown files to `docs/`
2. Update `mkdocs.yml` nav and `llmstxt/sections`
3. Run `./scripts/build_docs.sh`
4. Verify with `scripts/validate_llms_strategy.py`

### Modifying Categories

Edit `scripts/federate_llms_txt.py`:
- `categorize_path()` - keyword heuristics for categorization
- `EXPLICIT_CATEGORY_MAP` - hardcoded overrides

## Related Documentation

- `docs/development/documentation.md` - Full documentation workflow
- `mkdocs.yml` - MkDocs configuration and llmstxt plugin settings
- `scripts/federate_llms_txt.py` - Federation script source
