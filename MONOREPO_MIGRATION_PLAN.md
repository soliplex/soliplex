# Monorepo Migration Plan

## Executive Summary

This plan converts the current multi-repository structure into a single monorepo containing:
- **soliplex** (Python RAG backend + TUI)
- **soliplex-ingester** (Python document ingestion system)
- **ingester-agents** (Python SCM/FS agents)
- **flutter-ui** (Flutter/Dart mobile/web app)
- **ingester-ui** (Node/Svelte ingester interface)

The migration preserves git history using `git mv` and follows monorepo best practices for multi-language projects.

---

## Current State Analysis

### Existing Repositories
| Repository | Path | Type | Key Files |
|------------|------|------|-----------|
| soliplex | `C:\src\monkeytronics\enfold\soliplex` | Python + Flutter | pyproject.toml, src/soliplex/, src/flutter/ |
| soliplex-ingester | `C:\src\monkeytronics\enfold\soliplex_ingester` | Python + Svelte | pyproject.toml, src/soliplex/ingester/, ui/ |
| ingester-agents | `C:\src\monkeytronics\enfold\ingester-agents` | Python | pyproject.toml, src/soliplex/agents/ |

### Current soliplex State (Pre-Migration Cleanup Done)
- `soliplex/ui/` - **Removed** (was placeholder/unused)
- `soliplex/src/soliplex/ingester/` - **Removed** (duplicate code eliminated)
- `soliplex/tests/unit/` - Contains test files for soliplex core

---

## Target Structure

```
/soliplex/                          (monorepo root)
    /apps/
        /soliplex/                   (main RAG backend)
            /src/
                /soliplex/           (Python package)
            /tests/
                /unit/
                /functional/
            pyproject.toml
        /flutter-ui/                 (renamed from src/flutter)
            /lib/
            /test/
            pubspec.yaml
        /ingester/                   (from soliplex_ingester)
            /src/
                /soliplex/
                    /ingester/
            /tests/
                /unit/
                /functional/
            pyproject.toml
        /agents/                     (from ingester-agents)
            /src/
                /soliplex/
                    /agents/
            /tests/
                /unit/
                /functional/
            pyproject.toml
        /ingester-ui/                (from soliplex_ingester/ui)
            /src/
            package.json
    /scripts/                        (build and utility scripts)
    /docs/                           (documentation)
    /.github/
        /workflows/                  (unified CI/CD)
    pyproject.toml                   (workspace root)
```

---

## Migration Steps

### Phase 1: Preparation (Pre-Migration) - COMPLETED

1. **Backup all repositories**
   - Create backup branches in each repo
   - Export any uncommitted changes

2. **Clean up code duplication in soliplex** - **DONE**
   - ~~Remove `src/soliplex/ingester/`~~ - Already removed
   - ~~Remove `ui/` directory~~ - Already removed
   - Update imports to use workspace packages

3. **Ensure all tests pass** in each repository before migration

### Phase 2: Directory Structure Creation

1. Create `apps/` directory for all applications
2. Create `scripts/` directory for build utilities
3. Keep `docs/` at root level

### Phase 3: Move soliplex Application

Using `git mv` to preserve history:

```bash
# Create apps directory
mkdir -p apps/soliplex

# Move soliplex source
git mv src/soliplex apps/soliplex/src/soliplex

# Move tests under the application
git mv tests apps/soliplex/tests

# Move app-specific pyproject.toml (will need editing)
cp pyproject.toml apps/soliplex/pyproject.toml
```

### Phase 4: Move Flutter UI

```bash
# Rename and move flutter to apps
git mv src/flutter apps/flutter-ui
```

### Phase 5: Import External Projects

Copy files from external repositories (history not preserved - kept in original repos if needed):

```bash
# Import soliplex-ingester
mkdir -p apps/ingester
cp -r ../soliplex_ingester/src apps/ingester/
cp -r ../soliplex_ingester/tests apps/ingester/
cp ../soliplex_ingester/pyproject.toml apps/ingester/
git add apps/ingester/

# Import ingester-agents
mkdir -p apps/agents
cp -r ../ingester-agents/src apps/agents/
cp -r ../ingester-agents/tests apps/agents/
cp ../ingester-agents/pyproject.toml apps/agents/
git add apps/agents/
```

**Note:** History is not preserved for imported projects. Original repositories can be archived or deleted after migration is verified.

### Phase 6: Copy Ingester UI

```bash
# Copy the UI from ingester repo to apps (no history needed)
cp -r ../soliplex_ingester/ui apps/ingester-ui
git add apps/ingester-ui/
```

### Phase 7: Clean Up Duplicates - ALREADY DONE

~~After importing packages:~~
```bash
# Already removed - no action needed
# rm -rf apps/soliplex/src/soliplex/ingester
```
**Note:** The duplicate `src/soliplex/ingester/` and `ui/` directories have already been removed from soliplex.

### Phase 8: Create Root pyproject.toml

Create a workspace-level `pyproject.toml` using uv workspaces with common dependencies:

```toml
[project]
name = "soliplex-monorepo"
version = "1.0.0"
description = "Soliplex Monorepo - AI-powered RAG system"
requires-python = ">=3.12"
dependencies = [
    # Common dependencies shared across apps
    "haiku-rag-slim >= 0.23.0",
    "docling-core >= 2.51.1",
    "pydantic-settings >= 2.12.0",
    "sqlmodel >= 0.0.27",
    "aiosqlite",
    "fastapi[standard] >= 0.125.0",
]

[tool.uv.workspace]
members = [
    "apps/soliplex",
    "apps/ingester",
    "apps/agents",
]

[tool.uv.sources]
soliplex = { workspace = true }
soliplex-ingester = { workspace = true }
soliplex-agents = { workspace = true }

[dependency-groups]
dev = [
    "pytest>=9.0.0",
    "pytest-asyncio>=1.0.0",
    "pytest-cov>=7.0.0",
    "pytest-env>=1.0.0",
    "ruff>=0.14.0",
    "coverage>=7.0.0",
]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.6.0",
]
```

**Common dependencies moved to root:**
| Dependency | Used By | Notes |
|------------|---------|-------|
| `haiku-rag-slim` | soliplex, ingester | Core RAG functionality |
| `docling-core` | ingester | Document processing |
| `pydantic-settings` | all apps | Configuration management |
| `sqlmodel` | soliplex, ingester | Database models |
| `aiosqlite` | soliplex, ingester | Async SQLite |
| `fastapi[standard]` | soliplex, ingester | Web framework |

### Phase 9: Update Individual pyproject.toml Files

Each package needs its pyproject.toml updated:

**apps/soliplex/pyproject.toml:**
```toml
[project]
name = "soliplex"
# Add workspace dependencies
dependencies = [
    "soliplex-ingester",  # from workspace
    "soliplex-agents",    # from workspace
    # ... other deps
]
```

**apps/ingester/pyproject.toml:**
```toml
[project]
name = "soliplex-ingester"
dependencies = [
    "soliplex-agents",  # from workspace
    # ... other deps
]
```

### Phase 10: Update GitHub Actions

Create unified workflows with path-based triggers:

**.github/workflows/python-test.yaml:**
```yaml
name: Python Tests

on:
  push:
    branches: [main]
    paths:
      - 'apps/soliplex/**'
      - 'apps/ingester/**'
      - 'apps/agents/**'
      - 'pyproject.toml'
  pull_request:
    branches: [main]

jobs:
  test-soliplex:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv sync --all-packages
      - name: Test soliplex
        working-directory: apps/soliplex
        run: uv run pytest

  test-ingester:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv sync --all-packages
      - name: Test ingester
        working-directory: apps/ingester
        run: uv run pytest

  test-agents:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - name: Install dependencies
        run: uv sync --all-packages
      - name: Test agents
        working-directory: apps/agents
        run: uv run pytest
```

**.github/workflows/flutter-test.yml:**
```yaml
name: Flutter Tests

on:
  push:
    paths:
      - 'apps/flutter-ui/**'
  pull_request:
    paths:
      - 'apps/flutter-ui/**'

defaults:
  run:
    working-directory: apps/flutter-ui

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: subosito/flutter-action@v2
        with:
          channel: 'beta'
      - run: flutter pub get
      - run: flutter analyze
      - run: flutter test --coverage
```

**.github/workflows/node-test.yml:**
```yaml
name: Node/Svelte Tests

on:
  push:
    paths:
      - 'apps/ingester-ui/**'
  pull_request:
    paths:
      - 'apps/ingester-ui/**'

defaults:
  run:
    working-directory: apps/ingester-ui

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: npm ci
      - run: npm run check
      - run: npm run lint
```

**.github/workflows/deploy-site.yml:**
```yaml
name: Deploy Site

on:
  push:
    branches: [main]
    paths:
      - 'docs/**'
      - 'apps/flutter-ui/**'
      - 'mkdocs.yml'

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Build docs
      - uses: actions/setup-python@v5
        with:
          python-version: '3.x'
      - run: pip install mkdocs-material
      - run: mkdocs build

      # Build Flutter web
      - uses: subosito/flutter-action@v2
        with:
          channel: 'beta'
      - working-directory: apps/flutter-ui
        run: |
          flutter pub get
          flutter build web --release --base-href /soliplex/webapp/

      # Combine and deploy
      - run: |
          mkdir -p site/webapp
          cp -a apps/flutter-ui/build/web/. site/webapp/
      - uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
```

### Phase 11: Update Docker Configuration

**Dockerfile** (root level):
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace files
COPY pyproject.toml uv.lock ./
COPY apps/ ./apps/

# Install dependencies
RUN uv sync --frozen

# Run soliplex
CMD ["uv", "run", "soliplex-cli", "serve"]
```

**docker-compose.yaml:**
```yaml
version: '3.8'
services:
  soliplex_backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - ./apps/soliplex:/app/apps/soliplex
      - ./apps/ingester:/app/apps/ingester
      - ./apps/agents:/app/apps/agents
```

### Phase 12: Update Import Paths

After restructuring, update imports throughout the codebase:

**Before:**
```python
from soliplex.ingester.lib.config import IngesterConfig
```

**After (using workspace package):**
```python
from soliplex.ingester.lib.config import IngesterConfig
```

The import paths remain the same because the package names are preserved, but they now resolve through the workspace.

---

## Files to Update/Create

### New Files
| File | Purpose |
|------|---------|
| `pyproject.toml` (root) | Workspace configuration |
| `scripts/migrate.sh` | Migration script |
| `scripts/test-all.sh` | Run all tests |
| `scripts/build-all.sh` | Build all packages |
| `.github/workflows/python-test.yaml` | Updated Python CI |
| `.github/workflows/flutter-test.yml` | Updated Flutter CI |
| `.github/workflows/node-test.yml` | New Node CI |

### Files to Modify
| File | Changes |
|------|---------|
| `apps/soliplex/pyproject.toml` | Add workspace deps, update paths |
| `apps/ingester/pyproject.toml` | Update for workspace |
| `apps/agents/pyproject.toml` | Update for workspace |
| `mkdocs.yml` | Update doc paths if needed |
| `Dockerfile` | Update for new structure |
| `docker-compose.yaml` | Update paths |

### Files to Delete
| File | Reason | Status |
|------|--------|--------|
| `src/soliplex/ingester/` | Replaced by workspace package | **Already removed** |
| `ui/` | Unused placeholder | **Already removed** |
| `src/soliplex.egg-info/` | Build artifact | Will be cleaned during migration |

---

## Rollback Plan

If migration fails:

1. The script creates a backup branch before starting
2. Use `git reset --hard backup-pre-monorepo` to restore
3. External repos remain unchanged (copy, not move)

---

## Post-Migration Verification

1. **Test all Python packages:**
   ```bash
   uv sync --all-packages
   uv run pytest apps/soliplex/tests
   uv run pytest apps/ingester/tests
   uv run pytest apps/agents/tests
   ```

2. **Test Flutter app:**
   ```bash
   cd apps/flutter-ui
   flutter test
   ```

3. **Test Node app:**
   ```bash
   cd apps/ingester-ui
   npm ci && npm run check
   ```

4. **Verify imports work:**
   ```bash
   uv run python -c "from soliplex.config import Config; print('OK')"
   uv run python -c "from soliplex.ingester.lib.config import IngesterConfig; print('OK')"
   uv run python -c "from soliplex.agents.config import Settings; print('OK')"
   ```

5. **Run full CI locally:**
   ```bash
   ./scripts/test-all.sh
   ```

---

## Best Practices Applied

1. **Workspace Dependencies**: Using uv workspaces for Python package management
2. **Preserved History**: Using `git mv` for internal moves (soliplex, flutter)
3. **Simple Imports**: Copy external projects without history (ingester, agents, ingester-ui)
4. **Unified Apps Directory**: All applications in `apps/` for consistency
5. **Path-Based CI Triggers**: Only run tests for changed packages
6. **Unified Tooling**: Standardizing on uv for Python, consistent configs
7. **Documentation**: Keeping docs at root level for visibility
8. **Scripts Directory**: Centralized build and utility scripts

---

## Timeline Considerations

This migration should be done in a single session to avoid partial states. Ensure:
- All team members are notified
- No active PRs that would conflict
- CI/CD is paused during migration
- Time allocated for verification

---

## Questions to Resolve

1. ~~**Git subtree vs copy**: Do you want to preserve external repo history?~~ - **Resolved: Using copy (no history needed)**
2. **uv vs pip**: Confirm uv is acceptable for all developers
3. **Python version**: Standardize on 3.12 or 3.13?
4. **Node workspace**: Should we also create a package.json workspace for Node packages?
