# SPEC: SSE Transport Unification

| Field | Value |
|-------|-------|
| ID | SPEC:sse-transport-unification |
| Status | SUPERSEDED |
| Created | 2025-12-13 |
| Updated | 2025-12-13 |
| Version | 0.1.0 |
| Author | runyaga |
| Superseded By | SPEC:network-transport-layer |

## Summary

Unify HTTP and SSE transport to flow through a single observable layer. Currently, `HttpTransport` handles POST requests directly via `http.Client`, but SSE streaming (`runAgent`) uses `ag_ui.AgUiClient` which bypasses our transport layer. This prevents the network inspector from capturing SSE traffic and creates an inconsistent architecture.

## Problem

```
Current Architecture:
                                    ┌─────────────────────┐
POST requests ──► HttpTransport ───►│ NetworkInspector    │ ✓ Captured
                      │             └─────────────────────┘
                      │
SSE streams ─────► ag_ui.AgUiClient ──────────────────────► NOT Captured
```

The `ag_ui.AgUiClient` is instantiated separately in both `HttpTransport` and `ServerConnectionState`, creating:
1. **Observability gap** - SSE traffic invisible to network inspector
2. **Duplicate client instances** - Two AgUiClient instances per server
3. **No header refresh for SSE** - 401 handling only works for POST, not SSE

## Requirements

- [ ] Route SSE streams through HttpTransport (or a unified transport layer)
- [ ] Capture SSE request initiation in NetworkInspector
- [ ] Capture SSE stream completion/error in NetworkInspector
- [ ] Single AgUiClient instance per server (remove duplicate)
- [ ] Support 401 retry for SSE streams (header refresh)
- [ ] Maintain backward compatibility with existing RoomSession/Thread APIs

## Acceptance Criteria

- [ ] AC1: Opening network inspector shows SSE stream entries alongside HTTP POST entries
- [ ] AC2: SSE entries show: endpoint, start time, duration, event count, completion status
- [ ] AC3: Clicking an SSE entry shows stream metadata (not individual events)
- [ ] AC4: 401 during SSE stream triggers header refresh and retry
- [ ] AC5: No duplicate AgUiClient instances in ServerConnectionState

## Proposed Architecture

```
Unified Architecture:
                                         ┌─────────────────────┐
POST requests ──► HttpTransport ────────►│ NetworkInspector    │ ✓ Captured
                      │                  └─────────────────────┘
                      │                           ▲
SSE streams ─────► HttpTransport.runAgent() ──────┘ ✓ Captured
                      │
                      ▼
               ag_ui.AgUiClient (single instance, owned by HttpTransport)
```

## Options

### Option A: Extend HttpTransport to own AgUiClient
- HttpTransport creates and owns the single AgUiClient
- `runAgent()` already exists but delegates to AgUiClient - add inspector hooks there
- Remove AgUiClient from ServerConnectionState
- Pros: Minimal refactoring, clear ownership
- Cons: HttpTransport grows in responsibility

### Option B: Create NetworkTransportLayer abstraction
- New class that owns both http.Client and AgUiClient
- HttpTransport becomes a thin wrapper
- Pros: Better separation of concerns
- Cons: More refactoring, new abstraction layer

### Option C: Wrap AgUiClient with observable proxy
- Create InspectorAgUiClient that wraps AgUiClient
- Intercepts runAgent() calls for logging
- Pros: Non-invasive, follows existing patterns
- Cons: Another wrapper layer

**Recommendation:** Option A - least disruption, HttpTransport already has runAgent()

## Non-Goals

- Capturing individual SSE events in inspector (too verbose)
- Modifying ag_ui package itself
- Real-time SSE event streaming in inspector UI
- Replay of SSE streams

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| SSE stream interrupted | Show "interrupted" status with duration |
| SSE 401 mid-stream | Refresh headers, retry stream from beginning |
| Very long SSE stream | Show running duration, update on completion |
| Multiple concurrent SSE streams | Each tracked separately |
| SSE stream with no events | Show "completed" with 0 events |

## Dependencies

- Internal: SPEC:network-traffic-inspector (completed)
- External: ag_ui package (read-only, no modifications)

## Related

- ADRs: none yet
- Work Log: LOG:sse-transport-unification
- Related Spec: SPEC:network-traffic-inspector

---

## Completion Record

*Fill in when status → DONE*

| Field | Value |
|-------|-------|
| Completed | |
| Final Version | |

### Files Modified

-

### Notes

