# State Management

This document describes the state management architecture for the AGUI Dashboard application.

## Overview

The app uses [Riverpod](https://riverpod.dev/) for state management. Panel state (chat, canvas, context pane, activity status) is **server-scoped** - meaning it automatically resets when the user switches servers.

## Server-Scoped Provider Pattern

### Problem

When users switch between servers, panel state must reset. Without proper architecture:
- Chat messages from Server A appear when connected to Server B
- Canvas items persist across server switches
- Activity indicators show stale data

### Solution: Two-Tier Architecture

**Tier 1: Base Class**

All panel notifiers extend `ServerScopedNotifier<State>`:

```dart
// lib/core/providers/server_scoped_notifier.dart
abstract class ServerScopedNotifier<State> extends StateNotifier<State> {
  final String? serverId;

  ServerScopedNotifier(super.initialState, {this.serverId}) {
    debugPrint('${runtimeType}: Created for server $serverId');
  }

  @override
  void dispose() {
    debugPrint('${runtimeType}: Disposed (server $serverId)');
    super.dispose();
  }
}
```

**Tier 2: Centralized Provider Declarations**

All panel providers are declared in `lib/core/providers/panel_providers.dart` and watch `currentServerProvider`:

```dart
final chatProvider = StateNotifierProvider<ChatNotifier, ChatState>((ref) {
  final server = ref.watch(currentServerProvider);  // <-- Key: watch server
  return ChatNotifier(serverId: server?.id);
});

final canvasProvider = StateNotifierProvider<CanvasNotifier, CanvasState>((ref) {
  final server = ref.watch(currentServerProvider);
  return CanvasNotifier(serverId: server?.id);
});

final contextPaneProvider = StateNotifierProvider<ContextPaneNotifier, ContextPaneState>((ref) {
  final server = ref.watch(currentServerProvider);
  return ContextPaneNotifier(serverId: server?.id);
});

final activityStatusProvider = StateNotifierProvider<ActivityStatusNotifier, ActivityStatusState>((ref) {
  final config = ref.watch(activityStatusConfigProvider);
  final server = ref.watch(currentServerProvider);
  return ActivityStatusNotifier(config: config, serverId: server?.id);
});
```

### How It Works

1. Each provider watches `currentServerProvider`
2. When the server changes, Riverpod detects the dependency changed
3. Riverpod disposes the old notifier and creates a new one
4. The new notifier starts with fresh initial state

### Current Panel Providers

| Provider | Notifier | Service File | Purpose |
|----------|----------|--------------|---------|
| `chatProvider` | `ChatNotifier` | `chat_service.dart` | Chat messages and streaming state |
| `canvasProvider` | `CanvasNotifier` | `canvas_service.dart` | Canvas widget items |
| `contextPaneProvider` | `ContextPaneNotifier` | `context_pane_service.dart` | Activity feed and state snapshots |
| `activityStatusProvider` | `ActivityStatusNotifier` | `activity_status_service.dart` | Typing/thinking indicators |

## Adding a New Panel

### Step 1: Create the State and Notifier

```dart
// lib/core/services/my_panel_service.dart

import '../providers/server_scoped_notifier.dart';

class MyPanelState {
  final List<String> items;

  const MyPanelState({this.items = const []});

  MyPanelState copyWith({List<String>? items}) {
    return MyPanelState(items: items ?? this.items);
  }
}

class MyPanelNotifier extends ServerScopedNotifier<MyPanelState> {
  MyPanelNotifier({super.serverId}) : super(const MyPanelState());

  void addItem(String item) {
    state = state.copyWith(items: [...state.items, item]);
  }

  void clear() {
    state = const MyPanelState();
  }
}

// Note: Provider is declared in panel_providers.dart
```

### Step 2: Add Provider Declaration

Add to `lib/core/providers/panel_providers.dart`:

```dart
import '../services/my_panel_service.dart';

final myPanelProvider = StateNotifierProvider<MyPanelNotifier, MyPanelState>((ref) {
  final server = ref.watch(currentServerProvider);
  return MyPanelNotifier(serverId: server?.id);
});
```

### Step 3: Use in UI

```dart
import '../../core/providers/panel_providers.dart';

class MyPanelWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(myPanelProvider);

    return ListView.builder(
      itemCount: state.items.length,
      itemBuilder: (context, index) => Text(state.items[index]),
    );
  }
}
```

## File Structure

```
lib/core/
├── providers/
│   ├── panel_providers.dart       # All panel provider declarations
│   └── server_scoped_notifier.dart # Base class for panel notifiers
├── services/
│   ├── chat_service.dart          # ChatState, ChatNotifier
│   ├── canvas_service.dart        # CanvasState, CanvasNotifier
│   ├── context_pane_service.dart  # ContextPaneState, ContextPaneNotifier
│   ├── activity_status_service.dart # ActivityStatusState, ActivityStatusNotifier
│   └── server_config_service.dart # currentServerProvider (the dependency)
```

## Key Principles

1. **Never declare panel providers in service files** - Always use `panel_providers.dart`
2. **Always extend ServerScopedNotifier** - Enforces the pattern structurally
3. **Always watch currentServerProvider** - Enables automatic reset
4. **Import providers from panel_providers.dart** - Not from service files

## Non-Server-Scoped State

Not all state needs to be server-scoped. Examples of state that persists across server switches:

- `layoutModeProvider` - UI layout preference
- `themeProvider` - Dark/light mode
- `serverConfigProvider` - List of configured servers

These are declared in their respective service files, not in `panel_providers.dart`.

## Debugging

The `ServerScopedNotifier` base class logs creation and disposal:

```
ChatNotifier: Created for server abc123
ChatNotifier: Disposed (server abc123)
ChatNotifier: Created for server xyz789
```

This helps verify that state is being reset correctly when switching servers.
