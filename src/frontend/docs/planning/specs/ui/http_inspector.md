# HTTP Inspector

Collapsible drawer showing all HTTP interactions in the app.

## Scope

- App-wide (not thread-scoped)
- Real-time updates as requests happen
- Uses existing `HttpObserver` infrastructure from `soliplex_client`

## Event Types

| Event | Display |
|-------|---------|
| `HttpRequestEvent` | method, uri, headers, timestamp |
| `HttpResponseEvent` | status code, duration, body size |
| `HttpErrorEvent` | method, uri, exception, duration |
| `HttpStreamStartEvent` | method, uri (for SSE) |
| `HttpStreamEndEvent` | bytes received, duration, error |

## Provider Architecture

Current problem: Two separate adapter instances exist (one for REST, one for SSE).

```text
createPlatformAdapter() ──────┬──────────────────────────────┐
                              │                              │
                              v                              v
                   httpTransportProvider        httpAdapterProvider
                              │                              │
                              v                              v
                        SoliplexApi                  AdapterHttpClient
                        (REST API)                         │
                                                           v
                                                     AgUiClient
                                                     (SSE streaming)
```

Solution: Single shared observable adapter at the base:

```text
createPlatformAdapter()
         │
         v
observableAdapterProvider  <── wraps with ObservableHttpAdapter + observer
         │
    ┌────┴────┐
    │         │
    v         v
httpTransportProvider    httpAdapterProvider
    │                          │
    v                          v
SoliplexApi              AdapterHttpClient -> AgUiClient
(REST)                   (SSE)
```

## Provider Integration

```dart
// 1. Observer that stores events
final httpLogProvider =
    NotifierProvider<HttpLogNotifier, List<HttpEvent>>(HttpLogNotifier.new);

// 2. Single shared observable adapter (NEW)
final observableAdapterProvider = Provider<HttpClientAdapter>((ref) {
  final baseAdapter = createPlatformAdapter();
  final observer = ref.watch(httpLogProvider.notifier);
  final observable = ObservableHttpAdapter(
    adapter: baseAdapter,
    observers: [observer],
  );
  ref.onDispose(observable.close);
  return observable;
});

// 3. Modify existing providers to use shared adapter
final httpTransportProvider = Provider<HttpTransport>((ref) {
  final adapter = ref.watch(observableAdapterProvider);  // Changed
  return HttpTransport(adapter: adapter);
  // Note: Don't dispose transport here - adapter disposed by observableAdapterProvider
});

final httpAdapterProvider = Provider<HttpClientAdapter>((ref) {
  return ref.watch(observableAdapterProvider);  // Changed: just forward
});
```

**Requires**: `HttpObserver`, `ObservableHttpAdapter` from soliplex_client.

## UI States

| State | Display |
|-------|---------|
| No events | "No HTTP activity yet" |
| Has events | Scrollable list, newest at bottom |

## Actions

- Clear log
- Copy event as JSON
- Expand/collapse event details

## Implementation

### Files to Create

| File | Purpose |
|------|---------|
| `lib/core/providers/http_log_provider.dart` | HttpLogNotifier (Notifier + HttpObserver) |
| `lib/features/inspector/http_inspector_panel.dart` | Drawer panel with event list |
| `lib/features/inspector/widgets/http_event_tile.dart` | Single event display |

### Files to Modify

| File | Change |
|------|--------|
| `lib/core/providers/api_provider.dart` | Add `observableAdapterProvider`, modify `httpTransportProvider` and `httpAdapterProvider` to use it |
| `lib/features/thread/thread_screen.dart` | Add endDrawer + toggle button |

### Test Files

| File |
|------|
| `test/core/providers/http_log_provider_test.dart` |
| `test/features/inspector/http_inspector_panel_test.dart` |
| `test/features/inspector/widgets/http_event_tile_test.dart` |

## UI Design

**Layout:** Collapsible `endDrawer` on ThreadScreen (400px desktop, full mobile)

**Event tile:**

```text
+-------------------------------------+
| GET /api/v1/rooms                   |
| 10:23:45 -> 200 OK (45ms, 1.2KB)    |
+-------------------------------------+

+-------------------------------------+
| POST /api/v1/threads/.../runs       |
| 10:23:50 -> NetworkException (2s)   |
+-------------------------------------+

+-------------------------------------+
| SSE /api/v1/runs/.../stream         |
| 10:23:51 -> streaming... (5.2KB)    |
+-------------------------------------+
```

**Colors:**

- Request sent: blue
- Response success (2xx): green
- Response error (4xx/5xx): orange
- Network error: red
- Stream active: purple
- Stream complete: green

## Commit Plan

### Commit 1: Add HttpLogNotifier

**Status:** Complete

| File | Type | Status |
|------|------|--------|
| `lib/core/providers/http_log_provider.dart` | New | Done |
| `test/core/providers/http_log_provider_test.dart` | New | Done (12 tests) |

Standalone observer that stores HTTP events. Includes event cap (500 max) to prevent unbounded memory growth. No wiring yet.

### Commit 2: Wire observer into HTTP stack

**Status:** Pending

| File | Type | Change |
|------|------|--------|
| `lib/core/providers/api_provider.dart` | Modify | Add `observableAdapterProvider`, update `httpTransportProvider` and `httpAdapterProvider` |

### Commit 3: Add HTTP event UI components

**Status:** Pending

| File | Type |
|------|------|
| `lib/features/inspector/widgets/http_event_tile.dart` | New |
| `test/features/inspector/widgets/http_event_tile_test.dart` | New |
| `lib/features/inspector/http_inspector_panel.dart` | New |
| `test/features/inspector/http_inspector_panel_test.dart` | New |

### Commit 4: Integrate drawer into ThreadScreen

**Status:** Pending

| File | Type | Change |
|------|------|--------|
| `lib/features/thread/thread_screen.dart` | Modify | Add endDrawer + toggle button |

## Dependencies

- No new packages
- Uses existing `HttpObserver` from `soliplex_client`
