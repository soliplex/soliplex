# Streaming

Soliplex uses Pydantic AI's `run_stream()` method combined with the AG-UI protocol to deliver real-time responses to clients.

## Overview

```
Agent.run_stream() → AG-UI Events → SSE → Flutter Client
```

## Using run_stream()

### Basic Usage

```python
async with agent.run_stream(
    user_prompt,
    message_history=history,
    deps=agent_deps,
) as response:
    async for text in response.stream_text():
        # Process streaming text
        yield text
```

### With AG-UI Adapter

```python
from pydantic_ai.ui import ag_ui as ai_ag_ui

agui_adapter = await ai_ag_ui.AGUIAdapter.from_request(request=request, agent=agent)

agent_stream = agui_adapter.run_stream(
    deps=agent_deps,
    on_complete=finish_callback,
)

# Encode as SSE
sse_stream = agui_adapter.encode_stream(agent_stream)

return StreamingResponse(sse_stream, media_type="text/event-stream")
```

## AG-UI Event Types

### Text Events

```
event: TEXT_MESSAGE_START
data: {"type": "TEXT_MESSAGE_START", "message_id": "msg-1"}

event: TEXT_MESSAGE_CONTENT
data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello, "}

event: TEXT_MESSAGE_CONTENT
data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "world!"}

event: TEXT_MESSAGE_END
data: {"type": "TEXT_MESSAGE_END"}
```

### Tool Call Events

```
event: TOOL_CALL_START
data: {"type": "TOOL_CALL_START", "tool_call_id": "tc-1", "tool_name": "search_documents"}

event: TOOL_CALL_ARGS
data: {"type": "TOOL_CALL_ARGS", "delta": "{\"query\": \"RAG\"}"}

event: TOOL_CALL_END
data: {"type": "TOOL_CALL_END"}

event: TOOL_CALL_RESULT
data: {"type": "TOOL_CALL_RESULT", "tool_call_id": "tc-1", "result": "[...]"}
```

### Run Lifecycle Events

```
event: RUN_STARTED
data: {"type": "RUN_STARTED", "run_id": "run-1", "thread_id": "thread-1"}

event: RUN_FINISHED
data: {"type": "RUN_FINISHED"}

event: RUN_ERROR
data: {"type": "RUN_ERROR", "error": "Something went wrong"}
```

## Event Compaction

Consecutive text events are compacted to reduce overhead:

```python
from soliplex.agui import compact_event_stream

# Before: Many small TEXT_MESSAGE_CONTENT events
# After: Fewer, larger TEXT_MESSAGE_CONTENT events
compacted = compact_event_stream(agent_stream)
```

## Multiplexing Streams

Combine agent events with emitter events (e.g., research progress):

```python
from soliplex.agui.mpx import multiplex_streams

# Agent stream + emitter stream
emitter_stream = agui_parser.agui_events_from_dicts(emitter)
combined = multiplex_streams(agent_stream, emitter_stream)
```

## Stream Processing Pipeline

Full pipeline in `src/soliplex/views/agui.py`:

```python
# 1. Create AG-UI adapter
agui_adapter = await ai_ag_ui.AGUIAdapter.from_request(request=request, agent=agent)

# 2. Create agent dependencies with emitter
agent_deps = AgentDependencies(
    the_installation=installation,
    user=user,
    tool_configs=room_config.tool_configs,
    agui_emitter=AGUIEmitter(thread_id, run_id),
)

# 3. Run agent stream
agent_stream = agui_adapter.run_stream(deps=agent_deps, on_complete=finish_callback)

# 4. Compact consecutive text events
compacted = compact_event_stream(agent_stream)

# 5. Multiplex with emitter events
emitter_stream = agui_events_from_dicts(emitter)
combined = multiplex_streams(compacted, emitter_stream)

# 6. Persist events to database
persisted = tee_events(combined, events_list, on_done=save_events)

# 7. Encode as SSE
sse_stream = agui_adapter.encode_stream(persisted)

# 8. Return streaming response
return StreamingResponse(sse_stream, media_type="text/event-stream")
```

## Client-Side Handling (Flutter)

```dart
await for (final event in aguiStream) {
  switch (event.type) {
    case 'TEXT_MESSAGE_START':
      _startNewMessage(event.messageId);
    case 'TEXT_MESSAGE_CONTENT':
      _appendContent(event.delta);
    case 'TEXT_MESSAGE_END':
      _finalizeMessage();
    case 'TOOL_CALL_START':
      _showToolCall(event.toolName);
    case 'TOOL_CALL_RESULT':
      _showToolResult(event.result);
    case 'RUN_FINISHED':
      _completeRun();
    case 'RUN_ERROR':
      _showError(event.error);
  }
}
```

## OpenAI-Compatible Streaming

For completions endpoint (OpenAI format):

```python
async def stream_chat_responses(agent, deps, prompt, history):
    async with agent.run_stream(
        prompt,
        message_history=history,
        deps=deps,
    ) as response:
        i_chunk = 0
        place = 0

        async for text in response.stream_text():
            send = text[place:]
            yield openai_chunk_repr(agent.model.model_name, i_chunk, send)
            place = len(text)
            i_chunk += 1

    yield "data: [DONE]\n\n"
```

## Error Handling

```python
try:
    async with agent.run_stream(prompt, deps=deps) as response:
        async for text in response.stream_text():
            yield text
except Exception as e:
    yield RUN_ERROR_event(str(e))
```

## Best Practices

1. **Always use context manager** - `async with agent.run_stream()` ensures cleanup
2. **Handle cancellation** - Clients may disconnect mid-stream
3. **Persist events** - Save events for replay/debugging
4. **Compact when possible** - Reduce network overhead
5. **Include run lifecycle** - Send RUN_STARTED and RUN_FINISHED events

## Source Code

- AG-UI endpoint: `src/soliplex/views/agui.py`
- Completions streaming: `src/soliplex/views/completions.py`
