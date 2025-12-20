# RAG Database

Soliplex uses [haiku-rag](https://github.com/soliplex/haiku-rag) with LanceDB for vector storage and document retrieval.

## Overview

```
Documents → haiku-rag CLI → LanceDB (.lancedb) → search_documents tool → Agent
```

## Database Structure

RAG databases are stored as LanceDB directories:

```
installation/
├── db/
│   └── rag/
│       ├── knowledge.lancedb/     # Database for "knowledge" stem
│       │   ├── document.lance/
│       │   ├── chunk.lance/
│       │   └── data/
│       └── legal.lancedb/         # Database for "legal" stem
└── rooms/
    └── custom/
        └── custom.lancedb/        # Override path database
```

## Database Creation

Use the haiku-rag CLI to create and populate databases:

```bash
# Create a new database
haiku-rag init --db ./db/rag/knowledge.lancedb

# Add documents from a directory
haiku-rag add-src ./documents/ --db ./db/rag/knowledge.lancedb

# Add a single file with title
haiku-rag add-src ./docs/guide.pdf --db ./db/rag/knowledge.lancedb --title "User Guide"

# Add documents with metadata
haiku-rag add-src ./documents/ --db ./db/rag/knowledge.lancedb \
    --meta source=internal --meta department=engineering
```

## Path Resolution

Soliplex supports two ways to specify database paths:

### Using rag_lancedb_stem

References a database in the `RAG_LANCE_DB_PATH` directory:

```yaml
# rooms/research/room_config.yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"   # → {RAG_LANCE_DB_PATH}/knowledge.lancedb
```

The path is resolved as:
```
{RAG_LANCE_DB_PATH}/{stem}.lancedb
```

Where `RAG_LANCE_DB_PATH` is set in your installation's environment configuration (typically `db/rag/`).

### Using rag_lancedb_override_path

Specifies an absolute or relative path:

```yaml
# rooms/custom/room_config.yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_override_path: "./custom.lancedb"  # Relative to room_config.yaml
```

Relative paths are resolved from the configuration file's directory.

**Note**: You must specify exactly one of `rag_lancedb_stem` or `rag_lancedb_override_path`.

## Configuration Options

### Search Documents Tool

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    search_documents_limit: 10        # Max results to return (default: 5)
    allow_mcp: true                   # Expose via MCP server
```

### Research Report Tool

```yaml
tools:
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "knowledge"
    allow_mcp: true
```

### Ask With Rich Citations Tool

```yaml
tools:
  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"
```

## haiku-rag Configuration

Customize haiku-rag behavior with a `haiku.rag.yaml` file in the room directory:

```yaml
# rooms/research/haiku.rag.yaml
search:
  context_radius: 2           # Include N chunks before/after match
  rerank: true                # Enable reranking
embedding:
  model: "text-embedding-3-small"
```

The room-level config merges with the installation's base `haiku_rag_config`. If no room-level file exists, the installation config is used directly.

## Document Management

### Listing Documents

The API provides endpoints to list documents in a room's RAG database:

```bash
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/v1/rooms/{room_id}/documents
```

Response:
```json
{
  "room_id": "research",
  "document_set": {
    "doc-1": {
      "id": "doc-1",
      "uri": "file:///docs/guide.pdf",
      "title": "User Guide",
      "metadata": {"source": "internal", "department": "engineering"},
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

Note: `uri` and `title` may be null.

### Chunk Visualization

Retrieve visual representations of document chunks:

```bash
curl -H "Authorization: Bearer $TOKEN" \
    http://localhost:8000/api/v1/rooms/{room_id}/chunk/{chunk_id}
```

Response:
```json
{
  "chunk_id": "chunk-abc123",
  "document_uri": "file:///docs/guide.pdf",
  "images_base_64": ["iVBORw0KGgo..."]
}
```

Note: `document_uri` may be null.

## Context Expansion

When `context_radius` is set in `haiku.rag.yaml`, search results include surrounding chunks:

```yaml
# rooms/research/haiku.rag.yaml
search:
  context_radius: 2   # Include 2 chunks before and after
```

This provides more context for the LLM to generate accurate responses.

## Multiple Databases

Rooms can use different databases for different tools:

```yaml
tools:
  # General knowledge search
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "general"

  # Legal documents for research
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "legal"
```

## Troubleshooting

### Database Not Found

Error: `RAG DB file not found: /path/to/db.lancedb`

- Verify the database exists at the specified path
- Check that `rag_lancedb_stem` matches the actual database name
- For override paths, ensure the path is correct relative to the config file

### Empty Search Results

- Verify documents have been added with `haiku-rag list --db ./db/rag/knowledge.lancedb`
- Check that the query matches document content
- Increase `search_documents_limit` to see more results

## Source Code

- Database path resolution: `src/soliplex/config.py:416-442`
- Tool configurations: `src/soliplex/config.py:455-558`
- Room documents API: `src/soliplex/views/rooms.py:121-167`
