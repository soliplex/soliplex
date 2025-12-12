# App Features Tracking

This document tracks planned, in-progress, and completed features for the agui_dash_2 Flutter application.

## Planned Features

(None currently)

---

## In Progress

### 9. Network Layer Refactoring

**Status**: In Progress (Phase 1 Complete)

**Description**: Refactoring the network layer to support concurrent SSE streams, room session preservation, connection observability, and stop/cancel functionality. Web compatible with pluggable architecture for future native networking.

**Implementation Details**:

See `NETWORK-IMPL.md` for full architectural plan.

Files created (Phase 1):
- `lib/core/network/cancel_token.dart` - Cancellation support for network operations
- `lib/core/network/network_transport.dart` - Abstract interface for pluggable networking
- `lib/core/network/http_transport.dart` - Web-compatible implementation using ag_ui
- `lib/core/network/connection_events.dart` - Event types for observability
- `lib/core/network/room_session.dart` - Per-room state container
- `lib/core/network/connection_manager.dart` - Central hub managing all sessions
- `lib/core/network/network_observer.dart` - Read-only visibility into connections
- `lib/core/network/network.dart` - Barrel export file

Files created (Phase 2):
- `lib/core/services/room_chat_service.dart` - Per-room chat providers (roomChatProvider, activeChatProvider)

Files modified:
- `lib/infrastructure/quick_agui/thread.dart` - Added CancelToken support to startRun()
- `lib/core/utils/debug_log.dart` - Added network logging category
- `lib/features/chat/chat_content.dart` - Stop button, _syncToRoomProvider()
- `lib/features/chat/chat_screen.dart` - Room switching with session preservation

**Completed Phases**:
- [x] Phase 1: Core Infrastructure (transport, session, manager, observer)
- [x] Phase 2: Per-Room State (roomChatProvider family, activeChatProvider)
- [x] Phase 3: Integration (per-room state sync, room switching)
- [x] Phase 4: Stop Button (wired to ConnectionManager.cancelRun)
- [x] Phase 5: Session Preservation (save/restore chat history on room switch)

**Remaining Phases**:
- [ ] Phase 6: Network Observer UI (optional debug panel)

**Architecture**:
```
ConnectionManager (central hub)
    └── Map<roomId, RoomSession>
            └── Thread + ChatHistory + CancelToken
NetworkObserver (read-only visibility)
    └── events stream, connection info
```

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

### 5. Streaming Markdown with Hooks

**Status**: Completed

**Description**: Integrated `flutter_streaming_text_markdown` for streaming AI responses with Claude-style animation. Added extensible hook system for link taps, image completion tracking, code copy events, and text quoting.

**Implementation Details**:

Files created:
- `lib/core/services/markdown_hooks.dart` - Callback registry with typed callbacks (LinkTap, ImageLoad, CodeCopy, Quote, AllImagesLoaded)
- `lib/core/services/image_load_tracker.dart` - Per-message image loading state tracker with Riverpod provider
- `lib/features/chat/widgets/streaming_markdown_widget.dart` - Main wrapper: streaming animation during response, full markdown with callbacks when finalized
- `lib/features/chat/widgets/tracked_markdown_image.dart` - CachedNetworkImage wrapper with load state tracking
- `lib/features/chat/widgets/markdown_code_block.dart` - Custom code block builder with copy button and quote support
- `IMPLEMENTATION_STREAMING_MARKDOWN.md` - Full implementation documentation

Files modified:
- `pubspec.yaml` - Added `flutter_streaming_text_markdown`, `flutter_markdown`, `markdown`, `url_launcher`
- `lib/features/chat/chat_content.dart` - Replaced `MessageTextWithCodeBlocks` with `StreamingMarkdownWidget`
- `lib/features/chat/chat_screen.dart` - Initialize hooks with default behaviors

**Features**:
- **Streaming animation** - Claude-style character-by-character reveal during response streaming
- **Full markdown support** - Headers, lists, blockquotes, links, images, code blocks
- **Link handling** - Opens in external browser (customizable via hooks)
- **Image tracking** - Per-image load/error callbacks + all-images-loaded event per message
- **Code blocks** - Styled with language label, copy button with "Copied!" feedback
- **Quote support** - Context menu on selected text to insert as `> quoted text`
- **Extensible hooks** - Register custom callbacks for link taps, image loads, code copy, etc.

**Hook API**:
```dart
final hooks = ref.read(markdownHooksProvider);

// Custom link handling
hooks.onLinkTap = (href, text, messageId) {
  if (href?.startsWith('internal://') == true) {
    // Handle internally
  } else {
    launchUrl(Uri.parse(href!));
  }
};

// Track all images loaded (useful for auto-scroll)
hooks.onAllImagesLoaded = (messageId) {
  scrollController.animateTo(scrollController.position.maxScrollExtent, ...);
};

// Image load analytics
hooks.onImageLoad = (imageUrl, messageId, state) {
  analytics.track('image_load', {'url': imageUrl, 'state': state.name});
};
```

**Rendering Modes**:
- `isStreaming=true` → Uses `StreamingTextMarkdown.claude()` for animation
- `isStreaming=false` → Uses `MarkdownBody` with full callbacks (links, images, code blocks)

---

### 6. Friendly Tiered Error Display

**Status**: Completed

**Description**: Replaced harsh red error boxes with friendly, muted error cards. Errors are classified by type (network, server, tool) with appropriate messaging and expandable technical details.

**Implementation Details**:

Files created:
- `lib/core/models/error_types.dart` - ChatErrorType enum and ChatErrorInfo class with factory constructors
- `lib/features/chat/widgets/friendly_error_card.dart` - Expandable error card widget with tiered styling

Files modified:
- `lib/core/models/chat_models.dart` - Added `errorInfo` field to ChatMessage
- `lib/core/services/chat_service.dart` - Added typed error methods: `addNetworkError()`, `addServerError()`, `addToolError()`
- `lib/features/chat/builders/message_builder.dart` - Replaced `_buildErrorMessage()` with FriendlyErrorCard
- `lib/features/chat/chat_content.dart` - Updated error handling to use typed error methods

**Error Types**:
| Type | Icon | Friendly Message | Has Retry |
|------|------|------------------|-----------|
| Network | 🔌 | "Connection hiccup" | Yes |
| Server | 😅 | "Server had trouble with that" | No |
| Tool | 🔧 | "{tool_name} couldn't complete" | No |

**Features**:
- **Muted styling** - Uses `surfaceContainerHighest` background instead of red
- **Expandable details** - Click to show error code and technical details
- **Auto-classification** - Legacy errors auto-classified based on content
- **Retry button** - Network errors offer retry action
- **Tool context** - Tool errors show which tool failed and brief error snippet

**UI Behavior**:
- Collapsed by default showing friendly message + icon
- Expand arrow shown if technical details available
- Error code displayed in monospace when expanded
- Technical details in smaller, muted monospace text

---

### 7. Collapsible Thinking Display

**Status**: Completed

**Description**: Shows AI reasoning/thinking as a collapsible section within assistant messages. Auto-expands while streaming, auto-collapses when complete. Users can manually expand to review reasoning.

**Implementation Details**:

Files created:
- `lib/features/chat/widgets/collapsible_thinking_widget.dart` - Expandable thinking section with streaming support

Files modified:
- `lib/core/models/chat_models.dart` - Added `thinkingText`, `isThinkingStreaming`, `isThinkingExpanded` fields
- `lib/core/services/chat_service.dart` - Added `startThinking()`, `appendThinking()`, `finalizeThinking()`, `toggleThinkingExpanded()` methods
- `lib/features/chat/chat_content.dart` - Wired up thinking events, integrated widget into message builder

**Features**:
- Muted background styling with brain icon
- Pulsing icon animation while streaming
- Header shows "Thinking..." (streaming) or "View reasoning (N chars)" (collapsed)
- Uses `StreamingTextMarkdown.claude()` for animated streaming
- Uses `MarkdownBody` for finalized content with selectable text
- Max height 300px with scroll for long thinking content

**Event Flow**:
- `ThinkingTextMessageStartEvent` -> Attach to current assistant message, start buffer
- `ThinkingTextMessageContentEvent` -> Append delta to buffer
- `ThinkingTextMessageEndEvent` -> Finalize buffer, auto-collapse

---

### 8. Subtle Tool Call Display

**Status**: Completed

**Description**: Replaced prominent colored tool call bubbles with compact, inline indicators. Tool calls can be grouped and expanded to see individual tool status.

**Implementation Details**:

Files created:
- `lib/features/chat/widgets/tool_call_summary_widget.dart` - Compact grouped tool display and inline indicator
- `lib/core/models/chat_models.dart` - Added `ToolCallSummary` class, `MessageType.toolCallGroup`

Files modified:
- `lib/core/models/chat_models.dart` - Added `toolCalls`, `isToolGroupExpanded` fields to ChatMessage
- `lib/core/services/chat_service.dart` - Added `addToolCallToGroup()`, `updateToolCallInGroup()`, `finalizeToolCallGroup()`, `toggleToolGroupExpanded()` methods
- `lib/features/chat/builders/message_builder.dart` - Replaced prominent tool bubbles with compact `CompactToolCallIndicator`

**Features**:
- **Compact single tool**: Inline `[spinner] Tool Name` indicator
- **Grouped tools**: Collapsed shows "Used 3 tools" with overall status
- **Expanded view**: Individual tools with status icons (spinner/check/error)
- Color-coded status: Primary (executing), Muted (completed), Error (failed)
- Error messages shown inline when expanded

**Tool Call States**:
- `executing` - Spinner, primary color
- `completed` - Check mark, muted color
- `error:message` - X icon, error color with message snippet

---

## Notes

- Features should be implemented incrementally
- Each feature should have tests where appropriate
- Update this document as features progress through stages
