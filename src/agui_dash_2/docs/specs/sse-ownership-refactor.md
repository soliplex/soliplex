# SPEC: SSE Ownership Refactor

| Field | Value |
|-------|-------|
| ID | SPEC:sse-ownership-refactor |
| Status | PLANNED |
| Created | 2025-12-13 |
| Updated | 2025-12-13 |
| Version | 0.1.0 |
| Author | Claude |

## Summary

Refactor the SSE (Server-Sent Events) and network ownership hierarchy to eliminate legacy patterns, establish clear single ownership, and improve testability. This consolidates lessons learned from the network-transport-layer implementation.

## Background & Lessons Learned

From SPEC:network-transport-layer and ADR-0001, we learned:

1. **Injectable dependencies improve testability** - Making `AgUiClient` injectable in `NetworkTransportLayer` enabled comprehensive SSE testing (coverage: 59.7% → 95.5%)

2. **Single ownership principle** - NetworkTransportLayer owning both HTTP client and AgUiClient reduced confusion about "who owns what"

3. **Delegation pattern enables observability** - `RunAgentDelegate` type allows SSE to flow through transport layer without tight coupling

## Current Architecture (Problems)

```
┌─────────────────────────────────────────────────────────────┐
│ RoomSession                                                  │
│  ├── HttpTransport transport        (REST calls)            │
│  └── initialize(transportLayer?, agUiClient?)               │
│       ├── Thread.withDelegate()     (NEW: uses delegate)    │
│       └── Thread()                  (LEGACY: direct client) │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Thread                                                       │
│  ├── Thread()                       (legacy constructor)    │
│  │    └── _client: AgUiClient       (direct ownership)      │
│  └── Thread.withDelegate()          (new constructor)       │
│       └── _runAgentDelegate         (indirect via delegate) │
└─────────────────────────────────────────────────────────────┘
```

**Problems identified:**

| Problem | Location | Impact |
|---------|----------|--------|
| Dual constructor pattern | `Thread` | Confusion, code duplication, hard to test |
| Dual transport params | `RoomSession.initialize()` | Unclear which to use, transitional API |
| Dual transport ownership | RoomSession has HttpTransport, SSE via Thread | Scattered responsibility |
| Event processing bloat | `RoomSession.processEvent()` | 200+ line switch statement |
| Low coverage | `thread.dart: 51.8%`, `room_session.dart: 26.1%` | Risk of regressions |

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ RoomSession                                                  │
│  └── NetworkTransportLayer         (SINGLE transport owner) │
│       ├── .post()                  (REST calls)             │
│       └── .runAgent()              (SSE streaming)          │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Thread                                                       │
│  └── Thread.withDelegate()          (ONLY constructor)      │
│       └── runAgentDelegate          (always via delegate)   │
└─────────────────────────────────────────────────────────────┘
```

## Requirements

### Phase 1: Thread Simplification
- [ ] R1.1: Remove legacy `Thread()` constructor
- [ ] R1.2: Make `Thread.withDelegate()` the default/only constructor (rename to just `Thread()`)
- [ ] R1.3: Remove `@Deprecated client` getter
- [ ] R1.4: Update all Thread instantiation sites

### Phase 2: RoomSession Consolidation
- [ ] R2.1: Replace `HttpTransport transport` with `NetworkTransportLayer`
- [ ] R2.2: Remove dual-param pattern from `initialize()` (only accept `NetworkTransportLayer`)
- [ ] R2.3: Use `transportLayer.post()` instead of `transport.post()`
- [ ] R2.4: Remove `agUiClient` parameter entirely

### Phase 3: HttpTransport Removal
- [ ] R3.1: Migrate 401 retry logic from `HttpTransport` to `NetworkTransportLayer.post()`
- [ ] R3.2: Migrate `cancelRun()` logic to `NetworkTransportLayer`
- [ ] R3.3: Delete `HttpTransport` class (or mark deprecated for later removal)

### Phase 4: Event Processing Extraction (Optional)
- [ ] R4.1: Extract `RoomSession.processEvent()` to `EventProcessor` class
- [ ] R4.2: Make EventProcessor independently testable
- [ ] R4.3: RoomSession delegates to EventProcessor

### Phase 5: Test Coverage
- [ ] R5.1: Thread coverage ≥ 80%
- [ ] R5.2: RoomSession coverage ≥ 60%
- [ ] R5.3: NetworkTransportLayer coverage ≥ 95% (maintain)

## Acceptance Criteria

- [ ] AC1: Only one way to instantiate Thread (no legacy constructor)
- [ ] AC2: RoomSession only depends on NetworkTransportLayer for network I/O
- [ ] AC3: All SSE traffic observable via NetworkInspector
- [ ] AC4: No direct AgUiClient usage outside NetworkTransportLayer
- [ ] AC-TEST: Unit tests exist for all refactored code
- [ ] AC-COVERAGE: Coverage targets met (R5.x)

## Non-Goals

- **Not changing AG-UI protocol** - This is internal refactoring only
- **Not adding new features** - Pure cleanup, no new functionality
- **Not refactoring widget system** - GenUI/canvas handling unchanged
- **Not changing provider architecture** - Riverpod patterns stay the same

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Existing tests using legacy Thread() | Update to use delegate pattern with mock |
| ConnectionManager creating sessions | Update to pass NetworkTransportLayer |
| Tests mocking HttpTransport | Update to mock NetworkTransportLayer |
| ServerConfigService creating transport | Continue creating NetworkTransportLayer |

## Migration Path

### Step 1: Add Deprecation Warnings
```dart
@Deprecated('Use Thread.withDelegate() instead. Will be removed in v2.0')
Thread({required ag_ui.AgUiClient client, ...})
```

### Step 2: Update Internal Usage
- ConnectionManager → use delegate pattern
- Tests → use mocked delegates

### Step 3: Remove Deprecated Code
- Delete legacy constructor
- Rename `withDelegate` → default constructor

## Dependencies

- Internal: SPEC:network-transport-layer (completed)
- Internal: ADR-0001 (SSE delegate pattern decision)

## Related

- ADRs: ADR-0001-sse-delegate-pattern
- Work Log: LOG:sse-ownership-refactor (create with /docs-start)

## Files Affected

| File | Change |
|------|--------|
| `lib/infrastructure/quick_agui/thread.dart` | Remove legacy constructor |
| `lib/core/network/room_session.dart` | Use NetworkTransportLayer only |
| `lib/core/network/http_transport.dart` | Deprecate/remove |
| `lib/core/network/connection_manager.dart` | Update session creation |
| `lib/core/services/server_config_service.dart` | Verify transport creation |
| `test/infrastructure/quick_agui/thread_*.dart` | Update tests |
| `test/core/network/room_session_*.dart` | Update tests |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking existing tests | Medium | Low | Run full suite after each phase |
| Missing usage site | Low | Medium | Grep for legacy patterns before removal |
| Performance regression | Low | Low | SSE path unchanged, just different entry point |

---

## Completion Record

*Fill in when status → DONE*

| Field | Value |
|-------|-------|
| Completed | YYYY-MM-DD |
| Final Version | 1.0.0 |

### Files Modified

- *(fill in)*

### Tests

- *(fill in)*

### Coverage

| File | Before | After | Delta |
|------|--------|-------|-------|
| thread.dart | 51.8% | ? | ? |
| room_session.dart | 26.1% | ? | ? |

### Notes

*(fill in)*
