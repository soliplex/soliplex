# Soliplex Flutter App

Flutter client for Soliplex - a multi-platform chat application with AG-UI protocol support.

## Quick Commands

```bash
flutter analyze          # Must show "No issues found!"
flutter test             # All tests must pass
dart format lib test     # Format before commits
```

## Architecture Overview

```
lib/
├── core/
│   ├── models/          # Domain models (ChatMessage, Citation, etc.)
│   ├── network/         # AG-UI protocol, event processing, transport
│   ├── protocol/        # Chat session abstractions
│   ├── providers/       # Riverpod providers (panel_providers.dart)
│   ├── services/        # Business logic services
│   └── utils/           # API constants, URL builder
├── features/
│   ├── chat/            # Chat UI, view models, widgets
│   ├── room/            # Room selection, welcome cards
│   └── settings/        # App settings
├── infrastructure/      # External integrations (quick_agui, dartantic)
└── widgets/             # Shared widgets (markdown, registry)
```

## Reference Documentation

| Doc | Purpose |
|-----|---------|
| `SOLIPLEX.md` | Backend API (AG-UI endpoints, schemas, state sync) |
| `QUICK_AGUI.md` | quick_agui library issues and workarounds |
| `APP_FEATURES.md` | Feature tracking (planned → in progress → done) |
| `GENUI-WIDGETS.md` | Widget registry and GenUI system |
| `STATE_MANAGEMENT.md` | Riverpod patterns, server-scoped providers |
| `docs/AUTH_FLOWS.md` | OIDC authentication (web, mobile, desktop) |

## Key Patterns

### Server-Scoped Providers

Panel state resets when server changes. Always use `ServerScopedNotifier`:

```dart
// In panel_providers.dart
final myProvider = StateNotifierProvider<MyNotifier, MyState>((ref) {
  ref.watch(currentServerProvider);  // Required for reset
  return MyNotifier();
});
```

### Event Processing (AG-UI)

Events flow: `NetworkTransportLayer` → `EventProcessor` → `ChatSession` → UI

- `STATE_SNAPSHOT`: Full state replacement
- `STATE_DELTA`: JSON Patch incremental updates
- Buffer patterns: `ThinkingBufferState`, `CitationsBufferState`

### View Model Pattern

`ChatMessage` (domain) → `MessageViewModelMapper` → `ChatMessageViewModel` (UI)

Types: `TextMessageViewModel`, `ToolCallViewModel`, `GenUiViewModel`, `ErrorMessageViewModel`

## Platform-Specific Code

Must work on **Web**, **Mobile**, and **Desktop**. No `dart:io` on web.

| Feature | Approach | Files |
|---------|----------|-------|
| Room Notes | Hidden on web (`kIsWeb`) | `notes_service*.dart` |
| Feedback Storage | Conditional imports | `feedback_service_io.dart`, `feedback_service_web.dart` |

**Pattern:**
```dart
import 'my_service_io.dart' if (dart.library.html) 'my_service_web.dart' as platform;
```

## Adding Features

1. Update `APP_FEATURES.md` status
2. Add models to `core/models/`
3. Add event handling to `event_processor.dart`
4. Create view models in `features/*/view_models/`
5. Build widgets in `features/*/widgets/`
6. Write tests in `test/`

## Common Files

| Task | Files |
|------|-------|
| New chat message type | `chat_models.dart`, `event_processor.dart`, `chat_message_view_model.dart`, `message_view_model_mapper.dart`, `chat_message_bubble.dart` |
| New API endpoint | `api_constants.dart`, `url_builder.dart` |
| New provider | `panel_providers.dart` (server-scoped) or service file |
| New GenUI widget | `widgets/registry/`, `GENUI-WIDGETS.md` |

## Gotchas

- `quick_agui` has concurrency issues - see `QUICK_AGUI.md`
- Citations come via `STATE_DELTA`, not `STATE_SNAPSHOT`
- Always pass `roomId` through widget tree for API calls
- Use `CitationsBufferState` pattern to attach data to next message
