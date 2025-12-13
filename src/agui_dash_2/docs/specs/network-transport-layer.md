# SPEC: Network Transport Layer

| Field | Value |
|-------|-------|
| ID | SPEC:network-transport-layer |
| Status | DONE |
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

- [x] Create NetworkTransportLayer class owning http.Client and AgUiClient
- [x] Remove dead code from HttpTransport (_agUiClient, runAgent)
- [x] Remove AgUiClient from ServerConnectionState (now uses transport layer)
- [x] Route SSE through NetworkTransportLayer
- [x] NetworkInspector observes all traffic via transport layer
- [ ] Support 401 retry for SSE streams (deferred - requires ag_ui changes)
- [x] Maintain RoomSession/Thread API compatibility

## Acceptance Criteria

- [x] AC1: Single AgUiClient instance per server (in NetworkTransportLayer)
- [x] AC2: NetworkInspector shows SSE stream entries
- [x] AC3: SSE entries display: endpoint, duration, event count, status
- [ ] AC4: 401 during SSE triggers header refresh and retry (deferred - ag_ui handles SSE internally)
- [x] AC5: HttpTransport has no AgUiClient references (dead code removed)
- [x] AC-TEST: Unit tests exist for NetworkTransportLayer

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

| Field | Value |
|-------|-------|
| Completed | 2025-12-13 |
| Final Version | 0.1.0 |

### Files Modified

- `lib/core/network/network_transport_layer.dart` - **NEW** - Core transport layer class
- `lib/core/network/network_transport.dart` - Removed `runAgent()` from interface
- `lib/core/network/http_transport.dart` - Removed dead code, added transport layer support
- `lib/core/network/server_connection_state.dart` - Factory constructor, uses transport layer
- `lib/infrastructure/quick_agui/thread.dart` - Added `RunAgentDelegate`, `Thread.withDelegate()`
- `lib/core/network/room_session.dart` - Named parameters for `initialize()`
- `lib/core/network/connection_manager.dart` - Pass transport layer to session

### Tests

- `test/core/network/network_transport_layer_test.dart` - 9 tests for NetworkTransportLayer
- `test/core/network/room_session_state_test.dart` - Updated for named parameter syntax
- `test/core/network/room_session_enhanced_test.dart` - Updated for named parameter syntax

### Coverage

| File | Before | After | Delta |
|------|--------|-------|-------|
| http_transport.dart | 56% | n/a | Dead code removed |
| network_transport_layer.dart | n/a | New | New file |

### Notes

- AC4 (401 retry for SSE) deferred - requires changes to ag_ui package since it handles SSE internally
- SSE streams are recorded as single entries with metadata (method: 'SSE', event count, duration)
- Backward compatibility maintained via legacy `agUiClient` path in tests
- Debug logs confirm SSE lifecycle: start, event count, completion/error

