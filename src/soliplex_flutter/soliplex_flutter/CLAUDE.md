# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands

```bash
flutter run                    # Run on connected device/simulator
flutter run -d chrome          # Run in Chrome browser
flutter run -d macos           # Run as macOS desktop app
flutter build web              # Build for web deployment
flutter build apk              # Build Android APK
flutter build ios              # Build iOS app
```

## Testing

```bash
flutter test                           # Run all tests
flutter test test/widget_test.dart     # Run a specific test file
```

## Code Quality

```bash
flutter analyze                # Static analysis (lint checks)
flutter format .               # Format all Dart code
```

## Dependencies

```bash
flutter pub get                # Install dependencies
flutter pub upgrade            # Upgrade dependencies
```
