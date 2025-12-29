#!/bin/bash
#
# Monorepo Migration Script
# Converts the soliplex project structure to a monorepo layout
#
# Usage: ./scripts/migrate-to-monorepo.sh
#
# This script should be run from the soliplex root directory.
# It uses git mv to preserve history where possible.
#

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration - Update these paths as needed
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MONOREPO_ROOT="$(dirname "$SCRIPT_DIR")"
INGESTER_REPO="${MONOREPO_ROOT}/../soliplex_ingester"
AGENTS_REPO="${MONOREPO_ROOT}/../ingester-agents"

# Verify we're in the right place
verify_environment() {
    log_info "Verifying environment..."

    if [ ! -f "${MONOREPO_ROOT}/pyproject.toml" ]; then
        log_error "pyproject.toml not found. Run this script from the soliplex root."
        exit 1
    fi

    if [ ! -d "${MONOREPO_ROOT}/.git" ]; then
        log_error "Not a git repository. Aborting."
        exit 1
    fi

    if [ ! -d "$INGESTER_REPO" ]; then
        log_error "soliplex_ingester repo not found at: $INGESTER_REPO"
        exit 1
    fi

    if [ ! -d "$AGENTS_REPO" ]; then
        log_error "ingester-agents repo not found at: $AGENTS_REPO"
        exit 1
    fi

    log_success "Environment verified"
}

# Create backup branch
create_backup() {
    log_info "Creating backup branch..."
    cd "$MONOREPO_ROOT"

    BACKUP_BRANCH="backup-pre-monorepo-$(date +%Y%m%d-%H%M%S)"
    git branch "$BACKUP_BRANCH"

    log_success "Backup branch created: $BACKUP_BRANCH"
    echo "$BACKUP_BRANCH" > .migration-backup-branch
}

# Phase 1: Create directory structure
create_directories() {
    log_info "Creating monorepo directory structure..."
    cd "$MONOREPO_ROOT"

    mkdir -p apps
    mkdir -p scripts

    log_success "Directory structure created"
}

# Phase 2: Move soliplex application
move_soliplex_app() {
    log_info "Moving soliplex application to apps/soliplex..."
    cd "$MONOREPO_ROOT"

    # Create the app directory
    mkdir -p apps/soliplex/src

    # Move the Python source (preserving history)
    git mv src/soliplex apps/soliplex/src/

    # Move tests under the application
    git mv tests apps/soliplex/

    # Copy pyproject.toml (will be modified later)
    cp pyproject.toml apps/soliplex/pyproject.toml

    # Clean up egg-info if it exists
    rm -rf src/soliplex.egg-info 2>/dev/null || true

    log_success "Soliplex application moved"
}

# Phase 3: Move Flutter UI
move_flutter_ui() {
    log_info "Moving Flutter UI to apps/flutter-ui..."
    cd "$MONOREPO_ROOT"

    # Rename and move flutter to apps
    git mv src/flutter apps/flutter-ui

    # Remove empty src directory if it exists
    rmdir src 2>/dev/null || true

    log_success "Flutter UI moved and renamed"
}

# Phase 4: Import ingester package
import_ingester() {
    log_info "Importing soliplex-ingester to apps/ingester..."
    cd "$MONOREPO_ROOT"

    mkdir -p apps/ingester

    # Copy source files
    cp -r "${INGESTER_REPO}/src" apps/ingester/
    cp -r "${INGESTER_REPO}/tests" apps/ingester/
    cp "${INGESTER_REPO}/pyproject.toml" apps/ingester/

    # Copy uv.lock if exists
    if [ -f "${INGESTER_REPO}/uv.lock" ]; then
        cp "${INGESTER_REPO}/uv.lock" apps/ingester/
    fi

    # Add to git
    git add apps/ingester/

    log_success "Ingester imported to apps/ingester"
}

# Phase 5: Import agents package
import_agents() {
    log_info "Importing ingester-agents to apps/agents..."
    cd "$MONOREPO_ROOT"

    mkdir -p apps/agents

    # Copy source files
    cp -r "${AGENTS_REPO}/src" apps/agents/
    cp -r "${AGENTS_REPO}/tests" apps/agents/
    cp "${AGENTS_REPO}/pyproject.toml" apps/agents/

    # Copy uv.lock if exists
    if [ -f "${AGENTS_REPO}/uv.lock" ]; then
        cp "${AGENTS_REPO}/uv.lock" apps/agents/
    fi

    # Add to git
    git add apps/agents/

    log_success "Agents imported to apps/agents"
}

# Phase 6: Move ingester UI
move_ingester_ui() {
    log_info "Moving ingester UI to apps/ingester-ui..."
    cd "$MONOREPO_ROOT"

    # Copy the UI from ingester repo
    cp -r "${INGESTER_REPO}/ui" apps/ingester-ui

    # Add to git
    git add apps/ingester-ui/

    log_success "Ingester UI moved to apps/ingester-ui"
}

# Phase 7: Remove duplicate code from soliplex app (already done pre-migration)
remove_duplicates() {
    log_info "Checking for duplicate code in soliplex app..."
    cd "$MONOREPO_ROOT"

    # Check if the duplicate ingester directory exists and remove it
    # Note: This should already be removed pre-migration
    if [ -d "apps/soliplex/src/soliplex/ingester" ]; then
        git rm -rf apps/soliplex/src/soliplex/ingester
        log_success "Removed duplicate ingester code"
    else
        log_success "No duplicate ingester code found (already cleaned pre-migration)"
    fi

    # Clean up egg-info if it exists
    if [ -d "apps/soliplex/src/soliplex.egg-info" ]; then
        rm -rf apps/soliplex/src/soliplex.egg-info
        log_success "Removed egg-info directory"
    fi
}

# Phase 8: Create root pyproject.toml
create_root_pyproject() {
    log_info "Creating root pyproject.toml for workspace..."
    cd "$MONOREPO_ROOT"

    # Backup existing pyproject.toml
    mv pyproject.toml pyproject.toml.bak

    cat > pyproject.toml << 'PYPROJECT_EOF'
[project]
name = "soliplex-monorepo"
version = "1.0.0"
description = "Soliplex Monorepo - AI-powered RAG system with document ingestion"
authors = [{ name = "Enfold", email = "info@enfoldsystems.net" }]
readme = "README.md"
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
"soliplex.agents" = { workspace = true }

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

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["F", "E", "B", "U", "I", "PD", "TRY", "PT"]

[tool.ruff.lint.isort]
force-single-line = true

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
PYPROJECT_EOF

    git add pyproject.toml

    log_success "Root pyproject.toml created"
}

# Phase 9: Update app pyproject.toml
update_app_pyproject() {
    log_info "Updating apps/soliplex/pyproject.toml..."
    cd "$MONOREPO_ROOT"

    cat > apps/soliplex/pyproject.toml << 'APP_PYPROJECT_EOF'
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "soliplex"
version = "0.30dev0"
description = "An AI-powered Retrieval-Augmented Generation (RAG) system with a modern web interface."
authors = [{ name = "Enfold", email = "info@enfoldsystems.net" }]
readme = "../../README.md"
requires-python = ">=3.13"
classifiers = [
    "Programming Language :: Python :: 3",
    "Operating System :: OS Independent",
]
dependencies = [
    # App-specific dependencies (common deps inherited from root)
    "ag-ui-protocol >= 0.1.10",
    "authlib",
    "fastmcp >= 2.13.0.2, < 2.14",
    "greenlet",
    "itsdangerous",
    "jsonpatch",
    "jwcrypto",
    "logfire[fastapi]",
    "pyjwt",
    "python-keycloak",
    "starlette",
    "trio",
    "uvicorn[standard]",
    "certifi >= 2025.11.12",
    # Workspace dependencies
    "soliplex-ingester",
    "soliplex.agents",
]

[project.scripts]
soliplex-cli = "soliplex.cli:the_cli"
soliplex-tui = "soliplex.tui.cli:the_cli"
soliplex-tui-serve = "soliplex.tui.serve:main"

[dependency-groups]
dev = [
    "pytest",
    "pytest-cov",
    "pytest-asyncio",
    "coverage",
    "anyio",
    "trio",
    "ruff",
]
docs = [
    "mkdocs>=1.6.1",
    "mkdocs-material>=9.6.19",
    "click != 8.2.2, != 8.3.0",
]
postgres = [
    "asyncpg",
]
tui = [
    "textual",
    "textual-serve",
    "typer",
]

[tool.setuptools.packages.find]
where = ["src"]
include = ["soliplex*"]

[tool.pytest.ini_options]
pythonpath = "."
python_files = "test_*.py"
testpaths = ["tests/unit"]
addopts = "--cov=soliplex --cov=tests/unit --cov-branch --cov-fail-under=100"
filterwarnings = []
markers = [
    "needs_llm: functest requiring an LLM",
]

[tool.coverage.run]
omit = [
    "src/soliplex/cli.py",
    "src/soliplex/examples.py",
    "src/soliplex/tui.py",
]

[tool.coverage.report]
show_missing = true

[tool.ruff]
line-length = 79
target-version = "py313"

[tool.ruff.lint]
select = ["F", "E", "B", "U", "I", "PD", "TRY", "PT"]

[tool.ruff.lint.isort]
force-single-line = true

[tool.ruff.lint.flake8-pytest-style]
parametrize-names-type = "csv"
APP_PYPROJECT_EOF

    log_success "App pyproject.toml updated"
}

# Phase 10: Create GitHub Actions workflows
create_github_workflows() {
    log_info "Creating updated GitHub Actions workflows..."
    cd "$MONOREPO_ROOT"

    mkdir -p .github/workflows

    # Python test workflow
    cat > .github/workflows/python-test.yaml << 'PYTHON_WORKFLOW_EOF'
name: Python Tests

on:
  push:
    branches: [main]
    paths:
      - 'apps/soliplex/**'
      - 'apps/ingester/**'
      - 'apps/agents/**'
      - 'pyproject.toml'
      - 'uv.lock'
      - '.github/workflows/python-test.yaml'
  pull_request:
    branches: [main]
    paths:
      - 'apps/soliplex/**'
      - 'apps/ingester/**'
      - 'apps/agents/**'
      - 'pyproject.toml'
      - 'uv.lock'
      - '.github/workflows/python-test.yaml'
  workflow_dispatch:

jobs:
  test-soliplex:
    name: Test Soliplex App
    runs-on: ubuntu-latest
    timeout-minutes: 15
    env:
      SLACK_NOTIFY_URL: "${{ secrets.SLACK_NOTIFY_URL }}"
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: |
          uv sync --all-packages
          # Install docling with CPU-only PyTorch
          uv pip install docling --extra-index-url https://download.pytorch.org/whl/cpu

      - name: Run soliplex unit tests
        working-directory: apps/soliplex
        run: uv run pytest -s tests/unit

      - name: Run soliplex functional tests
        working-directory: apps/soliplex
        run: uv run pytest -s --no-cov -m "not needs_llm" tests/functional/

      - name: Run ruff linter
        working-directory: apps/soliplex
        run: uv run ruff check

      - name: Notify Slack on failure
        if: failure() && github.ref == 'refs/heads/main'
        run: |
          curl -X POST --data-urlencode \
            "payload={\"channel\": \"#soliplex\", \"text\": \":x: Soliplex tests failed\"}" \
            "$SLACK_NOTIFY_URL"

  test-ingester:
    name: Test Ingester App
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --all-packages

      - name: Run ingester unit tests
        working-directory: apps/ingester
        run: uv run pytest -s tests/unit

      - name: Run ruff linter
        working-directory: apps/ingester
        run: uv run ruff check

  test-agents:
    name: Test Agents App
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Set up Python
        run: uv python install 3.13

      - name: Install dependencies
        run: uv sync --all-packages

      - name: Run agents unit tests
        working-directory: apps/agents
        run: uv run pytest -s tests/unit

      - name: Run ruff linter
        working-directory: apps/agents
        run: uv run ruff check
PYTHON_WORKFLOW_EOF

    # Flutter test workflow
    cat > .github/workflows/flutter-test.yml << 'FLUTTER_WORKFLOW_EOF'
name: Flutter Tests

on:
  push:
    branches: [main]
    paths:
      - 'apps/flutter-ui/**'
      - '.github/workflows/flutter-test.yml'
  pull_request:
    branches: [main]
    paths:
      - 'apps/flutter-ui/**'
      - '.github/workflows/flutter-test.yml'

defaults:
  run:
    working-directory: apps/flutter-ui

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          channel: 'beta'
          cache: true

      - name: Install dependencies
        run: flutter pub get

      - name: Run analyzer
        run: flutter analyze --fatal-warnings

      - name: Run tests with coverage
        run: flutter test --coverage

      - name: Install lcov
        run: sudo apt-get install -y lcov

      - name: Check coverage threshold
        run: |
          MIN_COVERAGE=2
          SUMMARY=$(lcov --summary coverage/lcov.info 2>&1)
          LINE_COVERAGE=$(echo "$SUMMARY" | grep "lines" | sed 's/.*: \([0-9.]*\)%.*/\1/')
          LINE_INT=$(echo "$LINE_COVERAGE" | cut -d. -f1)

          echo "Line coverage: ${LINE_COVERAGE}%"
          echo "Minimum required: ${MIN_COVERAGE}%"

          if [ "$LINE_INT" -lt "$MIN_COVERAGE" ]; then
            echo "::error::Coverage ${LINE_COVERAGE}% is below minimum ${MIN_COVERAGE}%"
            exit 1
          fi

      - name: Upload coverage report
        uses: actions/upload-artifact@v4
        with:
          name: flutter-coverage-report
          path: apps/flutter-ui/coverage/html/
          retention-days: 30
FLUTTER_WORKFLOW_EOF

    # Node/Svelte test workflow
    cat > .github/workflows/node-test.yml << 'NODE_WORKFLOW_EOF'
name: Node/Svelte Tests

on:
  push:
    branches: [main]
    paths:
      - 'apps/ingester-ui/**'
      - '.github/workflows/node-test.yml'
  pull_request:
    branches: [main]
    paths:
      - 'apps/ingester-ui/**'
      - '.github/workflows/node-test.yml'

defaults:
  run:
    working-directory: apps/ingester-ui

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: apps/ingester-ui/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run type check
        run: npm run check

      - name: Run linter
        run: npm run lint

      - name: Build
        run: npm run build
NODE_WORKFLOW_EOF

    # Deploy site workflow
    cat > .github/workflows/deploy-site.yml << 'DEPLOY_WORKFLOW_EOF'
name: Deploy Site (Docs + WebApp)

on:
  push:
    branches: [main]
    paths:
      - 'mkdocs.yml'
      - 'docs/**'
      - 'apps/flutter-ui/**'
      - '.github/workflows/deploy-site.yml'

permissions:
  contents: write

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Build Documentation
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: 3.x

      - name: Install MkDocs Material
        run: pip install mkdocs-material

      - name: Build Docs
        run: mkdocs build

      # Build Flutter Web App
      - name: Setup Flutter
        uses: subosito/flutter-action@v2
        with:
          channel: 'beta'
          cache: true

      - name: Install Flutter dependencies
        working-directory: apps/flutter-ui
        run: flutter pub get

      - name: Build Flutter Web
        working-directory: apps/flutter-ui
        run: flutter build web --release --base-href /soliplex/webapp/ --no-tree-shake-icons

      # Combine and Deploy
      - name: Merge Web App into Site
        run: |
          mkdir -p site/webapp
          cp -a apps/flutter-ui/build/web/. site/webapp/
          touch site/.nojekyll

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
          publish_branch: gh-pages
DEPLOY_WORKFLOW_EOF

    git add .github/workflows/

    log_success "GitHub Actions workflows created"
}

# Phase 11: Create utility scripts
create_utility_scripts() {
    log_info "Creating utility scripts..."
    cd "$MONOREPO_ROOT"

    # Test all script
    cat > scripts/test-all.sh << 'TEST_ALL_EOF'
#!/bin/bash
# Run all tests across the monorepo

set -e

echo "=== Testing Soliplex App ==="
cd apps/soliplex
uv run pytest tests/unit
cd ../..

echo "=== Testing Ingester App ==="
cd apps/ingester
uv run pytest tests/unit
cd ../..

echo "=== Testing Agents App ==="
cd apps/agents
uv run pytest tests/unit
cd ../..

echo "=== Testing Flutter UI ==="
cd apps/flutter-ui
flutter test
cd ../..

echo "=== All tests passed! ==="
TEST_ALL_EOF
    chmod +x scripts/test-all.sh

    # Lint all script
    cat > scripts/lint-all.sh << 'LINT_ALL_EOF'
#!/bin/bash
# Run linters across the monorepo

set -e

echo "=== Linting Python apps ==="
uv run ruff check apps/soliplex apps/ingester apps/agents

echo "=== Linting Flutter ==="
cd apps/flutter-ui
flutter analyze
cd ../..

echo "=== Linting Node/Svelte ==="
cd apps/ingester-ui
npm run lint
cd ../..

echo "=== All linting passed! ==="
LINT_ALL_EOF
    chmod +x scripts/lint-all.sh

    # Build all script
    cat > scripts/build-all.sh << 'BUILD_ALL_EOF'
#!/bin/bash
# Build all apps in the monorepo

set -e

echo "=== Installing Python dependencies ==="
uv sync --all-packages

echo "=== Building Flutter Web ==="
cd apps/flutter-ui
flutter build web --release
cd ../..

echo "=== Building Ingester UI ==="
cd apps/ingester-ui
npm ci
npm run build
cd ../..

echo "=== All builds complete! ==="
BUILD_ALL_EOF
    chmod +x scripts/build-all.sh

    git add scripts/

    log_success "Utility scripts created"
}

# Phase 12: Update Docker files
update_docker_files() {
    log_info "Updating Docker configuration..."
    cd "$MONOREPO_ROOT"

    cat > Dockerfile << 'DOCKERFILE_EOF'
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace configuration
COPY pyproject.toml uv.lock* ./

# Copy all apps
COPY apps/ ./apps/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose port
EXPOSE 8000

# Default command
CMD ["uv", "run", "soliplex-cli", "serve", "--host", "0.0.0.0"]
DOCKERFILE_EOF

    cat > docker-compose.yaml << 'DOCKER_COMPOSE_EOF'
version: '3.8'

services:
  soliplex_backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./soliplex.db
    volumes:
      - ./apps/soliplex:/app/apps/soliplex
      - ./apps/ingester:/app/apps/ingester
      - ./apps/agents:/app/apps/agents
      - ./data:/app/data
    networks:
      - soliplex_network

  ingester:
    build:
      context: .
      dockerfile: Dockerfile
    command: ["uv", "run", "si-cli", "serve", "--host", "0.0.0.0"]
    ports:
      - "8001:8000"
    environment:
      - DOC_DB_URL=sqlite:///./ingester.db
    volumes:
      - ./apps/ingester:/app/apps/ingester
      - ./data:/app/data
    networks:
      - soliplex_network

networks:
  soliplex_network:
    driver: bridge
DOCKER_COMPOSE_EOF

    git add Dockerfile docker-compose.yaml

    log_success "Docker configuration updated"
}

# Phase 13: Update .gitignore
update_gitignore() {
    log_info "Updating .gitignore..."
    cd "$MONOREPO_ROOT"

    cat > .gitignore << 'GITIGNORE_EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.nox/

# Ruff
.ruff_cache/

# uv
uv.lock

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Flutter
apps/flutter-ui/.dart_tool/
apps/flutter-ui/.packages
apps/flutter-ui/build/
apps/flutter-ui/.flutter-plugins
apps/flutter-ui/.flutter-plugins-dependencies

# Node
node_modules/
apps/ingester-ui/.svelte-kit/
apps/ingester-ui/build/

# Environment
.env
.env.local
.env.*.local

# Databases
*.db
*.sqlite

# Logs
*.log

# Temp files
tmp/
temp/

# Migration artifacts
.migration-backup-branch
pyproject.toml.bak

# Claude
.claude/
GITIGNORE_EOF

    git add .gitignore

    log_success ".gitignore updated"
}

# Commit changes
commit_changes() {
    log_info "Committing migration changes..."
    cd "$MONOREPO_ROOT"

    git add -A
    git commit -m "refactor: migrate to monorepo structure

- Move soliplex app to apps/soliplex/
- Move Flutter UI to apps/flutter-ui/
- Import soliplex-ingester to apps/ingester/
- Import ingester-agents to apps/agents/
- Move ingester UI to apps/ingester-ui/
- Create uv workspace configuration
- Update GitHub Actions for monorepo
- Update Docker configuration
- Add utility scripts (test-all, lint-all, build-all)
- Remove duplicate ingester code from soliplex app

This migration preserves git history using git mv where possible.
External repos (ingester, agents) are copied (history in original repos).

$(cat <<'COMMIT_EOF'
New structure:
/apps/
  /soliplex/        - Main RAG backend
  /flutter-ui/      - Flutter mobile/web app
  /ingester/        - Document ingestion system
  /agents/          - SCM/FS agents
  /ingester-ui/     - Svelte ingester interface
/scripts/           - Build utilities
/docs/              - Documentation
COMMIT_EOF
)
"

    log_success "Changes committed"
}

# Print summary
print_summary() {
    echo ""
    echo "=============================================="
    echo -e "${GREEN}Migration Complete!${NC}"
    echo "=============================================="
    echo ""
    echo "New monorepo structure:"
    echo ""
    echo "  /apps/"
    echo "    /soliplex/        - Main RAG backend (Python)"
    echo "    /flutter-ui/      - Flutter mobile/web app"
    echo "    /ingester/        - Document ingestion (Python)"
    echo "    /agents/          - SCM/FS agents (Python)"
    echo "    /ingester-ui/     - Ingester UI (Svelte)"
    echo "  /scripts/           - Utility scripts"
    echo "  /docs/              - Documentation"
    echo ""
    echo "Next steps:"
    echo "  1. Run 'uv sync --all-packages' to install dependencies"
    echo "  2. Run './scripts/test-all.sh' to verify everything works"
    echo "  3. Review and adjust import statements if needed"
    echo "  4. Push changes to remote"
    echo ""
    echo "Backup branch: $(cat .migration-backup-branch)"
    echo "To rollback: git reset --hard $(cat .migration-backup-branch)"
    echo ""
}

# Main execution
main() {
    echo ""
    echo "=============================================="
    echo "  Soliplex Monorepo Migration Script"
    echo "=============================================="
    echo ""

    verify_environment
    create_backup
    create_directories
    move_soliplex_app
    move_flutter_ui
    import_ingester
    import_agents
    move_ingester_ui
    remove_duplicates
    create_root_pyproject
    update_app_pyproject
    create_github_workflows
    create_utility_scripts
    update_docker_files
    update_gitignore
    commit_changes
    print_summary
}

# Run main function
main "$@"
