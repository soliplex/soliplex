# Database Models and Schema

## Overview

Soliplex Ingester uses SQLModel (built on SQLAlchemy) for database modeling with async support. The system supports both SQLite (development) and PostgreSQL (production).

Database models defined in: `src/soliplex_ingester/lib/models.py`

## Database Connection

### Configuration

Set via environment variable:
```bash
DOC_DB_URL="sqlite+aiosqlite:///./db/documents.db"
# or
DOC_DB_URL="postgresql+asyncpg://user:pass@localhost/soliplex"
```

### Async Engine

The system uses async SQLAlchemy with connection pooling:

```python
from soliplex_ingester.lib.models import get_session

async with get_session() as session:
    # Your database operations
    result = await session.exec(select(Document))
```

## Core Models

### DocumentBatch

Represents a batch of documents ingested together.

**Table:** `documentbatch`

**Fields:**
- `id` (int, primary key) - Auto-increment batch ID
- `name` (str) - Human-readable batch name
- `source` (str) - Source system identifier
- `start_date` (datetime) - When batch processing started
- `completed_date` (datetime, nullable) - When batch completed
- `batch_params` (dict[str, str]) - JSON metadata

**Computed Fields:**
- `duration` (float) - Processing time in seconds

**Example:**
```json
{
  "id": 1,
  "name": "Q4 Financial Reports",
  "source": "sharepoint",
  "start_date": "2025-01-15T10:00:00",
  "completed_date": "2025-01-15T12:30:00",
  "batch_params": {"department": "finance"},
  "duration": 9000.0
}
```

---

### Document

Represents a unique document identified by content hash.

**Table:** `document`

**Fields:**
- `hash` (str, primary key) - SHA256 content hash (format: "sha256-...")
- `mime_type` (str) - Document MIME type
- `file_size` (int, nullable) - Size in bytes
- `doc_meta` (dict[str, str]) - JSON metadata
- `rag_id` (str, nullable) - HaikuRAG document ID
- `batch_id` (int, foreign key, nullable) - Associated batch

**Relationships:**
- Multiple `DocumentURI` records can reference the same document

**Deduplication:**
Documents are deduplicated by hash. If the same file is ingested multiple times, only one Document record exists.

**Example:**
```json
{
  "hash": "sha256-a1b2c3d4e5f6...",
  "mime_type": "application/pdf",
  "file_size": 1024000,
  "doc_meta": {
    "author": "John Doe",
    "title": "Q4 Report"
  },
  "rag_id": "doc_xyz123",
  "batch_id": 1
}
```

---

### DocumentURI

Maps source URIs to document hashes, allowing multiple URIs to reference the same document.

**Table:** `documenturi`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `doc_hash` (str, foreign key) - References `document.hash`
- `uri` (str) - Source system path/identifier
- `source` (str) - Source system name
- `version` (int) - Version number (increments on changes)
- `batch_id` (int, foreign key, nullable) - Associated batch

**Constraints:**
- Unique constraint on `(uri, source)` - One active URI per source

**Use Cases:**
- Track document locations across source systems
- Detect when a document at a URI has changed (hash mismatch)
- Support document versioning

**Example:**
```json
{
  "id": 42,
  "doc_hash": "sha256-a1b2c3d4e5f6...",
  "uri": "/sharepoint/finance/q4-report.pdf",
  "source": "sharepoint",
  "version": 2,
  "batch_id": 1
}
```

---

### DocumentURIHistory

Tracks historical versions of documents at specific URIs.

**Table:** `documenturihistory`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `doc_uri_id` (int, foreign key) - References `documenturi.id`
- `version` (int) - Version number
- `hash` (str) - Document hash at this version
- `process_date` (datetime) - When this version was processed
- `action` (str) - Action taken ("created", "updated", "deleted")
- `batch_id` (int, foreign key, nullable) - Associated batch
- `histmeta` (dict[str, str]) - JSON metadata

**Use Cases:**
- Audit trail of document changes
- Rollback to previous versions
- Compliance and record-keeping

**Example:**
```json
{
  "id": 100,
  "doc_uri_id": 42,
  "version": 1,
  "hash": "sha256-old-hash...",
  "process_date": "2025-01-10T10:00:00",
  "action": "created",
  "batch_id": 1,
  "histmeta": {"user": "importer"}
}
```

---

### DocumentBytes

Stores raw file bytes and artifacts in the database.

**Table:** `documentbytes`

**Fields:**
- `hash` (str, primary key) - Document hash
- `artifact_type` (str, primary key) - Type of artifact
- `storage_root` (str, primary key) - Storage location identifier
- `file_size` (int, nullable) - Size in bytes (auto-computed)
- `file_bytes` (bytes) - Raw binary data

**Artifact Types:**
- `document` - Raw document
- `parsed_markdown` - Extracted markdown
- `parsed_json` - Structured JSON
- `chunks` - Text chunks
- `embeddings` - Vector embeddings
- `rag` - RAG metadata

**Note:** For production, consider using file storage instead of database storage for large binaries.

**Example:**
```json
{
  "hash": "sha256-a1b2c3d4e5f6...",
  "artifact_type": "parsed_markdown",
  "storage_root": "db",
  "file_size": 50000,
  "file_bytes": b"# Document Title\n\n..."
}
```

---

## Workflow Models

### RunGroup

Groups related workflow runs together.

**Table:** `rungroup`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `name` (str, nullable) - Optional group name
- `workflow_definition_id` (str) - Workflow used
- `param_definition_id` (str) - Parameter set used
- `batch_id` (int, foreign key, nullable) - Associated batch
- `created_date` (datetime) - When group was created
- `start_date` (datetime) - When first run started
- `completed_date` (datetime, nullable) - When all runs completed
- `status` (RunStatus) - Overall group status
- `status_date` (datetime, nullable) - When status last changed
- `status_message` (str, nullable) - Status description
- `status_meta` (dict[str, str]) - JSON metadata

**Relationships:**
- Has many `WorkflowRun` records
- Has many `LifecycleHistory` records

**Example:**
```json
{
  "id": 5,
  "name": "Batch 1 Processing",
  "workflow_definition_id": "batch",
  "param_definition_id": "default",
  "batch_id": 1,
  "created_date": "2025-01-15T10:00:00",
  "start_date": "2025-01-15T10:01:00",
  "completed_date": null,
  "status": "RUNNING",
  "status_date": "2025-01-15T10:30:00",
  "status_message": "Processing documents",
  "status_meta": {}
}
```

---

### WorkflowRun

Represents a single workflow execution for one document.

**Table:** `workflowrun`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `workflow_definition_id` (str) - Workflow definition ID
- `run_group_id` (int, foreign key) - Parent group
- `batch_id` (int, foreign key) - Associated batch
- `doc_id` (str) - Document hash being processed
- `priority` (int) - Processing priority (higher = more urgent)
- `created_date` (datetime) - When run was created
- `start_date` (datetime) - When first step started
- `completed_date` (datetime, nullable) - When all steps completed
- `status` (RunStatus) - Current status
- `status_date` (datetime, nullable) - When status last changed
- `status_message` (str, nullable) - Status description
- `status_meta` (dict[str, str]) - JSON metadata
- `run_params` (dict[str, str|int|bool]) - Runtime parameters

**Computed Fields:**
- `duration` (float) - Processing time in seconds

**Relationships:**
- Has many `RunStep` records
- Belongs to `RunGroup`
- References `Document` via `doc_id`

**Example:**
```json
{
  "id": 100,
  "workflow_definition_id": "batch",
  "run_group_id": 5,
  "batch_id": 1,
  "doc_id": "sha256-a1b2c3d4e5f6...",
  "priority": 0,
  "created_date": "2025-01-15T10:00:00",
  "start_date": "2025-01-15T10:01:00",
  "completed_date": null,
  "status": "RUNNING",
  "status_date": "2025-01-15T10:05:00",
  "status_message": "Processing step 3 of 5",
  "status_meta": {},
  "run_params": {},
  "duration": null
}
```

---

### RunStep

Represents one step within a workflow run.

**Table:** `runstep`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `workflow_run_id` (int, foreign key) - Parent workflow run
- `workflow_step_number` (int) - Step sequence number
- `workflow_step_name` (str) - Step name/identifier
- `step_config_id` (int, foreign key) - Configuration used
- `step_type` (WorkflowStepType) - Type of step
- `is_last_step` (bool) - Whether this is the final step
- `created_date` (datetime) - When step was created
- `priority` (int) - Processing priority
- `start_date` (datetime, nullable) - When step started executing
- `status_date` (datetime, nullable) - When status last changed
- `completed_date` (datetime, nullable) - When step completed
- `retry` (int) - Current retry attempt (0-indexed)
- `retries` (int) - Maximum retry attempts
- `status` (RunStatus) - Current status
- `status_message` (str, nullable) - Status description
- `status_meta` (dict[str, str]) - JSON metadata
- `worker_id` (str, nullable) - Worker processing this step

**Computed Fields:**
- `duration` (float) - Execution time in seconds

**Relationships:**
- Belongs to `WorkflowRun`
- References `StepConfig`

**Example:**
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
  "status_message": "Parsing with Docling",
  "status_meta": {},
  "worker_id": "worker-abc-123",
  "duration": null
}
```

---

### StepConfig

Stores step configuration for reuse and tracking.

**Table:** `stepconfig`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `created_date` (datetime, nullable) - When config was created
- `step_type` (WorkflowStepType) - Type of step
- `config_json` (dict[str, str|int|bool], nullable) - Step parameters
- `cuml_config_json` (str, nullable) - Cumulative config from previous steps

**Use Cases:**
- Deduplicate identical configurations
- Track which configuration was used for each run
- Audit changes to processing parameters

**Example:**
```json
{
  "id": 10,
  "created_date": "2025-01-15T09:00:00",
  "step_type": "parse",
  "config_json": {
    "format": "markdown",
    "ocr_enabled": true
  },
  "cuml_config_json": "{\"validate\":{...},\"parse\":{...}}"
}
```

---

### ConfigSet

Represents a complete parameter set configuration.

**Table:** `configset`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `yaml_id` (str) - Parameter set ID from YAML
- `yaml_contents` (str) - Full YAML contents
- `created_date` (datetime, nullable) - When loaded

**Relationships:**
- Has many `ConfigSetItem` records (junction table)
- Links to multiple `StepConfig` records

**Use Cases:**
- Track which parameter sets were used
- Reproduce exact configurations
- Version control for processing parameters

---

### ConfigSetItem

Junction table linking config sets to step configs.

**Table:** `configsetitem`

**Fields:**
- `config_set_id` (int, primary key, foreign key) - References `configset.id`
- `config_id` (int, primary key, foreign key) - References `stepconfig.id`

---

### LifecycleHistory

Tracks lifecycle events during workflow execution.

**Table:** `lifecyclehistory`

**Fields:**
- `id` (int, primary key) - Auto-increment ID
- `event` (LifeCycleEvent) - Type of event
- `run_group_id` (int, foreign key) - Associated run group
- `workflow_run_id` (int, foreign key) - Associated workflow run
- `step_id` (int, nullable) - Associated step (if applicable)
- `start_date` (datetime) - When event started
- `completed_date` (datetime, nullable) - When event completed
- `status` (RunStatus) - Event status
- `status_date` (datetime, nullable) - When status changed
- `status_message` (str, nullable) - Status description
- `status_meta` (dict[str, str]) - JSON metadata

**Event Types:**
- `GROUP_START` / `GROUP_END`
- `ITEM_START` / `ITEM_END` / `ITEM_FAILED`
- `STEP_START` / `STEP_END` / `STEP_FAILED`

**Use Cases:**
- Audit trail of workflow execution
- Performance monitoring
- Debugging workflow issues

---

### WorkerCheckin

Tracks worker health and activity.

**Table:** `workercheckin`

**Fields:**
- `id` (str, primary key) - Worker identifier
- `first_checkin` (datetime) - When worker first registered
- `last_checkin` (datetime) - Most recent heartbeat

**Constraints:**
- Unique constraint on `id`

**Use Cases:**
- Monitor active workers
- Detect stale/crashed workers
- Worker load balancing

**Example:**
```json
{
  "id": "worker-abc-123",
  "first_checkin": "2025-01-15T10:00:00",
  "last_checkin": "2025-01-15T10:30:00"
}
```

---

## Enums

### RunStatus

Workflow and step status values.

```python
class RunStatus(str, Enum):
    PENDING = "PENDING"      # Not yet started
    RUNNING = "RUNNING"      # Currently executing
    COMPLETED = "COMPLETED"  # Finished successfully
    ERROR = "ERROR"          # Failed but will retry
    FAILED = "FAILED"        # Permanently failed
```

### WorkflowStepType

Types of workflow steps.

```python
class WorkflowStepType(str, Enum):
    INGEST = "ingest"
    VALIDATE = "validate"
    PARSE = "parse"
    CHUNK = "chunk"
    EMBED = "embed"
    STORE = "store"
    ENRICH = "enrich"
    ROUTE = "route"
```

### ArtifactType

Types of stored artifacts.

```python
class ArtifactType(Enum):
    DOC = "document"
    PARSED_MD = "parsed_markdown"
    PARSED_JSON = "parsed_json"
    CHUNKS = "chunks"
    EMBEDDINGS = "embeddings"
    RAG = "rag"
```

### LifeCycleEvent

Workflow lifecycle events.

```python
class LifeCycleEvent(str, Enum):
    GROUP_START = "group_start"
    GROUP_END = "group_end"
    ITEM_START = "item_start"
    ITEM_END = "item_end"
    ITEM_FAILED = "item_failed"
    STEP_START = "step_start"
    STEP_END = "step_end"
    STEP_FAILED = "step_failed"
```

---

## Relationships Diagram

```
DocumentBatch
    ↓ (1:N)
DocumentURI ──→ Document (N:1)
    ↓
DocumentURIHistory

DocumentBatch
    ↓ (1:N)
RunGroup
    ↓ (1:N)
WorkflowRun ──→ Document (N:1)
    ↓ (1:N)
RunStep ──→ StepConfig (N:1)

ConfigSet
    ↓ (N:M via ConfigSetItem)
StepConfig

RunGroup ──→ LifecycleHistory (1:N)
WorkflowRun ──→ LifecycleHistory (1:N)
```

---

## Database Initialization

### Using CLI

```bash
si-cli db-init
```

This creates tables and runs migrations.

### Using Alembic Directly

```bash
alembic upgrade head
```

### Programmatic

```python
from sqlalchemy import create_engine
from sqlmodel import SQLModel
from soliplex_ingester.lib.config import get_settings

settings = get_settings()
engine = create_engine(settings.doc_db_url)
SQLModel.metadata.create_all(engine)
```

---

## Migrations

### Location
`src/soliplex_ingester/migrations/`

### Configuration
`alembic.ini` (project root)

### Create Migration
```bash
alembic revision --autogenerate -m "description"
```

### Apply Migration
```bash
alembic upgrade head
```

### Rollback
```bash
alembic downgrade -1
```

---

## Indexes

Consider adding these indexes for production:

```sql
-- Workflow processing queries
CREATE INDEX idx_runstep_status ON runstep(status, priority DESC);
CREATE INDEX idx_workflowrun_status ON workflowrun(status, batch_id);
CREATE INDEX idx_rungroup_batch ON rungroup(batch_id);

-- Document lookups
CREATE INDEX idx_documenturi_source ON documenturi(source);
CREATE INDEX idx_document_batch ON document(batch_id);

-- Worker monitoring
CREATE INDEX idx_runstep_worker ON runstep(worker_id);
CREATE INDEX idx_workercheckin_last ON workercheckin(last_checkin);
```

---

## Backup and Maintenance

### SQLite Backup
```bash
sqlite3 db/documents.db ".backup backup.db"
```

### PostgreSQL Backup
```bash
pg_dump -h localhost -U user soliplex > backup.sql
```

### Vacuum (SQLite)
```bash
sqlite3 db/documents.db "VACUUM;"
```

### Analyze (PostgreSQL)
```bash
psql -h localhost -U user -d soliplex -c "ANALYZE;"
```

---

## Query Examples

### Find Failed Workflows
```python
from soliplex_ingester.lib.models import WorkflowRun, RunStatus, get_session
from sqlmodel import select

async with get_session() as session:
    query = select(WorkflowRun).where(WorkflowRun.status == RunStatus.FAILED)
    results = await session.exec(query)
    failed_runs = results.all()
```

### Get Batch Statistics
```python
from sqlmodel import func, select

async with get_session() as session:
    query = select(
        func.count(WorkflowRun.id).label("total"),
        WorkflowRun.status
    ).where(
        WorkflowRun.batch_id == batch_id
    ).group_by(WorkflowRun.status)

    results = await session.exec(query)
    stats = {row.status: row.total for row in results}
```

### Find Stale Workers
```python
from datetime import datetime, timedelta

cutoff = datetime.now() - timedelta(seconds=600)
query = select(WorkerCheckin).where(WorkerCheckin.last_checkin < cutoff)
stale_workers = await session.exec(query)
```
