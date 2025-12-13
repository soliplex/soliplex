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
- [ ] Update ServerConnectionState to use NetworkTransportLayer instead of creating AgUiClient directly
- [ ] Wire SSE through NetworkTransportLayer for inspector visibility
- [ ] Add tests for NetworkTransportLayer

---
