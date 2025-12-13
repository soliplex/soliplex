# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Soliplex Flutter** is an AI-powered RAG (Retrieval-Augmented Generation) interface client built with Flutter. It integrates with the AG-UI protocol for AI agent communication and provides a responsive multi-panel interface for chat, canvas rendering, and thread history.

### Current Status

- **Test Coverage**: 93.3% (2116 of 2269 lines) - exceeds 80% target
- **Source Files**: 42 Dart files in `lib/`
- **Test Files**: 31 test files covering widgets, features, and business logic
- **Branch**: `new_frontend` (main branch: `main`)
- **Known Issues**: Tracked in `planning/ISSUES.md`
- **Planning Docs**: Architecture and implementation plans in `planning/` directory

### Architecture

- **State Management**: Riverpod for reactive state management
- **HTTP Client**: Pure Dart `http` package (no Dio)
- **Local Persistence**: SharedPreferences (no Hive)
- **AI Protocol**: AG-UI SDK from https://github.com/soliplex/ag-ui
  - Supports `canvas_render` and `genui_render` UI tools
  - Real-time event streaming from backend
- **UI**: Material Design 3 with custom theming
- **Layout**: Responsive 3-column design (History | Canvas | Details/Chat)

### UI Layout

The app uses a responsive 3-column layout defined in `app_shell.dart`:

```
┌─────────┬───────────────────────┬─────────────┐
│         │                       │  Details    │
│ History │       Canvas          │─────────────│
│  (1/4)  │  (Current/Permanent)  │    Chat     │
│         │                       │             │
└─────────┴───────────────────────┴─────────────┘
```

- **History Panel**: Thread selection and navigation
- **Canvas Panel**: Tabbed view for Current/Permanent canvas rendering
- **Details Panel**: Thread details, state, and event log
- **Chat Panel**: Message input and conversation display

### Project Structure

```
lib/                       # 42 source files
├── main.dart              # App entry point with MaterialApp
├── app_shell.dart         # Responsive 3-column layout shell
├── client/                # API client and AG-UI integration
│   ├── agui/             # AG-UI protocol handlers (events, threads)
│   ├── api/              # HTTP API client (REST endpoints)
│   ├── models/           # Data models (Room, Thread, Message)
│   ├── session/          # Session and connection management
│   ├── utils/            # URL builder and utilities
│   ├── client.dart       # Public client exports
│   └── soliplex_client.dart  # Main client class (canvas_render, genui_render)
├── providers/             # Riverpod state providers
│   ├── client_provider.dart
│   ├── chat_provider.dart
│   ├── message_provider.dart
│   ├── canvas_provider.dart
│   ├── room_provider.dart
│   └── thread_provider.dart
└── features/              # Feature modules
    ├── chat/             # Chat interface with message bubbles
    ├── canvas/           # Canvas widgets (permanent & current)
    ├── details/          # Details panel with state/event tabs
    ├── history/          # Thread history view
    └── test_page/        # Testing/debug page with API testing

test/                      # 31 test files
├── client/               # Client and API unit tests
├── features/             # Feature widget tests
├── mocks/                # Mock implementations (mocktail)
├── provider/             # Provider unit tests
└── widget/               # App shell and page widget tests

planning/                  # Project documentation
├── INITIAL_PLAN.md       # Original project plan
├── PLAN_v1.md            # Architecture design v1
├── PLAN_v2.md            # Architecture design v2
└── ISSUES.md             # Known issues and feature requests
```

## Development Environment

### Requirements

- Flutter SDK: ^3.11.0-200.1.beta (Dart 3.11+)
- Platforms supported: Web, macOS, iOS, Android, Linux, Windows

### macOS Development

The app requires network permissions for macOS desktop builds:
- **Entitlements**: Configured in `macos/Runner/DebugProfile.entitlements` and `Release.entitlements`
- Network client/server permissions enabled for API communication
- App Sandbox enabled with JIT compilation support

## Build and Run Commands

```bash
flutter run                    # Run on connected device/simulator
flutter run -d chrome          # Run in Chrome browser
flutter run -d macos           # Run as macOS desktop app
flutter build web              # Build for web deployment
flutter build apk              # Build Android APK
flutter build ios              # Build iOS app
flutter build macos            # Build macOS desktop app
```

## Testing

### Test Coverage

**Current Coverage: 93.3%** (2116 of 2269 lines)
- Exceeds project target of 80%
- Coverage report: `coverage/lcov.info`
- HTML report: `coverage/html/index.html`

### Test Organization

- **31 test files** covering widgets, features, and business logic
- Test structure mirrors `lib/` directory
- **Unit tests**: `test/provider/` and `test/client/`
- **Widget tests**: `test/widget/` and `test/features/`
- **Mock objects**: `test/mocks/` using mocktail
- **Integration tests**: `integration_test/` (placeholder for future tests)

### Test Commands

```bash
flutter test                           # Run all tests
flutter test --coverage                # Run tests with coverage report
flutter test test/widget/              # Run all widget tests
flutter test test/features/chat/       # Run tests for specific feature
flutter test test/client/api/api_test.dart  # Run specific test file

# View coverage report
lcov --summary coverage/lcov.info      # Text summary
open coverage/html/index.html          # HTML report (macOS)
```

### Mocking

- Uses `mocktail` package for mocking dependencies
- Mock implementations in `test/mocks/`
- Mocks for: SoliplexClient, SoliplexApi, ConnectionManager

## Code Quality

### Analysis

```bash
flutter analyze                # Run static analysis with strict rules
flutter format .               # Format all Dart code
flutter format --set-exit-if-changed .  # Check formatting (CI)
```

### Linting Configuration

Strict analysis options configured in `analysis_options.yaml`:
- **Strict Mode**: Enforces strict-casts, strict-inference, strict-raw-types
- **Error Prevention**: Unawaited futures, resource cleanup, type safety
- **Style**: Single quotes, trailing commas, const constructors, final locals
- Based on `flutter_lints` with additional custom rules

## Dependencies

```bash
flutter pub get                # Install dependencies
flutter pub upgrade            # Upgrade dependencies
flutter pub outdated           # Check for outdated packages
```

### Key Dependencies

- **flutter_riverpod**: State management (^2.6.1)
- **http**: HTTP client (^1.2.2)
- **shared_preferences**: Local storage (^2.3.3)
- **ag_ui**: AI agent protocol (git dependency)

### Dev Dependencies

- **flutter_test**: Widget and unit testing
- **test**: Pure Dart testing (^1.25.8)
- **mocktail**: Mocking library (^1.0.4)
- **flutter_lints**: Linting rules (^6.0.0)

## Navigation

The app uses named routes defined in `lib/main.dart`:
- `/` - Main app shell (AppShell)
- `/test` - Test/debug page (TestPage)

## Development Workflow

1. Always run `flutter pub get` after pulling changes
2. Run `flutter analyze` before committing to catch lint errors
3. Maintain test coverage above 80% (current: 93.3%)
   - Run `flutter test --coverage` before committing
   - Check `lcov --summary coverage/lcov.info` for coverage stats
4. Use strict analysis rules - code must pass all lint checks
5. Follow Material Design 3 patterns for UI consistency
6. Use Riverpod providers for state management, avoid StatefulWidget where possible
7. Document known issues in `planning/ISSUES.md`
8. Keep planning documents updated as architecture evolves

## Backend Integration

The Flutter client connects to a Soliplex backend server (default: `http://localhost:8000`):
- **REST API**: Standard HTTP endpoints via `SoliplexApi`
- **AG-UI Protocol**: Real-time event streaming via `ConnectionManager`
- **Rooms**: Multi-room support with room-specific configurations
- **Threads**: Conversation threads within rooms
- **Canvas Tools**: `canvas_render` and `genui_render` for dynamic UI

See `/test` route in the app for API testing and connection debugging.

## Debugging

- **Test Page**: Navigate to `/test` route for API testing and debugging
- **DevTools**: Run `flutter pub global run devtools` for advanced debugging
- **Logs**: Use `flutter logs` to view app logs across devices