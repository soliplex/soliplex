# Flutter Frontend

The Soliplex Flutter app provides a cross-platform chat interface that connects to the backend API.

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
│   ├── providers/             # Riverpod providers
│   ├── services/              # API, SSE, auth services
│   ├── models/                # Data models
│   ├── widgets/               # UI components
│   └── screens/               # Page screens
├── test/                      # Unit and widget tests
└── pubspec.yaml               # Dependencies
```

## Key Patterns

### Server-Scoped Providers

Panel state is scoped to server connection:

```dart
final panelStateProvider = StateNotifierProvider.family<
    PanelStateNotifier, PanelState, ServerConfig>(
  (ref, serverConfig) => PanelStateNotifier(serverConfig),
);
```

### Platform-Specific Code

Platform code uses conditional imports:

```dart
// Platform-agnostic interface
abstract class StorageService {
  Future<void> save(String key, String value);
}

// Implementation files
// storage_io.dart - Mobile/desktop
// storage_web.dart - Web
```

### AG-UI Event Handling

Events are processed via stream:

```dart
await for (final event in aguiStream) {
  switch (event.type) {
    case 'TEXT_MESSAGE_CONTENT':
      _appendContent(event.delta);
    case 'TOOL_CALL_START':
      _showToolCall(event);
    case 'RUN_FINISHED':
      _completeRun();
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
| `lib/providers/` | Riverpod state providers |
| `lib/services/` | API and stream handling |
| `lib/widgets/` | Reusable UI components |
| `lib/screens/` | Full page layouts |
