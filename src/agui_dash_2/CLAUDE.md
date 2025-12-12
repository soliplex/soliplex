# Claude Code Notes

Project-specific instructions for Claude Code when working on this codebase.

## Reference Documentation

- **SOLIPLEX.md** - Backend API documentation for AG-UI integration (endpoints, request/response schemas, state sync)
- **QUICK_AGUI.md** - Notes on the quick_agui Flutter library (issues, workarounds, architecture)
- **APP_FEATURES.md** - Planned, in-progress, and completed app features (feedback chips, notes pad, etc.)

## Documentation Requirements

- Any newly discovered information about `quick_agui` - especially design shortcomings, bugs, or architectural issues - should be documented in `QUICK_AGUI.md`
- This includes issues like:
  - Concurrency problems (e.g., shared state causing duplicate processing)
  - Event streaming edge cases
  - Tool registration/execution quirks
  - Any workarounds implemented in the app layer to compensate for library limitations
- Backend API discoveries should be documented in `SOLIPLEX.md`
- **Feature tracking**: When working on new features, update `APP_FEATURES.md`:
  - Move features from "Planned" to "In Progress" when starting work
  - Move features from "In Progress" to "Completed" when done
  - Add implementation notes, files modified, and any gotchas discovered
