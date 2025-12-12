# App Features Tracking

This document tracks planned, in-progress, and completed features for the agui_dash_2 Flutter application.

## Planned Features

(None currently)

---

## In Progress

(None currently)

---

## Completed

### 1. Text-Oriented Changes

**Status**: Completed

**Description**: Enhanced text handling in chat with selection, copy, search, and quote reply features for power users.

**Implementation Details**:

Files created:
- `lib/features/chat/widgets/code_block_widget.dart` - Code block rendering with copy buttons and quote support
- `lib/features/chat/widgets/chat_search_bar.dart` - Search bar UI
- `lib/core/services/chat_search_service.dart` - Search state management

Files modified:
- `lib/features/chat/chat_content.dart` - Integrated all text features

**Features**:
- **Selectable text** - All message text is now selectable
- **Copy button** - Far-right of feedback row copies entire message
- **Cmd+K paste** - Keyboard shortcut to paste into input
- **Code block copy** - Individual copy button per ``` fenced code block
- **Search (Cmd+F)** - Search bar with match navigation (prev/next)
- **Quote reply** - Select text, right-click "Quote" to insert as `> quoted text`

**Keyboard Shortcuts**:
- `Cmd+K` - Paste from clipboard
- `Cmd+F` - Open search bar

---

### 2. Room Notes Pad

**Status**: Completed

**Description**: A notepad button in the app bar that opens a markdown editor for keeping notes. Notes are persisted per-room to local files.

**Implementation Details**:

Files created:
- `lib/features/notes/notes_service.dart` - File I/O with Riverpod StateNotifier
- `lib/features/notes/notes_dialog.dart` - Dialog UI with text editor, save/close buttons

Files modified:
- `lib/features/chat/chat_screen.dart` - Added notepad icon button to app bar actions
- `pubspec.yaml` - Added `path_provider` dependency

**Features**:
- Notepad icon button in app bar (only visible when room is selected)
- Opens dialog with monospace text editor
- Auto-saves on close
- Manual save button with "Unsaved" indicator
- Error handling with visual feedback
- Notes persisted to `{documents}/soliplex_notes/{room_id}.md`

---

### 3. Activity Status Indicator

**Status**: Completed

**Description**: Animated status indicator showing personality-driven messages during response generation. Displays cycling messages based on AG-UI events and tool calls.

**Implementation Details**:

Files created:
- `lib/core/models/activity_status_config.dart` - Configuration model with default personality messages and support for event/tool-specific messages
- `lib/core/services/activity_status_service.dart` - StateNotifier managing activity state, timers, and message cycling

Files modified:
- `lib/features/chat/chat_content.dart` - Integration: event handling in `_processEvent()`, overlay widget in `build()`, includes `_ActivityDots` widget

**Features**:
- Pulsing dots animation (like typing indicator)
- Smooth text transitions with fade + slide
- Event-driven messages (Thinking, TextMessageStart, ToolCallStart)
- Tool-specific messages (e.g., "Finding your location..." for get_location)
- Time-based cycling (configurable interval, default 3s)
- Initial delay before showing first message (default 500ms)
- Client API for injecting custom status messages
- Stop button (non-functional placeholder, ready for future implementation)

**Configuration**:
```dart
// Default messages configured in ActivityStatusConfig.defaultConfig
idleMessages: ['Thinking...', 'Processing your request...', ...]
eventMessages: {'Thinking': ['Deep in thought...'], ...}
toolMessages: {'get_location': ['Finding your location...'], ...}

// Inject custom message at runtime
ref.read(activityStatusProvider.notifier).injectMessage(
  'Analyzing your data...',
  duration: const Duration(seconds: 2),
);
```

**UI Location**: Overlays the chat input area when active (replaces input field with status + stop button)

---

### 4. Response Feedback Chips

**Status**: Completed

**Description**: Added feedback chips to assistant message cards allowing users to rate responses with thumbs up/down and provide optional comments.

**Implementation Details**:

Files created:
- `lib/features/chat/widgets/feedback_dialog.dart` - Dialog for collecting feedback with rating toggle and comment field
- `lib/features/chat/widgets/message_feedback_chips.dart` - Thumbs up/down chip buttons displayed below assistant messages
- `lib/core/services/feedback_service.dart` - Service for persisting feedback to local JSON files

Files modified:
- `lib/features/chat/chat_content.dart` - Added `MessageFeedbackChips` to assistant messages in `messageTextBuilder`
- `lib/features/chat/chat_screen.dart` - Initialize `feedbackProvider` when room is selected

**Storage**:
- Feedback stored per-room in: `{documents}/soliplex_feedback/{room_id}.json`
- Format: JSON with rating, comment, messageId, timestamp

**UI Behavior**:
- Thumbs up/down buttons appear below all finalized assistant text and GenUI messages
- Clicking a button opens feedback dialog with rating pre-selected
- Can toggle rating by clicking same button again (removes feedback)
- Comment indicator icon shown if feedback includes a comment
- Feedback persists across sessions

---

## Notes

- Features should be implemented incrementally
- Each feature should have tests where appropriate
- Update this document as features progress through stages
