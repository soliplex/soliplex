# Documentation Scripts

Scripts for building and validating Soliplex documentation with LLM-optimized federation.

## Scripts

| Script | Purpose |
|--------|---------|
| `build_docs.sh` | Orchestrates full documentation build + federation |
| `generate_dart_markdown.sh` | Generates Dart API markdown from source |
| `generate_client_api_index.py` | Creates client API index page |
| `federate_llms_txt.py` | MkDocs post-build hook for llms.txt federation |
| `validate_llms_strategy.py` | Validates federation output |
| `llms_constants.py` | Shared constants for federation scripts |

## Lifecycle

```
┌─────────────────────┐
│  build_docs.sh      │
└────────┬────────────┘
         │
    ┌────▼────┐
    │ Dart    │ generate_dart_markdown.sh
    │ Markdown│ generate_client_api_index.py
    └────┬────┘
         │
    ┌────▼────┐
    │ MkDocs  │ uv run mkdocs build
    │ Build   │
    └────┬────┘
         │
    ┌────▼────────────┐
    │ Post-Build Hook │ federate_llms_txt.py
    │ (Federation)    │
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ Validation      │ validate_llms_strategy.py
    └─────────────────┘
```

## Local Development

For live preview while editing docs:

```bash
uv run mkdocs serve
```

This starts a local server at `http://127.0.0.1:8000` with hot-reload. Note: Federation doesn't run during serve (it's a post-build hook).

## Building

| Command | Dart Docs | MkDocs | Federation | Validation |
|---------|-----------|--------|------------|------------|
| `uv run mkdocs build` | No | Yes | Yes | No |
| `./scripts/build_docs.sh` | Yes | Yes | Yes | Yes |

### Quick Build (MkDocs only)

```bash
uv run mkdocs build
```

**Does NOT regenerate Dart API docs.** Use this when you've only changed markdown files or Python docstrings. Federation runs automatically via post-build hook.

### Full Build

```bash
./scripts/build_docs.sh
```

**Regenerates Dart API docs** from Flutter source, then builds MkDocs and validates. Use this when Flutter/Dart code has changed.

## Build Modes

Control URL format in `llms.txt` files via `DOCS_MODE`:

| Mode | Command | URL Format in llms.txt |
|------|---------|------------------------|
| Remote (default) | `uv run mkdocs build` | `https://soliplex.github.io/soliplex/...` |
| Local | `DOCS_MODE=local uv run mkdocs build` | `/Users/you/project/site/...` |
| Relative | `DOCS_MODE=relative uv run mkdocs build` | `llms-server.txt` |

Examples:

```bash
# Remote mode (default) - HTTPS URLs for hosted docs
./scripts/build_docs.sh

# Local mode - Absolute filesystem paths for local agents
DOCS_MODE=local ./scripts/build_docs.sh

# Relative mode - Portable relative paths
DOCS_MODE=relative ./scripts/build_docs.sh
```

## Testing

Run script tests (separate from main package tests):

```bash
uv run pytest tests/unit/scripts/ -v --no-cov
```

## Validation

Validate federation output:

```bash
uv run python scripts/validate_llms_strategy.py
uv run python scripts/validate_llms_strategy.py --json  # JSON output
```

Checks performed:
- **Context efficiency**: Maps < domain-specific thresholds (10-20%)
- **Link integrity**: All relative links resolve
- **File existence**: All expected files exist

## Adding New Domains

1. Add domain config to `llms_constants.py`:
   ```python
   DOMAINS["newdomain"] = {
       "map": "llms-newdomain.txt",
       "content": "llms-newdomain-full.txt",
       "threshold": 0.15,
   }
   ```

2. Add section mapping:
   ```python
   SECTIONS["New Domain Name"] = "llms-newdomain.txt"
   ```

3. Add categorization rules if needed (server or client categories)

4. Update validation thresholds based on expected content

## Modifying Categories

### Server API Categories

Edit `SERVER_SOURCE_CATEGORIES` in `llms_constants.py`:
```python
SERVER_SOURCE_CATEGORIES = {
    "config.py": "Configuration",
    "models.py": "Models & Data",
    # Add new mappings here
}
```

### Client API Categories

Edit `CLIENT_PATH_KEYWORDS` in `llms_constants.py`:
```python
CLIENT_PATH_KEYWORDS = {
    "widget": "UI Components",
    "service": "Services & State",
    # Add new mappings here
}
```

## Naming Convention

| Prefix | Purpose |
|--------|---------|
| `build_*` | Creates/generates artifacts |
| `generate_*` | Creates specific output files |
| `validate_*` | Checks correctness, returns pass/fail |
| `federate_*` | Splits/distributes content (MkDocs hook) |
