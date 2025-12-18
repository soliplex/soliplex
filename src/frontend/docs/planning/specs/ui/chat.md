# Chat

Displays messages for the current thread, handles input, shows agent activity.

## Scope

- Thread-scoped (changes when thread changes)
- Shows streaming responses in real-time
- Displays agent activity ("Thinking...", "Calling tool...")

## Provider Integration

```dart
final room = ref.watch(currentRoomProvider);
final thread = ref.watch(currentThreadProvider);
final historyAsync = ref.watch(threadMessagesProvider(thread?.id ?? ''));
final runState = ref.watch(activeRunProvider);

// Merged messages for display
final allMessages = [...historyAsync.valueOrNull ?? [], ...runState.messages];
```

## Can Send Logic

| Room | Threads Exist | Thread Selected | New Intent | Can Send? | Action |
|------|---------------|-----------------|------------|-----------|--------|
| None | - | - | - | No | - |
| Selected | No | No | No | **Yes** | Create thread |
| Selected | Yes | No | No | No | - |
| Selected | Yes | No | **Yes** | **Yes** | Create thread |
| Selected | Yes | Yes | - | Yes | Use selected |

## UI States

| State | Display |
|-------|---------|
| No room | "Select a room to start chatting" |
| Room has threads, none selected | "Select a conversation from the list" |
| New intent set | "Start a new conversation" |
| Running | Message list + activity indicator + cancel button |
| Error | Error message + retry option |

## Message Display

- User: right-aligned, colored background
- Assistant: left-aligned, different background
- Streaming: typing cursor while `isStreaming == true`
- Support markdown, code blocks with syntax highlighting

## Actions

- **Copy**: Copy message to clipboard
- **Pin**: Add to permanent canvas (future)

## Keyboard Shortcuts (Desktop)

- Enter: Send
- Shift+Enter: New line
- Escape: Cancel

## Implementation Phases

| Phase | Goal |
|-------|------|
| 1 | Basic chat: message list, input, send |
| 2 | Streaming, activity indicator, input states, cancel |
| 3 | Markdown, code blocks, auto-scroll, keyboard shortcuts |
