# Flutter Agent Instructions

Extends `/AGENTS.md`. Specific to `src/flutter/`.

**Remember**: Default skeptical. "Do we need this yet?" "What's the simplest fix?"

## Tool Preferences

Prefer `dart mcp-server` (stdio) tools over CLI:

| Task | MCP Tool | Instead of CLI |
|------|----------|----------------|
| Run tests | `run_tests` | `flutter test` |
| Analyze | `analyze_files` | `flutter analyze` |
| Format | `dart_format` | `dart format` |
| Pub commands | `pub` | `flutter pub` |

## Code Quality

Always run in this order:
1. `dart_format` (format)
2. `analyze_files` (lint)
3. `run_tests` (test)

All three must pass before code is complete.

## Accessibility

Always add accessibility information to widgets:
- `Tooltip` for icon buttons and non-text actions
- `Semantics` labels for screen readers
- `excludeFromSemantics: true` only when parent provides context

## Patterns

- Use Riverpod for state management
- Prefer functional widgets
- Platform-specific: `*_io.dart` / `*_web.dart` with conditional imports
