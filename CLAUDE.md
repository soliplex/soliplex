# Soliplex Global Claude Context

## Core Mandates & Standards
- **Zero Tolerance Policy**: All linters and tests must pass 100%. No warnings or errors are acceptable in commits.
- **Workflow Order**: Before any commit, follow this sequence using `dart mcp-server` tools:
    1. Format code (`mcp__dart-mcp__dart_format`)
    2. Run analysis (`mcp__dart-mcp__analyze_files`)
    3. Run tests (`mcp__dart-mcp__run_tests`)
- **Linting**: Always use the latest `very_good_analysis` package. It is the project standard for strict enforcement of best practices.
- **Tooling Preference**: Always prefer `dart mcp-server` tools over direct command line usage for formatting, linting, testing, and pub commands.

## Project Architecture
- **Soliplex**: A multi-platform application (Web, Mobile, Desktop).
- **Frontend**: Flutter-based (`src/flutter`). Uses Riverpod for state management.
- **Backend**: Python-based (`src/soliplex`).
- **Documentation**: Strict documentation lifecycle (Specs, ADRs, Work Logs) managed in `docs/`.

## MCP Tools Reference

| Task | MCP Tool |
|------|----------|
| Format code | `mcp__dart-mcp__dart_format` |
| Analyze/lint | `mcp__dart-mcp__analyze_files` |
| Run tests | `mcp__dart-mcp__run_tests` |
| Add packages | `mcp__dart-mcp__pub` (command: "add") |
| Get dependencies | `mcp__dart-mcp__pub` (command: "get") |
| Apply fixes | `mcp__dart-mcp__dart_fix` |
| Search pub.dev | `mcp__dart-mcp__pub_dev_search` |
| Launch app | `mcp__dart-mcp__launch_app` |
| Hot reload | `mcp__dart-mcp__hot_reload` |

## LLM Documentation

Federated documentation for context-optimized agent access. See `docs/development/llms-strategy.md` for full details.

### Building for Local Agents
```bash
DOCS_MODE=absolute ./scripts/build_docs.sh
```

### Quick Access (in `site/`)
| File | Purpose |
|------|---------|
| `llms.txt` | Entry point - links to domain maps |
| `llms-project-full.txt` | Architecture, setup, config |
| `llms-server-full.txt` | Python backend API |
| `llms-client-full.txt` | Flutter widget library |

### Verify Your Understanding
After reading the llms files, you should be able to answer:
- **Project**: "What are the main components of Soliplex?"
- **Server**: "What CLI commands are available and what do they do?"
- **Client**: "How does RoomService connect to the backend?"

If you cannot answer these from the docs, the documentation may need improvement.

## Critical Memories & Best Practices
- **Flutter UI Fixes**: For complex syntax errors in nested widget trees, rewrite the entire widget or a large block rather than small targeted string replacements to ensure correct closing of braces/parentheses.
- **Test Stability**: The `flutter test` runner may cache kernel binaries and fail to reflect recent changes. If unexpected failures occur after code fixes, run `flutter clean`.
- **iOS Stability**: `ios/Runner.xcodeproj/project.pbxproj` is susceptible to syntax corruption (e.g., redundant semicolons) during automated find-and-replace. Verify this file if `pod install` or iOS builds fail.
- **Web Compatibility**: SOLIPLEX supports Web. Avoid `dart:io` in shared packages; use conditional imports (`*_io.dart` vs `*_web.dart`).

## Subproject Instructions
- `src/flutter/CLAUDE.md` - Flutter app-specific patterns, architecture, and common files
