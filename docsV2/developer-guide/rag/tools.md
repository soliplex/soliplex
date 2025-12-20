# RAG Tools

Soliplex provides three RAG tools with increasing levels of sophistication.

## Tool Comparison

| Tool | Purpose | Output | MCP Compatible |
|------|---------|--------|----------------|
| `search_documents` | Vector similarity search | Raw search results | Yes |
| `research_report` | Graph-based deep research | Structured report | Yes |
| `ask_with_rich_citations` | QA with inline citations | Answer string with citations | No |

## search_documents

Simple vector similarity search against the RAG database.

### Implementation

```python
async def search_documents(
    query: str,
    tool_config: config.SearchDocumentsToolConfig = None,
) -> list[SearchResult]:
    """Search the document knowledge base for relevant information."""
    async with rag_client.HaikuRAG(
        db_path=tool_config.rag_lancedb_path,
        config=hr_config,
    ) as rag:
        results = await rag.search(
            query,
            limit=tool_config.search_documents_limit,
        )

        if hr_config.search.context_radius > 0:
            results = await rag.expand_context(results)

        return results
```

### Configuration

```yaml
tools:
  - tool_name: "soliplex.tools.search_documents"
    rag_lancedb_stem: "knowledge"
    search_documents_limit: 10    # Max results (default: 5)
    allow_mcp: true               # Expose via MCP
    haiku_rag_config:
      search:
        context_radius: 2         # Include surrounding chunks
```

### Response Format

Returns a list of `SearchResult` objects:

```python
class SearchResult:
    chunk_id: str
    document_id: str
    document_uri: str
    content: str
    score: float
    metadata: dict
```

### Use Case

Best for simple retrieval where the agent needs raw document chunks to formulate its own response.

---

## research_report

Performs deep research using a graph-based workflow that iteratively refines the search.

### Implementation

```python
async def research_report(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> rag_research.ResearchReport:
    """Perform research against document knowledge base."""
    hr_config = tool_config.haiku_rag_config
    graph = rag_research_graph.build_research_graph(hr_config)

    async with rag_client.HaikuRAG(...) as client:
        context = rag_research.ResearchContext(
            original_question=question,
        )
        state = rag_research_state.ResearchState.from_config(
            context=context,
            config=hr_config,
        )
        graph_deps = rag_research_state.ResearchDeps(
            client=client,
            agui_emitter=ctx.deps.agui_emitter,
        )
        return await graph.run(state=state, deps=graph_deps)
```

### Configuration

```yaml
tools:
  - tool_name: "soliplex.tools.research_report"
    rag_lancedb_stem: "knowledge"
    allow_mcp: true
```

### Response Format

Returns a structured `ResearchReport`:

```python
class ResearchReport:
    question: str
    answer: str
    sources: list[Source]
    confidence: float
    follow_up_questions: list[str]
```

### Progress Events

The research workflow emits progress events via the AG-UI emitter:

```
event: CUSTOM
data: {"type": "RESEARCH_PROGRESS", "step": "Analyzing question..."}

event: CUSTOM
data: {"type": "RESEARCH_PROGRESS", "step": "Searching documents..."}

event: CUSTOM
data: {"type": "RESEARCH_PROGRESS", "step": "Synthesizing answer..."}
```

### Use Case

Best for complex questions requiring multiple search iterations and source synthesis.

---

## ask_with_rich_citations

Answers questions with inline citations, tracking question history in AG-UI state.

### Implementation

```python
async def ask_with_rich_citations(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> str:
    """Answer questions using document knowledge base with citations."""
    agui_emitter = ctx.deps.agui_emitter
    agui_state = AWRC_AGUI_State.model_validate(ctx.deps.state)

    # Apply document filter if set
    search_filter = None
    documents = agui_state.filter_documents
    if documents and documents.document_ids:
        quoted = [f"'{id}'" for id in documents.document_ids]
        search_filter = f"id IN ({', '.join(quoted)})"

    async with rag_client.HaikuRAG(...) as rag:
        response, citations = await rag.ask(question, filter=search_filter)

        # Track in ask_history
        agui_state.ask_history.questions.append(
            QuestionResponseCitations(
                question=question,
                response=response,
                citations=citations,
            )
        )
        agui_emitter.update_state(agui_state)

        return response
```

### Configuration

```yaml
tools:
  - tool_name: "soliplex.tools.ask_with_rich_citations"
    rag_lancedb_stem: "knowledge"
```

**Note**: This tool cannot be exposed via MCP because it requires FastAPI context.

### Document Filtering

Filter searches to specific documents using AG-UI state:

```json
{
  "filter_documents": {
    "document_ids": ["doc-1", "doc-2"]
  }
}
```

The filter is applied as a LanceDB query predicate.

### Citation Tracking

Citations are tracked in the `ask_history` state:

```json
{
  "ask_history": {
    "questions": [
      {
        "question": "What is RAG?",
        "response": "RAG (Retrieval-Augmented Generation) is...",
        "citations": [
          {
            "chunk_id": "chunk-123",
            "document_id": "doc-1",
            "text": "source text...",
            "page": 5
          }
        ]
      }
    ]
  }
}
```

### Use Case

Best for interactive Q&A where users need to see sources and may want to filter to specific documents.

---

## Tool Requirements

| Tool | Requirement | Description |
|------|-------------|-------------|
| `search_documents` | `TOOL_CONFIG` | Needs SearchDocumentsToolConfig |
| `research_report` | `FASTAPI_CONTEXT` | Needs RunContext (AG-UI emitter) |
| `ask_with_rich_citations` | `FASTAPI_CONTEXT` | Needs RunContext (AG-UI state) |

Tools with `FASTAPI_CONTEXT` requirement cannot be exposed via MCP.

## Creating Custom RAG Tools

Extend the `_RAGToolBase` class for custom RAG tools:

```python
import dataclasses
from soliplex import config

@dataclasses.dataclass
class CustomRAGToolConfig(config.ToolConfig, config._RAGToolBase):
    tool_name: str = "mypackage.tools.custom_rag"
    custom_param: str = None

async def custom_rag(
    query: str,
    tool_config: CustomRAGToolConfig = None,
) -> list[str]:
    """Custom RAG implementation."""
    async with rag_client.HaikuRAG(
        db_path=tool_config.rag_lancedb_path,
        config=tool_config.haiku_rag_config,
    ) as rag:
        # Custom logic here
        results = await rag.search(query)
        return [r.content for r in results]
```

## Source Code

- Tool implementations: `src/soliplex/tools.py`
- Tool configurations: `src/soliplex/config.py:456-557`
