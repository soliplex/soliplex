# SPEC: Network Traffic Inspector

| Field | Value |
|-------|-------|
| ID | SPEC:network-traffic-inspector |
| Status | DONE |
| Created | 2025-12-13 |
| Updated | 2025-12-13 |
| Version | 1.0.0 |
| Author | runyaga |

## Summary

A cross-platform network traffic inspector for diagnosing HTTP communication issues between the app and backend services. Modeled on browser developer tools network inspectors, it provides a familiar interface for viewing request/response flow with expandable details and curl export capability. Works on web, desktop, and mobile platforms.

## Requirements

- [x] List view showing all HTTP requests with columns: Method (VERB), URL, Status Code, Latency, Timestamp
- [x] Sortable/filterable columns (at minimum by status code and method) *(filter API implemented, UI deferred)*
- [x] Click-to-expand detail view for individual requests
- [x] Request detail panel showing: headers, query params, request body
- [x] Response detail panel showing: headers, status, response body
- [x] Smart content detection: render JSON/text nicely, hide binary with "Show binary" option
- [x] Copy as curl button that generates a curl-compatible command
- [x] Historical log storage (persist during session, no streaming complexity)
- [x] Clear log functionality
- [x] Cross-platform support (web, desktop, mobile)

## Acceptance Criteria

- [x] AC1: User can open inspector and see a table of recent HTTP requests with method, URL, status, latency, and time
- [x] AC2: User can click a request row and see expanded request/response details
- [x] AC3: JSON responses are pretty-printed; binary content shows placeholder with option to reveal
- [x] AC4: User can click "Copy as curl" and paste a working curl command in terminal
- [x] AC5: User can clear the log to start fresh
- [x] AC6: Inspector works identically on web, desktop, and mobile builds

## Non-Goals

- Not a proxy or man-in-the-middle tool - only inspects traffic from this app
- No request replay/modification functionality
- No persistent storage across app restarts
- No WebSocket/SSE frame-level inspection (HTTP requests only)
- No request interception or blocking

## Edge Cases

| Case | Expected Behavior |
|------|-------------------|
| Very large response body (>1MB) | Truncate display with "Show full response" option |
| Binary content (images, etc.) | Show content-type and size, "Show binary" button |
| Failed request (network error) | Show error state in status column, error details in expanded view |
| Request with no response body | Show empty state in response panel |
| Sensitive headers (Authorization) | Display normally (user's own traffic, not a security concern) |
| Concurrent requests | Each logged separately with accurate timestamps |

## Dependencies

- External: None (uses existing HTTP client infrastructure)
- Internal: Requires HTTP client wrapper/interceptor to capture traffic

## Related

- ADRs: none yet
- Work Log: LOG:network-traffic-inspector

---

## Completion Record

| Field | Value |
|-------|-------|
| Completed | 2025-12-13 |
| Final Version | 1.0.0 |

### Files Modified

**Core implementation:**
- `lib/core/network/network_inspector_models.dart` - NetworkEntry data model
- `lib/core/network/network_inspector.dart` - NetworkInspector class and Riverpod providers
- `lib/core/network/http_transport.dart` - Inspector hooks in post() and cancelRun()
- `lib/core/network/server_connection_state.dart` - Inspector parameter passthrough
- `lib/core/network/connection_registry.dart` - Inspector injection from provider
- `lib/core/network/connection_manager.dart` - Lint fixes

**UI:**
- `lib/features/inspector/network_inspector_screen.dart` - Inspector UI
- `lib/app_shell.dart` - Navigation extension
- `lib/features/chat/chat_screen.dart` - Inspector button in app bar

**Tests:**
- `test/core/network/network_inspector_models_test.dart` - 40 unit tests for NetworkEntry
- `test/core/network/network_inspector_test.dart` - 37 unit tests for NetworkInspector

### Notes

- Filter UI deferred to future enhancement; underlying `filter()` API is implemented and tested
- SSE stream inspection is tracked separately in SPEC:sse-transport-unification
