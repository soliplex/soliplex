# Backend Request: StateHandler Protocol Support

## Summary

Enable AG-UI state sync so the Flutter client can send application state (canvas contents) to the agent with each request.

## What to Implement

Modify `AgentDependencies` in `soliplex/agents.py` to implement pydantic-ai's `StateHandler` protocol.

### Current Implementation

```python
class AgentDependencies(pydantic.BaseModel):
    the_installation: typing.Any
    user: models.UserProfile = None
    tool_configs: ToolConfigMap = None
    agui_emitter: typing.Any = None
```

### Required Change

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

Key changes:
1. Convert from `pydantic.BaseModel` to `@dataclass`
2. Add non-optional `state: dict` field
3. Update any code that creates `AgentDependencies` instances to pass `state`

### Files to Modify

- `soliplex/agents.py` - Change class definition
- `soliplex/installation.py` - Update `get_agent_deps_for_room()` to pass state
- Any other files that instantiate `AgentDependencies`

## Why We Want This

### Problem

The LLM agent has no visibility into client-side state. When users:
- Pin items to the canvas
- Delete items from the canvas
- Ask "what's on my canvas?"

The agent cannot answer accurately because it only knows what it rendered, not the current state.

### Solution

AG-UI's `state` field in `RunAgentInput` allows the client to send arbitrary state with each request. The agent can then:
- Know exactly what's on the canvas
- Avoid saying "already on canvas" for deleted items
- Answer questions about pinned items accurately
- Make context-aware decisions

### Example State Payload

```json
{
  "state": {
    "canvas": [
      {
        "id": "staff-u1",
        "widget": "SkillsCard",
        "data": {
          "person_id": "u1",
          "name": "John Smith",
          "title": "Engineering Lead",
          "skills": [{"name": "Flutter", "level": 5}, ...]
        }
      },
      {
        "id": "project-p1",
        "widget": "ProjectCard",
        "data": {...}
      }
    ]
  }
}
```

### Prompt Integration

Once enabled, the system prompt would include:
```
## Canvas State

The `state.canvas` field contains the current canvas contents.
When user asks "what's on my canvas?", reference state.canvas.
Do not re-add items already on canvas (check state.canvas first).
```

## How to Test

### 1. Unit Test - AgentDependencies

```python
def test_agent_dependencies_has_state():
    from soliplex.agents import AgentDependencies
    import dataclasses

    # Verify it's a dataclass
    assert dataclasses.is_dataclass(AgentDependencies)

    # Verify state field exists and is required
    fields = {f.name: f for f in dataclasses.fields(AgentDependencies)}
    assert 'state' in fields
    assert fields['state'].default is dataclasses.MISSING  # Not optional
```

### 2. Integration Test - State in Request

```bash
# Create thread
THREAD=$(curl -s -X POST "http://localhost:8000/api/v1/rooms/genui/agui" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{}')

THREAD_ID=$(echo $THREAD | jq -r '.thread_id')
RUN_ID=$(echo $THREAD | jq -r '.runs | keys[0]')

# Execute run WITH state - should not error
curl -X POST "http://localhost:8000/api/v1/rooms/genui/agui/$THREAD_ID/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "threadId": "'$THREAD_ID'",
    "runId": "'$RUN_ID'",
    "state": {
      "canvas": [
        {"id": "staff-u1", "widget": "SkillsCard", "data": {"name": "John Smith"}}
      ]
    },
    "messages": [{"role": "user", "content": "What is on my canvas?"}],
    "tools": [],
    "context": [],
    "forwardedProps": null
  }'
```

**Expected**: SSE stream with agent response referencing "John Smith" from canvas state.

**Current behavior**: `UserError: State is provided but deps of type AgentDependencies does not implement the StateHandler protocol`

### 3. Flutter Client Test

Once backend is updated, uncomment in `chat_content.dart`:
```dart
final canvasState = ref.read(canvasProvider);
// ...
state: canvasState.toJson(),
```

Then:
1. Add items to canvas via "pin to canvas"
2. Delete some items manually
3. Ask "what's on my canvas?"
4. Verify agent only lists items currently on canvas

## Priority

Medium - The app works without this, but state sync enables a much better UX for canvas-aware interactions.

## Investigation Notes (2024-12)

### What We Tried

We created `soliplex/genui.py` with:

1. **`GenUIDependencies`** - A dataclass with `state: dict[str, Any]` field (implements StateHandler protocol)

2. **`genui_agent_factory`** - Creates a `pydantic_ai.Agent` with:
   - `deps_type=GenUIDependencies`
   - A dynamic system prompt via `@agent.system_prompt` decorator

3. **Modified `installation.py`** - `get_agent_deps_for_room()` now checks `agent._deps_type` and creates the correct deps class

### What Works

- Factory is called: `[GenUI] genui_agent_factory called!`
- System prompt function is registered: `agent._system_prompt_functions = [SystemPromptRunner(...)]`
- Flutter client sends state via `RunAgentInput.state`

### What Doesn't Work

- **The `@agent.system_prompt` decorated function is never called during a run**
- We verified with `print()` statements - the function is registered but never invoked
- Tried `@agent.system_prompt(dynamic=True)` but this broke the system

### Root Cause (Suspected)

The AG-UI adapter (`AGUIAdapter.run_stream()`) calls `agent.run_stream_events()` which should call `agent.run()` internally. However, the system prompt functions are not being invoked. Possible reasons:

1. The AG-UI adapter may be bypassing the normal prompt building
2. There may be a caching issue with non-dynamic system prompts
3. The `message_history` being passed may cause prompts to be skipped

### Next Steps

1. Debug `pydantic_ai/agent/abstract.py` to see where system prompts are built
2. Check if AG-UI adapter passes `message_history` which might skip prompt evaluation
3. Consider injecting canvas state directly into the static `instructions` instead of using dynamic prompts
4. Ask pydantic-ai maintainers about `@agent.system_prompt` + AG-UI adapter compatibility

### Attempt 2: Custom Agent Wrapper (like FauxAgent)

We tried creating a `GenUIAgent` class that wraps `pydantic_ai.Agent` and intercepts `run_stream_events()` to inject canvas state into `instructions`:

```python
@dataclasses.dataclass
class GenUIAgent:
    inner_agent: pydantic_ai.Agent[GenUIDependencies, Any]
    base_prompt: str
    output_type = None

    async def run_stream_events(self, ..., deps, instructions=None, **kwargs):
        canvas_prompt = _format_canvas_state(deps.state if deps else {})
        full_instructions = f"{self.base_prompt}\n\n{canvas_prompt}"

        async for event in self.inner_agent.run_stream_events(
            ..., instructions=full_instructions, **kwargs
        ):
            yield event
```

**Result**: JSON validation errors. The model returns markdown text but pydantic-ai tries to parse it as JSON. Setting `output_type=str` causes `{"response":null}` responses.

The issue appears to be a fundamental incompatibility between:
- Custom agent wrappers that delegate to inner agents
- The AG-UI adapter's expectations about response types

### Solution Found (2024-12)

**Key insight**: The AG-UI adapter's `run_stream()` method accepts an `instructions` parameter (see `pydantic_ai/ui/_adapter.py:290`). We don't need a custom wrapper agent - we can build dynamic instructions in `views/agui.py` and pass them to the adapter.

The fix involves:

1. **Simple `genui.py`**: Return a standard `pydantic_ai.Agent` with `GenUIDependencies` (dataclass with `state` field). No wrapper class needed.

2. **Dynamic instructions in `views/agui.py`**: Check if agent has `_genui_base_prompt` attribute, then build full instructions with canvas state from `agui_adapter.state`.

3. **Pass instructions to adapter**: Call `agui_adapter.run_stream(deps=..., instructions=dynamic_instructions)`

### Current Status

**Canvas state sync enabled** - The solution works without a custom wrapper agent.

Files modified:
- `soliplex/genui.py` - Simple factory returning standard `pydantic_ai.Agent` with `GenUIDependencies`
- `soliplex/views/agui.py` - Builds dynamic instructions with canvas state
- `soliplex/installation.py` - Updated `get_agent_deps_for_room()` to accept `agent` parameter
- `example/rooms/genui/room_config.yaml` - Uses `genui_agent_factory`
- `lib/features/chat/chat_content.dart` - State sync re-enabled

## References

- pydantic-ai StateHandler protocol: Check pydantic-ai docs for `StateHandler`
- pydantic-ai AG-UI adapter: `pydantic_ai/ui/_adapter.py` - `run_stream()` accepts `instructions` parameter
- Flutter client code: `lib/core/services/canvas_service.dart` (serialization ready)
- AG-UI spec: `RunAgentInput.state` field
- genui.py: `soliplex/genui.py` - working implementation
