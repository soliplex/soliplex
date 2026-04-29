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
runtime data directories (`db/`, `documents/`, `uploads/`). This keeps the build
context small and prevents secrets from leaking into the image.

## Docker Compose

In the `docker-compose.yaml` you can find 3 services for soliplex usage or development, these are:
- `docling-serve`
- `soliplex_indexer`
- `soliplex_backend`

In addition, there are additional services commented out, that are included as conveninence to quickly build and use the frontends to interact with soliplex. These are:
- `soliplex_frontend`
- `chatbot_builder`
- `chatbot_dev`
- `chatbot_widget`

### `docling-serve` and `soliplex_indexer`

These two services work together to index documents into a RAG database. This database needs to be manually initialized:
```bash
$ docker compose run --rm soliplex_indexer haiku-rag --config=/app/installation/haiku.rag.yaml init --db=/app/db/rag/rag.lancedb
```

After this, when the stack is up, the documents inside `documents/` are automatically picked up and indexed into the RAG database.

### `soliplex_backend`

This is the main service which executes the `soliplex` backend, as the name obviously implies.

This service requires a few environment variables set in order to work, copy the `.env.example` as `.env` and assign needed values to the relevant variables.(see [Environment Variables](#environment-variables) below).

After this, you can start the stack:
```bash
$ docker compose up
```

On Linux, pass your UID/GID so that files written by the container are
owned by your host user:

```bash
$ APP_UID=$(id -u) APP_GID=$(id -g) docker compose up
```

### `soliplex_frontend` (Optional)

This optional service is included as a convenience to quickly be able to have the [Flutter frontend](https://github.com/soliplex/frontend) running locally, connected with the `soliplex_backend` service.
In order to do so, clone the repo in `src/frontend` and uncomment the lines in the `docker-compose.yaml` and start the stack with:
```bash
$ docker compose up
```

Once the services are up, you can access the GUI from a web browser, by visiting http://localhost:9000
The soliplex backend can be reached at http://localhost:8000

### `chatbot_dev` (Optional)

This optional service is included as a convenience to develop the embeddable [chat widget](https://github.com/soliplex/chatbot).
Notice that this widget was implemented using React, and it is completely independent from the `soliplex_frontend` service.
In order to use it, clone the repo in `src/chatbot` and uncomment the lines for this service in the `docker-compose.yaml` finally start the stack with:
```bash
$ docker compose up
```

Once all services are up, you can access the React app from a web browser, by visiting http://localhost:3000
The soliplex backend can be reached at http://localhost:8000
Since this is React in dev mode, changes to the code are applied live and don't require any restarts.

### `chatbot_builder` and `chatbot_widget` (Optional)

These 2 services are intended to be used together and are independent from the `soliplex_frontend` and `chatbot_dev` services mentioned before.
It shares the same codebase and repo from `chatbot_dev` (`src/chatbot`) but instead of starting react in dev mode, it is intended to test the embeddable widget in production mode, by compiling the source and serving it with an nginx container.

In order to use it, clone the repo in `src/chatbot` and uncomment the lines for these services in the `docker-compose.yaml` finally start the stack with:
```bash
$ docker compose up
```

Once all services are up, you can visit http://localhost:8080/ to open the website, with the compiled JS embedded. Changes to the code, will reload the whole page.

The soliplex backend can be reached at http://localhost:8000

### Sandboxed python modules

You can include Python modules, to be executed in rooms in their own sandbox. A "server_time" is included as example at `sandbox/environments/server_time`, configured to be used in the `example/rooms/server_time` room. It is important to notice that a proper description should be included in the `pyproject.toml` for your module, in order for the AI agent to pass the correct `environment_name` to the `execute_script` call.
Notice that changes to these modules will require a `docker compose build` in order for the code to be updated and used.
You can uncomment the:
```
    # environment:
    #   - TZ=Pacific/Auckland
```
lines in the `docker-compose.yaml` file in order to test that the python code is actually being called.


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

### Running haiku.rag commands manually

If you want to jump into the running container and execute `haiku-rag` commands manually, you can do so with `docker compose exec soliplex_backend /bin/bash` and from here run `haiku-rag` commands.

Alternatively, you can start a new, separate container, with `docker compose run soliplex_backend /bin/bash` and run `haiku-rag` commands.

### Accessing the Application

- **Backend API**: <http://localhost:8000>
- **API Documentation**: <http://localhost:8000/docs>
- **Flutter frontend (Optional)**: <http://localhost:9000>
- **Embeddable widget (Optional, React dev mode)**: <http://localhost:3000>
- **Embeddable widget (Optional, Nginx prod mode)**: <http://localhost:8080>

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

### Documents Files (`./documents:/app/docs`)

Documents inside this folder will be automatically picked up and indexed into the RAG database.

**Important**: Initialize the RAG database before first run (see RAG
Setup below).

### Source Code (`./src/soliplex:/app/src/soliplex`)

Bind-mounts your working tree into the container so that edits are picked up by the uvicorn reloader.

### Tests (`./tests:/app/tests`)

Only used by the `soliplex_backend` service. Allows running the test suite
inside the container:

```bash
docker compose run --rm soliplex_backend uv run pytest
```

## RAG Database Setup in Docker

The RAG database must be initialized before starting the backend server.

```bash
$ docker compose run --rm soliplex_indexer haiku-rag --config=/app/installation/haiku.rag.yaml init --db=/app/db/rag/rag.lancedb
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
APP_UID=$(id -u) APP_GID=$(id -g) docker compose up --build soliplex_backend
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
