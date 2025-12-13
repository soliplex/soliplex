# Technical Debt Backlog

Tracked redesign candidates and technical debt items.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| `open` | Identified, not yet addressed |
| `spec-created` | Follow-up spec exists |
| `in-progress` | Being worked on |
| `resolved` | Completed |

---

## Open Items

| ID | Description | Discovered In | Priority | Status |
|----|-------------|---------------|----------|--------|
| DEBT:room-session-dual-params | RoomSession.initialize() has dual-param API (transportLayer, agUiClient) for test convenience | SPEC:sse-ownership-refactor | medium | spec-created |
| DEBT:event-processing-bloat | RoomSession.processEvent() is 200+ line switch statement | SPEC:sse-ownership-refactor | low | open |

---

## Item Details

### DEBT:room-session-dual-params

**Location:** `lib/core/network/room_session.dart:initialize()`

**Problem:** The `agUiClient` parameter exists solely for test convenience. Production code uses `transportLayer`. This dual-param pattern creates confusion and maintenance burden.

**Follow-up:** SPEC:room-session-test-cleanup

**Added:** 2025-12-13

---

### DEBT:event-processing-bloat

**Location:** `lib/core/network/room_session.dart:processEvent()`

**Problem:** Large switch statement handling all AG-UI event types. Could be extracted to a separate event processor class for better testability.

**Follow-up:** None yet (optional refactor)

**Added:** 2025-12-13

---

## Adding New Items

When you discover technical debt during work:

1. Add entry to the table above
2. Add detail section with location, problem, follow-up
3. Tag in your work log: `Added DEBT:xxx to BACKLOG.md`
4. If significant, create a follow-up spec

**ID Format:** `DEBT:kebab-case-name`
