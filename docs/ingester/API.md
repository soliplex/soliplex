# Soliplex Ingester API Reference

## Base URL

All API endpoints are prefixed with `/api/v1/` unless otherwise noted.

## Authentication

Currently, the API does not implement authentication. This should be added for production deployments.

---

## Document Endpoints

### GET /api/v1/document/

Get documents by source or batch ID.

**Query Parameters:**
- `source` (string, optional) - Source identifier to filter documents
- `batch_id` (integer, optional) - Batch ID to filter documents

**Response:**
- `200 OK` - Array of DocumentURI objects
- `400 Bad Request` - Neither source nor batch_id provided

**Example:**
```bash
curl "http://localhost:8000/api/v1/document/?batch_id=1"
```

---

### POST /api/v1/document/ingest-document

Ingest a new document into the system.

**Content-Type:** `multipart/form-data`

**Form Parameters:**
- `file` (file, optional) - Document file to upload
- `input_uri` (string, optional) - URI to fetch document from
- `mime_type` (string, optional) - MIME type of the document
- `source_uri` (string, required) - Source URI/path identifier
- `source` (string, required) - Source system identifier
- `batch_id` (integer, required) - Batch ID to assign document
- `doc_meta` (string, optional) - JSON string of metadata (default: `{}`)
- `priority` (integer, optional) - Processing priority (default: 0)

**Response:**
- `201 Created` - Document ingested successfully
- `400 Bad Request` - Invalid parameters or metadata
- `500 Internal Server Error` - Processing error

**Success Response Body:**
```json
{
  "batch_id": 1,
  "document_uri": "/path/to/doc.pdf",
  "document_hash": "sha256-abc123...",
  "source": "filesystem",
  "uri_id": 42
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/document/ingest-document" \
  -F "file=@document.pdf" \
  -F "source_uri=/documents/report.pdf" \
  -F "source=filesystem" \
  -F "batch_id=1" \
  -F "doc_meta={\"author\":\"John Doe\"}"
```

---

## Batch Endpoints

### GET /api/v1/batch/

List all document batches.

**Response:**
- `200 OK` - Array of DocumentBatch objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/batch/"
```

---

### POST /api/v1/batch/

Create a new document batch.

**Content-Type:** `application/x-www-form-urlencoded`

**Form Parameters:**
- `source` (string, required) - Source system identifier
- `name` (string, required) - Human-readable batch name

**Response:**
- `201 Created` - Batch created successfully

**Response Body:**
```json
{
  "batch_id": 1
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/batch/" \
  -d "source=filesystem" \
  -d "name=Q4 Reports"
```

---

### POST /api/v1/batch/start-workflows

Start workflow processing for all documents in a batch.

**Content-Type:** `application/x-www-form-urlencoded`

**Form Parameters:**
- `batch_id` (integer, required) - Batch ID to process
- `workflow_definition_id` (string, optional) - Workflow to use (default: from config)
- `priority` (integer, optional) - Processing priority (default: 0)
- `param_id` (string, optional) - Parameter set ID (default: "default")

**Response:**
- `201 Created` - Workflows started successfully
- `404 Not Found` - Batch not found
- `500 Internal Server Error` - Processing error

**Response Body:**
```json
{
  "message": "Workflows started",
  "workflows": 10,
  "run_group": 5
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/batch/start-workflows" \
  -d "batch_id=1" \
  -d "workflow_definition_id=batch" \
  -d "param_id=default"
```

---

### GET /api/v1/batch/status

Get detailed status for a batch.

**Query Parameters:**
- `batch_id` (integer, required) - Batch ID

**Response:**
- `200 OK` - Batch status details
- `404 Not Found` - Batch not found

**Response Body:**
```json
{
  "batch": {
    "id": 1,
    "name": "Q4 Reports",
    "source": "filesystem",
    "start_date": "2025-01-15T10:00:00",
    "completed_date": null
  },
  "document_count": 10,
  "workflow_count": {
    "COMPLETED": 7,
    "RUNNING": 2,
    "PENDING": 1
  },
  "workflows": [...],
  "parsed": 7,
  "remaining": 3
}
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/batch/status?batch_id=1"
```

---

## Workflow Endpoints

### GET /api/v1/workflow/

Get workflow runs, optionally filtered by batch ID.

**Query Parameters:**
- `batch_id` (integer, optional) - Filter by batch ID

**Response:**
- `200 OK` - Array of WorkflowRun objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/?batch_id=1"
```

---

### GET /api/v1/workflow/by-status

Get workflow runs filtered by status.

**Query Parameters:**
- `status` (enum, required) - One of: PENDING, RUNNING, COMPLETED, ERROR, FAILED
- `batch_id` (integer, optional) - Filter by batch ID

**Response:**
- `200 OK` - Array of WorkflowRun objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/by-status?status=FAILED"
```

---

### GET /api/v1/workflow/definitions

List all available workflow definitions.

**Response:**
- `200 OK` - Array of workflow definition summaries

**Response Body:**
```json
[
  {
    "id": "batch",
    "name": "Batch Workflow"
  },
  {
    "id": "interactive",
    "name": "Interactive Workflow"
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/definitions"
```

---

### GET /api/v1/workflow/definitions/{workflow_id}

Get detailed workflow definition by ID.

**Path Parameters:**
- `workflow_id` (string, required) - Workflow definition ID

**Response:**
- `200 OK` - Complete WorkflowDefinition object
- `404 Not Found` - Workflow definition not found

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/definitions/batch"
```

---

### GET /api/v1/workflow/param-sets

List all available parameter sets.

**Response:**
- `200 OK` - Array of parameter set summaries

**Response Body:**
```json
[
  {
    "id": "default",
    "name": "Default Parameters"
  },
  {
    "id": "high_quality",
    "name": "High Quality Processing"
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/param-sets"
```

---

### GET /api/v1/workflow/param-sets/{set_id}

Get parameter set by ID.

**Path Parameters:**
- `set_id` (string, required) - Parameter set ID

**Response:**
- `200 OK` - Complete WorkflowParams object
- `404 Not Found` - Parameter set not found

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/param-sets/default"
```

---

### GET /api/v1/workflow/param-sets/target/{target}

Get parameter sets that target a specific LanceDB directory.

**Path Parameters:**
- `target` (string, required) - LanceDB data directory path

**Response:**
- `200 OK` - Array of matching WorkflowParams objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/param-sets/target/lancedb"
```

---

### GET /api/v1/workflow/steps

Get workflow steps filtered by status.

**Query Parameters:**
- `status` (enum, required) - One of: PENDING, RUNNING, COMPLETED, ERROR, FAILED

**Response:**
- `200 OK` - Array of RunStep objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/steps?status=RUNNING"
```

---

### GET /api/v1/workflow/run-groups

Get workflow run groups, optionally filtered by batch ID.

**Query Parameters:**
- `batch_id` (integer, optional) - Filter by batch ID

**Response:**
- `200 OK` - Array of RunGroup objects
- `500 Internal Server Error` - Processing error

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/run-groups?batch_id=1"
```

---

### GET /api/v1/workflow/run-groups/{run_group_id}

Get specific run group by ID.

**Path Parameters:**
- `run_group_id` (integer, required) - Run group ID

**Response:**
- `200 OK` - RunGroup object
- `500 Internal Server Error` - Processing error

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/run-groups/5"
```

---

### GET /api/v1/workflow/run-groups/{run_group_id}/stats

Get statistics for a run group.

**Path Parameters:**
- `run_group_id` (integer, required) - Run group ID

**Response:**
- `200 OK` - Statistics object with status counts and durations
- `500 Internal Server Error` - Processing error

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/run-groups/5/stats"
```

---

### GET /api/v1/workflow/runs

Get workflow runs for a batch.

**Query Parameters:**
- `batch_id` (integer, required) - Batch ID

**Response:**
- `200 OK` - Array of WorkflowRun objects

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/runs?batch_id=1"
```

---

### GET /api/v1/workflow/runs/{workflow_id}

Get specific workflow run by ID, including steps.

**Path Parameters:**
- `workflow_id` (integer, required) - Workflow run ID

**Response:**
- `200 OK` - WorkflowRun object with steps array

**Example:**
```bash
curl "http://localhost:8000/api/v1/workflow/runs/42"
```

---

### POST /api/v1/workflow/

Start a new workflow run for a single document.

**Content-Type:** `application/x-www-form-urlencoded`

**Form Parameters:**
- `doc_id` (string, required) - Document hash to process
- `workflow_definition_id` (string, optional) - Workflow to use
- `param_id` (string, optional) - Parameter set ID
- `priority` (integer, optional) - Processing priority (default: 0)

**Response:**
- `201 Created` - Workflow run created
- `500 Internal Server Error` - Processing error

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/" \
  -d "doc_id=sha256-abc123..." \
  -d "workflow_definition_id=batch" \
  -d "priority=10"
```

---

### POST /api/v1/workflow/retry

Retry failed workflow steps for a run group.

**Content-Type:** `application/x-www-form-urlencoded`

**Form Parameters:**
- `run_group_id` (integer, required) - Run group ID to retry

**Response:**
- `201 Created` - Failed steps reset successfully
- `500 Internal Server Error` - Processing error

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/retry" \
  -d "run_group_id=5"
```

---

## Source Status Endpoint

### POST /api/v1/source-status

Check document status for a source system.

**Content-Type:** `application/x-www-form-urlencoded`

**Form Parameters:**
- `source` (string, required) - Source system identifier
- `hashes` (string, required) - JSON object mapping URIs to hashes

**Response:**
- `200 OK` - Status object indicating new/changed/deleted documents

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/source-status" \
  -d "source=filesystem" \
  -d 'hashes={"file1.pdf":"sha256-abc","file2.pdf":"sha256-def"}'
```

---

## Data Models

### DocumentBatch
```json
{
  "id": 1,
  "name": "Q4 Reports",
  "source": "filesystem",
  "start_date": "2025-01-15T10:00:00",
  "completed_date": null,
  "batch_params": {},
  "duration": null
}
```

### Document
```json
{
  "hash": "sha256-abc123...",
  "mime_type": "application/pdf",
  "file_size": 1024000,
  "doc_meta": {"author": "John Doe"},
  "rag_id": "doc_123",
  "batch_id": 1
}
```

### DocumentURI
```json
{
  "id": 42,
  "doc_hash": "sha256-abc123...",
  "uri": "/documents/report.pdf",
  "source": "filesystem",
  "version": 1,
  "batch_id": 1
}
```

### WorkflowRun
```json
{
  "id": 100,
  "workflow_definition_id": "batch",
  "run_group_id": 5,
  "batch_id": 1,
  "doc_id": "sha256-abc123...",
  "priority": 0,
  "created_date": "2025-01-15T10:00:00",
  "start_date": "2025-01-15T10:01:00",
  "completed_date": null,
  "status": "RUNNING",
  "status_date": "2025-01-15T10:05:00",
  "status_message": null,
  "status_meta": {},
  "run_params": {},
  "duration": null
}
```

### RunStep
```json
{
  "id": 500,
  "workflow_run_id": 100,
  "workflow_step_number": 2,
  "workflow_step_name": "parse",
  "step_config_id": 10,
  "step_type": "parse",
  "is_last_step": false,
  "created_date": "2025-01-15T10:01:00",
  "priority": 0,
  "start_date": "2025-01-15T10:02:00",
  "status_date": "2025-01-15T10:05:00",
  "completed_date": null,
  "retry": 0,
  "retries": 3,
  "status": "RUNNING",
  "status_message": null,
  "status_meta": {},
  "worker_id": "worker-abc-123",
  "duration": null
}
```

### RunStatus Enum
- `PENDING` - Not yet started
- `RUNNING` - Currently executing
- `COMPLETED` - Finished successfully
- `ERROR` - Failed but will retry
- `FAILED` - Permanently failed after all retries

### WorkflowStepType Enum
- `ingest` - Load document
- `validate` - Validate document
- `parse` - Extract text/structure
- `chunk` - Split into chunks
- `embed` - Generate embeddings
- `store` - Save to RAG system
- `enrich` - Add metadata
- `route` - Conditional routing

---

## Error Responses

All error responses follow this format:

```json
{
  "error": "Error message describing what went wrong",
  "status_code": 400
}
```

Common HTTP status codes:
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server-side error

---

## Rate Limiting

Currently, no rate limiting is implemented. For production deployments, consider adding rate limiting middleware.

---

## OpenAPI/Swagger Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
