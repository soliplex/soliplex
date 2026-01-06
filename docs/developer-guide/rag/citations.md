# Citations

Soliplex provides a citation system that links AI responses to source documents, enabling users to verify and explore the underlying knowledge.

## Citation Flow

```
User Question
    ↓
ask_with_rich_citations tool
    ↓
haiku-rag search + answer
    ↓
Citations stored in AG-UI state (ask_history)
    ↓
AG-UI STATE_DELTA event
    ↓
Flutter displays citations
    ↓
User clicks citation → Chunk visualization API
```

## Backend: Generating Citations

### ask_with_rich_citations Tool

The primary citation-generating tool:

```python
async def ask_with_rich_citations(
    ctx: pydantic_ai.RunContext[agents.AgentDependencies],
    question: str,
) -> str:
    async with rag_client.HaikuRAG(...) as rag:
        # haiku-rag returns response + citations
        response, citations = await rag.ask(question, filter=search_filter)

        # Store in AG-UI state for frontend access
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

### Citation Data Model

Citations use the `Citation` model from haiku.rag:

```python
# From haiku.rag.graph.common.models
class Citation(pydantic.BaseModel):
    document_id: str
    chunk_id: str
    document_uri: str
    document_title: str | None = None
    page_numbers: list[int] = []
    headings: list[str] | None = None
    content: str           # The cited text

# Soliplex models wrapping citations
class QuestionResponseCitations(pydantic.BaseModel):
    question: str
    response: str
    citations: list[hr_graph_models.Citation] = []

class AskedAndAnswered(pydantic.BaseModel):
    questions: list[QuestionResponseCitations] = []
```

## AG-UI State Synchronization

Citations are synchronized to the frontend via AG-UI STATE_DELTA events using JSON Patch RFC 6902 format:

```
event: STATE_DELTA
data: {
  "type": "STATE_DELTA",
  "delta": [
    {
      "op": "replace",
      "path": "/ask_history",
      "value": {
        "questions": [
          {
            "question": "What is RAG?",
            "response": "RAG is...",
            "citations": [...]
          }
        ]
      }
    }
  ]
}
```

The frontend receives state updates (as JSON Patch operations) and extracts citations from the `/ask_history` path.

## Frontend: Displaying Citations

### Flutter Implementation

The Flutter app processes AG-UI events with typed pattern matching:

```dart
// Event processor handles STATE_DELTA with JSON Patch format
EventProcessingResult _processStateDelta(ag_ui.StateDeltaEvent event) {
  final delta = event.delta as List<dynamic>? ?? [];

  for (final op in delta) {
    final path = op['path'] as String?;
    final operation = op['op'] as String?;
    final value = op['value'];

    // Check for ask_history being set/replaced
    if (path == '/ask_history' &&
        (operation == 'replace' || operation == 'add') &&
        value is Map<String, dynamic>) {
      citations = _extractCitationsFromAskHistory(value);
    }
  }
  // Buffer citations for attachment to next text message
  return EventProcessingResult(citationsBufferUpdate: ...);
}

// Collapsible citations widget with chunk visualization
class CollapsibleCitationsWidget extends ConsumerStatefulWidget {
  final List<Citation> citations;
  final String roomId;

  void _showChunkVisualization(BuildContext context, Citation citation) {
    final uri = urlBuilder.roomChunk(roomId, citation.chunkId);
    showDialog<void>(
      context: context,
      builder: (ctx) => _ChunkVisualizationDialog(uri: uri, citation: citation),
    );
  }
}
```

### Citation Display Pattern

Citations are typically displayed as:

1. **Inline references** - Numbers or markers in the response text
2. **Citation list** - Below the response with source details
3. **Interactive chips** - Clickable elements that expand to show context

## Chunk Visualization API

When users click a citation, the frontend can fetch a visual representation:

### Request

```bash
GET /api/v1/rooms/{room_id}/chunk/{chunk_id}
Authorization: Bearer {token}
```

### Response

```json
{
  "chunk_id": "chunk-abc123",
  "document_uri": "file:///docs/guide.pdf",   // may be null
  "images_base_64": [
    "iVBORw0KGgoAAAANSUhEUgAA...",
    "iVBORw0KGgoAAAANSUhEUgAA..."
  ]
}
```

The `document_uri` field is optional and may be null.

### Implementation

```python
@router.get("/v1/rooms/{room_id}/chunk/{chunk_id}")
async def get_chunk_visualization(
    request: fastapi.Request,
    room_id: str,
    chunk_id: str,
    the_installation: Installation,
    token: HTTPAuthorizationCredentials,
) -> ChunkVisualization:
    user = auth.authenticate(the_installation, token)
    room_config = the_installation.get_room_config(room_id, user)

    # Find tool with haiku_rag_config
    for tool_config in room_config.tool_configs.values():
        hr_config = getattr(tool_config, "haiku_rag_config", None)
        if hr_config is not None:
            async with rag_client.HaikuRAG(...) as rag:
                chunk = await rag.chunk_repository.get_by_id(chunk_id)
                images = await rag.visualize_chunk(chunk)
            break

    # Convert PIL images to base64
    base64_images = []
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        base64_images.append(base64.b64encode(buffer.read()).decode("utf-8"))

    return ChunkVisualization(
        chunk_id=chunk_id,
        document_uri=chunk.document_uri,
        images_base_64=base64_images,
    )
```

The visualization shows the original document page(s) with the chunk text highlighted.

## Document Filtering

Users can restrict citations to specific documents:

### Setting the Filter

```json
// AG-UI state
{
  "filter_documents": {
    "document_ids": ["doc-1", "doc-2"]
  }
}
```

### Filter Application

```python
# In ask_with_rich_citations
documents = agui_state.filter_documents
document_ids = getattr(documents, "document_ids", ()) or ()
quoted = [f"'{id}'" for id in document_ids]

if quoted:
    search_filter = f"id IN ({', '.join(quoted)})"

response, citations = await rag.ask(question, filter=search_filter)
```

### Use Case

Document filtering allows users to:
- Focus on specific sources
- Compare information across selected documents
- Exclude irrelevant documents from consideration

## ask_history State

The `ask_history` state tracks all Q&A interactions in a session:

```json
{
  "ask_history": {
    "questions": [
      {
        "question": "What is RAG?",
        "response": "RAG (Retrieval-Augmented Generation) is...",
        "citations": [
          {
            "document_id": "doc-1",
            "chunk_id": "chunk-1",
            "document_uri": "file:///docs/guide.pdf",
            "document_title": "RAG Guide",
            "page_numbers": [12, 13],
            "headings": ["Introduction", "Overview"],
            "content": "Retrieval-Augmented Generation combines..."
          }
        ]
      },
      {
        "question": "How does embedding work?",
        "response": "Embeddings are vector representations...",
        "citations": [...]
      }
    ]
  }
}
```

This enables:
- Session history display
- Follow-up question context
- Citation cross-referencing

## Best Practices

1. **Always show sources** - Users trust AI more when they can verify
2. **Make citations clickable** - Enable exploration of source material
3. **Show relevant context** - Use context_radius to include surrounding text
4. **Filter when appropriate** - Let users focus on specific documents
5. **Handle missing chunks** - Gracefully handle deleted or moved documents

## Source Code

- Citation tool: `src/soliplex/tools.py:133-185`
- Chunk visualization: `src/soliplex/views/rooms.py:170-231`
- Models: `src/soliplex/models.py`
