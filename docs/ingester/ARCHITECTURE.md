# Soliplex Ingester Architecture

## Overview

Soliplex Ingester is a document processing and RAG (Retrieval-Augmented Generation) ingestion system designed to handle large-scale document workflows. It provides a FastAPI-based REST API, workflow orchestration, and integration with document parsing and embedding services.

## System Components

### 1. FastAPI Server

The server provides REST API endpoints for document and workflow management:

- **Document Routes** (`/api/v1/document/*`) - Document upload, retrieval, and management
- **Batch Routes** (`/api/v1/batch/*`) - Batch processing operations
- **Workflow Routes** (`/api/v1/workflow/*`) - Workflow execution and monitoring
- **Stats Routes** (`/api/v1/stats/*`) - System statistics and metrics

Server entry point: `src/soliplex_ingester/server/__init__.py:30`

### 2. Workflow System

The workflow system orchestrates multi-step document processing pipelines:

```
Document → Validate → Parse → Chunk → Embed → Store
```

**Workflow Components:**

- **WorkflowDefinition** - Defines the steps and lifecycle events for a workflow
- **WorkflowRun** - Represents a single execution instance for one document
- **RunGroup** - Groups multiple workflow runs together
- **RunStep** - Individual step execution within a workflow run

**Step Types:**
- `INGEST` - Load document into system
- `VALIDATE` - Validate document format and content
- `PARSE` - Extract text and structure from document
- `CHUNK` - Split document into semantic chunks
- `EMBED` - Generate vector embeddings
- `STORE` - Save to RAG system (LanceDB + HaikuRAG)
- `ENRICH` - Add metadata or additional processing
- `ROUTE` - Conditional routing logic

Implementation: `src/soliplex_ingester/lib/wf/`

### 3. Worker System

Async workers process workflow steps concurrently:

- Workers poll for pending workflow steps
- Configurable concurrency levels for different operations
- Automatic retry logic with configurable retry counts
- Health check/heartbeat system via `WorkerCheckin`

Worker implementation: `src/soliplex_ingester/lib/wf/runner.py`

### 4. Storage Layer

**Database:**
- SQLModel + SQLAlchemy with async support
- Supports SQLite (dev) and PostgreSQL (production)
- Alembic for migrations

**File Storage:**
- Configurable backends (filesystem, S3-compatible via OpenDAL)
- Separate storage locations for different artifact types:
  - Raw documents
  - Parsed markdown
  - Parsed JSON
  - Chunks
  - Embeddings

**Vector Storage:**
- LanceDB for vector embeddings
- HaikuRAG client for retrieval operations

### 5. Document Processing Pipeline

```mermaid
graph LR
    A[Upload Document] --> B[Create DocumentURI]
    B --> C[Hash & Store as Document]
    C --> D[Queue Workflow Run]
    D --> E[Validate Step]
    E --> F[Parse with Docling]
    F --> G[Chunk Text]
    G --> H[Generate Embeddings]
    H --> I[Store in LanceDB]
    I --> J[Update RAG Index]
```

### 6. External Services

**Docling Server:**
- Document parsing service
- Extracts text, structure, and metadata
- Configurable via `DOCLING_SERVER_URL`

**HaikuRAG:**
- RAG backend for document retrieval
- Vector search and document management
- Optional (controlled by `DO_RAG` setting)

## Data Flow

### Document Ingestion Flow

1. **Upload** - Client uploads document via `/api/v1/document/upload`
2. **Hash & Dedupe** - System computes SHA256 hash, checks for duplicates
3. **Create URI** - Maps source URI to document hash
4. **Batch Assignment** - Associates document with processing batch
5. **Workflow Creation** - Creates WorkflowRun and RunSteps
6. **Worker Processing** - Workers pick up and execute steps
7. **Status Updates** - Database tracks step and run status
8. **Completion** - Document marked complete when all steps succeed

### Workflow Execution Flow

1. **Worker Startup** - Worker registers and starts polling
2. **Step Selection** - Worker queries for PENDING steps with `FOR UPDATE` lock
3. **Status Transition** - PENDING → RUNNING → COMPLETED/ERROR/FAILED
4. **Step Execution** - Calls registered handler method
5. **Artifact Storage** - Saves intermediate results
6. **Retry Logic** - Automatic retry on ERROR status
7. **Run Completion** - Aggregates step status to run status
8. **Group Completion** - Aggregates run status to group status

## Configuration

Configuration via environment variables with `pydantic-settings`:

- Database connection
- File storage paths
- Worker concurrency settings
- External service URLs
- Workflow and parameter directories

See `src/soliplex_ingester/lib/config.py:15` for full configuration schema.

## Scalability

**Horizontal Scaling:**
- Multiple workers can run concurrently
- Database row-level locking prevents duplicate processing
- Stateless API servers can be load balanced

**Vertical Scaling:**
- Configurable concurrency per worker
- Batch size controls for embedding operations
- Connection pooling for database access

**Workflow Parallelism:**
- Multiple workflows can process simultaneously
- Steps within a workflow run sequentially
- Different documents process independently

## Technology Stack

- **Web Framework:** FastAPI 0.120+
- **Database ORM:** SQLModel 0.0.27+
- **Async Runtime:** asyncio
- **CLI:** Typer
- **Document Parsing:** Docling
- **Vector DB:** LanceDB 0.25+
- **RAG:** HaikuRAG
- **Storage:** OpenDAL (multi-backend support)

## Extension Points

**Custom Workflow Steps:**
Define custom step handlers by:
1. Creating a new async function matching the EventHandler signature
2. Registering in workflow YAML configuration
3. Implementing retry logic and error handling

**Custom Storage Backends:**
Configure via `FILE_STORE_TARGET` environment variable and OpenDAL configuration.

**Custom Lifecycle Events:**
Add event handlers in workflow configuration to respond to:
- `GROUP_START` / `GROUP_END`
- `ITEM_START` / `ITEM_END`
- `STEP_START` / `STEP_END`
- `ITEM_FAILED` / `STEP_FAILED`

## Monitoring

**Database Tables:**
- `workflowrun` - Track run status and duration
- `runstep` - Monitor individual step execution
- `workcheckin` - Worker health and activity
- `lifecyclehistory` - Audit trail of events

**Metrics Available:**
- Document processing throughput
- Step success/failure rates
- Worker utilization
- Processing durations
- Batch completion times

Access via `/api/v1/stats/*` endpoints.
