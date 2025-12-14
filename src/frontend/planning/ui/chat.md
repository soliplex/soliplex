# Chat

The chat component displays messages between the user and the AI agent, handles message input, and shows agent activity status.

## Scope

- Displays messages for the **current thread**
- When thread changes, loads message history and resets active run state
- Shows streaming responses in real-time
- Displays agent activity ("Thinking...", "Calling tool...")

## Provider Integration

The chat component consumes these providers from core_frontend:

```dart
// Current context
final room = ref.watch(currentRoomProvider);
final thread = ref.watch(currentThreadProvider);

// Message history (past messages for this thread)
final historyAsync = ref.watch(threadMessagesProvider(thread?.id ?? ''));

// Active run state (current streaming response)
final runState = ref.watch(activeRunProvider);

// To send messages
final runNotifier = ref.read(activeRunProvider.notifier);
```

### Combined Message List

```dart
// Merge history with current run messages for display
final allMessages = [
  ...historyAsync.valueOrNull ?? [],
  ...runState.messages,
];
```

### Can Send Logic

Determines when the send button should be enabled:

```dart
bool get canSend {
  final room = ref.watch(currentRoomProvider);
  final thread = ref.watch(currentThreadProvider);
  final threads = ref.watch(threadsProvider);
  final runState = ref.watch(activeRunProvider);
  final newThreadIntent = ref.watch(newThreadIntentProvider);

  if (room == null) return false;                    // No room
  if (runState.status == RunStatus.running) return false; // Already running
  if (thread != null) return true;                   // Thread selected
  if (newThreadIntent) return true;                  // User wants new thread

  // No thread selected - only allow if room has no threads
  return threads.valueOrNull?.isEmpty ?? true;
}
```

| Room | Threads Exist | Thread Selected | New Intent | Can Send? | Action on Send |
|------|---------------|-----------------|------------|-----------|----------------|
| None | - | - | - | No | - |
| Selected | No | No | No | **Yes** | Create thread |
| Selected | Yes | No | No | No | - (require selection) |
| Selected | Yes | No | **Yes** | **Yes** | Create thread |
| Selected | Yes | Yes | - | Yes | Use selected |

## UI States

### Empty States

| Condition | Message | Input |
|-----------|---------|-------|
| No room selected | "Select a room to start chatting" | Disabled |
| Room has threads, none selected | "Select a conversation from the list" | Disabled |
| Room has threads, new intent set | "Start a new conversation" | Enabled |
| Room empty (no threads) | "Start a new conversation" | Enabled |
| Thread selected, no messages | Welcome message or prompt | Enabled |

### Loading History

- Show loading indicator
- Input field disabled

### Idle (Has Messages)

- Show message list
- Input field enabled

### Running (Agent Responding)

- Show message list with streaming message
- Show activity indicator (e.g., "Thinking...")
- Input field disabled
- Show cancel button

### Error

- Show error message with retry option
- Input field enabled

## Message Display

### Text Messages

- User messages: right-aligned, colored background
- Assistant messages: left-aligned, different background
- Support markdown rendering
- Code blocks with syntax highlighting

### Streaming Messages

While `message.isStreaming == true`:

- Show typing cursor or animation at end of text
- Text appears progressively as content arrives

### Media Messages (Future)

For `MessageType.image`, `audio`, `video`, `file`:

- Show appropriate preview/player
- Show download option

### Tool Calls (Optional)

When agent calls a tool:

- Can show collapsible "Called {toolName}" indicator
- Or just show activity in status area

## Activity Indicator

Display `runState.activity` when not null:

```text
┌─────────────────────────────────┐
│  🔄 Thinking...                 │
│  🔧 Calling search_documents... │
│  📝 Writing response...         │
└─────────────────────────────────┘
```

Position: Above input field or below last message.

## Input Area

### Components

- Text input field (multiline)
- Send button
- (Optional) Attachment button for file upload

### States

| State | Input | Send Button |
|-------|-------|-------------|
| No room selected | Disabled | Disabled |
| Room has threads, none selected | Disabled | Disabled |
| Room empty, no thread | Enabled | Enabled (if text not empty) |
| Thread selected, idle | Enabled | Enabled (if text not empty) |
| Running | Disabled | Hidden, show Cancel instead |
| Error | Enabled | Enabled |
| Loading History | Disabled | Disabled |

### Send Action

```dart
void onSend(String content) async {
  if (!canSend || content.trim().isEmpty) return;

  final roomId = ref.read(currentRoomProvider)!.id;
  final threadId = ref.read(currentThreadProvider)?.id;

  // sendMessage creates thread if threadId is null, returns the thread
  final thread = await ref.read(activeRunProvider.notifier)
      .sendMessage(roomId, threadId, content);

  // Update last used thread for this room
  await ref.read(lastThreadStorageProvider).setLastThread(roomId, thread.id);

  // If thread was just created, select it and refresh list
  if (threadId == null) {
    ref.read(currentThreadProvider.notifier).state = thread;
    ref.invalidate(threadsProvider);
  }

  // Clear new thread intent (if it was set)
  ref.read(newThreadIntentProvider.notifier).state = false;

  // Clear input field
  textController.clear();
}
```

### Cancel Action

```dart
void onCancel() {
  ref.read(activeRunProvider.notifier).cancel();
}
```

## Message Actions

On hover (desktop) or long-press (mobile), show actions:

| Action | Description |
|--------|-------------|
| Copy | Copy message text to clipboard |
| Pin to Canvas | Add to permanent canvas (future) |

## Thread Switching

When `currentThreadProvider` changes:

1. Call `runNotifier.reset()` to clear active run state
2. `threadMessagesProvider` automatically loads new history
3. Scroll to bottom of message list

## Keyboard Shortcuts (Desktop)

| Shortcut | Action |
|----------|--------|
| Enter | Send message (if not empty) |
| Shift+Enter | New line in input |
| Escape | Cancel running request |

## Implementation Notes

### Build Custom vs Library

**Recommendation: Build custom.**

The suggested libraries (`flutter_chat_ui`, `dash_chat_2`) are designed for traditional chat and don't handle:

- Streaming text (character-by-character)
- Activity indicators
- AG-UI event integration

A custom implementation with `ListView.builder` and `StreamBuilder` will integrate better with the Riverpod state.

### Scrolling Behavior

- Auto-scroll to bottom when new messages arrive
- Don't auto-scroll if user has scrolled up (reading history)
- Show "scroll to bottom" button when not at bottom

### Performance

- Use `ListView.builder` for large message lists
- Consider message virtualization for very long threads

## Dependencies

```yaml
dependencies:
  flutter_markdown: ^0.7.0      # Markdown rendering
  # Or use: markdown_widget, flutter_html
```

## Implementation Plan

### Phase 1: Basic Chat

**Goal:** User can see messages and send new ones.

- Create `ChatScreen` widget that consumes `activeRunProvider`
- Build `MessageList` with `ListView.builder`
- Create `MessageBubble` widget (user vs assistant styling)
- Build `ChatInput` widget with text field and send button
- Wire up `onSend` to call `sendMessage()`
- Display basic text messages (no markdown yet)
- Write widget test for message list rendering

**Verification:**
```bash
flutter analyze
flutter test test/ui/chat/
```

**Acceptance criteria:**
- [ ] User can type and send messages
- [ ] Messages display in list
- [ ] Response appears after sending
- [ ] `flutter analyze` passes
- [ ] Test coverage >= 90% for new code

**Done when:** User can type a message, send it, and see the response appear.

---

### Phase 2: Streaming & States

**Goal:** Streaming feels responsive, UI states are clear.

- Show streaming messages with cursor/animation while `isStreaming == true`
- Display activity indicator when `runState.activity` is set
- Implement input states (disabled while running)
- Add cancel button during running state
- Handle error state display with retry option
- Implement loading state while fetching history
- Implement empty state for new threads
- Write widget test for activity indicator
- Write widget test for input states

**Verification:**
```bash
flutter analyze
flutter test test/ui/chat/
```

**Acceptance criteria:**
- [ ] Streaming messages show cursor animation
- [ ] Activity indicator displays during agent work
- [ ] Input disabled while running
- [ ] Cancel button works
- [ ] Error and loading states display correctly
- [ ] `flutter analyze` passes
- [ ] Test coverage >= 90% for new code

**Done when:** User sees "Thinking..." while agent works, streaming text appears smoothly, can cancel a request.

---

### Phase 3: Polish

**Goal:** Full-featured, production-ready chat.

- Add markdown rendering with `flutter_markdown`
- Add code block syntax highlighting
- Implement auto-scroll (scroll to bottom on new messages)
- Add "scroll to bottom" button when scrolled up
- Implement thread switching (reset state, load history)
- Add keyboard shortcuts (Enter to send, Escape to cancel)
- Add message actions (copy to clipboard)
- Handle long messages gracefully
- Write remaining widget tests
- Test on mobile (touch interactions)

**Verification:**
```bash
flutter analyze
dart format --set-exit-if-changed lib/ test/
flutter test
flutter test --coverage
```

**Documentation:**
- Update CLAUDE.md with Chat component file structure
- Document message rendering patterns and streaming behavior

**Acceptance criteria:**
- [ ] Markdown renders correctly
- [ ] Code blocks have syntax highlighting
- [ ] Auto-scroll works on new messages
- [ ] Keyboard shortcuts work (Enter, Escape)
- [ ] Copy to clipboard works
- [ ] `flutter analyze` passes with no warnings
- [ ] `dart format` reports no changes
- [ ] All tests pass
- [ ] Overall test coverage >= 85%
- [ ] CLAUDE.md updated

**Done when:** Chat feels polished, keyboard shortcuts work, markdown renders correctly. CLAUDE.md updated.

---

### Future (Not in v1)

- Media message display (images, files)
- Pin to canvas action
- Tool call visualization (collapsible indicators)
- Message search

## Testing

- Widget test: renders message list correctly
- Widget test: send button states (enabled/disabled)
- Widget test: activity indicator display
- Widget test: streaming message with cursor
- Widget test: error state with retry
- Unit test: message list merging (history + run)

### Coverage Requirements

- **Per phase:** >= 90% coverage for new code
- **Overall (Phase 3):** >= 85% total coverage
- **CI gate:** Tests must pass before merge

### Verification Commands

```bash
# Lint (run after each phase)
flutter analyze
dart format --set-exit-if-changed lib/ test/

# Tests (run after each phase)
flutter test test/ui/chat/

# Full test suite (run before PR)
flutter test

# Coverage report
flutter test --coverage
genhtml coverage/lcov.info -o coverage/html
open coverage/html/index.html
```
