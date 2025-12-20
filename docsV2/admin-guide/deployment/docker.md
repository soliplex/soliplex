# Docker Deployment

Deploy Soliplex using Docker containers.

## Quick Start

```bash
# Build image
docker build -t soliplex .

# Run with minimal config
docker run -p 8000:8000 \
    -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
    -v ./config:/app/config \
    soliplex serve /app/config/installation.yaml
```

## Docker Compose

### Basic Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  soliplex:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    depends_on:
      - ollama
    command: serve /app/config/installation.yaml

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

### With Persistent Database

```yaml
version: '3.8'

services:
  soliplex:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - DB_PASSWORD_FILE=/run/secrets/db_password
    volumes:
      - ./config:/app/config
      - ./data:/app/data
    secrets:
      - db_password
    depends_on:
      - ollama
      - postgres

  postgres:
    image: postgres:16
    environment:
      - POSTGRES_DB=soliplex
      - POSTGRES_USER=soliplex
      - POSTGRES_PASSWORD_FILE=/run/secrets/db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    secrets:
      - db_password

  ollama:
    image: ollama/ollama
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

secrets:
  db_password:
    file: ./secrets/db_password.txt

volumes:
  postgres_data:
  ollama_data:
```

## Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy source
COPY src/ src/

# Create non-root user
RUN useradd -m soliplex
USER soliplex

EXPOSE 8000

ENTRYPOINT ["soliplex-cli"]
CMD ["serve", "--help"]
```

## Environment Variables

Pass environment variables via Docker:

```yaml
services:
  soliplex:
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - LOG_LEVEL=INFO
      - URL_SAFE_TOKEN_SECRET=${URL_SAFE_TOKEN_SECRET}
```

Or use an env file:

```yaml
services:
  soliplex:
    env_file:
      - .env
```

## Secrets

### Using Docker Secrets

```yaml
services:
  soliplex:
    secrets:
      - openai_api_key
      - db_password

secrets:
  openai_api_key:
    file: ./secrets/openai_api_key.txt
  db_password:
    file: ./secrets/db_password.txt
```

Configure in installation.yaml:

```yaml
secrets:
  - secret_name: "OPENAI_API_KEY"
    sources:
      - kind: "file_path"
        file_path: "/run/secrets/openai_api_key"
```

## Volumes

### Configuration Volume

```yaml
volumes:
  - ./config:/app/config:ro  # Read-only config
```

### Data Volume

```yaml
volumes:
  - ./data:/app/data  # Thread persistence, RAG databases
```

### RAG Database Volume

```yaml
volumes:
  - ./db/rag:/app/db/rag:ro  # Pre-built RAG databases
```

## GPU Support

### NVIDIA GPU

```yaml
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### AMD GPU (ROCm)

```yaml
services:
  ollama:
    image: ollama/ollama:rocm
    devices:
      - /dev/kfd
      - /dev/dri
```

## Network Configuration

### Internal Network

```yaml
services:
  soliplex:
    networks:
      - backend
      - frontend

  ollama:
    networks:
      - backend  # Only accessible to soliplex

  nginx:
    networks:
      - frontend
    ports:
      - "443:443"

networks:
  backend:
    internal: true
  frontend:
```

## Health Checks

```yaml
services:
  soliplex:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/installation"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 10s
```

## Reverse Proxy

### Nginx

```yaml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - soliplex
```

```nginx
# nginx.conf
server {
    listen 443 ssl;
    server_name soliplex.example.com;

    ssl_certificate /etc/nginx/certs/cert.pem;
    ssl_certificate_key /etc/nginx/certs/key.pem;

    location / {
        proxy_pass http://soliplex:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Traefik

```yaml
services:
  traefik:
    image: traefik:v2.10
    command:
      - "--providers.docker=true"
      - "--entrypoints.websecure.address=:443"
    ports:
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  soliplex:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.soliplex.rule=Host(`soliplex.example.com`)"
      - "traefik.http.routers.soliplex.entrypoints=websecure"
      - "traefik.http.routers.soliplex.tls=true"
```

## Production Compose

```yaml
version: '3.8'

services:
  soliplex:
    build: .
    restart: unless-stopped
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - LOG_LEVEL=WARNING
    volumes:
      - ./config:/app/config:ro
      - soliplex_data:/app/data
    secrets:
      - url_safe_token_secret
    depends_on:
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/installation"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 2G

  ollama:
    image: ollama/ollama
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - soliplex

secrets:
  url_safe_token_secret:
    file: ./secrets/url_safe_token_secret.txt

volumes:
  soliplex_data:
  ollama_data:
```

## Source Code

- Dockerfile: `Dockerfile`
- Docker Compose examples: `docker-compose.yml`
