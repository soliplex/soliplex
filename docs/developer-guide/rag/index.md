# RAG System

Soliplex integrates with [haiku-rag](https://github.com/haiku-rag/haiku-rag) for Retrieval-Augmented Generation (RAG) capabilities, using LanceDB as the vector store.

## Overview

RAG enables agents to:

- Search document knowledge bases
- Ground responses in source material
- Provide citations with chunk references
- Generate research reports from multiple sources

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Agent     │────▶│  RAG Tools   │────▶│  LanceDB    │
│             │     │              │     │  (Vector)   │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │   haiku.rag │
                    │   Library   │
                    └─────────────┘
```

## Sections

- **[Database](database.md)** - Setting up and managing RAG databases
- **[Tools](tools.md)** - search_documents, research_report, ask_with_rich_citations
- **[Citations](citations.md)** - Citation system flow and chunk visualization

## Quick Example

### Room Configuration with RAG

```yaml
# rooms/research/room_config.yaml
id: "research"
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "rag"
    search_documents_limit: 10
    allow_mcp: true
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "rag"
    allow_mcp: true
```

### Installation-Level RAG Configuration

```yaml
# haiku.rag.yaml (referenced via haiku_rag_config_file in installation.yaml)
environment: development

embeddings:
  model:
    name: text-embedding-3-small
    provider: openai

processing:
  chunk_size: 512

search:
  context_radius: 2
```

Room-level `haiku.rag.yaml` files can override these settings.

## RAG Tools

| Tool | Purpose |
|------|---------|
| `search_documents` | Vector similarity search |
| `research_report` | Graph-based multi-document research |
| `ask_with_rich_citations` | QA with inline citations |

## Key Concepts

### Document Ingestion

Documents are added via haiku-rag CLI:

```bash
haiku-rag add-src ./documents/ --db db/rag/knowledge.lancedb
```

### Chunk Visualization

The API provides chunk visualization with page highlighting:

```
GET /api/v1/rooms/{room_id}/chunk/{chunk_id}
```

Returns page images with bounding boxes around the relevant text.

### AG-UI State for Document Filtering

Clients can filter documents via state:

```json
{
  "filter_documents": {
    "document_ids": ["doc-1", "doc-2"]
  }
}
```

When set, only the specified documents will be searched.

## Source Files

| File | Purpose |
|------|---------|
| `src/soliplex/tools.py` | RAG tool implementations |
| `src/soliplex/config.py` | RAG configuration classes |
| `example/haiku.rag.yaml` | Example haiku-rag configuration |
