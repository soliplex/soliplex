# SPEC: RoomSession Test Cleanup

| Field | Value |
|-------|-------|
| ID | SPEC:room-session-test-cleanup |
| Status | PLANNED |
| Created | 2025-12-13 |
| Updated | 2025-12-13 |
| Version | 0.1.0 |
| Author | Claude |

## Summary

Remove the legacy `agUiClient` parameter from `RoomSession.initialize()` and update tests to use `NetworkTransportLayer` with mock clients. This completes the SSE ownership cleanup.

## Background

From SPEC:sse-ownership-refactor:
- Phase 1 (Thread Simplification) - DONE
- Phase 2 (HttpTransport Cleanup) - DONE
- Phase 3 (RoomSession Consolidation) - Deferred to this spec

The `agUiClient` parameter in `RoomSession.initialize()` exists solely for test convenience. Production code uses `transportLayer`. Removing it will:
1. Simplify the API (single path)
2. Ensure tests match production behavior
3. Complete the single-ownership model

## Problem Validation

*Completed 2025-12-13*

### What problem does this solve?
Tests use `agUiClient` (mock SSE directly) while production uses `transportLayer` (SSE through observable layer). This creates a dual code path in `initialize()` (~15 lines) and tests don't exercise the exact production path.

### Is this root cause or symptom?
- [x] Root cause - this directly fixes the issue
- [ ] Symptom - the real problem is: ___

The `agUiClient` param exists because tests were written before `NetworkTransportLayer` existed. It's evolutionary debt, not masking a deeper issue.

### What happens if we DON'T do this?
- Tests work but don't exercise exact production path
- Two code paths in `initialize()` (~15 lines)
- Minor cognitive overhead understanding "which path"
- **No bugs, no user impact**

### Cost/Benefit
- **Effort:** Medium - ~15 tests to refactor, need new test helper infrastructure
- **Benefit:** Low - Code hygiene, test fidelity (not bug fixing)

### Verdict
- [ ] **Critical** - Blocking bugs, security, data loss
- [ ] **High** - User-facing issues, significant tech debt
- [ ] **Medium** - Improvements, moderate cleanup
- [x] **Low** - Nice-to-have, minor cleanup (reconsider priority)

## Requirements

- [ ] R1: Create test helper for `NetworkTransportLayer` with mock clients
- [ ] R2: Update `room_session_enhanced_test.dart` to use `transportLayer`
- [ ] R3: Update `room_session_state_test.dart` to use `transportLayer`
- [ ] R4: Remove `agUiClient` parameter from `RoomSession.initialize()`
- [ ] R5: Update documentation/comments

## Acceptance Criteria

- [ ] AC1: `RoomSession.initialize()` only accepts `transportLayer`
- [ ] AC2: All room_session tests pass using `transportLayer`
- [ ] AC-TEST: Test coverage maintained or improved

## Files Affected

| File | Change |
|------|--------|
| `lib/core/network/room_session.dart` | Remove `agUiClient` parameter |
| `test/core/network/room_session_enhanced_test.dart` | Use `transportLayer` |
| `test/core/network/room_session_state_test.dart` | Use `transportLayer` |
| `test/mocks/` (new?) | Test helper for NetworkTransportLayer |

## Dependencies

- Internal: SPEC:sse-ownership-refactor (completed phases 1-2)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Test complexity increases | Medium | Low | Create reusable test helper |
| Mock setup becomes verbose | Low | Low | Helper function encapsulates setup |
