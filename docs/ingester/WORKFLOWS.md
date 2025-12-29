# Workflow System Documentation

## Overview

The Soliplex Ingester workflow system orchestrates multi-step document processing pipelines. Each document flows through a series of configurable steps, with automatic retry logic, status tracking, and parallel processing support.

## Core Concepts

### Workflow Definition

A **WorkflowDefinition** specifies the processing pipeline for documents. It defines:
- Unique ID and name
- Item steps (processing stages)
- Lifecycle event handlers
- Retry policies

Defined in YAML files at: `config/workflows/*.yaml`

### Workflow Run

A **WorkflowRun** represents a single execution of a workflow for one document. It tracks:
- Status (PENDING → RUNNING → COMPLETED/FAILED)
- Start and completion timestamps
- Priority level
- Associated document and batch

### Run Group

A **RunGroup** aggregates multiple workflow runs that were started together (e.g., all documents in a batch). It provides:
- Group-level status tracking
- Aggregate statistics
- Batch coordination

### Run Step

A **RunStep** is one stage of execution within a workflow run. Each step:
- Executes a specific handler method
- Has its own status and retry counter
- Produces artifacts stored in the file system
- Updates database on completion/failure

## Workflow Step Types

The system supports these predefined step types:

### INGEST
- **Purpose:** Load raw document into the system
- **Input:** File bytes or URI
- **Output:** Document stored in file system
- **Artifact:** `ArtifactType.DOC`

### VALIDATE
- **Purpose:** Check document format and readability
- **Input:** Raw document
- **Output:** Validation result
- **Handler:** `soliplex_ingester.lib.workflow.validate_document`

### PARSE
- **Purpose:** Extract text, structure, and metadata
- **Input:** Raw document
- **Output:** Markdown and JSON representations
- **Artifacts:** `ArtifactType.PARSED_MD`, `ArtifactType.PARSED_JSON`
- **Handler:** `soliplex_ingester.lib.workflow.parse_document`
- **Service:** Docling server

### CHUNK
- **Purpose:** Split document into semantic chunks
- **Input:** Parsed markdown
- **Output:** Array of text chunks
- **Artifact:** `ArtifactType.CHUNKS`
- **Handler:** `soliplex_ingester.lib.workflow.chunk_document`

### EMBED
- **Purpose:** Generate vector embeddings for chunks
- **Input:** Text chunks
- **Output:** Embedding vectors
- **Artifact:** `ArtifactType.EMBEDDINGS`
- **Handler:** `soliplex_ingester.lib.workflow.embed_document`

### STORE
- **Purpose:** Save embeddings to RAG system
- **Input:** Embeddings
- **Output:** RAG document ID
- **Artifact:** `ArtifactType.RAG`
- **Handler:** `soliplex_ingester.lib.workflow.save_to_rag`
- **Backend:** LanceDB + HaikuRAG

### ENRICH
- **Purpose:** Add metadata or perform additional processing
- **Input:** Document and existing artifacts
- **Output:** Enhanced metadata
- **Handler:** Custom (user-defined)

### ROUTE
- **Purpose:** Conditional logic for workflow branching
- **Input:** Document state
- **Output:** Routing decision
- **Handler:** Custom (user-defined)

## Workflow Configuration

### Workflow Definition YAML

Example: `config/workflows/batch.yaml`

```yaml
id: batch
name: Batch Workflow
meta: {}

item_steps:
  validate:
    name: docling validate
    retries: 3
    method: soliplex_ingester.lib.workflow.validate_document
    parameters: {}

  parse:
    name: docling parse
    retries: 3
    method: soliplex_ingester.lib.workflow.parse_document
    parameters: {}

  chunk:
    name: docling chunk
    retries: 3
    method: soliplex_ingester.lib.workflow.chunk_document
    parameters: {}

  embed:
    name: embeddings
    retries: 3
    method: soliplex_ingester.lib.workflow.embed_document
    parameters: {}

  store:
    name: save to rag
    retries: 3
    method: soliplex_ingester.lib.workflow.save_to_rag
    parameters: {}

lifecycle_events:
  group_start:
    - name: log group start
      method: soliplex_ingester.lib.workflow.log_event
      retries: 1
      parameters:
        message: "Starting workflow group"
```

### Parameter Set YAML

Parameters control step behavior without changing the workflow definition.

Example: `config/params/default.yaml`

```yaml
id: default
name: Default Parameters
meta:
  description: Standard processing parameters

config:
  parse:
    format: markdown
    ocr_enabled: true

  chunk:
    chunk_size: 512
    chunk_overlap: 50
    separator: "\n\n"

  embed:
    model: text-embedding-3-small
    batch_size: 1000

  store:
    data_dir: lancedb
    collection_name: documents
```

## Workflow Execution

### Creating Workflows

**For a Batch:**
```bash
curl -X POST "http://localhost:8000/api/v1/batch/start-workflows" \
  -d "batch_id=1" \
  -d "workflow_definition_id=batch" \
  -d "param_id=default"
```

**For a Single Document:**
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/" \
  -d "doc_id=sha256-abc123..." \
  -d "workflow_definition_id=batch"
```

### Worker Processing

Workers continuously poll for pending steps:

1. Query database for PENDING steps with highest priority
2. Lock step with `FOR UPDATE` to prevent duplicate processing
3. Transition status: PENDING → RUNNING
4. Execute handler method
5. Store artifacts in file system
6. Update step status: RUNNING → COMPLETED/ERROR
7. Update parent run status based on step results
8. Repeat

Start a worker:
```bash
si-cli worker
```

Or via server (starts worker automatically):
```bash
si-cli serve
```

### Status Transitions

**Valid Transitions:**
- PENDING → RUNNING
- RUNNING → COMPLETED
- RUNNING → ERROR
- ERROR → RUNNING (retry)
- ERROR → FAILED (after max retries)

**Invalid Transitions:**
- COMPLETED → RUNNING (no re-running completed steps)
- FAILED → RUNNING (use retry endpoint instead)

## Lifecycle Events

Lifecycle events allow custom logic at key points:

### Event Types

- `GROUP_START` - Run group begins
- `GROUP_END` - Run group completes
- `ITEM_START` - Workflow run begins
- `ITEM_END` - Workflow run completes
- `ITEM_FAILED` - Workflow run fails
- `STEP_START` - Step begins
- `STEP_END` - Step completes
- `STEP_FAILED` - Step fails

### Event Handler Example

```yaml
lifecycle_events:
  item_failed:
    - name: notify on failure
      method: myapp.notifications.send_alert
      retries: 3
      parameters:
        channel: "#alerts"
        message: "Document processing failed"
```

## Retry Logic

### Automatic Retries

Steps automatically retry on error:
- Configurable retry count per step
- Exponential backoff (implementation dependent)
- Status: ERROR during retries, FAILED when exhausted

### Manual Retry

Reset failed steps for a run group:
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/retry" \
  -d "run_group_id=5"
```

This resets all FAILED steps to PENDING for re-processing.

## Monitoring

### Check Run Group Status

```bash
curl "http://localhost:8000/api/v1/workflow/run-groups/5/stats"
```

Returns:
```json
{
  "total_runs": 100,
  "completed": 95,
  "running": 3,
  "pending": 0,
  "failed": 2,
  "average_duration": 45.3,
  "group_status": "RUNNING"
}
```

### Check Specific Workflow Run

```bash
curl "http://localhost:8000/api/v1/workflow/runs/42"
```

Returns workflow run with all steps and their status.

### Query Steps by Status

```bash
curl "http://localhost:8000/api/v1/workflow/steps?status=FAILED"
```

Lists all failed steps for investigation.

## Custom Step Handlers

### Handler Signature

```python
async def custom_handler(
    run_step: RunStep,
    workflow_run: WorkflowRun,
    doc: Document,
    step_params: dict[str, Any]
) -> dict[str, Any]:
    """
    Custom workflow step handler.

    Args:
        run_step: Current step being executed
        workflow_run: Parent workflow run
        doc: Document being processed
        step_params: Parameters from config

    Returns:
        Dictionary with result metadata

    Raises:
        Exception: On failure (will trigger retry)
    """
    # Your processing logic here
    result_data = await process_document(doc)

    # Store artifacts if needed
    await store_artifact(
        doc.hash,
        ArtifactType.CUSTOM,
        result_data
    )

    return {"status": "success", "items_processed": 42}
```

### Registering Custom Handler

1. **Define the handler** in your Python module
2. **Add to workflow YAML:**
   ```yaml
   item_steps:
     custom_step:
       name: My Custom Step
       retries: 2
       method: myapp.handlers.custom_handler
       parameters:
         param1: value1
   ```
3. **Ensure module is importable** by the worker process

## Worker Configuration

### Environment Variables

- `INGEST_WORKER_CONCURRENCY` - Max concurrent workflow steps (default: 10)
- `INGEST_QUEUE_CONCURRENCY` - Max concurrent queue operations (default: 20)
- `DOCLING_CONCURRENCY` - Max concurrent Docling requests (default: 3)
- `WORKER_TASK_COUNT` - Steps to fetch per query (default: 5)
- `WORKER_CHECKIN_INTERVAL` - Heartbeat interval in seconds (default: 120)
- `WORKER_CHECKIN_TIMEOUT` - Worker timeout in seconds (default: 600)

### Multiple Workers

Run multiple workers for increased throughput:

```bash
# Terminal 1
si-cli worker

# Terminal 2
si-cli worker

# Terminal 3
si-cli worker
```

Database locking ensures no duplicate processing.

## Artifact Storage

### Storage Paths

Artifacts are stored under `FILE_STORE_DIR` with subdirectories:

- `document_store_dir/` - Raw documents
- `parsed_markdown_store_dir/` - Parsed markdown
- `parsed_json_store_dir/` - Parsed JSON
- `chunks_store_dir/` - Text chunks
- `embeddings_store_dir/` - Embedding vectors

### File Naming

Files are named by document hash:
```
{storage_dir}/{hash}
```

Example:
```
file_store/markdown/sha256-abc123def456...
```

### Storage Backends

Configure via `FILE_STORE_TARGET`:
- `fs` - Local filesystem (default)
- `s3` - S3-compatible storage (via OpenDAL)
- Other OpenDAL-supported backends

## Best Practices

### Workflow Design

1. **Keep steps atomic** - Each step should do one thing well
2. **Make steps idempotent** - Re-running a step should be safe
3. **Use appropriate retries** - 3 retries for transient errors, 1 for validation
4. **Store intermediate results** - Save artifacts for debugging and recovery

### Error Handling

1. **Raise exceptions** for retriable errors
2. **Log context** before raising (worker ID, document hash, step)
3. **Use status_meta** to store error details
4. **Monitor failed steps** and investigate patterns

### Performance

1. **Tune concurrency** based on available resources
2. **Batch operations** where possible (embeddings)
3. **Use priorities** for urgent documents
4. **Monitor worker health** via heartbeat table

### Testing

1. **Test handlers independently** with mock data
2. **Use small batches** for integration testing
3. **Verify artifact storage** after each step
4. **Test retry logic** by simulating failures

## Troubleshooting

### Stuck Workflows

**Symptom:** Workflows remain in RUNNING status indefinitely

**Solution:**
1. Check worker logs for exceptions
2. Query stuck steps: `SELECT * FROM runstep WHERE status='RUNNING' AND start_date < NOW() - INTERVAL '1 hour'`
3. Check worker heartbeat: `SELECT * FROM workercheckin`
4. Restart workers if stale

### Failed Steps

**Symptom:** Steps transition to FAILED status

**Solution:**
1. Query step details: `GET /api/v1/workflow/steps?status=FAILED`
2. Check `status_message` and `status_meta` for error info
3. Fix underlying issue (service down, invalid config, etc.)
4. Retry: `POST /api/v1/workflow/retry`

### Slow Processing

**Symptom:** Low throughput, long durations

**Solution:**
1. Check Docling server response time
2. Increase `INGEST_WORKER_CONCURRENCY`
3. Run multiple workers
4. Verify database performance (add indexes if needed)
5. Check network latency to external services

### Duplicate Processing

**Symptom:** Same document processed multiple times

**Solution:**
1. Verify database locking is working (`FOR UPDATE`)
2. Check for unique constraint violations in logs
3. Ensure workers use distinct worker IDs
4. Verify step status transitions are atomic
