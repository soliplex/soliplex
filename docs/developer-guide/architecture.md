# Architecture

This document provides a comprehensive overview of Soliplex's architecture, component interactions, and data flows.

## System Overview

Soliplex is a multi-component AI platform with three main layers:

```mermaid
graph TB
    subgraph "Client Layer"
        Flutter[Flutter App<br/>Web / Mobile / Desktop]
    end

    subgraph "API Layer"
        FastAPI[FastAPI Server]
        AGUI[AG-UI Handler]
        Auth[OIDC Auth]
    end

    subgraph "Agent Layer"
        Agents[Pydantic AI Agents]
        Tools[Tool System]
        MCP_C[MCP Client]
        MCP_S[MCP Server]
    end

    subgraph "Data Layer"
        RAG[(LanceDB<br/>Vector Store)]
        SQLite[(SQLite<br/>Thread Store)]
    end

    subgraph "LLM Layer"
        Ollama[Ollama<br/>Local Inference]
        OpenAI[OpenAI API<br/>Cloud Inference]
    end

    Flutter -->|SSE| AGUI
    Flutter -->|REST| FastAPI
    FastAPI --> Auth
    AGUI --> Agents
    Agents --> Tools
    Tools --> RAG
    Agents --> MCP_C
    MCP_C -->|Stdio/HTTP| ExtMCP[External MCP Servers]
    MCP_S -->|HTTP| ExtClient[External MCP Clients]
    Agents -->|Inference| Ollama
    Agents -->|Inference| OpenAI
    AGUI --> SQLite
```

## Component Details

### Frontend (Flutter)

!!! note "Separate Repository"
    The Flutter frontend is maintained at [github.com/soliplex/flutter](https://github.com/soliplex/flutter).

| Component | Technology | Purpose |
|-----------|------------|---------|
| **UI Framework** | Flutter 3.x | Cross-platform rendering |
| **State Management** | Riverpod | Reactive state handling |
| **HTTP Client** | http | REST API calls |
| **SSE Client** | Custom | AG-UI streaming |

### Backend (Python)

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Web Framework** | FastAPI | Async REST API |
| **Agent Framework** | Pydantic AI | LLM orchestration |
| **Vector Store** | LanceDB | RAG embeddings |
| **MCP** | FastMCP | Tool protocol |
| **Observability** | Logfire | Logging/tracing |

## Request Flow

### Chat Message Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Flutter
    participant A as AG-UI Endpoint
    participant P as Pydantic AI Agent
    participant T as Tools
    participant L as LLM (Ollama/OpenAI)
    participant D as Database

    U->>F: Type message
    F->>A: POST /v1/rooms/{room_id}/agui/{thread_id}/{run_id}
    A->>D: Load thread history
    A->>P: run_stream(prompt, deps, history)

    loop Streaming Response
        P->>L: Generate tokens
        L-->>P: Token chunks
        P-->>A: AG-UI Events
        A-->>F: SSE Events
        F-->>U: Render text
    end

    opt Tool Call
        P->>T: Execute tool
        T-->>P: Tool result
        P->>L: Continue with result
    end

    P-->>A: AgentRunResultEvent
    A->>D: Persist run events
    A-->>F: RUN_FINISHED
```

### Authentication Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Flutter
    participant S as Soliplex
    participant O as OIDC Provider

    U->>F: Click Login
    F->>S: GET /login
    S-->>F: Available providers
    F->>S: GET /login/{provider}
    S-->>F: Redirect to OIDC
    F->>O: Authenticate
    O-->>F: Redirect with code
    F->>S: GET /auth/{provider}?code=...
    S->>O: Exchange code for tokens
    O-->>S: Tokens
    S-->>F: Access token + refresh token
    F->>S: API calls with Bearer token
```

## Data Models

### Thread/Run Hierarchy

```mermaid
classDiagram
    class Thread {
        +str thread_id
        +str room_id
        +str user_name
        +datetime created
        +dict thread_metadata
    }

    class Run {
        +str run_id
        +str thread_id
        +str parent_run_id
        +datetime created
        +datetime finished
        +list_events() list[Event]
    }

    class Event {
        +str type
        +str message_id
        +dict data
        +datetime timestamp
    }

    Thread "1" --> "*" Run : contains
    Run "1" --> "*" Event : contains
```

### Configuration Hierarchy

```mermaid
classDiagram
    class Installation {
        +str id
        +list secrets
        +dict environment
        +list agent_configs
        +list room_paths
    }

    class RoomConfig {
        +str id
        +AgentConfig agent_config
        +list tool_configs
        +dict mcp_client_toolset_configs
        +bool allow_mcp
    }

    class AgentConfig {
        +str id
        +str model_name
        +str system_prompt
        +str provider_type
    }

    class FactoryAgentConfig {
        +str id
        +str factory_name
        +dict extra_config
    }

    Installation "1" --> "*" RoomConfig : references
    RoomConfig "1" --> "1" AgentConfig : has
    AgentConfig <|-- FactoryAgentConfig : extends
```

## Component Interactions

### Agent System

```mermaid
graph LR
    subgraph "Agent Creation"
        Config[AgentConfig] --> Factory[Agent Factory]
        Factory --> Agent[Pydantic AI Agent]
    end

    subgraph "Runtime"
        Agent --> |run_stream| Stream[Event Stream]
        Agent --> |tools| Tools[Tool Execution]
        Agent --> |deps| Deps[AgentDependencies]
    end

    subgraph "Dependencies"
        Deps --> User[UserProfile]
        Deps --> Install[Installation]
        Deps --> TC[ToolConfigs]
        Deps --> Emit[AGUIEmitter]
    end
```

### MCP Integration

```mermaid
graph TB
    subgraph "MCP Server Mode"
        Room[Room Config] -->|allow_mcp: true| MCP_S[MCP Server]
        MCP_S -->|exposes| RoomTools[Room Tools]
        ExtClient[External Client] -->|authenticated| MCP_S
    end

    subgraph "MCP Client Mode"
        Room -->|mcp_client_toolsets| MCP_C[MCP Client]
        MCP_C -->|stdio| Subprocess[npx/python]
        MCP_C -->|http| Remote[Remote Server]
        MCP_C -->|provides| ExtTools[External Tools]
    end

    subgraph "Agent"
        Agent[Pydantic AI Agent]
        Agent --> RoomTools
        Agent --> ExtTools
    end
```

## Scalability Considerations

### Stateless Backend

The FastAPI backend is stateless:

- Thread/run data persisted to SQLite (configurable)
- No in-memory session state
- Horizontal scaling possible with shared database

### Agent Caching

Agents are cached by ID to avoid recreation:

```python
_agent_cache: dict[str, Agent] = {}

def get_agent(config):
    if config.id not in _agent_cache:
        _agent_cache[config.id] = create_agent(config)
    return _agent_cache[config.id]
```

### Streaming Architecture

AG-UI uses Server-Sent Events for efficient streaming:

- Single HTTP connection per run
- Events compacted to reduce overhead
- Multiplexed streams for agent + emitter events

## Security Architecture

### Authentication

```mermaid
graph LR
    Request[API Request] --> Auth[Auth Middleware]
    Auth -->|Valid Token| Handler[Route Handler]
    Auth -->|Invalid| Reject[401 Unauthorized]
    Handler --> Deps[AgentDependencies]
    Deps --> User[UserProfile]
```

### MCP Token Security

```mermaid
graph LR
    User[Authenticated User] --> Token[GET /mcp_token]
    Token --> Sign[Sign with Secret]
    Sign --> Scoped[Scope to Room ID]
    Scoped --> Timed[Optional Expiration]
    Timed --> MCP_Token[URL-Safe Token]
```

## File Organization

```
src/soliplex/
├── __init__.py
├── agents.py          # Agent creation, caching
├── config.py          # Configuration parsing
├── installation.py    # Installation management
├── mcp_server.py      # MCP server
├── mcp_client.py      # MCP client
├── mcp_auth.py        # MCP authentication
├── models.py          # Pydantic models
├── tools.py           # Tool implementations
├── examples.py        # Factory agent examples
├── agui/              # AG-UI protocol
│   ├── __init__.py    # Core AG-UI types and utilities
│   ├── features.py    # Feature flags
│   ├── mpx.py         # Multiplexing utilities
│   ├── parser.py      # Event parsing
│   ├── persistence.py # Thread/run storage
│   └── util.py        # Helper functions
├── authz/             # Authorization
│   ├── __init__.py    # Authorization service
│   └── schema.py      # SQLAlchemy models
├── views/             # FastAPI routes
│   ├── agui.py        # AG-UI streaming
│   ├── auth.py        # Legacy auth
│   ├── authn.py       # Authentication
│   ├── authz.py       # Authorization endpoints
│   ├── completions.py # Completion configs
│   ├── installation.py # Installation info
│   ├── quizzes.py     # Quiz endpoints
│   └── rooms.py       # Room endpoints
└── tui/               # Terminal UI client
    ├── __init__.py
    ├── cli.py         # CLI entry point
    ├── main.py        # TUI app, screens, widgets
    ├── rest_api.py    # REST API client
    └── serve.py       # Web-serve wrapper
```

## TUI Architecture

The Terminal User Interface provides a Textual-based client for Soliplex.

```mermaid
graph TB
    subgraph "TUI Application"
        App[SoliplexTUI App]
        RS[RoomSelect Screen]
        RV[RoomView Screen]
        TV[ThreadRunsView]
        RunV[RunView Screen]
        Dialog[Metadata Dialogs]
    end

    subgraph "REST API Layer"
        API[TUI_REST_API]
    end

    subgraph "Backend"
        Server[Soliplex Server]
    end

    App --> RS
    RS -->|room selected| RV
    RV -->|Ctrl+T| TV
    RV -->|Ctrl+R| TV
    TV -->|run selected| RunV
    RV -->|Ctrl+Z| Dialog
    RunV -->|Ctrl+Z| Dialog

    RV --> API
    API -->|HTTP| Server
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `TUI_REST_API` | `rest_api.py` | HTTP client for backend communication |
| `SoliplexTUI` | `main.py` | Main app with room selection |
| `RoomView` | `main.py` | Chat interface with thread management |
| `RunView` | `main.py` | Detailed run event viewer |
| `EditThreadMetadataDialog` | `main.py` | Thread name/description editing |
| `EditRunMetadataDialog` | `main.py` | Run label editing |

### Screen Flow

1. **Room Selection** → User picks a room from available rooms
2. **Room Chat** → Chat interface with current thread
3. **Thread List** → Browse all threads via `Ctrl+T`
4. **Run List** → Browse runs in current thread via `Ctrl+R`
5. **Run Details** → View run events and messages

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Agent Framework** | Pydantic AI | Type-safe, streaming support, tool integration |
| **Vector Store** | LanceDB | Embedded, fast, good Python support |
| **Streaming Protocol** | AG-UI over SSE | Rich event types, browser compatible |
| **MCP Implementation** | FastMCP | Official Python SDK, dual mode |
| **State Management** | Riverpod | Testable, scoped providers |
