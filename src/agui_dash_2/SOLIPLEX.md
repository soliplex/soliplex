# Soliplex Backend - AG-UI Integration

This document describes how the Soliplex backend implements AG-UI and how the Flutter client interacts with it.

## API Endpoints

Base URL format: Bare server URL (e.g., `http://localhost:8000`)
API prefix: `/api/v1` (added automatically by `UrlBuilder`)

### Rooms API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rooms` | List all rooms |
| GET | `/api/v1/rooms/{room_id}` | Get room details |

### AG-UI Thread Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rooms/{room_id}/agui` | List threads in room |
| POST | `/api/v1/rooms/{room_id}/agui` | Create new thread (auto-creates initial run) |
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Get thread details with runs |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}` | Create new run for thread |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/meta` | Update thread metadata |

### AG-UI Run Execution

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Get run details with events |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}` | Execute run (streams SSE events) |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/cancel` | Cancel active run |
| POST | `/api/v1/rooms/{room_id}/agui/{thread_id}/{run_id}/meta` | Update run metadata |

## URL Construction

The Flutter client uses centralized `UrlBuilder` utility for consistent URL handling:

```dart
// Create builder from bare server URL
final builder = UrlBuilder('https://server.com');

// Available methods:
builder.rooms();                              // /api/v1/rooms
builder.room(roomId);                         // /api/v1/rooms/{roomId}
builder.roomThreads(roomId);                  // /api/v1/rooms/{roomId}/agui (thread listing)
builder.createThread(roomId);                 // /api/v1/rooms/{roomId}/agui (POST)
builder.thread(roomId, threadId);             // /api/v1/rooms/{roomId}/agui/{threadId}
builder.createRun(roomId, threadId);          // /api/v1/rooms/{roomId}/agui/{threadId} (POST)
builder.run(roomId, threadId, runId);         // /api/v1/rooms/{roomId}/agui/{threadId}/{runId}
builder.executeRun(roomId, threadId, runId);  // /api/v1/rooms/{roomId}/agui/{threadId}/{runId} (POST)
builder.cancelRun(roomId, threadId, runId);   // /api/v1/rooms/{roomId}/agui/{threadId}/{runId}/cancel
```

See `lib/core/utils/url_builder.dart` for full implementation.

## Request/Response Flow

### 1. Create Thread
```bash
POST /api/v1/rooms/genui/agui
Content-Type: application/json
{}
```

Response includes `thread_id` and initial `run_id`.

### 2. Create Run (for subsequent messages)
```bash
POST /api/v1/rooms/genui/agui/{thread_id}
Content-Type: application/json
{}
```

Response includes new `run_id`.

### 3. Execute Run (SSE stream)
```bash
POST /api/v1/rooms/genui/agui/{thread_id}/{run_id}
Content-Type: application/json
Accept: text/event-stream

{
  "threadId": "...",
  "runId": "...",
  "state": { ... },           // Client state (canvas, etc.)
  "messages": [ ... ],        // Chat messages
  "tools": [ ... ],           // Client-side tools
  "context": [ ... ],         // Additional context
  "forwardedProps": null
}
```

## RunAgentInput Schema

The POST body for run execution follows the AG-UI `RunAgentInput` schema:

```typescript
interface RunAgentInput {
  threadId: string;
  runId: string;
  parentRunId?: string;
  state: any;                 // Arbitrary client state
  messages: Message[];        // User, Assistant, Tool messages
  tools: Tool[];              // Client-side tool definitions
  context: Context[];         // Additional context items
  forwardedProps?: any;
}
```

### State Field

The `state` field accepts arbitrary JSON and is passed to the agent. Use this for:
- Canvas contents
- User preferences
- Application state the agent should know about

Example:
```json
{
  "state": {
    "canvas": [
      {"id": "staff-u1", "widget": "SkillsCard", "data": {...}},
      {"id": "project-p1", "widget": "ProjectCard", "data": {...}}
    ]
  }
}
```

The agent receives this state and can reference it in the system prompt to provide context-aware responses.

#### Backend Requirement: StateHandler Protocol

**IMPORTANT**: To use the `state` field, the backend's `AgentDependencies` class must implement pydantic-ai's `StateHandler` protocol:

1. `AgentDependencies` must be a **dataclass** (not `pydantic.BaseModel`)
2. It must have a **non-optional `state` field**

Current `AgentDependencies` in `soliplex/agents.py`:
```python
class AgentDependencies(pydantic.BaseModel):  # ❌ BaseModel, not dataclass
    the_installation: typing.Any
    user: models.UserProfile = None
    tool_configs: ToolConfigMap = None
    agui_emitter: typing.Any = None
    # ❌ Missing `state` field
```

Required change:
```python
from dataclasses import dataclass

@dataclass
class AgentDependencies:
    the_installation: typing.Any
    user: models.UserProfile
    tool_configs: ToolConfigMap
    agui_emitter: typing.Any
    state: dict  # Required for StateHandler protocol
```

Until this is implemented, the Flutter client should NOT send state (will cause `UserError`).

## Flutter Client Integration

### AgUiService

The `AgUiService` class (`lib/core/services/agui_service.dart`) manages communication:

1. **configure()** - Set room and base URL
2. **chat()** - Send message and handle response stream
   - Accepts `state` parameter for client state
   - Handles tool execution loop automatically

### Thread Class

The `Thread` class (`lib/infrastructure/quick_agui/thread.dart`) wraps AG-UI client:

1. **startRun()** - Execute a run with messages and state
2. **sendToolResults()** - Continue after tool execution
3. Manages message history and tool registration

### State Sync

Canvas state is sent with each request:

```dart
// In chat_content.dart
final canvasState = ref.read(canvasProvider);
await agUiService.chat(
  text,
  state: canvasState.toJson(),  // {"canvas": [...]}
  // ...
);
```

## Authentication

All endpoints require Bearer token authentication via `Authorization` header.

## Event Types

The SSE stream emits AG-UI events:
- `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`
- `TEXT_MESSAGE_START`, `TEXT_MESSAGE_CONTENT`, `TEXT_MESSAGE_END`
- `TOOL_CALL_START`, `TOOL_CALL_ARGS`, `TOOL_CALL_END`
- `TOOL_CALL_RESULT`
- `STATE_SNAPSHOT`, `STATE_DELTA`
- `THINKING_*` events
- `ACTIVITY_SNAPSHOT`
- `CUSTOM` (for genui_render, canvas_render)

## Notes

- Thread IDs and Run IDs are UUIDs generated server-side
- Each user message requires a new run (create run, then execute)
- Tool results are sent via a new run that continues the conversation
- The server uses pydantic-ai's `AGUIAdapter` to process requests

---

## Agent Factory Pattern

Soliplex supports custom agent factories via `FactoryAgentConfig`. This allows rooms to use custom agents with different dependencies, tools, or behavior.

### Configuration

In `room_config.yaml`:
```yaml
agent:
  kind: "factory"
  factory_name: "soliplex.genui.genui_agent_factory"
  with_agent_config: true
  extra_config:
    model_name: "gpt-4o"
    provider_key: "secret:OPENAI_API_KEY"
```

### Factory Function Signature

When `with_agent_config: true`, the factory receives the `FactoryAgentConfig` as first argument:

```python
def my_agent_factory(
    agent_config: config.FactoryAgentConfig,
    tool_configs: config.ToolConfigMap = None,
    mcp_client_toolset_configs: config.MCP_ClientToolsetConfigMap = None,
) -> pydantic_ai.Agent:
    # Access installation config for secrets/environment
    installation_config = agent_config._installation_config

    # Access extra_config for custom settings
    model_name = agent_config.extra_config.get("model_name", "default")

    # Build and return agent
    return pydantic_ai.Agent(...)
```

### Key Files

| File | Purpose |
|------|---------|
| `soliplex/config.py` | `FactoryAgentConfig` class (line ~892) |
| `soliplex/agents.py` | `get_agent_from_configs()` calls factory |
| `soliplex/installation.py` | `get_agent_deps_for_room()` creates deps |
| `soliplex/examples.py` | `faux_agent_factory` reference implementation |

### Dependencies Flow

1. **Agent creation**: `get_agent_from_configs()` calls `agent_config.factory()`
2. **Deps creation**: `get_agent_deps_for_room()` creates `AgentDependencies` instance
3. **Run execution**: pydantic-ai receives deps, injects state if StateHandler

### StateHandler Challenge

The current architecture has a coupling issue:

1. `AgentDependencies` is defined in `agents.py` as a Pydantic BaseModel
2. `get_agent_deps_for_room()` always creates `agents.AgentDependencies`
3. Custom factories can use different `deps_type`, but deps are still created centrally

**Problem**: If a custom agent factory uses a StateHandler-compatible deps class:
```python
@dataclass
class GenUIDependencies:
    state: dict[str, Any]  # For StateHandler protocol
    # ... other fields
```

The `installation.py:get_agent_deps_for_room()` still creates `agents.AgentDependencies` (BaseModel, no state field), causing the StateHandler error.

**Solutions**:

1. **Per-room deps factory**: Let `FactoryAgentConfig` specify a deps factory
2. **Modify global AgentDependencies**: Convert to dataclass, add `state` field
3. **Agent-level deps creation**: Have agents create their own deps

Option 2 is simplest but affects all agents. Option 1 is cleanest for per-room customization.

### Dynamic System Prompts

pydantic-ai supports dynamic prompts via `@agent.system_prompt` decorator:

```python
agent = pydantic_ai.Agent(
    model=...,
    deps_type=MyDeps,
    instructions="Static base prompt here",
)

@agent.system_prompt
def dynamic_prompt(ctx: pydantic_ai.RunContext[MyDeps]) -> str:
    """This is called at runtime and can access deps."""
    canvas_items = ctx.deps.state.get("canvas", [])
    return f"Current canvas has {len(canvas_items)} items."
```

The static `instructions` and dynamic `@agent.system_prompt` are concatenated.

### Accessing State in Prompts

State is NOT automatically in prompts. Access via RunContext:

```python
@agent.system_prompt
def canvas_aware_prompt(ctx: pydantic_ai.RunContext[MyDeps]) -> str:
    state = ctx.deps.state  # AG-UI state injected here
    canvas = state.get("canvas", [])
    # Format and return prompt section
```

### Example: GenUI Agent

A complete GenUI agent with state support would need:

1. **Custom deps** (`genui.py`):
```python
@dataclass
class GenUIDependencies:
    the_installation: Any
    user: Any = None
    tool_configs: dict = None
    agui_emitter: Any = None
    state: dict[str, Any] = field(default_factory=dict)
```

2. **Agent factory** (`genui.py`):
```python
def genui_agent_factory(agent_config, tool_configs=None, mcp_client_toolset_configs=None):
    agent = pydantic_ai.Agent(
        model=...,
        deps_type=GenUIDependencies,
        instructions=BASE_PROMPT,
    )

    @agent.system_prompt
    def canvas_prompt(ctx):
        return format_canvas_state(ctx.deps.state)

    return agent
```

3. **Deps creation** - Need to modify `installation.py:get_agent_deps_for_room()` to use the correct deps class for factory agents.
