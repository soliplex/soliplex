# SPEC: Network Transport Layer

| Field | Value |
|-------|-------|
| ID | SPEC:network-transport-layer |
| Status | IN_PROGRESS |
| Created | 2025-12-13 |
| Updated | 2025-12-13 |
| Version | 0.1.0 |
| Author | runyaga |

## Summary

Create a NetworkTransportLayer abstraction that owns both `http.Client` and `ag_ui.AgUiClient`, unifying all network traffic through one layer. This provides a single source of truth for network I/O, enables complete NetworkInspector coverage (including SSE), and establishes cleaner separation of concerns.

**Supersedes:** SPEC:sse-transport-unification

## Problem

Current architecture has fragmented network ownership:

```
┌─────────────────────────────────────────────────────────────┐
│ HttpTransport                                               │
│   └─ http.Client (used)                                     │
│   └─ _agUiClient (DEAD CODE - never called)                 │
├─────────────────────────────────────────────────────────────┤
│ ServerConnectionState                                       │
│   └─ agUiClient (actually used for SSE)                     │
│      └─ RoomSession → Thread → client.runAgent()            │
└─────────────────────────────────────────────────────────────┘
```

Problems:
1. **Duplicate instances** - Two AgUiClient per server, one unused
2. **SSE bypasses HttpTransport** - NetworkInspector misses SSE traffic
3. **No 401 retry for SSE** - Header refresh only works for HTTP POST
4. **Dead code** - HttpTransport._agUiClient and runAgent() never called

## Requirements

- [ ] Create NetworkTransportLayer class owning http.Client and AgUiClient
- [ ] Remove dead code from HttpTransport (_agUiClient, runAgent)
- [ ] Remove AgUiClient from ServerConnectionState
- [ ] Route SSE through NetworkTransportLayer
- [ ] NetworkInspector observes all traffic via transport layer
- [ ] Support 401 retry for SSE streams
- [ ] Maintain RoomSession/Thread API compatibility

## Acceptance Criteria

- [ ] AC1: Single AgUiClient instance per server (in NetworkTransportLayer)
- [ ] AC2: NetworkInspector shows SSE stream entries
- [ ] AC3: SSE entries display: endpoint, duration, event count, status
- [ ] AC4: 401 during SSE triggers header refresh and retry
- [ ] AC5: HttpTransport has no AgUiClient references (dead code removed)
- [ ] AC-TEST: Unit tests exist for NetworkTransportLayer

## Architecture

### Before
```
POST ──► HttpTransport ──► NetworkInspector ✓
SSE  ──► ServerConnectionState.agUiClient ──► (missed)
```

### After
```
POST ──► HttpTransport ──► NetworkTransportLayer ──► NetworkInspector ✓
SSE  ──► HttpTransport ──► NetworkTransportLayer ──► NetworkInspector ✓
                                │
                                ▼
                          http.Client + AgUiClient
```

### Class Responsibilities

| Class | Responsibility |
|-------|----------------|
| NetworkTransportLayer | Owns http.Client + AgUiClient, observable hooks |
| HttpTransport | API methods (sendMessage, fetchRooms, runAgent) |
| NetworkInspector | Observes traffic from transport layer |
| ServerConnectionState | Connection lifecycle, no network clients |

## Non-Goals

- Capturing individual SSE events (too verbose)
- Modifying ag_ui package
- Real-time SSE event streaming in inspector UI
- WebSocket support (future work)

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| SSE stream interrupted | Inspector shows "interrupted" with duration |
| SSE 401 mid-stream | Refresh headers, retry from beginning |
| Long-running SSE stream | Show running duration, update on completion |
| Concurrent SSE streams | Each tracked separately |
| Network disconnect during SSE | Show error status |

## Dependencies

- Internal: SPEC:network-traffic-inspector (completed)
- External: ag_ui package (no modifications)

## Related

- ADRs: none yet
- Work Log: LOG:network-transport-layer
- Supersedes: SPEC:sse-transport-unification

---

## Completion Record

*Fill in when status → DONE*

| Field | Value |
|-------|-------|
| Completed | |
| Final Version | |

### Files Modified

-

### Tests

-

### Coverage

| File | Before | After | Delta |
|------|--------|-------|-------|
| | | | |

### Notes

