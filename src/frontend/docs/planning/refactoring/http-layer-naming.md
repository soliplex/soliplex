# Refactor HTTP Layer Naming

## Summary

Rename HTTP layer classes for clarity:

1. Use `*Client` for the HTTP client hierarchy (interface + implementations)
2. Reserve `*Adapter` only for true Adapter pattern usage (bridging interfaces)

## Naming Changes

| Current Name | New Name | File Rename | Status |
|--------------|----------|-------------|--------|
| `HttpClientAdapter` | `SoliplexHttpClient` | `http_client_adapter.dart` → `soliplex_http_client.dart` | Done |
| `AdapterResponse` | `HttpResponse` | `adapter_response.dart` → `http_response.dart` | Done |
| `DartHttpAdapter` | `DartHttpClient` | `dart_http_adapter.dart` → `dart_http_client.dart` | Done |
| `ObservableHttpAdapter` | `ObservableHttpClient` | `observable_http_adapter.dart` → `observable_http_client.dart` | Done |
| `AdapterHttpClient` | `HttpClientAdapter` | `adapter_http_client.dart` → `http_client_adapter.dart` | Done |
| `CupertinoHttpAdapter` | `CupertinoHttpClient` | `cupertino_http_adapter.dart` → `cupertino_http_client.dart` | Done |
| `createPlatformAdapter` | `createPlatformClient` | (same file) | Done |

**Parameter/variable renames:**

| Context | Old | New | Status |
|---------|-----|-----|--------|
| `HttpTransport({required ... adapter})` | `adapter` | `client` | Done |
| `ObservableHttpClient({required ... adapter})` | `adapter` | `client` | Done |
| `HttpClientAdapter({required ... adapter})` | `adapter` | `client` | Done |
| `observableAdapterProvider` | - | `observableClientProvider` | Done |
| `httpAdapterProvider` | - | `soliplexHttpClientProvider` | Done |

## Architecture After Rename

### Class Hierarchy

```text
┌─────────────────────────────────────────────────────────────────────┐
│                     SoliplexHttpClient                              │
│                        (interface)                                  │
│  Methods: request(), requestStream(), close()                       │
│  Returns: HttpResponse                                              │
└─────────────────────────────────────────────────────────────────────┘
                              ▲
                              │ implements
          ┌───────────────────┼───────────────────┐
          │                   │                   │
┌─────────┴─────────┐ ┌───────┴───────┐ ┌─────────┴─────────┐
│   DartHttpClient  │ │ Cupertino-    │ │ ObservableHttp-   │
│                   │ │ HttpClient    │ │ Client            │
│ Default impl      │ │ iOS/macOS     │ │ Decorator         │
│ using package:http│ │ NSURLSession  │ │ wraps any client  │
│                   │ │               │ │ + observers       │
│ [soliplex_client] │ │ [soliplex_    │ │ [soliplex_client] │
│                   │ │ client_native]│ │                   │
└───────────────────┘ └───────────────┘ └───────────────────┘
```

### Provider Dependency Graph (Flutter App)

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         Flutter App                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  configProvider ─────────────────┐                                  │
│       │                          │                                  │
│       ▼                          ▼                                  │
│  urlBuilderProvider         observableClientProvider                │
│       │                          │                                  │
│       │                          │ Creates: ObservableHttpClient    │
│       │                          │   wrapping createPlatformClient()│
│       │                          │   with HttpLogNotifier observer  │
│       │                          │                                  │
│       │              ┌───────────┴───────────┐                      │
│       │              │                       │                      │
│       │              ▼                       ▼                      │
│       │    httpTransportProvider    soliplexHttpClientProvider      │
│       │              │                       │                      │
│       │              │ Creates:              │ Returns: same as     │
│       │              │ HttpTransport         │ observableClient-    │
│       │              │                       │ Provider             │
│       │              │                       │                      │
│       ▼              ▼                       ▼                      │
│  ┌─────────────────────────┐        httpClientProvider              │
│  │      apiProvider        │                 │                      │
│  │                         │                 │ Creates:             │
│  │  Creates: SoliplexApi   │                 │ HttpClientAdapter    │
│  │  (REST API client)      │                 │ (bridges to          │
│  │                         │                 │  http.Client)        │
│  └─────────────────────────┘                 │                      │
│                                              ▼                      │
│                                     agUiClientProvider              │
│                                              │                      │
│                                              │ Creates: AgUiClient  │
│                                              │ (SSE streaming)      │
│                                              ▼                      │
│                                     ┌─────────────────┐             │
│                                     │ ActiveRun-      │             │
│                                     │ Notifier        │             │
│                                     │ (orchestrates   │             │
│                                     │  AG-UI runs)    │             │
│                                     └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────┘
```

### Request Flow: REST API

```text
Widget calls api.getRooms()
         │
         ▼
┌─────────────────┐
│   SoliplexApi   │  Constructs URL, calls transport
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  HttpTransport  │  JSON encode, exception mapping, CancelToken
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ ObservableHttpClient│  Notifies HttpLogNotifier (onRequest/onResponse)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  DartHttpClient or  │  Platform-specific HTTP execution
│  CupertinoHttpClient│
└────────┬────────────┘
         │
         ▼
    HttpResponse
    (statusCode, bodyBytes, headers)
```

### Request Flow: AG-UI Streaming

```text
ActiveRunNotifier starts run
         │
         ▼
┌─────────────────┐
│   AgUiClient    │  External library, needs http.Client
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  HttpClientAdapter  │  TRUE ADAPTER: bridges SoliplexHttpClient → http.Client
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ ObservableHttpClient│  Notifies HttpLogNotifier (onStreamStart/onStreamEnd)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  DartHttpClient or  │  Platform-specific SSE stream
│  CupertinoHttpClient│
└────────┬────────────┘
         │
         ▼
    Stream<List<int>>
    (byte chunks for SSE parsing)
```

### Package Boundaries

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    soliplex_frontend (Flutter)                      │
│                                                                     │
│  lib/core/providers/api_provider.dart                               │
│    - observableClientProvider                                       │
│    - httpTransportProvider                                          │
│    - apiProvider                                                    │
│    - soliplexHttpClientProvider                                     │
│    - httpClientProvider                                             │
│    - agUiClientProvider                                             │
│                                                                     │
│  Depends on: soliplex_client, soliplex_client_native                │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ imports
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    soliplex_client (Pure Dart)                      │
│                                                                     │
│  lib/src/http/                                                      │
│    - soliplex_http_client.dart   (interface)                        │
│    - http_response.dart          (response data class)              │
│    - dart_http_client.dart       (default implementation)           │
│    - observable_http_client.dart (decorator)                        │
│    - http_client_adapter.dart    (bridges to http.Client)           │
│    - http_transport.dart         (JSON + exceptions layer)          │
│    - http_observer.dart          (observer interface + events)      │
│                                                                     │
│  lib/src/api/                                                       │
│    - soliplex_api.dart           (REST API client)                  │
│                                                                     │
│  No Flutter dependency - usable in CLI, server, etc.                │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ imports (for platform detection)
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                 soliplex_client_native (Platform)                   │
│                                                                     │
│  lib/src/clients/                                                   │
│    - cupertino_http_client.dart  (iOS/macOS NSURLSession)           │
│                                                                     │
│  lib/src/platform/                                                  │
│    - create_platform_client.dart (factory function)                 │
│    - create_platform_client_io.dart   (returns Cupertino on Apple)  │
│    - create_platform_client_stub.dart (returns Dart elsewhere)      │
│                                                                     │
│  Depends on: soliplex_client, cupertino_http                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Why "Adapter" Only for HttpClientAdapter

```text
┌────────────────────────────────────────────────────────────────────┐
│                     Adapter Pattern (GoF)                          │
│                                                                    │
│  "Convert the interface of a class into another interface         │
│   clients expect."                                                 │
│                                                                    │
│  HttpClientAdapter is the ONLY true adapter:                       │
│                                                                    │
│    AgUiClient ──expects──▶ http.Client                             │
│                               ▲                                    │
│                               │ extends                            │
│                    HttpClientAdapter                               │
│                               │                                    │
│                               │ delegates to                       │
│                               ▼                                    │
│                    SoliplexHttpClient                              │
│                                                                    │
│  It bridges OUR interface (SoliplexHttpClient)                     │
│  to THEIR interface (http.Client from package:http)                │
│                                                                    │
│  Other classes are NOT adapters:                                   │
│    - DartHttpClient: implementation, not adapter                   │
│    - CupertinoHttpClient: implementation, not adapter              │
│    - ObservableHttpClient: decorator pattern, not adapter          │
└────────────────────────────────────────────────────────────────────┘
```

## Commit Plan

| # | Description | Status |
|---|-------------|--------|
| 0 | Reset branch to new_frontend | Done |
| 1 | Rename HttpClientAdapter → SoliplexHttpClient | Done |
| 2 | Rename AdapterResponse → HttpResponse | Done |
| 3 | Rename DartHttpAdapter → DartHttpClient | Done |
| 4 | Rename ObservableHttpAdapter → ObservableHttpClient | Done |
| 5 | Rename AdapterHttpClient → HttpClientAdapter | Done |
| 6 | Rename CupertinoHttpAdapter → CupertinoHttpClient + createPlatformClient | Done |
| 7 | Finalize documentation | Done |
