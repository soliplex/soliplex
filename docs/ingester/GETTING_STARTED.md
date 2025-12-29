# Getting Started with Soliplex Ingester

## Quick Start

This guide will help you get Soliplex Ingester up and running in minutes.

## Prerequisites

- Python 3.12 or higher
- pip or uv package manager
- SQLite (included with Python) or PostgreSQL
- Docling server for document parsing (optional)
- S3 backend (optional)

## Docker Services

A sample docker compose file is provided to show how to configure services used by the ingester.

### postgres

The postgres configuration includes references to startup scripts to create sample users and permissions, but for a production deployment, a more sophisticated secrets configuration should be used. Data is stored in a docker volume which may also need to be changed for a production setup.

### docling-serve

Docling-serve is used to convert pdf documents into markdown and docling JSON documents for use in the pipelline. In order to allow for higher concurrency, the example file shows how to use multiple instances of docling that are load balanced using cookies. The docling client in the ingester handles the cookies to ensure the full request cycle stays on the same server. 

The configuration also shows how to provision GPUs for use in parsing.  Depending on server hardware, the device ids may have to be changed. Multiple instances can share a single GPU but testing is required to determine the optimal configuration.

Docling serve is prone to leak memory so constraining its memory allocation is necessary to prevent overloading server resources.  The restart settings along with load balancing and retry logic in the client will ensure that the ingester is able to continue uninterrupted.

### seaweedfs

SeaweedFS is provided as a simple S3 compatible storage if desired for either the intermediate artifacts or the final LanceDB databases. An initialization script is provided to create the necessary bucket and authentication information. A production configuration should use a more robust secrets confugration.  Cloud providers can also be used for storage if desired.

### 




### 1. Install Package


#### Installation from source
**Using pip:**
```bash
cd soliplex-ingester
pip install -e .
```

**Using uv:**
```bash
cd soliplex-ingester
uv pip install -e .
```

#### Running your own Install
You can integrate soliplex ingester into another python project by installing it like any other package.  This will allow you to use custom methods for any part of the workflow if desired.

```
uv init --lib <my project name>
uv add https://github.com/soliplex/ingester.git
uv run si-cli bootstrap

```

This installs the package and makes the `si-cli` command available.

### 2. Verify Installation

```bash
si-cli --help
```

You should see the CLI help menu.

## Configuration

### 3. Set Environment Variables
Automatically configure:
```
uv run init-env
```

Manually create a `.env` file in the project root:

```bash
# Minimum required configuration
DOC_DB_URL=sqlite+aiosqlite:///./db/documents.db

# Optional: Docling service (for document parsing)
DOCLING_SERVER_URL=http://localhost:5001/v1

# Optional: Adjust logging
LOG_LEVEL=INFO
```

Load the environment:
```bash
export $(cat .env | xargs)
```

Or on Windows:
```powershell
Get-Content .env | ForEach-Object { $var = $_.Split('='); [Environment]::SetEnvironmentVariable($var[0], $var[1]) }
```
Alternatively, si-cli can be run via uv to initialize the environment file
```
uv run --env-file=.env si-cli
```

### 4. Validate Configuration

```bash
si-cli validate-settings
```

This should display your configuration without errors.

## Database Setup

### 5. Initialize Database

```bash
si-cli db-init
```

This creates:
- SQLite database file at `db/documents.db`
- All necessary tables
- Runs migrations

## Start the Server

### 6. Run the Development Server

```bash
si-cli serve --reload
```

The server starts on `http://127.0.0.1:8000` with:
- Auto-reload on code changes
- Integrated worker for processing
- OpenAPI docs at `/docs`

**Test the server:**
```bash
curl http://localhost:8000/docs
```

You should see the Swagger UI.

## Your First Batch

### 7. Create a Batch

```bash
curl -X POST "http://localhost:8000/api/v1/batch/" \
  -d "source=test" \
  -d "name=My First Batch"
```

**Response:**
```json
{
  "batch_id": 1
}
```

### 8. Ingest a Document

**Option A: Upload a file**
```bash
curl -X POST "http://localhost:8000/api/v1/document/ingest-document" \
  -F "file=@sample.pdf" \
  -F "source_uri=/documents/sample.pdf" \
  -F "source=test" \
  -F "batch_id=1"
```

**Option B: Provide a URI** (requires Docling server)
```bash
curl -X POST "http://localhost:8000/api/v1/document/ingest-document" \
  -F "input_uri=https://example.com/document.pdf" \
  -F "source_uri=/remote/document.pdf" \
  -F "source=test" \
  -F "batch_id=1"
```

**Response:**
```json
{
  "batch_id": 1,
  "document_uri": "/documents/sample.pdf",
  "document_hash": "sha256-abc123...",
  "source": "test",
  "uri_id": 1
}
```

### 9. Start Workflow Processing

```bash
curl -X POST "http://localhost:8000/api/v1/batch/start-workflows" \
  -d "batch_id=1" \
  -d "workflow_definition_id=batch"
```

**Response:**
```json
{
  "message": "Workflows started",
  "workflows": 1,
  "run_group": 1
}
```

### 10. Monitor Progress

**Check batch status:**
```bash
curl "http://localhost:8000/api/v1/batch/status?batch_id=1"
```

**Response:**
```json
{
  "batch": { ... },
  "document_count": 1,
  "workflow_count": {
    "COMPLETED": 0,
    "RUNNING": 1,
    "PENDING": 0
  },
  "workflows": [ ... ],
  "parsed": 0,
  "remaining": 1
}
```

**Watch workflow runs:**
```bash
watch -n 5 'curl -s "http://localhost:8000/api/v1/workflow/?batch_id=1"'
```

### 11. View Results

Once processing completes, check the document:

```bash
curl "http://localhost:8000/api/v1/document/?batch_id=1"
```

Look for the `rag_id` field - if present, the document was successfully processed and stored in the RAG system.

## Next Steps

### Explore Workflows

**List available workflows:**
```bash
si-cli list-workflows
```

**Inspect a workflow:**
```bash
si-cli dump-workflow batch
```

**View workflow runs:**
```bash
curl "http://localhost:8000/api/v1/workflow/?batch_id=1"
```

### Configure Parameters

**List parameter sets:**
```bash
si-cli list-param-sets
```

**View parameters:**
```bash
si-cli dump-param-set default
```

**Create custom parameters:**
1. Copy `config/params/default.yaml` to `config/params/custom.yaml`
2. Modify settings as needed
3. Use in API: `-d "param_id=custom"`

### Scale Workers

**Run additional workers:**
```bash
# Terminal 1
si-cli worker

# Terminal 2
si-cli worker

# Terminal 3
si-cli worker
```

Each worker processes steps independently, increasing throughput.

### Monitor System

**API Documentation:**
Browse to `http://localhost:8000/docs` for interactive API docs.

**Database Inspection:**
```bash
sqlite3 db/documents.db
sqlite> .tables
sqlite> SELECT * FROM documentbatch;
sqlite> SELECT * FROM workflowrun WHERE batch_id = 1;
```

## Troubleshooting

### Server Won't Start

**Problem:** Configuration validation fails

**Solution:**
```bash
si-cli validate-settings
```

Fix any reported errors in your `.env` file.

---

**Problem:** Port already in use

**Solution:**
```bash
si-cli serve --port 8001
```

---

### Workflows Stuck

**Problem:** Workflows remain in PENDING status

**Solution:**
Ensure a worker is running:
```bash
si-cli worker
```

Check worker logs for errors.

---

### Document Parsing Fails

**Problem:** Parse step fails with connection error

**Solution:**
1. Verify Docling server is running
2. Check `DOCLING_SERVER_URL` is correct
3. Test connectivity:
   ```bash
   curl http://localhost:5001/v1/health
   ```

---

### Database Errors

**Problem:** Database connection fails

**Solution:**
1. Check `DOC_DB_URL` format
2. Ensure directory exists: `mkdir -p db`
3. Check permissions: `chmod 755 db`
4. Reinitialize: `si-cli db-init`

---

## Development Mode

For active development:

**1. Enable auto-reload:**
```bash
si-cli serve --reload
```

**2. Set debug logging:**
```bash
export LOG_LEVEL=DEBUG
si-cli serve --reload
```

**3. Watch logs:**
```bash
si-cli serve --reload 2>&1 | tee server.log
```

**4. Monitor database:**
```bash
watch -n 2 'sqlite3 db/documents.db "SELECT status, COUNT(*) FROM workflowrun GROUP BY status"'
```

## Production Deployment

### Configuration

Create production `.env`:

```bash
# Database
DOC_DB_URL=postgresql+asyncpg://user:password@db-host:5432/soliplex

# Services
DOCLING_SERVER_URL=http://docling-prod:5001/v1

# Logging
LOG_LEVEL=WARNING

# Performance
INGEST_WORKER_CONCURRENCY=20
DOCLING_CONCURRENCY=5
WORKER_TASK_COUNT=10

# Storage
FILE_STORE_DIR=/var/lib/soliplex/files
LANCEDB_DIR=/var/lib/soliplex/lancedb
```

### Run Services

**Server:**
```bash
si-cli serve --host 0.0.0.0 --port 8000 --workers 4
```

**Workers:** (in separate processes)
```bash
si-cli worker  # Worker 1
si-cli worker  # Worker 2
si-cli worker  # Worker 3
```

**Behind Nginx:**
```nginx
upstream soliplex {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name soliplex.example.com;

    location / {
        proxy_pass http://soliplex;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Docker Deployment

**Dockerfile:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -e .

CMD ["si-cli", "serve", "--host", "0.0.0.0"]
```

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  server:
    build: .
    ports:
      - "8000:8000"
    environment:
      DOC_DB_URL: postgresql+asyncpg://postgres:password@db/soliplex
      DOCLING_SERVER_URL: http://docling:5001/v1
    depends_on:
      - db

  worker:
    build: .
    command: si-cli worker
    environment:
      DOC_DB_URL: postgresql+asyncpg://postgres:password@db/soliplex
      DOCLING_SERVER_URL: http://docling:5001/v1
    depends_on:
      - db
    deploy:
      replicas: 3

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: soliplex
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
```

**Run:**
```bash
docker-compose up -d
```

## Learning More

### Documentation

- [Architecture Overview](ARCHITECTURE.md) - System design and components
- [API Reference](API.md) - Complete REST API documentation
- [Workflow System](WORKFLOWS.md) - Workflow concepts and configuration
- [Database Schema](DATABASE.md) - Data models and relationships
- [Configuration](CONFIGURATION.md) - Environment variables and settings
- [CLI Reference](CLI.md) - Command-line interface guide

### Examples

Check the `examples/` directory (if available) for:
- Sample workflows
- Integration scripts
- Custom step handlers
- Batch processing examples

### Community

- **Issues:** Report bugs and request features
- **Discussions:** Ask questions and share ideas
- **Contributing:** See CONTRIBUTING.md (if available)

## Common Patterns

### Batch Document Ingestion

```python
import asyncio
from pathlib import Path
import httpx

async def ingest_directory(directory: Path, batch_id: int, source: str):
    """Ingest all documents in a directory."""
    async with httpx.AsyncClient() as client:
        for file_path in directory.glob("**/*.pdf"):
            with open(file_path, "rb") as f:
                files = {"file": f}
                data = {
                    "source_uri": str(file_path),
                    "source": source,
                    "batch_id": batch_id,
                }
                response = await client.post(
                    "http://localhost:8000/api/v1/document/ingest-document",
                    files=files,
                    data=data,
                )
                print(f"Ingested {file_path}: {response.status_code}")

# Usage
asyncio.run(ingest_directory(Path("/documents"), batch_id=1, source="filesystem"))
```

### Monitor Batch Progress

```python
import asyncio
import httpx

async def wait_for_batch(batch_id: int, poll_interval: int = 5):
    """Wait for batch processing to complete."""
    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                f"http://localhost:8000/api/v1/batch/status",
                params={"batch_id": batch_id}
            )
            data = response.json()
            counts = data["workflow_count"]

            print(f"Completed: {counts.get('COMPLETED', 0)}, "
                  f"Running: {counts.get('RUNNING', 0)}, "
                  f"Failed: {counts.get('FAILED', 0)}")

            if counts.get("RUNNING", 0) == 0 and counts.get("PENDING", 0) == 0:
                print("Batch complete!")
                break

            await asyncio.sleep(poll_interval)

# Usage
asyncio.run(wait_for_batch(1))
```

### Retry Failed Workflows

```bash
#!/bin/bash
# retry_failed.sh

BATCH_ID=$1
RUN_GROUP=$(curl -s "http://localhost:8000/api/v1/workflow/run-groups?batch_id=${BATCH_ID}" | jq -r '.[0].id')

if [ -n "$RUN_GROUP" ]; then
    curl -X POST "http://localhost:8000/api/v1/workflow/retry" \
        -d "run_group_id=${RUN_GROUP}"
    echo "Retried run group ${RUN_GROUP}"
else
    echo "No run group found for batch ${BATCH_ID}"
fi
```

## What's Next?

Now that you have Soliplex Ingester running:

1. **Customize workflows** - Create workflows for your specific needs
2. **Integrate services** - Connect your data sources and RAG backends
3. **Scale processing** - Add more workers and optimize configuration
4. **Monitor production** - Set up logging, metrics, and alerting
5. **Build applications** - Use the API to build document processing apps

Welcome to Soliplex Ingester! 🚀
