# API Models

Pydantic models for Soliplex API requests and responses.

## User Models

### UserProfile

User information from OIDC token:

```python
class UserProfile(pydantic.BaseModel):
    given_name: str
    family_name: str
    email: str
    preferred_username: str
```

### UserInfo

Full user info response:

```python
UserInfo = dict[str, typing.Any]  # Raw OIDC claims
```

---

## Room Models

### Room

Room configuration response:

```python
class Room(pydantic.BaseModel):
    id: str
    description: str | None
    has_rag: bool
    has_quizzes: bool

    @classmethod
    def from_config(cls, room_config: RoomConfig) -> "Room":
        ...
```

### ConfiguredRooms

Map of available rooms:

```python
ConfiguredRooms = dict[str, Room]
```

### RAGDocument

Document in a RAG database:

```python
class RAGDocument(pydantic.BaseModel):
    id: str
    uri: str
    title: str | None
    metadata: dict
    created_at: datetime
    updated_at: datetime
```

### RoomDocuments

Room's document listing:

```python
class RoomDocuments(pydantic.BaseModel):
    room_id: str
    document_set: dict[str, RAGDocument]
```

### ChunkVisualization

Chunk visualization response:

```python
class ChunkVisualization(pydantic.BaseModel):
    chunk_id: str
    document_uri: str
    images_base_64: list[str]  # Base64-encoded PNG images
```

### MCPToken

MCP access token:

```python
class MCPToken(pydantic.BaseModel):
    room_id: str
    mcp_token: str
```

---

## AG-UI Models

### AGUI_Thread

Thread representation:

```python
class AGUI_Thread(pydantic.BaseModel):
    room_id: str
    thread_id: str
    created: datetime
    metadata: AGUI_ThreadMetadata | None
    runs: dict[str, AGUI_Run] | None

    @classmethod
    def from_thread(cls, a_thread, a_thread_meta, a_thread_runs) -> "AGUI_Thread":
        ...
```

### AGUI_ThreadMetadata

Thread metadata:

```python
class AGUI_ThreadMetadata(pydantic.BaseModel):
    title: str | None = None

    @classmethod
    def from_thread_meta(cls, thread_meta) -> "AGUI_ThreadMetadata":
        ...
```

### AGUI_Threads

List of threads:

```python
class AGUI_Threads(pydantic.BaseModel):
    threads: list[AGUI_Thread]
```

### AGUI_Run

Run representation:

```python
class AGUI_Run(pydantic.BaseModel):
    room_id: str
    thread_id: str
    run_id: str
    parent_run_id: str | None
    created: datetime
    run_input: RunAgentInput | None
    events: list[dict] | None
    metadata: AGUI_RunMetadata | None
    usage: tuple[int, int, int, int] | None  # input, output, requests, tool_calls

    @classmethod
    def from_run(cls, a_run, a_run_input, a_run_meta, a_run_events, a_run_usage) -> "AGUI_Run":
        ...
```

### AGUI_RunMetadata

Run metadata:

```python
class AGUI_RunMetadata(pydantic.BaseModel):
    status: str | None = None

    @classmethod
    def from_run_meta(cls, a_run_meta) -> "AGUI_RunMetadata":
        ...
```

### AGUI_NewThreadRequest

Request to create a new thread:

```python
class AGUI_NewThreadRequest(pydantic.BaseModel):
    metadata: AGUI_ThreadMetadata | None = None
```

### AGUI_NewRunRequest

Request to create a new run:

```python
class AGUI_NewRunRequest(pydantic.BaseModel):
    parent_run_id: str | None = None
    metadata: AGUI_RunMetadata | None = None
```

### AGUI_State

Shared state for tools:

```python
class AGUI_State(pydantic.BaseModel):
    filter_documents: FilterDocuments | None = None
    ask_history: AskedAndAnswered | None = None
```

### FilterDocuments

Document filter state:

```python
class FilterDocuments(pydantic.BaseModel):
    document_ids: list[str] | None = None
```

### AskedAndAnswered

Citation history:

```python
class AskedAndAnswered(pydantic.BaseModel):
    questions: list[QuestionResponseCitations] = []

class QuestionResponseCitations(pydantic.BaseModel):
    question: str
    response: str
    citations: list[Citation]
```

---

## Completion Models

### Completion

Completion configuration:

```python
class Completion(pydantic.BaseModel):
    id: str
    model_name: str

    @classmethod
    def from_config(cls, completion_config) -> "Completion":
        ...
```

### ConfiguredCompletions

Map of available completions:

```python
ConfiguredCompletions = dict[str, Completion]
```

### ChatCompletionRequest

OpenAI-compatible chat request:

```python
class ChatCompletionRequest(pydantic.BaseModel):
    messages: list[ChatMessage]
    stream: bool = True
    temperature: float | None = None
    max_tokens: int | None = None

class ChatMessage(pydantic.BaseModel):
    role: str  # "user", "assistant", "system"
    content: str
```

---

## Authentication Models

### OIDCAuthSystem

OIDC provider configuration:

```python
class OIDCAuthSystem(pydantic.BaseModel):
    id: str
    display_name: str
    authorize_url: str

    @classmethod
    def from_config(cls, auth_config) -> "OIDCAuthSystem":
        ...
```

### ConfiguredOIDCAuthSystems

Map of available auth providers:

```python
ConfiguredOIDCAuthSystems = dict[str, OIDCAuthSystem]
```

---

## Quiz Models

### Quiz

Quiz representation:

```python
class Quiz(pydantic.BaseModel):
    id: str
    title: str
    description: str | None
```

---

## Error Models

### HTTPException

Standard error response:

```python
{
    "detail": "Error message"
}
```

Status codes:
- `400` - Bad request
- `401` - Unauthorized
- `404` - Not found
- `500` - Internal server error

---

## Type Aliases

Common type definitions:

```python
# Configuration maps
ToolConfigMap = dict[str, ToolConfig]
MCP_ClientToolsetConfigMap = dict[str, MCP_ClientToolsetConfig]

# Event types
AGUI_Events = list[dict]
AGUI_EventStream = AsyncIterator[dict]
```

## Source Code

- Models: `src/soliplex/models.py`
- AG-UI models: `src/soliplex/agui/`
