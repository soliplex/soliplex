# AG-UI Frontend-Backend Alignment Specification

## Executive Summary

The `docs/llm/agui.md` documentation accurately describes the **backend API** but does not reflect the **current frontend implementation gaps**. Specifically, the frontend cannot yet:
- Load and display historical threads when clicked
- Reconstruct conversation history from prior runs

This spec documents the gaps and provides implementation requirements.

---

## Current State Analysis

### What Works

| Feature | Backend | Frontend |
|---------|---------|----------|
| Create thread | ✅ | ✅ |
| Execute run with SSE | ✅ | ✅ |
| Create subsequent runs | ✅ | ✅ |
| Store run_input per run | ✅ | N/A |
| List threads in room | ✅ | ✅ |
| Display thread list UI | N/A | ✅ |
| Accumulate messages within session | N/A | ✅ |

### What's Missing

| Feature | Backend | Frontend | Gap |
|---------|---------|----------|-----|
| Load thread history on click | ✅ Ready | ❌ TODO | Frontend needs implementation |
| Reconstruct messages from runs | ✅ Data available | ❌ Missing | No reconstruction logic |
| Resume thread with history | ✅ API exists | ❌ Partial | Thread selected but messages not loaded |
| Display assistant responses from history | ✅ Stored in run_input | ❌ Missing | Only user messages extractable currently |

---

## Backend Data Model (Verified)

### Message Accumulation Pattern

The backend stores **cumulative message history** in each run's `run_input.messages`:

```
Thread: b4593511-4444-447f-a904-c133482d1c76
├── Run 1 (created: 19:27:13)
│   └── run_input.messages: [
│         {role: "user", content: "Tell me a joke about cats"}
│       ]
│
└── Run 2 (created: 19:27:56)
    └── run_input.messages: [
          {role: "user", content: "Tell me a joke about cats"},
          {role: "assistant", content: "Here's a quick one..."},
          {role: "user", content: "Now tell me one about dogs"}
        ]
```

**Key insight**: The latest run's `run_input.messages` contains the **complete conversation history** up to that point.

### What's NOT Stored in run_input

The `run_input.messages` only contains messages that were **sent TO the agent**. It does NOT include:
- The assistant's response from that run (streamed via SSE events)
- Tool call results that were handled server-side

**Implication**: To reconstruct a complete conversation, the frontend must:
1. Get `run_input.messages` from the latest run
2. Fetch or reconstruct the assistant's final response from that run

---

## Gap Analysis

### Gap 1: Thread Click Handler (Critical)

**File**: `src/flutter/lib/features/layouts/threecol_layout.dart:315-327`

**Current code**:
```dart
onTap: () async {
  ref.read(threadHistoryProvider(params).notifier)
      .selectThread(thread.threadId);
  connectionManager.clearMessages(roomId);
  // TODO(dev): Load thread history from server
},
```

**Required**: Implement thread history loading.

### Gap 2: Message Reconstruction Logic (Critical)

**Missing entirely**. No code exists to:
1. Fetch thread details: `GET /rooms/{room_id}/agui/{thread_id}`
2. Extract runs and sort by creation time
3. Get messages from the latest run's `run_input`
4. Load messages into RoomSession

### Gap 3: Assistant Response Recovery (Important)

The backend stores `run_input` (what was sent TO the agent) but the GET endpoint returns `events: null`. This means:
- User messages: ✅ Available in `run_input.messages`
- Assistant messages: ⚠️ Only available if client sent them in subsequent run's `run_input`

**Current behavior**: If a conversation has N runs, runs 2..N contain previous assistant responses in their `run_input.messages`. Run N's assistant response is NOT stored.

**Options**:
1. Store events in backend (increases storage, enables full replay)
2. Accept that the final assistant response is lost on page refresh (current implicit behavior)
3. Add a new endpoint to fetch reconstructed conversation

### Gap 4: Thread Metadata Display (Minor)

Thread titles are stored in `metadata.name` but the UI shows "Thread {index}" as placeholder.

---

## Implementation Specification

### Phase 1: Basic Thread History Loading

#### 1.1 Add ThreadHistoryService.fetchThreadDetails()

```dart
/// Fetch full thread details including all runs
Future<ThreadDetails?> fetchThreadDetails(String threadId) async {
  final uri = _urlBuilder.threadDetails(roomId, threadId);
  final response = await _transportLayer.get(uri);

  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return ThreadDetails.fromJson(data);
  }
  return null;
}
```

#### 1.2 Add ThreadDetails Model

```dart
class ThreadDetails {
  final String threadId;
  final String roomId;
  final Map<String, RunDetails> runs;
  final DateTime created;
  final ThreadMetadata? metadata;

  /// Get messages from the latest run's run_input
  List<Message> get reconstructedMessages {
    if (runs.isEmpty) return [];

    final sortedRuns = runs.values.toList()
      ..sort((a, b) => a.created.compareTo(b.created));

    final latestRun = sortedRuns.last;
    return latestRun.runInput?.messages ?? [];
  }
}

class RunDetails {
  final String runId;
  final String threadId;
  final DateTime created;
  final RunAgentInput? runInput;
}
```

#### 1.3 Update Thread Click Handler

```dart
onTap: () async {
  // 1. Select thread in UI state
  ref.read(threadHistoryProvider(params).notifier)
      .selectThread(thread.threadId);

  // 2. Fetch thread details
  final details = await ref
      .read(threadHistoryProvider(params).notifier)
      .fetchThreadDetails(thread.threadId);

  if (details == null) return;

  // 3. Reconstruct messages
  final messages = details.reconstructedMessages
      .map((m) => ChatMessage.fromAgUiMessage(m))
      .toList();

  // 4. Load into session
  connectionManager.loadMessages(roomId, messages);

  // 5. Initialize session with existing thread
  await connectionManager.initializeWithThread(
    roomId: roomId,
    threadId: thread.threadId,
  );
},
```

#### 1.4 Add RoomSession.initializeWithThread()

```dart
/// Initialize session with an existing thread (for history loading)
Future<void> initializeWithThread({
  required String threadId,
}) async {
  // Create a new run in the existing thread
  final response = await transport.post(
    _urlBuilder.createRun(roomId, threadId),
    {},
  );

  final runId = response['run_id'] as String;
  _activeRunId = runId;

  // Create Thread instance with existing ID
  _thread = Thread(id: threadId, runAgent: runAgentDelegate);

  // Load the reconstructed message history into thread
  for (final msg in _messages) {
    _thread!.messageHistory.add(msg.toAgUiMessage());
  }

  _state = SessionState.active;
}
```

---

### Phase 2: Full Conversation Reconstruction

#### 2.1 Backend: Store Events (Optional)

If full replay is needed, modify `src/soliplex/agui/persistence.py` to store events:

```python
class Run(Base):
    # ... existing fields ...
    events: Mapped[list[dict]] = mapped_column(JSON, default=list)
```

And update the run execution to persist events as they stream.

#### 2.2 Backend: Add Conversation Reconstruction Endpoint (Recommended)

```python
@router.get("/rooms/{room_id}/agui/{thread_id}/conversation")
async def get_thread_conversation(room_id: str, thread_id: str):
    """Return the reconstructed conversation for a thread.

    Assembles messages from all runs, deduplicates, and includes
    assistant responses where available.
    """
    thread = await get_thread(room_id, thread_id)

    # Sort runs by creation time
    sorted_runs = sorted(thread.runs.values(), key=lambda r: r.created)

    # Get messages from latest run (contains all prior messages)
    if sorted_runs:
        latest_run = sorted_runs[-1]
        messages = latest_run.run_input.messages if latest_run.run_input else []
    else:
        messages = []

    return {"messages": messages}
```

---

### Phase 3: Enhanced UX

#### 3.1 Thread Title Generation

Auto-generate thread titles from first user message:

```python
# Backend: In thread creation
metadata = AGUI_ThreadMetadata(
    name=truncate(first_message.content, 50),
    description=None
)
```

#### 3.2 Loading States

Add loading indicator while fetching thread history:

```dart
// In thread click handler
setState(() => _isLoadingHistory = true);
try {
  // ... fetch and load ...
} finally {
  setState(() => _isLoadingHistory = false);
}
```

#### 3.3 Error Handling

Handle cases where thread no longer exists or is corrupted:

```dart
if (details == null) {
  showSnackBar('Could not load thread history');
  ref.read(threadHistoryProvider(params).notifier).removeThread(threadId);
  return;
}
```

---

## API Alignment Checklist

### Existing Endpoints (Verified Working)

- [x] `GET /rooms/{room_id}/agui` - List threads
- [x] `POST /rooms/{room_id}/agui` - Create thread
- [x] `GET /rooms/{room_id}/agui/{thread_id}` - Get thread with runs
- [x] `POST /rooms/{room_id}/agui/{thread_id}` - Create run
- [x] `POST /rooms/{room_id}/agui/{thread_id}/{run_id}` - Execute run (SSE)

### Endpoints Needing Frontend Integration

- [ ] `GET /rooms/{room_id}/agui/{thread_id}` - **Used for history loading**
- [ ] `POST /rooms/{room_id}/agui/{thread_id}/meta` - Thread metadata updates

### Suggested New Endpoints

- [ ] `GET /rooms/{room_id}/agui/{thread_id}/conversation` - Reconstructed conversation
- [ ] `DELETE /rooms/{room_id}/agui/{thread_id}` - Delete thread (if not exists)

---

## Documentation Updates Required

Update `docs/llm/agui.md` to add:

1. **Message Accumulation Pattern** section explaining how `run_input.messages` grows
2. **Thread History Reconstruction** section with algorithm
3. **Frontend Implementation Status** section noting current gaps
4. **Conversation Reconstruction** section once implemented

---

## Priority Order

1. **P0 (Critical)**: Thread click loads history (Phase 1.1-1.4)
2. **P1 (Important)**: Backend conversation endpoint (Phase 2.2)
3. **P2 (Nice-to-have)**: Event storage for full replay (Phase 2.1)
4. **P3 (Polish)**: Thread titles, loading states (Phase 3)
