# Refactor HTTP Layer Naming

## Summary

Rename HTTP layer classes for clarity:

1. Use `*Client` for the HTTP client hierarchy (interface + implementations)
2. Reserve `*Adapter` only for true Adapter pattern usage (bridging interfaces)

## Naming Changes

| Old Name | New Name | File Rename |
|----------|----------|-------------|
| `HttpClientAdapter` | `SoliplexHttpClient` | `http_client_adapter.dart` → `soliplex_http_client.dart` |
| `AdapterResponse` | `HttpResponse` | `adapter_response.dart` → `http_response.dart` |
| `DartHttpAdapter` | `DartHttpClient` | `dart_http_adapter.dart` → `dart_http_client.dart` |
| `ObservableHttpAdapter` | `ObservableHttpClient` | `observable_http_adapter.dart` → `observable_http_client.dart` |
| `AdapterHttpClient` | `HttpClientAdapter` | `adapter_http_client.dart` → `http_client_adapter.dart` |
| `CupertinoHttpAdapter` | `CupertinoHttpClient` | `cupertino_http_adapter.dart` → `cupertino_http_client.dart` |
| `createPlatformAdapter` | `createPlatformClient` | (same file) |

**Parameter/variable renames:**

| Context | Old | New |
|---------|-----|-----|
| `HttpTransport({required ... adapter})` | `adapter` | `client` |
| `ObservableHttpClient({required ... adapter})` | `adapter` | `client` |
| `HttpClientAdapter({required ... adapter})` | `adapter` | `client` |
| `observableAdapterProvider` | - | `observableClientProvider` |
| `httpAdapterProvider` | - | `soliplexHttpClientProvider` |

## Architecture

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
│       │              │ Creates:              │ Alias: exposes       │
│       │              │ HttpTransport         │ SoliplexHttpClient   │
│       │              │                       │ interface for SSE    │
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

**Note:** `soliplexHttpClientProvider` is an alias for `observableClientProvider`.
Both return the same `ObservableHttpClient` instance. The alias exists to provide
a semantically clear name when code needs the `SoliplexHttpClient` interface
(e.g., for SSE streaming) rather than knowing about the observable wrapper.

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
         │ imports both packages
         │
    ┌────┴────────────────────────────┐
    │                                 │
    ▼                                 ▼
┌───────────────────────────┐  ┌──────────────────────────────────────┐
│ soliplex_client           │  │ soliplex_client_native               │
│ (Pure Dart)               │  │ (Platform-specific)                  │
│                           │  │                                      │
│ lib/src/http/             │  │ lib/src/clients/                     │
│  - soliplex_http_client   │◀─┤  - cupertino_http_client             │
│    (interface)            │  │    (iOS/macOS NSURLSession)          │
│  - http_response          │  │                                      │
│  - dart_http_client       │  │ lib/src/platform/                    │
│  - observable_http_client │  │  - create_platform_client            │
│  - http_client_adapter    │  │    (factory function)                │
│  - http_transport         │  │                                      │
│  - http_observer          │  │ Depends on:                          │
│                           │  │  - soliplex_client (for interface)   │
│ lib/src/api/              │  │  - cupertino_http                    │
│  - soliplex_api           │  │                                      │
│                           │  │                                      │
│ No Flutter dependency     │  │                                      │
└───────────────────────────┘  └──────────────────────────────────────┘
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
