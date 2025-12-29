# CLI Reference

## Overview

Soliplex Ingester provides a command-line interface (CLI) built with Typer. The CLI binary is named `si-cli`.

**Installation:**
After installing the package, the `si-cli` command is available:
```bash
pip install -e .
si-cli --help
```

**Entry Point:** `src/soliplex_ingester/cli.py:35`

---

## Global Options

All commands support these options:

```bash
si-cli --help           # Show help for all commands
si-cli COMMAND --help   # Show help for specific command
```

**Initialization:**
Before running any command, the CLI automatically:
1. Validates settings
2. Sets up logging based on `LOG_LEVEL`

---

## Commands

### validate-settings

Validate and display application settings.

**Usage:**
```bash
si-cli validate-settings
```

**Description:**
- Validates all environment variables
- Displays current configuration
- Exits with error code if validation fails

**Example Output:**
```
doc_db_url='sqlite+aiosqlite:///./db/documents.db'
docling_server_url='http://localhost:5001/v1'
docling_http_timeout=600
log_level='INFO'
file_store_target='fs'
file_store_dir='file_store'
...
```

**Error Output:**
```
invalid settings
{'type': 'missing', 'loc': ('doc_db_url',), 'msg': 'Field required'}
```

**Exit Codes:**
- `0` - Settings valid
- `1` - Validation failed

**Implementation:** `src/soliplex_ingester/cli.py:38`

---

### db-init

Initialize database tables and run migrations.

**Usage:**
```bash
si-cli db-init
```

**Description:**
- Creates all database tables using SQLModel metadata
- Runs Alembic migrations to latest version
- Idempotent (safe to run multiple times)

**Prerequisites:**
- `DOC_DB_URL` environment variable must be set
- Database server must be accessible
- User must have CREATE TABLE permissions

**Example:**
```bash
export DOC_DB_URL="sqlite+aiosqlite:///./db/documents.db"
si-cli db-init
```

**Notes:**
- For SQLite, creates database file if it doesn't exist
- For PostgreSQL, database must already exist
- Uses synchronous SQLAlchemy engine (not async)

**Implementation:** `src/soliplex_ingester/cli.py:68`

---

### serve

Start the FastAPI web server.

**Usage:**
```bash
si-cli serve [OPTIONS]
```

**Options:**

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--host` | `-h` | str | `127.0.0.1` | Bind address |
| `--port` | `-p` | int | `8000` | Port number |
| `--uds` | - | str | None | Unix domain socket path |
| `--fd` | - | int | None | File descriptor to bind |
| `--reload` | `-r` | bool | False | Auto-reload on file changes |
| `--workers` | - | int | None | Number of worker processes |
| `--access-log` | - | bool | None | Enable/disable access log |
| `--proxy-headers` | - | bool | None | Trust proxy headers |
| `--forwarded-allow-ips` | - | str | None | IPs to trust for proxy headers |

**Examples:**

**Basic server:**
```bash
si-cli serve
```

**Custom host and port:**
```bash
si-cli serve --host 0.0.0.0 --port 9000
```

**Development mode with auto-reload:**
```bash
si-cli serve --reload
```

**Production with multiple workers:**
```bash
si-cli serve --workers 4 --host 0.0.0.0
```

**Unix socket:**
```bash
si-cli serve --uds /tmp/soliplex.sock
```

**Behind proxy:**
```bash
si-cli serve --proxy-headers --forwarded-allow-ips "10.0.0.0/8"
```

**Reload Configuration:**
When `--reload` is enabled:
- Watches Python files in `soliplex_ingester` package
- Watches `*.yaml`, `*.yml`, `*.txt` files
- Automatically restarts on changes

**Worker Note:**
The server automatically starts a background worker on startup. The worker processes workflow steps concurrently with serving API requests.

**Environment Variables:**
- `WEB_CONCURRENCY` - Default number of workers if not specified

**Implementation:** `src/soliplex_ingester/cli.py:207`

---

### worker

Run a standalone workflow processing worker.

**Usage:**
```bash
si-cli worker
```

**Description:**
- Starts a worker that polls for pending workflow steps
- Executes steps according to workflow definitions
- Runs indefinitely until interrupted (Ctrl+C)

**Behavior:**
- Registers worker with unique ID in database
- Sends heartbeat every `WORKER_CHECKIN_INTERVAL` seconds
- Processes steps based on priority and availability
- Handles retries according to step configuration

**Example:**
```bash
si-cli worker
```

**Multiple Workers:**
Run multiple instances for increased throughput:
```bash
# Terminal 1
si-cli worker

# Terminal 2
si-cli worker

# Terminal 3
si-cli worker
```

**Graceful Shutdown:**
- Press `Ctrl+C` to stop worker
- Worker will finish current step before exiting
- Pending steps remain in database for other workers

**Monitoring:**
Check worker status via API:
```bash
curl http://localhost:8000/api/v1/workflow/steps?status=RUNNING
```

**Implementation:** `src/soliplex_ingester/cli.py:148`

---

### validate-haiku

Validate HaikuRAG integration for a batch.

**Usage:**
```bash
si-cli validate-haiku BATCH_ID [OPTIONS]
```

**Arguments:**
- `BATCH_ID` (int, required) - Batch ID to validate

**Options:**
- `--detail` (bool) - Show detailed output (not yet implemented)

**Description:**
- Checks all documents in batch
- Verifies parsed markdown exists
- Confirms documents are indexed in HaikuRAG
- Reports any errors or missing documents

**Example:**
```bash
si-cli validate-haiku 1
```

**Output:**
```json
-----------results--------------
 found 10 results
-----------fails--------------
[
  {
    "doc": "sha256-abc123...",
    "haiku": null,
    "message": "Document not found in HaikuRAG",
    "status": "haiku error"
  }
]
```

**Status Values:**
- `success` - Document indexed correctly
- `no_id` - Document has no `rag_id` (not yet stored)
- `md error` - Parsed markdown not found
- `haiku error` - Error fetching from HaikuRAG

**Implementation:** `src/soliplex_ingester/cli.py:133`

---

### list-workflows

List all available workflow definitions.

**Usage:**
```bash
si-cli list-workflows
```

**Description:**
- Scans `WORKFLOW_DIR` for YAML files
- Displays workflow IDs

**Example:**
```bash
si-cli list-workflows
```

**Output:**
```
batch
batch_split
interactive
```

**Implementation:** `src/soliplex_ingester/cli.py:189`

---

### dump-workflow

Display complete workflow definition.

**Usage:**
```bash
si-cli dump-workflow WORKFLOW_ID
```

**Arguments:**
- `WORKFLOW_ID` (str, required) - Workflow definition ID

**Description:**
- Loads workflow from YAML
- Displays as formatted JSON

**Example:**
```bash
si-cli dump-workflow batch
```

**Output:**
```json
{
  "id": "batch",
  "name": "Batch Workflow",
  "meta": {},
  "item_steps": {
    "validate": {
      "name": "docling validate",
      "retries": 3,
      "method": "soliplex_ingester.lib.workflow.validate_document",
      "parameters": {}
    },
    ...
  },
  "lifecycle_events": null
}
```

**Implementation:** `src/soliplex_ingester/cli.py:162`

---

### list-param-sets

List all available parameter sets.

**Usage:**
```bash
si-cli list-param-sets
```

**Description:**
- Scans `PARAM_DIR` for YAML files
- Displays parameter set IDs

**Example:**
```bash
si-cli list-param-sets
```

**Output:**
```
default
high_quality
fast_processing
```

**Implementation:** `src/soliplex_ingester/cli.py:201`

---

### dump-param-set

Display complete parameter set configuration.

**Usage:**
```bash
si-cli dump-param-set [PARAM_ID]
```

**Arguments:**
- `PARAM_ID` (str, optional) - Parameter set ID (default: "default")

**Description:**
- Loads parameter set from YAML
- Displays as formatted JSON

**Example:**
```bash
si-cli dump-param-set default
```

**Output:**
```json
{
  "id": "default",
  "name": "Default Parameters",
  "meta": {},
  "config": {
    "parse": {
      "format": "markdown",
      "ocr_enabled": true
    },
    "chunk": {
      "chunk_size": 512,
      "chunk_overlap": 50
    },
    ...
  }
}
```

**Implementation:** `src/soliplex_ingester/cli.py:175`

---

## Usage Patterns

### Development Workflow

**1. Validate configuration:**
```bash
si-cli validate-settings
```

**2. Initialize database:**
```bash
si-cli db-init
```

**3. Start server with reload:**
```bash
si-cli serve --reload
```

**4. (Optional) Start additional workers:**
```bash
si-cli worker
```

---

### Production Deployment

**1. Validate configuration:**
```bash
si-cli validate-settings
```

**2. Run migrations:**
```bash
si-cli db-init
```

**3. Start server with multiple workers:**
```bash
si-cli serve --host 0.0.0.0 --port 8000 --workers 4
```

**4. Start dedicated worker processes:**
```bash
# In separate terminals/services
si-cli worker  # Process 1
si-cli worker  # Process 2
si-cli worker  # Process 3
```

---

### Batch Processing

**1. Create batch and ingest documents:**
```bash
# Use API or client library
curl -X POST http://localhost:8000/api/v1/batch/ \
  -d "source=filesystem" \
  -d "name=Test Batch"
```

**2. Start workflows:**
```bash
curl -X POST http://localhost:8000/api/v1/batch/start-workflows \
  -d "batch_id=1" \
  -d "workflow_definition_id=batch"
```

**3. Start workers to process:**
```bash
si-cli worker
```

**4. Monitor progress:**
```bash
curl http://localhost:8000/api/v1/batch/status?batch_id=1
```

**5. Validate results:**
```bash
si-cli validate-haiku 1
```

---

### Configuration Management

**List available workflows:**
```bash
si-cli list-workflows
```

**Inspect workflow:**
```bash
si-cli dump-workflow batch
```

**List parameter sets:**
```bash
si-cli list-param-sets
```

**Inspect parameters:**
```bash
si-cli dump-param-set default
```

---

### Troubleshooting

**Check configuration:**
```bash
si-cli validate-settings
```

**Verify database connection:**
```bash
si-cli db-init
```

**Test server startup:**
```bash
si-cli serve --host localhost --port 8000
# Press Ctrl+C to stop
```

**Check worker connectivity:**
```bash
si-cli worker
# Should start without errors
# Press Ctrl+C to stop
```

**Validate batch processing:**
```bash
si-cli validate-haiku BATCH_ID
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Configuration error / validation failed |
| `130` | Interrupted by user (Ctrl+C) |

---

## Environment Variables

The CLI respects all configuration environment variables. Key ones for CLI usage:

- `DOC_DB_URL` - Database connection (required)
- `LOG_LEVEL` - Logging verbosity (DEBUG, INFO, WARNING, ERROR)
- `WORKFLOW_DIR` - Workflow definitions directory
- `PARAM_DIR` - Parameter sets directory
- `DOCLING_SERVER_URL` - Docling service endpoint

See [CONFIGURATION.md](CONFIGURATION.md) for complete list.

---

## Logging

### Log Levels

Set via `LOG_LEVEL` environment variable:

```bash
LOG_LEVEL=DEBUG si-cli serve
```

**Levels:**
- `DEBUG` - Detailed diagnostic information
- `INFO` - General informational messages (default)
- `WARNING` - Warning messages
- `ERROR` - Error messages
- `CRITICAL` - Critical error messages

### Log Output

Logs are written to stderr. Redirect as needed:

```bash
si-cli worker 2>&1 | tee worker.log
```

### Log Format

Default format includes:
- Timestamp
- Log level
- Logger name
- Message

Example:
```
2025-01-15 10:00:00,123 INFO soliplex_ingester.cli Starting server
2025-01-15 10:00:01,456 INFO soliplex_ingester.server Starting worker
```

---

## Signal Handling

### Graceful Shutdown

The CLI handles signals for graceful shutdown:

**Signals:**
- `SIGINT` (Ctrl+C) - Graceful shutdown
- `SIGTERM` - Graceful shutdown

**Behavior:**
1. Stop accepting new work
2. Complete current operations
3. Clean up resources
4. Exit with code 0

**Example:**
```bash
si-cli worker
# Press Ctrl+C
# Worker completes current step and exits
```

---

## Platform Notes

### Windows

On Windows, the CLI automatically sets the event loop policy for compatibility:

```python
if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

This is handled automatically; no user action required.

### Unix/Linux

No special configuration needed.

---

## Running with Python

If `si-cli` is not in PATH, run directly:

```bash
python -m soliplex_ingester.cli --help
```

---

## Docker Usage

**Dockerfile CMD examples:**

**Server:**
```dockerfile
CMD ["si-cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
```

**Worker:**
```dockerfile
CMD ["si-cli", "worker"]
```

**Init container:**
```dockerfile
CMD ["si-cli", "db-init"]
```

---

## Systemd Service

**Example service file:**

**/etc/systemd/system/soliplex-ingester.service:**
```ini
[Unit]
Description=Soliplex Ingester API Server
After=network.target postgresql.service

[Service]
Type=simple
User=soliplex
Group=soliplex
WorkingDirectory=/opt/soliplex-ingester
EnvironmentFile=/etc/soliplex/config.env
ExecStart=/opt/soliplex-ingester/.venv/bin/si-cli serve --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

**/etc/systemd/system/soliplex-worker@.service:**
```ini
[Unit]
Description=Soliplex Ingester Worker %i
After=network.target postgresql.service

[Service]
Type=simple
User=soliplex
Group=soliplex
WorkingDirectory=/opt/soliplex-ingester
EnvironmentFile=/etc/soliplex/config.env
Environment="WORKER_ID=worker-%i"
ExecStart=/opt/soliplex-ingester/.venv/bin/si-cli worker
Restart=on-failure
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

**Start services:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable soliplex-ingester
sudo systemctl start soliplex-ingester
sudo systemctl enable soliplex-worker@{1..3}
sudo systemctl start soliplex-worker@{1..3}
```

---

## Future Commands

Commands planned for future releases:

- `si-cli batch create` - Create batch via CLI
- `si-cli batch ingest` - Ingest documents from directory
- `si-cli batch status` - Check batch status
- `si-cli workflow retry` - Retry failed workflows
- `si-cli stats` - Display system statistics
- `si-cli clean` - Clean up old data

---

## Getting Help

**Command help:**
```bash
si-cli --help
si-cli serve --help
si-cli worker --help
```

**Report issues:**
- GitHub: https://github.com/your-repo/soliplex-ingester/issues
- Include `si-cli validate-settings` output
- Include relevant logs with `LOG_LEVEL=DEBUG`
