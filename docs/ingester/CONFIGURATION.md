# Configuration Guide

## Overview

Soliplex Ingester is configured via environment variables using Pydantic Settings. All configuration is defined in `src/soliplex_ingester/lib/config.py:15`.

## Environment Variables

### Database Configuration

#### DOC_DB_URL (required)

Database connection URL.

**SQLite Example:**
```bash
DOC_DB_URL="sqlite+aiosqlite:///./db/documents.db"
```

**PostgreSQL Example:**
```bash
DOC_DB_URL="postgresql+asyncpg://username:password@localhost:5432/soliplex"
```

**Notes:**
- Must use async drivers (`aiosqlite` or `asyncpg`)
- SQLite uses relative or absolute file paths
- PostgreSQL requires credentials and network access

---

### External Services

#### DOCLING_SERVER_URL

Docling document parsing service endpoint.

**Default:** `http://localhost:5001/v1`

**Example:**
```bash
DOCLING_SERVER_URL="http://docling.internal.company.com/v1"
```

**Notes:**
- Used for document parsing (PDF, DOCX, etc.)
- Must be accessible from worker nodes
- Health check: `GET {url}/health`

#### DOCLING_HTTP_TIMEOUT

HTTP timeout for Docling requests in seconds.

**Default:** `600` (10 minutes)

**Example:**
```bash
DOCLING_HTTP_TIMEOUT=300
```

**Notes:**
- Large documents may require longer timeouts
- Adjust based on document size and complexity

---

### Logging

#### LOG_LEVEL

Python logging level.

**Default:** `INFO`

**Options:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Example:**
```bash
LOG_LEVEL=DEBUG
```

---

### File Storage

#### FILE_STORE_TARGET

Storage backend type.

**Default:** `fs` (filesystem)

**Options:**
- `fs` - Local filesystem
- `s3` - S3-compatible storage (requires OpenDAL config)

**Example:**
```bash
FILE_STORE_TARGET=s3
```

#### FILE_STORE_DIR

Base directory for file storage.

**Default:** `file_store`

**Example:**
```bash
FILE_STORE_DIR=/var/lib/soliplex/files
```

**Notes:**
- Used when `FILE_STORE_TARGET=fs`
- Must be writable by the application user
- Consider disk space requirements

#### DOCUMENT_STORE_DIR

Subdirectory for raw documents.

**Default:** `raw`

**Full Path:** `{FILE_STORE_DIR}/{DOCUMENT_STORE_DIR}`

#### PARSED_MARKDOWN_STORE_DIR

Subdirectory for parsed markdown.

**Default:** `markdown`

#### PARSED_JSON_STORE_DIR

Subdirectory for parsed JSON.

**Default:** `json`

#### CHUNKS_STORE_DIR

Subdirectory for text chunks.

**Default:** `chunks`

#### EMBEDDINGS_STORE_DIR

Subdirectory for embedding vectors.

**Default:** `embeddings`

---

### Vector Database

#### LANCEDB_DIR

Directory for LanceDB vector storage.

**Default:** `lancedb`

**Example:**
```bash
LANCEDB_DIR=/var/lib/soliplex/lancedb
```

**Notes:**
- Stores vector embeddings for RAG retrieval
- Requires sufficient disk space
- Periodically compact for performance

---

### Worker Configuration

#### INGEST_QUEUE_CONCURRENCY

Maximum concurrent queue operations.

**Default:** `20`

**Example:**
```bash
INGEST_QUEUE_CONCURRENCY=50
```

**Notes:**
- Controls internal queue processing
- Higher values increase throughput but use more memory

#### INGEST_WORKER_CONCURRENCY

Maximum concurrent workflow steps per worker.

**Default:** `10`

**Example:**
```bash
INGEST_WORKER_CONCURRENCY=20
```

**Notes:**
- Primary throughput control
- Balance against CPU and external service limits
- Monitor resource usage when tuning

#### DOCLING_CONCURRENCY

Maximum concurrent Docling requests.

**Default:** `3`

**Example:**
```bash
DOCLING_CONCURRENCY=5
```

**Notes:**
- Prevents overwhelming Docling service
- Coordinate with Docling server capacity
- Increase if Docling can handle load

#### WORKER_TASK_COUNT

Number of workflow steps to fetch per query.

**Default:** `5`

**Example:**
```bash
WORKER_TASK_COUNT=10
```

**Notes:**
- Batch size for step queries
- Higher values reduce database round-trips
- Lower values improve fairness across workers

#### WORKER_CHECKIN_INTERVAL

Worker heartbeat interval in seconds.

**Default:** `120` (2 minutes)

**Example:**
```bash
WORKER_CHECKIN_INTERVAL=60
```

**Notes:**
- How often workers update health status
- Lower values increase database load slightly
- Used for monitoring worker liveness

#### WORKER_CHECKIN_TIMEOUT

Worker timeout threshold in seconds.

**Default:** `600` (10 minutes)

**Example:**
```bash
WORKER_CHECKIN_TIMEOUT=300
```

**Notes:**
- When to consider a worker stale
- Should be significantly larger than `WORKER_CHECKIN_INTERVAL`
- Used for detecting crashed workers

#### EMBED_BATCH_SIZE

Batch size for embedding operations.

**Default:** `1000`

**Example:**
```bash
EMBED_BATCH_SIZE=500
```

**Notes:**
- Number of chunks to embed at once
- Higher values improve throughput
- Limited by embedding service capacity and memory

---

### Workflow Configuration

#### WORKFLOW_DIR

Directory containing workflow YAML definitions.

**Default:** `config/workflows`

**Example:**
```bash
WORKFLOW_DIR=/etc/soliplex/workflows
```

**Notes:**
- Scanned for `*.yaml` files at startup
- Hot-reload if `--reload` flag is used

#### DEFAULT_WORKFLOW_ID

Default workflow to use when not specified.

**Default:** `batch_split`

**Example:**
```bash
DEFAULT_WORKFLOW_ID=batch
```

**Notes:**
- Must match an `id` in workflow YAML files
- Used when API requests omit `workflow_definition_id`

#### PARAM_DIR

Directory containing parameter set YAML files.

**Default:** `config/params`

**Example:**
```bash
PARAM_DIR=/etc/soliplex/params
```

#### DEFAULT_PARAM_ID

Default parameter set to use when not specified.

**Default:** `default`

**Example:**
```bash
DEFAULT_PARAM_ID=high_quality
```

**Notes:**
- Must match an `id` in parameter YAML files

---

### Feature Flags

#### DO_RAG

Enable/disable HaikuRAG integration.

**Default:** `True`

**Example:**
```bash
DO_RAG=false
```

**Notes:**
- Set to `false` for testing without RAG backend
- When disabled, `store` step becomes a no-op
- Useful for CI/CD testing

---

## Configuration File

While the system uses environment variables, you can organize them in a `.env` file:

**.env Example:**
```bash
# Database
DOC_DB_URL=sqlite+aiosqlite:///./db/documents.db

# External Services
DOCLING_SERVER_URL=http://localhost:5001/v1
DOCLING_HTTP_TIMEOUT=600

# Logging
LOG_LEVEL=INFO

# Storage
FILE_STORE_TARGET=fs
FILE_STORE_DIR=file_store
LANCEDB_DIR=lancedb

# Worker Settings
INGEST_WORKER_CONCURRENCY=10
DOCLING_CONCURRENCY=3
WORKER_TASK_COUNT=5
WORKER_CHECKIN_INTERVAL=120
WORKER_CHECKIN_TIMEOUT=600
EMBED_BATCH_SIZE=1000

# Workflow Configuration
WORKFLOW_DIR=config/workflows
DEFAULT_WORKFLOW_ID=batch
PARAM_DIR=config/params
DEFAULT_PARAM_ID=default

# Features
DO_RAG=true
```

Load with:
```bash
export $(cat .env | xargs)
si-cli serve
```

---

## Nested Configuration (Advanced)

Pydantic Settings supports nested configuration using `__` delimiter.

**Example:**
```bash
# Not yet implemented in current version
# DEFAULT_S3__BUCKET=my-bucket
# DEFAULT_S3__ENDPOINT_URL=https://s3.amazonaws.com
```

See `src/soliplex_ingester/lib/config.py:16` for nested model definitions.

---

## Configuration Validation

### Validate Settings

Check configuration without starting services:

```bash
si-cli validate-settings
```

**Output:**
```
doc_db_url='sqlite+aiosqlite:///./db/documents.db'
docling_server_url='http://localhost:5001/v1'
log_level='INFO'
...
```

**Validation Errors:**
```
invalid settings
{'type': 'missing', 'loc': ('doc_db_url',), 'msg': 'Field required'}
```

---

## Environment-Specific Configuration

### Development

**dev.env:**
```bash
DOC_DB_URL=sqlite+aiosqlite:///./db/dev.db
LOG_LEVEL=DEBUG
INGEST_WORKER_CONCURRENCY=5
DO_RAG=false
```

### Staging

**staging.env:**
```bash
DOC_DB_URL=postgresql+asyncpg://user:pass@staging-db:5432/soliplex
LOG_LEVEL=INFO
INGEST_WORKER_CONCURRENCY=10
DOCLING_SERVER_URL=http://docling-staging:5001/v1
DO_RAG=true
```

### Production

**production.env:**
```bash
DOC_DB_URL=postgresql+asyncpg://user:pass@prod-db:5432/soliplex
LOG_LEVEL=WARNING
INGEST_WORKER_CONCURRENCY=20
DOCLING_CONCURRENCY=5
DOCLING_SERVER_URL=http://docling-prod:5001/v1
FILE_STORE_TARGET=s3
DO_RAG=true
WORKER_CHECKIN_INTERVAL=60
```

---

## Docker Configuration

### Docker Compose Example

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  ingester:
    image: soliplex-ingester:latest
    environment:
      DOC_DB_URL: postgresql+asyncpg://postgres:password@db:5432/soliplex
      DOCLING_SERVER_URL: http://docling:5001/v1
      LOG_LEVEL: INFO
      FILE_STORE_DIR: /data/files
      LANCEDB_DIR: /data/lancedb
      INGEST_WORKER_CONCURRENCY: 15
    volumes:
      - ./config/workflows:/app/config/workflows
      - ./config/params:/app/config/params
      - data-volume:/data
    depends_on:
      - db
      - docling

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: soliplex
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - db-volume:/var/lib/postgresql/data

  docling:
    image: docling-server:latest
    ports:
      - "5001:5001"

volumes:
  db-volume:
  data-volume:
```

### Kubernetes ConfigMap

**configmap.yaml:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: soliplex-config
data:
  DOC_DB_URL: "postgresql+asyncpg://user:pass@postgres-service:5432/soliplex"
  DOCLING_SERVER_URL: "http://docling-service:5001/v1"
  LOG_LEVEL: "INFO"
  INGEST_WORKER_CONCURRENCY: "20"
  WORKFLOW_DIR: "/config/workflows"
  PARAM_DIR: "/config/params"
```

---

## Performance Tuning

### High Throughput

```bash
INGEST_WORKER_CONCURRENCY=50
DOCLING_CONCURRENCY=10
WORKER_TASK_COUNT=20
EMBED_BATCH_SIZE=2000
```

**Notes:**
- Requires powerful hardware
- Monitor CPU, memory, and I/O
- Coordinate with external service capacity

### Resource Constrained

```bash
INGEST_WORKER_CONCURRENCY=5
DOCLING_CONCURRENCY=2
WORKER_TASK_COUNT=3
EMBED_BATCH_SIZE=500
```

**Notes:**
- Reduces memory and CPU usage
- Lower throughput but more stable
- Good for shared environments

### Batch Processing

```bash
INGEST_WORKER_CONCURRENCY=30
DOCLING_CONCURRENCY=8
WORKER_TASK_COUNT=10
WORKER_CHECKIN_INTERVAL=300
```

**Notes:**
- Optimized for processing large batches
- Reduces monitoring overhead
- Assumes long-running workers

---

## Secrets Management

### Using Environment Files

Keep secrets out of version control:

```bash
# .env.secrets (add to .gitignore)
DOC_DB_URL=postgresql+asyncpg://user:$(cat /run/secrets/db_password)@db/soliplex
```

### Using Secret Management Tools

**AWS Secrets Manager:**
```bash
export DOC_DB_URL=$(aws secretsmanager get-secret-value --secret-id db-url --query SecretString --output text)
```

**HashiCorp Vault:**
```bash
export DOC_DB_URL=$(vault kv get -field=url secret/soliplex/db)
```

**Kubernetes Secrets:**
```yaml
env:
  - name: DOC_DB_URL
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: url
```

---

## Troubleshooting

### Configuration Not Loading

**Symptom:** Application uses default values

**Solutions:**
1. Verify environment variables are set: `env | grep DOC_`
2. Check for typos in variable names
3. Ensure `.env` file is in correct directory
4. Verify `.env` file is being loaded

### Validation Errors

**Symptom:** Application fails to start with validation error

**Solutions:**
1. Run `si-cli validate-settings` to see errors
2. Check required fields are set
3. Verify value types (e.g., integers for ports)
4. Check URL formats

### Connection Errors

**Symptom:** Cannot connect to database or Docling

**Solutions:**
1. Verify URLs are correct
2. Test connectivity: `curl http://docling-url/health`
3. Check network policies/firewall
4. Verify credentials

### File Permissions

**Symptom:** Cannot write to storage directories

**Solutions:**
1. Check directory exists and is writable
2. Verify application user permissions
3. Create directories if needed: `mkdir -p file_store lancedb`
4. Set ownership: `chown -R app-user file_store lancedb`

---

## Configuration Reference

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `DOC_DB_URL` | str | Yes | - | Database connection URL |
| `DOCLING_SERVER_URL` | str | No | `http://localhost:5001/v1` | Docling service URL |
| `DOCLING_HTTP_TIMEOUT` | int | No | `600` | Docling timeout (seconds) |
| `LOG_LEVEL` | str | No | `INFO` | Logging level |
| `FILE_STORE_TARGET` | str | No | `fs` | Storage backend type |
| `FILE_STORE_DIR` | str | No | `file_store` | Base storage directory |
| `LANCEDB_DIR` | str | No | `lancedb` | LanceDB directory |
| `DOCUMENT_STORE_DIR` | str | No | `raw` | Raw documents subdir |
| `PARSED_MARKDOWN_STORE_DIR` | str | No | `markdown` | Markdown subdir |
| `PARSED_JSON_STORE_DIR` | str | No | `json` | JSON subdir |
| `CHUNKS_STORE_DIR` | str | No | `chunks` | Chunks subdir |
| `EMBEDDINGS_STORE_DIR` | str | No | `embeddings` | Embeddings subdir |
| `INGEST_QUEUE_CONCURRENCY` | int | No | `20` | Queue concurrency |
| `INGEST_WORKER_CONCURRENCY` | int | No | `10` | Worker concurrency |
| `DOCLING_CONCURRENCY` | int | No | `3` | Docling concurrency |
| `WORKER_TASK_COUNT` | int | No | `5` | Steps per query |
| `WORKER_CHECKIN_INTERVAL` | int | No | `120` | Heartbeat interval (sec) |
| `WORKER_CHECKIN_TIMEOUT` | int | No | `600` | Worker timeout (sec) |
| `EMBED_BATCH_SIZE` | int | No | `1000` | Embedding batch size |
| `WORKFLOW_DIR` | str | No | `config/workflows` | Workflow definitions dir |
| `DEFAULT_WORKFLOW_ID` | str | No | `batch_split` | Default workflow |
| `PARAM_DIR` | str | No | `config/params` | Parameter sets dir |
| `DEFAULT_PARAM_ID` | str | No | `default` | Default parameter set |
| `DO_RAG` | bool | No | `True` | Enable RAG integration |
