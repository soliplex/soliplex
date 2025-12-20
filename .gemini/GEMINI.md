# Soliplex Global Gemini Context

## Core Mandates & Standards
- **Zero Tolerance Policy**: All linters and tests must pass 100%. No warnings or errors are acceptable in commits.
- **Workflow Order**: Before any commit, follow this sequence (preferring `dart mcp-server` tools when available):
    1. Format code
    2. Run analysis (Linter)
    3. Run tests
- **Linting**: Always use the latest `very_good_analysis` package. It is the project standard for strict enforcement of best practices.
- **Tooling Preference**: Prefer the `dart mcp-server` over direct command line usage for all development tasks (formatting, linting, testing).

## MCP Tools Reference

| Task | MCP Tool |
|------|----------|
| Format code | `dart_format` |
| Analyze/lint | `analyze_files` |
| Run tests | `run_tests` |
| Add packages | `pub` (command: "add") |
| Get dependencies | `pub` (command: "get") |
| Apply fixes | `dart_fix` |
| Search pub.dev | `pub_dev_search` |
| Launch app | `launch_app` |
| Hot reload | `hot_reload` |

## Project Architecture
- **Soliplex**: A multi-platform application (Web, Mobile, Desktop).
- **Frontend**: Flutter-based (`src/flutter`). Uses Riverpod for state management.
- **Backend**: Python-based (`src/soliplex`).
- **Documentation**: Strict documentation lifecycle (Specs, ADRs, Work Logs) managed in `docs/`.

## Critical Memories & Best Practices
- **Flutter UI Fixes**: For complex syntax errors in nested widget trees, rewrite the entire widget or a large block rather than small targeted string replacements to ensure correct closing of braces/parentheses.
- **Test Stability**: The `flutter test` runner may cache kernel binaries and fail to reflect recent changes. If unexpected failures occur after code fixes, run `flutter clean`.
- **iOS Stability**: `ios/Runner.xcodeproj/project.pbxproj` is susceptible to syntax corruption (e.g., redundant semicolons) during automated find-and-replace. Verify this file if `pod install` or iOS builds fail.
- **Web Compatibility**: SOLIPLEX supports Web. Avoid `dart:io` in shared packages; use conditional imports (`*_io.dart` vs `*_web.dart`).

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

## Subproject Instructions
- `src/flutter/GEMINI.md` - Flutter app-specific patterns and documentation lifecycle