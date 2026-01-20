# Docker Deployment

This guide covers running Soliplex using Docker and Docker Compose.

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- Access to an LLM provider (Ollama or OpenAI)

## Docker Compose Setup

The project includes a `docker-compose.yaml` file that orchestrates both the backend server and frontend web client.

### Services

The compose configuration defines two services:

#### 1. `soliplex_backend` (Python Backend)
- **Port**: 8000
- **Technology**: Python 3.13 with FastAPI
- **Purpose**: API server, RAG processing, AI integration
- **Volumes**:
  - `./example:/app/installation` - Configuration files
  - `./db:/app/db` - Database storage (RAG, threads, etc.)

#### 2. `soliplex_web` (Flutter Frontend)
- **Port**: 9000
- **Technology**: Flutter web application
- **Purpose**: User interface for chat and document interaction

### Configuration

1. **Create environment file**

   Copy the example environment file and configure your secrets:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` to set required variables (see Environment Variables section below).

2. **Configure installation path**

   The backend expects configuration at `/app/installation` inside the container.
   By default, the `./example` directory is mounted there.

   To use a custom configuration:
   ```yaml
   volumes:
     - ./path/to/your/config:/app/installation
     - ./db:/app/db
   ```

3. **Database persistence**

   The `./db` directory is mounted to persist:
   - RAG vector database (`db/rag/`)
   - Thread persistence database
   - Room authorization database

### Running with Docker Compose

#### Start all services
```bash
docker-compose up
```

Add `-d` flag to run in detached mode:
```bash
docker-compose up -d
```

#### Start specific service
```bash
docker-compose up soliplex_backend
```

#### View logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f soliplex_backend
```

#### Stop services
```bash
docker-compose down
```

#### Rebuild after code changes
```bash
docker-compose up --build
```

### Accessing the Application

- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Frontend Web UI**: http://localhost:9000

## Building Custom Docker Images

### Backend Dockerfile

The backend [Dockerfile](../Dockerfile) uses Python 3.13 and installs Soliplex in editable mode.

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

### Frontend Dockerfile

Build the Flutter web client:
```bash
cd src/flutter
docker build -t soliplex-web .
```

Run manually:
```bash
docker run -p 9000:9000 soliplex-web
```

## Environment Variables

The backend container reads environment variables from:
1. `.env` file (specified with `env_file` in docker-compose.yaml)
2. Environment variables set in docker-compose.yaml
3. Shell environment (if using `docker run`)

### Required Variables

See [.env.example](../.env.example) for a complete list.

**For Ollama:**
```bash
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

**For OpenAI:**
```bash
OPENAI_API_KEY=sk-...
```

### Accessing Host Services

When running Ollama or other services on your host machine, use `host.docker.internal`:

```bash
# In .env file
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Linux, you may need to add this to docker-compose.yaml (already included):
```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Volume Mounts

### Configuration Files (`./example:/app/installation`)

Mounts your configuration directory into the container. Contents:
- `installation.yaml` or `minimal.yaml` - Main installation config
- `haiku.rag.yaml` - RAG configuration
- `rooms/` - Room configurations
- `completions/` - Completion endpoint configurations
- `oidc/` - OIDC provider configurations
- `quizzes/` - Quiz question files

### Database Files (`./db:/app/db`)

Persists application data:
- `db/rag/rag.lancedb/` - RAG vector database
- SQLite databases for threads and authorization (if using defaults)

**Important**: Initialize the RAG database before first run (see RAG Setup below).

## RAG Database Setup in Docker

The RAG database must be initialized before starting the backend server.

### Option 1: Initialize on Host (Recommended)

Initialize the database on your host machine before running Docker:

```bash
# Create Python virtual environment
python3.13 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install haiku-rag (full version for ingestion)
pip install haiku-rag

# Set Ollama URL
export OLLAMA_BASE_URL=http://localhost:11434

# Initialize and populate RAG database
haiku-rag --config example/haiku.rag.yaml init --db db/rag/rag.lancedb
haiku-rag --config example/haiku.rag.yaml add-src --db db/rag/rag.lancedb docs/
```

The `./db` directory will be mounted into the container with the initialized database.

### Option 2: Initialize in Container

Run initialization inside the backend container:

```bash
# Start container with shell
docker-compose run --rm soliplex_backend /bin/bash

# Inside container
export OLLAMA_BASE_URL=http://host.docker.internal:11434
pip install haiku-rag  # Install full version
haiku-rag --config /app/installation/haiku.rag.yaml init --db /app/db/rag/rag.lancedb
haiku-rag --config /app/installation/haiku.rag.yaml add-src --db /app/db/rag/rag.lancedb /app/docs/
exit
```

## Common Issues

### Port Already in Use

If ports 8000 or 9000 are already allocated:

Edit `docker-compose.yaml`:
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

If missing, initialize as described in RAG Database Setup section.

### Permission Issues

If you encounter permission errors with mounted volumes:

```bash
# Ensure directories exist and are writable
mkdir -p db/rag
chmod -R 755 db/
```

## Development Workflow

### Hot Reload

The backend supports hot reload for development:

```yaml
# In docker-compose.yaml, add to backend service
command: [
  "soliplex-cli", "serve",
  "--host=0.0.0.0",
  "--reload", "both",
  "/app/installation"
]
volumes:
  - ./src/soliplex:/app/src/soliplex  # Mount source code
  - ./example:/app/installation
  - ./db:/app/db
```

Changes to Python code or YAML configs will automatically reload the server.

### Running Tests

```bash
# Run tests in container
docker-compose run --rm soliplex_backend pytest

# With coverage
docker-compose run --rm soliplex_backend pytest --cov=soliplex
```

## Production Considerations

1. **Authentication**: Never use `--no-auth-mode` in production
2. **Secrets**: Use Docker secrets or environment variable injection from secrets managers
3. **Database**: Consider PostgreSQL instead of SQLite for production
4. **Reverse Proxy**: Place behind nginx or traefik with HTTPS
5. **Health Checks**: Add health check endpoints to docker-compose
6. **Resource Limits**: Set memory and CPU limits

Example production docker-compose additions:
```yaml
services:
  soliplex_backend:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Next Steps

- Configure OIDC authentication: [OIDC Providers](config/oidc_providers.md)
- Set up rooms: [Room Configuration](config/rooms.md)
- Configure agents: [Agent Configuration](config/agents.md)
- Review server documentation: [Server Setup](server.md)
