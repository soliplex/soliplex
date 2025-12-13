# Work Log: Network Transport Layer

| Field | Value |
|-------|-------|
| Spec | SPEC:network-transport-layer |
| Created | 2025-12-13 |
| Status | active |

---

## 2025-12-13 - Session 1

### Context
Remove dead code from HttpTransport first. The `_agUiClient` instance and `runAgent()` method in HttpTransport are never called - actual SSE flows through ServerConnectionState.agUiClient.

### Baseline Coverage
*Captured at start via `flutter test --coverage`*

| File | Lines | Hit | Coverage |
|------|-------|-----|----------|
| lib/core/network/http_transport.dart | 82 | 46 | 56% |
| lib/core/network/server_connection_state.dart | 62 | 41 | 66% |

### Changes
- `lib/core/network/network_transport.dart`: Removed `runAgent()` from interface (was never called)
- `lib/core/network/http_transport.dart`: Removed `_agUiClient` field and `runAgent()` method (~50 lines of dead code)
- `lib/core/network/http_transport.dart`: Removed unused imports (`dart:async`, `ag_ui`, `cancel_token.dart`)
- `lib/core/network/network_transport_layer.dart`: **NEW** - Created NetworkTransportLayer class
  - Owns http.Client and ag_ui.AgUiClient
  - Provides `post()` with observable hooks for NetworkInspector
  - Provides `runAgent()` wrapper with SSE stream tracking (start, end, event count, errors)
  - Supports 401 retry with header refresh
- `lib/core/network/http_transport.dart`: Updated to optionally use NetworkTransportLayer
  - Added `transportLayer` parameter to constructor
  - Added `HttpTransport.fromTransportLayer()` factory constructor
  - Delegates HTTP operations to transport layer when provided
  - Legacy mode creates own http.Client (backward compatible)

### Decisions
- Removed `runAgent()` entirely from interface since no callers exist. SSE is handled separately via ServerConnectionState.agUiClient.
- NetworkTransportLayer records SSE streams as single entries (method: 'SSE') with metadata (event count, duration), not individual events (too verbose)

### Next
- [x] Update ServerConnectionState to use NetworkTransportLayer instead of creating AgUiClient directly
- [x] Wire SSE through NetworkTransportLayer for inspector visibility
- [ ] Add tests for NetworkTransportLayer

---

## 2025-12-13 - Session 2

### Context
Wire SSE through NetworkTransportLayer so NetworkInspector can observe SSE streams.

### Changes
- `lib/core/network/server_connection_state.dart`:
  - Changed to factory constructor pattern
  - Creates NetworkTransportLayer internally
  - HttpTransport now uses transport layer (no duplicate http.Client)
  - `agUiClient` getter returns from transport layer
  - Added `transportLayer` getter for SSE routing
- `lib/infrastructure/quick_agui/thread.dart`:
  - Added `RunAgentDelegate` typedef for SSE streaming
  - Added `Thread.withDelegate()` constructor for transport layer integration
  - `_getRunAgentStream()` helper uses delegate or falls back to client
- `lib/core/network/room_session.dart`:
  - Changed `initialize()` to named parameters
  - Accepts `transportLayer` or `agUiClient` (for backward compat)
  - Uses `Thread.withDelegate()` when transport layer provided
- `lib/core/network/connection_manager.dart`:
  - Updated to pass `transportLayer` to `session.initialize()`
- `test/core/network/room_session_enhanced_test.dart`, `room_session_state_test.dart`:
  - Updated `initialize()` calls to use named parameter syntax

### Decisions
- SSE now flows through NetworkTransportLayer when `transportLayer` is provided to `RoomSession.initialize()`
- Legacy path with `agUiClient` still works for tests
- Thread uses delegate pattern to avoid coupling to NetworkTransportLayer directly

### Next
- [x] Add tests for NetworkTransportLayer
- [ ] Verify SSE entries appear in NetworkInspector UI

---

## 2025-12-13 - Session 3 (Testing)

### Context
Add unit tests for NetworkTransportLayer.

### Tests Created
- `test/core/network/network_transport_layer_test.dart`: 9 tests
  - HTTP POST records request/response in inspector
  - HTTP POST records errors in inspector
  - 401 retry with header refresh
  - Dispose prevents further requests
  - isDisposed returns correct state
  - close is idempotent
  - Default headers used in requests
  - updateHeaders changes future requests
  - AgUiClient exposed for SSE

### Test Results
- **Total**: 291 tests
- **All passing**: Yes

### Next
- [ ] Manual verification: SSE entries appear in NetworkInspector UI

---
