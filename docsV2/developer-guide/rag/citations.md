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

```python
class Citation(pydantic.BaseModel):
    chunk_id: str
    document_id: str
    document_uri: str
    text: str              # The cited text
    page: int | None       # Page number if available
    metadata: dict         # Additional metadata

class QuestionResponseCitations(pydantic.BaseModel):
    question: str
    response: str
    citations: list[Citation]

class AskedAndAnswered(pydantic.BaseModel):
    questions: list[QuestionResponseCitations] = []
```

## AG-UI State Synchronization

Citations are synchronized to the frontend via AG-UI state events:

```
event: STATE_DELTA
data: {
  "type": "STATE_DELTA",
  "delta": {
    "ask_history": {
      "questions": [
        {
          "question": "What is RAG?",
          "response": "RAG is...",
          "citations": [...]
        }
      ]
    }
  }
}
```

The frontend receives state updates and can display citations alongside responses.

## Frontend: Displaying Citations

### Flutter Implementation

The Flutter app listens for state updates and renders citations:

```dart
// Listen for AG-UI state changes
aguiStream.listen((event) {
  if (event.type == 'STATE_DELTA') {
    final askHistory = event.delta['ask_history'];
    if (askHistory != null) {
      _updateCitations(askHistory);
    }
  }
});

// Render citation chips
Widget _buildCitations(List<Citation> citations) {
  return Wrap(
    children: citations.map((c) => CitationChip(
      citation: c,
      onTap: () => _showChunkVisualization(c.chunkId),
    )).toList(),
  );
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
  "document_uri": "file:///docs/guide.pdf",
  "images_base_64": [
    "iVBORw0KGgoAAAANSUhEUgAA...",
    "iVBORw0KGgoAAAANSUhEUgAA..."
  ]
}
```

### Implementation

```python
@router.get("/v1/rooms/{room_id}/chunk/{chunk_id}")
async def get_chunk_visualization(
    room_id: str,
    chunk_id: str,
    the_installation: Installation,
    token: HTTPAuthorizationCredentials,
) -> ChunkVisualization:
    async with rag_client.HaikuRAG(...) as rag:
        chunk = await rag.chunk_repository.get_by_id(chunk_id)
        images = await rag.visualize_chunk(chunk)

    # Convert PIL images to base64
    base64_images = []
    for img in images:
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        base64_images.append(base64.b64encode(buffer.read()).decode())

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

if document_ids:
    quoted = [f"'{id}'" for id in document_ids]
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
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "text": "Retrieval-Augmented Generation combines...",
            "page": 12
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
