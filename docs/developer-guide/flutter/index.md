# Flutter Frontend

!!! warning "Deprecated - Flutter Client Removed"
    The Flutter frontend was removed from the repository in January 2025. This documentation is retained for historical reference only. The source code at `src/flutter/lib/` no longer exists.

    **Current clients:**

    - **TUI** - Terminal-based client at `src/soliplex/tui/`. See [CLI Reference](../../reference/cli.md#tui-client).
    - **Custom clients** - Build your own using the [REST API](../api/rest-endpoints.md) and [AG-UI Protocol](../api/agui-protocol.md).

---

*The following documentation describes the removed Flutter client and is kept for reference.*

The Soliplex Flutter app provided a cross-platform chat interface that connected to the backend API.

## Overview

| Aspect | Technology |
|--------|------------|
| **Framework** | Flutter 3.x |
| **State Management** | Riverpod |
| **Protocol** | AG-UI over SSE |
| **Platforms** | Web, iOS, Android, Desktop |

## Sections

- **[Architecture](architecture.md)** - State management, providers, and patterns
- **[Widgets](widgets.md)** - Widget registry and GenUI components

## Project Structure

```
src/flutter/
├── lib/
│   ├── main.dart              # App entry point
│   ├── app_shell.dart         # Root app widget
│   ├── core/                  # Core functionality
│   │   ├── auth/              # OIDC authentication
│   │   ├── models/            # Domain models
│   │   ├── network/           # AG-UI transport, event processing
│   │   ├── providers/         # Riverpod providers
│   │   ├── services/          # Business logic services
│   │   └── utils/             # Utilities
│   ├── features/              # Feature modules (chat, room, canvas, etc.)
│   ├── infrastructure/        # External integrations (quick_agui)
│   └── widgets/               # Shared UI components
├── test/                      # Unit and widget tests
└── pubspec.yaml               # Dependencies
```

## Key Patterns

### Server-Scoped Providers

Panel state resets when the server changes. Providers watch `currentServerFromAppStateProvider`:

```dart
final myPanelProvider = StateNotifierProvider<MyNotifier, MyState>((ref) {
  final server = ref.watch(currentServerFromAppStateProvider);
  return MyNotifier(serverId: server?.id);
});
```

### Platform-Specific Code

Platform code uses conditional imports:

```dart
// Main file (feedback_service.dart)
import 'feedback_service_io.dart'
    if (dart.library.html) 'feedback_service_web.dart' as platform;

// Platform-agnostic usage
final content = await platform.loadFeedbackData(roomId);
await platform.saveFeedbackData(roomId, jsonEncode(data));
```

### AG-UI Event Handling

Events are processed via typed pattern matching:

```dart
EventProcessingResult _processEvent(ag_ui.BaseEvent event) {
  switch (event) {
    case ag_ui.TextMessageContentEvent():
      return _appendContent(event.delta);
    case ag_ui.ToolCallStartEvent():
      return _processToolCallStart(event);
    case ag_ui.RunFinishedEvent():
      return _completeRun();
  }
}
```

## Development

```bash
cd src/flutter

# Install dependencies
flutter pub get

# Run on Chrome
flutter run -d chrome --web-port 59001

# Run tests
flutter test

# Analyze (zero warnings required!)
flutter analyze

# Format
dart format lib test
```

## Documentation Files

Additional Flutter documentation in the source tree:

| File | Purpose |
|------|---------|
| `src/flutter/CLAUDE.md` | Development guidance |
| `src/flutter/SOLIPLEX.md` | AG-UI protocol details |
| `src/flutter/APP_FEATURES.md` | Feature tracking |

## Source Files

| Directory | Purpose |
|-----------|---------|
| `lib/core/providers/` | Riverpod state providers |
| `lib/core/services/` | Business logic and API handling |
| `lib/core/network/` | AG-UI transport, event processing |
| `lib/core/models/` | Domain models |
| `lib/features/` | Feature modules (chat, room, canvas) |
| `lib/widgets/` | Shared UI components |
