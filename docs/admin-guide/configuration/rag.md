# RAG Configuration

Configure Retrieval-Augmented Generation (RAG) for document search and Q&A.

## Quick Start

```yaml
# rooms/research/room_config.yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
```

## Database Setup

### Creating a Database

Use the haiku-rag CLI:

```bash
# Initialize database
haiku-rag init ./db/rag/knowledge.lancedb

# Ingest documents
haiku-rag ingest ./db/rag/knowledge.lancedb ./documents/

# List documents
haiku-rag list ./db/rag/knowledge.lancedb
```

### Database Location

Databases are stored in the `db/rag/` directory:

```
installation/
└── db/
    └── rag/
        ├── knowledge.lancedb/
        └── legal.lancedb/
```

## Tool Configuration

### search_documents

Basic document search:

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"      # → db/rag/knowledge.lancedb
    search_documents_limit: 10          # Max results (default: 5)
    allow_mcp: true                     # Expose via MCP
```

### research_report

Deep research with iterative search:

```yaml
tools:
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "knowledge"
    allow_mcp: true
```

### ask_with_rich_citations

Q&A with inline citations:

```yaml
tools:
  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"
```

## Path Configuration

### Using rag_lancedb_stem

Reference a database in `db/rag/`:

```yaml
rag_lancedb_stem: "knowledge"   # → db/rag/knowledge.lancedb
```

### Using rag_lancedb_override_path

Use an explicit path:

```yaml
rag_lancedb_override_path: "/data/rag/custom.lancedb"
```

Relative paths are resolved from the config file:

```yaml
rag_lancedb_override_path: "./local.lancedb"
```

**Note:** Exactly one of `rag_lancedb_stem` or `rag_lancedb_override_path` must be specified.

## haiku-rag Configuration

Create `haiku.rag.yaml` in the installation directory:

```yaml
# haiku.rag.yaml
embedding:
  model: "text-embedding-3-small"   # OpenAI embedding model
  dimensions: 1536

search:
  context_radius: 2                 # Include N chunks before/after
  rerank: true                      # Enable reranking
  limit: 10                         # Default search limit

chunking:
  strategy: "semantic"              # Semantic chunking
  max_size: 500                     # Max chunk size (tokens)
  overlap: 50                       # Overlap between chunks
```

Reference in installation:

```yaml
# installation.yaml
haiku_rag_config_file: "./haiku.rag.yaml"
```

## Context Expansion

Include surrounding chunks for better context:

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    haiku_rag_config:
      search:
        context_radius: 2   # Include 2 chunks before/after
```

## Multiple Databases

Use different databases for different tools:

```yaml
tools:
  # General knowledge
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "general"
    search_documents_limit: 5

  # Legal documents for research
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "legal"
```

## Document Ingestion

### File Types

haiku-rag supports:
- PDF documents
- Markdown files
- Text files
- HTML files

### Ingestion Commands

```bash
# Ingest all supported files
haiku-rag ingest ./db/rag/knowledge.lancedb ./documents/

# Ingest specific patterns
haiku-rag ingest ./db/rag/knowledge.lancedb ./documents/ --pattern "*.pdf"

# Ingest with metadata
haiku-rag ingest ./db/rag/knowledge.lancedb ./documents/ \
    --metadata '{"source": "internal", "department": "engineering"}'

# Update existing documents
haiku-rag ingest ./db/rag/knowledge.lancedb ./documents/ --update
```

### Listing Documents

```bash
$ haiku-rag list ./db/rag/knowledge.lancedb

Documents in knowledge.lancedb:
- doc-1: User Guide (file:///docs/guide.pdf)
- doc-2: API Reference (file:///docs/api.pdf)
```

## API Endpoints

### List Documents

```bash
GET /api/v1/rooms/{room_id}/documents
```

Response:
```json
{
  "room_id": "research",
  "document_set": {
    "doc-1": {
      "id": "doc-1",
      "uri": "file:///docs/guide.pdf",
      "title": "User Guide"
    }
  }
}
```

### Chunk Visualization

```bash
GET /api/v1/rooms/{room_id}/chunk/{chunk_id}
```

Response:
```json
{
  "chunk_id": "chunk-abc123",
  "document_uri": "file:///docs/guide.pdf",
  "images_base_64": ["iVBORw0KGgo..."]
}
```

## Troubleshooting

### Database Not Found

Error: `RAG DB file not found: /path/to/db.lancedb`

**Solutions:**
1. Verify the database exists
2. Check `rag_lancedb_stem` matches the actual database name
3. For override paths, ensure the path is correct relative to config file

### Empty Results

**Solutions:**
1. Verify documents have been ingested: `haiku-rag list ./db/rag/knowledge.lancedb`
2. Check query relevance to document content
3. Increase `search_documents_limit`
4. Verify embedding model matches ingestion model

### Slow Search

**Solutions:**
1. Reduce `search_documents_limit`
2. Disable reranking if not needed
3. Consider database optimization

## Complete Example

```yaml
# installation.yaml
haiku_rag_config_file: "./haiku.rag.yaml"

# rooms/research/room_config.yaml
id: "research"
name: "Research Assistant"
description: "Document research with citations"

agent:
  model_name: "gpt-oss:latest"
  system_prompt: |
    You are a research assistant.
    Use the search_documents tool to find relevant information.
    Always cite your sources.

tools:
  - tool_name: "soliplex.tools.get_current_datetime"

  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    search_documents_limit: 10
    allow_mcp: true

  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"
```

## Source Code

- RAG tools: `src/soliplex/tools.py`
- Tool configuration: `src/soliplex/config.py`
- Room documents API: `src/soliplex/views/rooms.py`
