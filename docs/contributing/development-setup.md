# Development Setup

Set up your development environment for contributing to Soliplex.

## Prerequisites

- Python 3.13+
- Git
- Ollama (for local LLM)
- Flutter 3.x (optional, see [Flutter repository](https://github.com/soliplex/flutter))

## Clone Repository

```bash
git clone https://github.com/soliplex/soliplex.git
cd soliplex
```

## Backend Setup

### Create Virtual Environment

```bash
python3.13 -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows
```

### Install Dependencies

```bash
# Install in development mode
pip install -e ".[dev]"
```

### Verify Installation

```bash
soliplex-cli --help
```

## Frontend Setup (Optional)

The Flutter frontend is maintained in a separate repository. To develop on the frontend:

```bash
# Clone the Flutter repo as a sibling directory
git clone https://github.com/soliplex/flutter ../flutter
cd ../flutter
flutter pub get
flutter doctor
```

See the [Flutter repository](https://github.com/soliplex/flutter) for detailed frontend development instructions.

## Start Development Services

### Start Ollama

```bash
ollama serve
# In another terminal:
ollama pull gpt-oss:latest
```

### Start Backend

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
soliplex-cli serve example/minimal.yaml --no-auth-mode
```

### Start Frontend (Optional)

```bash
# If you have the Flutter repo cloned at ../flutter
cd ../flutter
flutter run -d chrome --web-port 59001 --dart-define=DEFAULT_SERVER_URL=http://localhost:8000
```

## Running Tests

### Backend Tests

```bash
# Run all unit tests (100% coverage required)
pytest

# Run specific test file
pytest tests/unit/test_agents.py

# Run with coverage report
pytest --cov=soliplex --cov-report=html
```

### Frontend Tests

See the [Flutter repository](https://github.com/soliplex/flutter) for frontend testing instructions.

### Functional Tests (requires LLM)

```bash
pytest tests/functional/
```

## Code Quality

### Python Linting

```bash
# Check for issues
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Format code
ruff format src/
```

### Flutter Linting

See the [Flutter repository](https://github.com/soliplex/flutter) for frontend linting instructions.

## Project Structure

```
soliplex/
├── src/
│   └── soliplex/          # Python backend
│       ├── views/         # FastAPI routes
│       ├── agui/          # AG-UI protocol
│       ├── authz/         # Authorization
│       ├── tui/           # Terminal UI client
│       ├── agents.py      # Agent management
│       ├── config.py      # Configuration
│       └── tools.py       # Agent tools
├── tests/
│   ├── unit/              # Unit tests
│   └── functional/        # Integration tests
├── docs/                  # Documentation
└── example/               # Example configurations
```

!!! note "Frontend Repository"
    The Flutter frontend is maintained separately at [github.com/soliplex/flutter](https://github.com/soliplex/flutter).

## Development Workflow

1. **Create branch** from main
2. **Make changes** with tests
3. **Run tests** - all must pass
4. **Run linters** - no warnings
5. **Commit** with clear message
6. **Push** and create PR

## IDE Setup

### VS Code

Recommended extensions:
- Python
- Pylance
- Ruff

### PyCharm

- Configure Python interpreter to use venv
- Enable ruff for linting

## Claude Code Integration

If you use [Claude Code](https://claude.ai/code) for AI-assisted development, the project includes MCP (Model Context Protocol) server configurations.

### GitHub MCP Server

The GitHub MCP server enables Claude Code to interact with GitHub issues, pull requests, and repository operations.

**Prerequisites:**

- Docker installed and running
- GitHub Personal Access Token (PAT)

**Setup:**

1. Create a GitHub PAT at https://github.com/settings/tokens
   - Classic token: select `repo` scope
   - Or fine-grained token: grant repository read/write access

2. Create your `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Add your token to `.env`:
   ```
   GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
   ```

4. Restart Claude Code - the GitHub MCP server will connect automatically

**Verify:**

Ask Claude to list issues: "List open issues in this repo"

**Available Operations:**

- List/create/comment on issues
- List/create/review pull requests
- Create branches
- Search code and repositories

### Other MCP Servers

The project also includes:

- **context7** - Library documentation lookup (no setup required)

See `.mcp.json` for the full MCP configuration.

## Environment Variables

For development:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Set log level via CLI option:

```bash
soliplex-cli serve example/minimal.yaml --no-auth-mode --log-level DEBUG
```

## Troubleshooting

### Import Errors

```bash
pip install -e ".[dev]"
```

### Test Database Issues

Tests use in-memory SQLite by default. Check no stale databases exist.

## Next Steps

- Read [Code Style](code-style.md) guide
- Review existing code patterns
- Pick an issue to work on
- Join the community discussions
