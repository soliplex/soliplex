# Python Backend Instructions

Extends `/CLAUDE.md`. Specific to `src/soliplex/`.

## Code Patterns

### Models
- Use `pydantic.BaseModel` for API schemas
- Use `SQLModel` for database models
- Keep models in `models.py`, not scattered

### Views (FastAPI)
- Views in `views/` directory
- Use dependency injection for services
- Return proper HTTP status codes
- Async handlers where I/O occurs

### Configuration
- `config.py` is large (~70KB) - read sections carefully
- Secrets use `secret:KEY_NAME` pattern
- Environment fallbacks via `InstallationConfig`

### AG-UI Protocol
- Implementation in `agui/` directory
- `parser.py` handles message parsing
- `persistence.py` handles state
- Events flow through SSE streams

### MCP Integration
- `mcp_server.py` - Server-side tools
- `mcp_client.py` - Client toolsets
- `mcp_auth.py` - Authentication

## Test Patterns

Tests mirror source structure in `tests/unit/`:
```
tests/unit/
├── views/test_*.py    View tests
├── agui/test_*.py     AG-UI tests
├── test_config.py     Config tests (large)
└── test_models.py     Model tests
```

Use fixtures from `conftest.py`. Async tests require `@pytest.mark.asyncio`.

## Quality

- `uv run ruff check src/soliplex` - Must pass
- `uv run pytest` - 100% coverage required
- No `# type: ignore` without justification
