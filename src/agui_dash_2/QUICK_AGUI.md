# Quick AG-UI Architecture

This document describes the `quick_agui` infrastructure used in `agui_dash_2` for AG-UI protocol communication.

## Overview

The `quick_agui` module provides a clean separation of concerns for AG-UI client communication:

```
┌─────────────────────────────────────────────────────────────┐
│                      AgUiService                            │
│  - Manages configuration (baseUrl, roomId)                  │
│  - Creates threads and runs via HTTP                        │
│  - Registers tools with Thread                              │
│  - Handles tool result loop                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                        Thread                               │
│  - Maintains message history                                │
│  - Processes SSE events from ag_ui.AgUiClient               │
│  - Manages tool call registry                               │
│  - Executes client tools via pluggable executors            │
│  - Exposes reactive streams for UI                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  Message  │  │   State   │  │   Steps   │
│  Stream   │  │  Stream   │  │  Stream   │
└───────────┘  └───────────┘  └───────────┘
```

## Core Components

### Thread (`lib/infrastructure/quick_agui/thread.dart`)

The Thread class is the core abstraction for an AG-UI conversation.

**Responsibilities:**
- Maintains `messageHistory` list of all messages in the conversation
- Processes SSE events from `ag_ui.AgUiClient.runAgent()`
- Tracks pending and completed tool calls via `ToolCallRegistry`
- Auto-executes client-side tools using pluggable `ToolExecutor` callbacks
- Exposes broadcast streams for reactive UI updates

**Key Properties:**
```dart
final String id;                           // Thread ID from server
final ag_ui.AgUiClient client;             // AG-UI SSE client
final List<ag_ui.Message> messageHistory;  // All messages
ag_ui.State? currentState;                 // Latest state snapshot
```

**Streams (all broadcast):**
```dart
Stream<ag_ui.Message> messageStream;   // User and assistant messages
Stream<ag_ui.State> stateStream;       // State snapshots/deltas
Stream<ag_ui.BaseEvent> stepsStream;   // All AG-UI events (for UI)
```

**Tool Registration:**
```dart
void addTool(ag_ui.Tool tool, ToolExecutor executor);
void removeTool(String toolName);
```

**Run Lifecycle:**
```dart
// Start a run, returns tool results that need to be sent back
Future<List<ag_ui.ToolMessage>> startRun({
  required String endpoint,
  required String runId,
  List<ag_ui.Message>? messages,
  dynamic state,
});

// Send tool results and continue
Future<List<ag_ui.ToolMessage>> sendToolResults({
  required String endpoint,
  required String runId,
  required List<ag_ui.ToolMessage> toolMessages,
});
```

### Helper Classes

#### TextMessageBuffer (`text_message_buffer.dart`)

Accumulates streamed text content by messageId.

```dart
class TextMessageBuffer {
  final String messageId;
  void add(String id, String content);  // Validates messageId matches
  String get content;                    // Returns accumulated text
}
```

Used to buffer `TextMessageContentEvent` deltas until `TextMessageEndEvent`.

#### ToolCallReceptionBuffer (`tool_call_reception_buffer.dart`)

Buffers streamed tool call arguments.

```dart
class ToolCallReceptionBuffer {
  final String id;
  final String name;
  void appendArgs(String delta);
  String get args;                    // Raw JSON string
  ag_ui.ToolCall get toolCall;        // Parsed ToolCall object
  ag_ui.AssistantMessage get message; // Wrapped in AssistantMessage
}
```

Used to buffer `ToolCallArgsEvent` deltas until `ToolCallEndEvent`.

#### ToolCallRegistry (`tool_call_registry.dart`)

Tracks pending and completed tool calls.

```dart
class ToolCallRegistry {
  void register(ToolCall call);
  void markCompleted(String toolCallId, ToolMessage message);
  Iterable<ToolCall> get pendingCalls;
  Iterable<ToolMessage> get results;
  void clear();
}
```

Separates tool calls into:
- **Pending**: Client tools that need execution
- **Completed**: Tools with results (either from server or client execution)

## Event Processing Flow

### 1. Text Message Events

```
TextMessageStartEvent → create TextMessageBuffer
TextMessageContentEvent → buffer.add(delta)
TextMessageEndEvent → create AssistantMessage, add to history
```

### 2. Tool Call Events

```
ToolCallStartEvent → create ToolCallReceptionBuffer
ToolCallArgsEvent → buffer.appendArgs(delta)
ToolCallEndEvent →
  - Add AssistantMessage with tool_calls to history
  - If client tool: register in ToolCallRegistry as pending
```

### 3. Tool Execution

After SSE stream ends, Thread checks for pending client tools:

```dart
final pendingToolCalls = _toolRegistry.pendingCalls;
if (pendingToolCalls.isNotEmpty) {
  final results = await _executeClientTools(pendingToolCalls.toList());
  return results;  // Caller should send these back to server
}
```

### 4. State Events

```
StateSnapshotEvent → replace currentState, emit on stateStream
StateDeltaEvent → merge delta into currentState (simplified)
```

## AgUiService Integration

The `AgUiService` wraps Thread and handles:

1. **Configuration**: baseUrl, roomId, headers
2. **Thread/Run Creation**: HTTP POST to create thread and runs
3. **Tool Registration**: Registers `LocalToolsService` tools with Thread
4. **Tool Result Loop**: Sends tool results back until no more pending

### chat() Method

Main entry point for sending messages:

```dart
Future<void> chat(
  String userMessage, {
  required LocalToolsService localToolsService,
  required void Function(ag_ui.BaseEvent event) onEvent,
}) async {
  // 1. Create thread if needed (POST to /rooms/{room}/agui)
  // 2. Register tools with thread
  // 3. Subscribe to stepsStream for UI updates
  // 4. Call thread.startRun()
  // 5. Loop: while toolResults.isNotEmpty, create new run and send results
}
```

## Tool Executor Pattern

Tools are registered with a callback that receives the `ToolCall` and returns a JSON string result:

```dart
typedef ToolExecutor = Future<String> Function(ag_ui.ToolCall call);

_thread.addTool(agTool, (call) async {
  final args = jsonDecode(call.function.arguments);
  final result = await localToolsService.executeTool(call.id, call.function.name, args);
  return jsonEncode(result.success ? result.result : {'error': result.error});
});
```

## Important Design Decisions

### 1. Mutable Lists for Tools

Thread constructor creates mutable copies of tool lists:

```dart
Thread({...})
  : _tools = tools != null ? List.from(tools) : <ag_ui.Tool>[],
    _toolExecutors = toolExecutors != null ? Map.from(toolExecutors) : {};
```

**Why**: Default `const []` parameters are unmodifiable; `addTool()` would fail.

### 2. Broadcast Streams

All streams are broadcast (`StreamController.broadcast()`):

**Why**: Multiple listeners may need the same events (UI components, logging, etc.)

### 3. Tool Result Loop in Caller

`startRun()` returns pending tool results rather than looping internally:

**Why**:
- Caller controls when/if to continue
- Each continuation needs a new run ID (HTTP POST)
- Allows caller to update UI between iterations

### 4. Client Tool Detection

```dart
final isClientTool = _tools.any((t) => t.name == toolCall.function.name);
if (isClientTool) {
  _toolRegistry.register(toolCall);
}
```

**Why**: Only tools registered with Thread are client tools. Server tools have results sent via `ToolCallResultEvent`.

## Concurrency Considerations

### Location Permission Lock

The `LocalToolsService` uses a lock for location permission requests:

```dart
bool _locationPermissionInProgress = false;
Completer<LocationPermission>? _permissionCompleter;
```

**Why**: `Geolocator.requestPermission()` throws if called while another request is in progress. Multiple tool calls can happen concurrently.

### Widget Disposal in Async Streams

When processing events in Flutter widgets:

```dart
// WRONG - ref may be invalid after await
await for (final event in events) {
  ref.read(someProvider.notifier).doSomething();  // May throw!
}

// CORRECT - capture before async loop
final notifier = ref.read(someProvider.notifier);
await for (final event in events) {
  if (!mounted) break;
  notifier.doSomething();
}
```

**Why**: Widget may be disposed during async iteration; `ref` becomes invalid.

## State Delta Handling

Current implementation uses simple merge:

```dart
case ag_ui.StateDeltaEvent(delta: final deltas):
  if (currentState is Map<String, dynamic>) {
    final current = currentState as Map<String, dynamic>;
    for (final delta in deltas) {
      if (delta is Map<String, dynamic>) {
        current.addAll(delta);
      }
    }
  }
```

**Limitation**: This doesn't handle JSON Patch operations (add, remove, replace, move, copy, test). For full compliance, use the `json_patch` package.

## File Structure

```
lib/infrastructure/quick_agui/
├── thread.dart                    # Core Thread class
├── text_message_buffer.dart       # Text streaming buffer
├── tool_call_reception_buffer.dart # Tool args streaming buffer
└── tool_call_registry.dart        # Pending/completed tool tracking
```

## Usage Example

```dart
// Create client and thread
final client = ag_ui.AgUiClient(
  config: ag_ui.AgUiClientConfig(baseUrl: 'http://localhost:8000/api/v1'),
);

final thread = Thread(id: threadId, client: client);

// Register tools
thread.addTool(
  ag_ui.Tool(name: 'get_location', description: '...', parameters: {...}),
  (call) async => '{"lat": 37.7749, "lng": -122.4194}',
);

// Listen to events
thread.stepsStream.listen((event) => print('Event: $event'));
thread.messageStream.listen((msg) => print('Message: $msg'));

// Start conversation
var toolResults = await thread.startRun(
  endpoint: 'rooms/myroom/agui/$threadId/$runId',
  runId: runId,
  messages: [ag_ui.UserMessage(id: 'msg1', content: 'Hello')],
);

// Handle tool results
while (toolResults.isNotEmpty) {
  final newRunId = await createRun(threadId);
  toolResults = await thread.sendToolResults(
    endpoint: 'rooms/myroom/agui/$threadId/$newRunId',
    runId: newRunId,
    toolMessages: toolResults,
  );
}
```

## Lessons Learned & Known Issues

This section documents design issues discovered during development and the fixes applied.

### 1. Single Shared Text Buffer (Fixed)

**Problem**: Thread originally used a single `_textBuffer` instance for all text messages:
```dart
var _textBuffer = TextMessageBuffer('');
```

When concurrent text messages were streamed (e.g., multiple tool calls triggering responses), they would overwrite each other's buffer content, causing corrupted/mixed text.

**Fix**: Changed to a Map keyed by messageId:
```dart
final Map<String, TextMessageBuffer> _textBuffers = {};

case ag_ui.TextMessageStartEvent(messageId: final msgId):
  _textBuffers[msgId] = TextMessageBuffer(msgId);

case ag_ui.TextMessageContentEvent(messageId: final msgId, delta: final text):
  _textBuffers[msgId]?.add(msgId, text);

case ag_ui.TextMessageEndEvent(messageId: final msgId):
  final buffer = _textBuffers.remove(msgId);
  // ... use buffer.content
```

### 2. Broadcast Stream Duplicate Subscribers (Fixed)

**Problem**: When `chat()` was called multiple times before the first completed, each call created a new subscription to `stepsStream` (a broadcast stream). All subscribers received ALL events, causing duplicate message processing.

**Fix**: Added a mutex lock in `AgUiService.chat()` to serialize calls:
```dart
Completer<void>? _chatLock;

Future<void> chat(...) async {
  // Wait for any pending chat() to complete
  while (_chatLock != null) {
    await _chatLock!.future;
  }
  _chatLock = Completer<void>();

  try {
    // ... chat logic
  } finally {
    _chatLock!.complete();
    _chatLock = null;
  }
}
```

### 3. Duplicate Tool Registration (Fixed)

**Problem**: `_registerTools()` was called on every `chat()` invocation. Since `addTool()` simply appended to the `_tools` list, duplicate tools accumulated:
```dart
void addTool(ag_ui.Tool tool, ToolExecutor executor) {
  _tools.add(tool);  // Keeps adding duplicates!
  _toolExecutors[tool.name] = executor;
}
```

**Fix**: `addTool()` now removes existing tools with the same name first:
```dart
void addTool(ag_ui.Tool tool, ToolExecutor executor) {
  _tools.removeWhere((t) => t.name == tool.name);
  _tools.add(tool);
  _toolExecutors[tool.name] = executor;
}
```

### 4. Duplicate UI Tool Execution (Fixed)

**Problem**: UI tools (genui_render, canvas_render) could be executed multiple times for the same tool call ID, causing duplicate widgets to appear.

**Fix**: Added deduplication in the UI layer using a Set of processed tool call IDs:
```dart
final Set<String> _processedUiToolCalls = {};

uiToolHandler: (toolCallId, toolName, args) async {
  if (_processedUiToolCalls.contains(toolCallId)) {
    return {'skipped': true, 'reason': 'duplicate'};
  }
  _processedUiToolCalls.add(toolCallId);
  // ... handle tool
}
```

Also required updating the `UiToolHandler` typedef to include `toolCallId`:
```dart
typedef UiToolHandler = Future<Map<String, dynamic>> Function(
  String toolCallId,  // Added for deduplication
  String toolName,
  Map<String, dynamic> args,
);
```

### 5. Single Streaming Message ID in ChatState (Fixed)

**Problem**: `ChatState` tracked only one `currentStreamingMessageId`. When multiple messages streamed concurrently, they all tried to write to the same message.

**Fix**: Changed to track multiple streaming messages:
```dart
// Before
final String? currentStreamingMessageId;

// After
final Set<String> streamingMessageIds;
```

And updated methods to take explicit message IDs:
```dart
// Before
void appendToStreamingMessage(String delta);
void finalizeStreamingMessage();

// After
void appendToStreamingMessage(String messageId, String delta);
void finalizeStreamingMessage(String messageId);
```

### 6. Message ID Mapping for Events (Fixed)

**Problem**: The UI layer used a single `_currentMessageId` variable to track which message was being streamed. With concurrent streams, this caused events from different messages to be applied to the wrong UI message.

**Fix**: Map AG-UI event messageIds to internal chat messageIds:
```dart
final Map<String, String> _messageIdMap = {};  // aguiMessageId -> chatMessageId
final Map<String, StringBuffer> _textBuffers = {};

case ag_ui.TextMessageStartEvent():
  final chatMessageId = chatNotifier.startAgentMessage();
  _messageIdMap[event.messageId] = chatMessageId;
  _textBuffers[event.messageId] = StringBuffer();

case ag_ui.TextMessageContentEvent():
  final chatMessageId = _messageIdMap[event.messageId];
  if (chatMessageId != null) {
    chatNotifier.appendToStreamingMessage(chatMessageId, event.delta);
  }
```

### 7. Cascading Tool Call Loop for UI Tools (Fixed)

**Problem**: When UI-only tools (`genui_render`, `canvas_render`) were called by the LLM, the client would:
1. Execute the tool locally (render widget)
2. Return a result like `{"rendered": true}`
3. Send the tool result back to the server via a new run
4. The LLM would see the minimal result and potentially call the same tool again
5. This created an infinite loop of `RunStarted` → `RunFinished` events:
```
flutter: [AG-UI] RunFinished runId=c71138f4-90dd-46ef-8e73-f8996d6c7a19
flutter: [AG-UI] RunStarted runId=b99b78de-72c5-4c41-8c81-95f0f2a9c894
flutter: [AG-UI] RunFinished runId=b99b78de-72c5-4c41-8c81-95f0f2a9c894
flutter: [AG-UI] RunStarted runId=1195fc7b-6a23-4883-a65a-b6d283f536d7
... (continues indefinitely)
```

**Root Cause**: UI-only tools are "fire and forget" - they render something visually but the LLM doesn't need to know the result. Sending results back caused the LLM to continue the conversation unnecessarily.

**Fix**: Added a `fireAndForget` parameter to `addTool()`:
```dart
// In Thread class
final Set<String> _fireAndForgetTools = {};

void addTool(ag_ui.Tool tool, ToolExecutor executor, {bool fireAndForget = false}) {
  _tools.removeWhere((t) => t.name == tool.name);
  _tools.add(tool);
  _toolExecutors[tool.name] = executor;
  if (fireAndForget) {
    _fireAndForgetTools.add(tool.name);
  }
}

// In _executeAndTrack()
Future<void> _executeAndTrack(ag_ui.ToolCall toolCall, List<ag_ui.ToolMessage> results) async {
  final isFireAndForget = _fireAndForgetTools.contains(toolCall.function.name);

  final result = await _executeClientTool(toolCall);
  final message = ag_ui.ToolMessage(...);

  // Only add to results if NOT fire-and-forget
  if (!isFireAndForget) {
    results.add(message);
  }
  _toolRegistry.markCompleted(toolCall.id, message);
}
```

And in `AgUiService._registerTools()`:
```dart
final isFireAndForget = _uiTools.contains(toolDef.name);  // canvas_render, genui_render
_thread!.addTool(agTool, executor, fireAndForget: isFireAndForget);
```

**Result**: Fire-and-forget tools still execute and render UI, but their results are not sent back to the server. Since `toolResults` is empty, the `while (toolResults.isNotEmpty)` loop exits and the conversation ends normally.

## Design Recommendations

Based on lessons learned:

1. **Always use per-message/per-call state** - Never use single shared buffers for concurrent operations
2. **Include IDs in all callbacks** - Tool handlers, event processors, etc. should receive identifying information for deduplication
3. **Serialize operations when using broadcast streams** - Or filter events by run/message ID
4. **Idempotent tool registration** - `addTool()` should handle being called multiple times with the same tool
5. **Clear state between operations** - Ensure registries, buffers, and trackers are properly cleaned up
6. **Distinguish UI-only vs conversation tools** - Tools that only affect the UI (rendering widgets) should be "fire and forget" - execute locally but don't send results back to the server to avoid infinite loops
