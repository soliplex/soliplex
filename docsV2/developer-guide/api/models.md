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
    name: str
    description: str
    welcome_message: str
    suggestions: list[str]
    enable_attachments: bool
    tools: ConfiguredTools
    mcp_client_toolsets: ConfiguredMCPClientToolsets
    quizzes: ConfiguredQuizzes
    agent: Agent
    allow_mcp: bool
    agui_feature_names: list[str]  # AG-UI features used by room's tools

    @classmethod
    def from_config(cls, room_config: RoomConfig) -> "Room":
        ...
```

### ConfiguredRooms

Map of available rooms:

```python
ConfiguredRooms = dict[str, Room]
```

### Tool

Tool configuration exposed in Room response:

```python
class Tool(pydantic.BaseModel):
    kind: str                           # Tool type identifier
    tool_name: str                      # Unique tool name
    tool_description: str               # Description shown to agent
    tool_requires: ToolRequires         # Requirements (e.g., "tool_config")
    allow_mcp: bool                     # Exposed via MCP server
    agui_feature_names: list[str]       # AG-UI features this tool uses
    extra_parameters: dict[str, Any]    # Additional config parameters
```

### ConfiguredTools

Map of tools available in a room:

```python
ConfiguredTools = dict[str, Tool]
```

### RAGDocument

Document in a RAG database:

```python
class RAGDocument(pydantic.BaseModel):
    id: str
    uri: str | None
    title: str | None
    metadata: dict[str, typing.Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime
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
    document_uri: str | None
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
    runs: dict[str, AGUI_Run] | None = {}
    created: datetime.datetime | None = None
    metadata: AGUI_ThreadMetadata | None = None

    @classmethod
    def from_thread(cls, a_thread, a_thread_meta, a_thread_runs) -> "AGUI_Thread":
        ...
```

### AGUI_ThreadMetadata

Thread metadata:

```python
class AGUI_ThreadMetadata(pydantic.BaseModel):
    name: str | None = None
    description: str | None = None

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
    thread_id: str
    run_id: str
    parent_run_id: str | None = None
    run_input: RunAgentInput | None = None
    created: datetime.datetime | None = None
    finished: datetime.datetime | None = None
    events: list[agui_core.Event] | None = []
    metadata: AGUI_RunMetadata | None = None
    usage: AGUI_RunUsage | None = None

    @classmethod
    def from_run(cls, a_run, a_run_input, a_run_meta, a_run_events, a_run_usage) -> "AGUI_Run":
        ...
```

### AGUI_RunMetadata

Run metadata:

```python
class AGUI_RunMetadata(pydantic.BaseModel):
    label: str | None = None

    @classmethod
    def from_run_meta(cls, a_run_meta) -> "AGUI_RunMetadata":
        ...
```

### AGUI_RunUsage

Run usage statistics:

```python
class AGUI_RunUsage(pydantic.BaseModel):
    input_tokens: int
    output_tokens: int
    requests: int
    tool_calls: int

    @classmethod
    def from_tuple(cls, usage_tuple) -> "AGUI_RunUsage":
        ...
```

### AGUI_RunFeedback

Feedback for a run:

```python
class AGUI_RunFeedback(pydantic.BaseModel):
    feedback: str              # Required - feedback value (e.g., "positive", "negative")
    reason: str | None = None  # Optional - reason for the feedback
```

Used with `POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}/feedback` endpoint.

### AGUI_Feature

AG-UI feature definition returned in Installation response:

```python
class AGUI_Feature(pydantic.BaseModel):
    name: str                           # Feature identifier (e.g., "filter_documents")
    description: str                    # From model class docstring
    source: str                         # "client", "server", or "either"
    json_schema: dict[str, typing.Any]  # JSON Schema for the feature model
```

Features define contracts between client and server for named fields in AG-UI state.

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

Shared state type alias (flexible dict):

```python
AGUI_State = dict[str, typing.Any]
```

Tools that need typed state can use `AWRC_AGUI_State`:

```python
class AWRC_AGUI_State(pydantic.BaseModel):
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
    name: str
    tools: ConfiguredTools
    agent: Agent

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
    model: str
    messages: list[ChatMessage]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    stop: list[str] | None = None
    max_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0
    user: str | None = None

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
    title: str
    server_url: str
    token_validation_pem: str
    client_id: str
    scope: str | None = None

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
    randomize: bool
    max_questions: int | None = None
    questions: list[QuizQuestion]
```

---

## Installation Models

### Installation

Installation configuration response from `GET /v1/installation`:

```python
class Installation(pydantic.BaseModel):
    id: str                             # Installation identifier
    rooms: ConfiguredRooms              # Available rooms
    completions: ConfiguredCompletions  # Available completions
    oidc_auth_systems: ConfiguredOIDCAuthSystems  # Auth providers
    agui_features: list[AGUI_Feature]   # Registered AG-UI features

    @classmethod
    def from_config(cls, installation_config) -> "Installation":
        ...
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
AGUI_Events = list[agui_core.Event]
AGUI_EventStream = AsyncIterator[agui_core.Event]

# State
AGUI_State = dict[str, typing.Any]
```

## Source Code

- Models: `src/soliplex/models.py`
- AG-UI types: `src/soliplex/agui/__init__.py`
- Tool state models: `src/soliplex/tools.py`
