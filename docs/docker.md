# Docker Deployment

This guide covers running Soliplex using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+ with BuildKit enabled
- Docker Compose 2.0+
- Access to an LLM provider (Ollama or OpenAI)

## Dockerfile Overview

The [Dockerfile](../Dockerfile) uses a multi-stage build with three
stages:

| Stage         | Purpose                                             |
|---------------|-----------------------------------------------------|
| `base`        | System packages and non-root user                   |
| `development` | Full toolchain; expects bind-mounted source code    |
| `production`  | Minimal image with only runtime dependencies        |

The **production** stage is the last stage in the file, so it is the
default target when no `--target` is specified.

```bash
# Production (default)
docker build -t soliplex .

# Development
docker build -t soliplex-dev --target development .
```

### Non-root User

Both targets run as a `soliplex` user rather than root. The UID and GID
default to `1000` and can be set at build time:

```bash
docker build --build-arg APP_UID=$(id -u) --build-arg APP_GID=$(id -g) .
```

This is most useful on Linux hosts where bind-mounted files must match
the host user's ownership. On Docker Desktop (Windows / macOS), the
defaults work without adjustment.

### Health Check

Both targets include a `HEALTHCHECK` instruction that polls the
`GET /ok` endpoint:

```text
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ok')"
```

Docker uses this to report container health and to drive restart
policies and Compose `depends_on` conditions.

### .dockerignore

The repository includes a `.dockerignore` file that excludes `.git`,
`.venv`, `__pycache__`, `.env`, test suites, documentation sources, and
runtime data directories (`db/`, `uploads/`). This keeps the build
context small and prevents secrets from leaking into the image.

## Docker Compose

The `docker-compose.yaml` defines two backend services:

### `soliplex_backend` (production)

Builds the default **production** target. Configuration is mounted from
the host; source code is baked into the image.

```bash
docker compose up soliplex_backend
```

### `soliplex_dev` (development)

Builds the **development** target with hot reloading and bind-mounted
source code so that edits on the host take effect immediately.

```bash
docker compose up soliplex_dev
```

On Linux, pass your UID/GID so that files written by the container are
owned by your host user:

```bash
APP_UID=$(id -u) APP_GID=$(id -g) docker compose up soliplex_dev
```

The development service:

- Bind-mounts `./src/soliplex` into the container (live code changes)
- Bind-mounts `./tests` for in-container test runs
- Runs with `--reload=both` so uvicorn restarts on Python or YAML
  config changes
- Uses `--no-auth-mode` for convenience

### Configuration

1. **Create environment file**

    Copy the example environment file and configure your secrets:

    ```bash
    cp .env.example .env
    ```

    Edit `.env` to set required variables (see
    [Environment Variables](#environment-variables) below).

2. **Configure installation path**

    The backend expects configuration at `/app/installation` inside the
    container. By default, the `./example` directory is mounted there.

    To use a custom configuration:

    ```yaml
    volumes:
      - ./path/to/your/config:/app/installation
    ```

3. **Database persistence**

    The `./db` directory is mounted to persist:

   - RAG vector database (`db/rag/`)
   - Thread persistence database
   - Room authorization database

### Common Commands

```bash
# Start production backend
docker compose up soliplex_backend

# Start development backend with hot reload
docker compose up soliplex_dev

# Rebuild after dependency changes
docker compose up --build soliplex_backend

# Run in detached mode
docker compose up -d soliplex_backend

# View logs
docker compose logs -f soliplex_backend

# Stop all services
docker compose down
```

### Accessing the Application

- **Backend API**: <http://localhost:8000>
- **API Documentation**: <http://localhost:8000/docs>

## Building Custom Docker Images

Build manually:

```bash
docker build -t soliplex-backend .
```

Run manually:

```bash
docker run -p 8000:8000 \
  --env-file .env \
  -v $(pwd)/example:/app/installation \
  -v $(pwd)/db:/app/db \
  soliplex-backend
```

## Environment Variables

The backend container reads environment variables from:

1. `.env` file (specified with `env_file` in `docker-compose.yaml`)
2. Environment variables set in `docker-compose.yaml`
3. Shell environment (if using `docker run`)

### Required Variables

See [.env.example](../.env.example) for a complete list.

**For Ollama:**

If you run Ollama as a Docker container:

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Otherwise:

```bash
OLLAMA_BASE_URL=http://your-ollama-host:11434
```

**For OpenAI:**

```bash
OPENAI_API_KEY=sk-...
```

### Accessing Host Services

When running Ollama or other services on your host machine, use
`host.docker.internal`:

```bash
# In .env file
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, you may need to add this to `docker-compose.yaml` (already
included):

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Volume Mounts

### Configuration Files (`./example:/app/installation`)

Mounts your configuration directory into the container. Contents:

- `installation.yaml` or `minimal.yaml` -- Main installation config
- `haiku.rag.yaml` -- RAG configuration
- `rooms/` -- Room configurations
- `completions/` -- Completion endpoint configurations
- `oidc/` -- OIDC provider configurations
- `quizzes/` -- Quiz question files

### Database Files (`./db:/app/db`)

Persists application data:

- `db/rag/rag.lancedb/` -- RAG vector database
- SQLite databases for threads and authorization (if using defaults)

**Important**: Initialize the RAG database before first run (see RAG
Setup below).

### Source Code (`./src/soliplex:/app/src/soliplex`)

Only used by the `soliplex_dev` service. Bind-mounts your working tree
into the container so that edits are picked up by the uvicorn reloader.

### Tests (`./tests:/app/tests`)

Only used by the `soliplex_dev` service. Allows running the test suite
inside the container:

```bash
docker compose run --rm soliplex_dev uv run pytest
```

## RAG Database Setup in Docker

The RAG database must be initialized before starting the backend server.

### Option 1: Initialize on Host (Recommended)

Initialize the database on your host machine before running Docker:

```bash
# Install haiku-rag (full version for ingestion)
uv pip install haiku-rag

# Set Ollama URL
export OLLAMA_BASE_URL=http://localhost:11434

# Initialize and populate RAG database
haiku-rag --config example/haiku.rag.yaml init --db db/rag/rag.lancedb
haiku-rag --config example/haiku.rag.yaml add-src --db db/rag/rag.lancedb docs/
```

The `./db` directory will be mounted into the container with the
initialized database.

### Option 2: Initialize in Container

Run initialization inside the backend container:

```bash
# Start container with shell
docker compose run --rm soliplex_backend /bin/bash

# Inside container
export OLLAMA_BASE_URL=http://host.docker.internal:11434
pip install haiku-rag  # Install full version
haiku-rag --config /app/installation/haiku.rag.yaml init --db /app/db/rag/rag.lancedb
haiku-rag --config /app/installation/haiku.rag.yaml add-src --db /app/db/rag/rag.lancedb /app/docs/
exit
```

## Common Issues

### Port Already in Use

If port 8000 is already allocated, edit `docker-compose.yaml`:

```yaml
ports:
  - "8001:8000"  # Map host port 8001 to container port 8000
```

### Cannot Connect to Ollama

Ensure `OLLAMA_BASE_URL` uses `host.docker.internal`:

```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Verify Ollama is running on host:

```bash
ollama list
```

### RAG Database Not Found

The backend will fail if the RAG database hasn't been initialized.

Check for database files:

```bash
ls -la db/rag/
```

If missing, initialize as described in the RAG Database Setup section.

### Permission Issues

If you encounter permission errors with mounted volumes on Linux, ensure
the container user's UID matches your host user:

```bash
APP_UID=$(id -u) APP_GID=$(id -g) docker compose up --build soliplex_dev
```

For existing directories:

```bash
mkdir -p db uploads
chmod -R 755 db/
```

## Production Considerations

1. **Authentication**: Never use `--no-auth-mode` in production
2. **Secrets**: Use Docker secrets or a secrets manager rather than
   `.env` files
3. **Database**: Consider PostgreSQL instead of SQLite for production
4. **Reverse Proxy**: Place behind nginx or traefik with HTTPS
5. **Resource Limits**: Set memory and CPU limits via Compose `deploy`
6. **Capabilities**: Replace `privileged: true` with the narrowest
   capability set that supports bubblewrap (e.g.,
   `cap_add: [SYS_ADMIN]`) and test thoroughly

## Next Steps

- Configure OIDC authentication: [OIDC Providers](config/oidc_providers.md)
- Set up rooms: [Room Configuration](config/rooms.md)
- Configure agents: [Agent Configuration](config/agents.md)
- Review server documentation: [Server Setup](server.md)
