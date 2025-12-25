# Refactor HTTP Layer Naming

## Summary

Rename HTTP layer classes for clarity:
1. Use `*Client` for the HTTP client hierarchy (interface + implementations)
2. Reserve `*Adapter` only for true Adapter pattern usage (bridging interfaces)

## Naming Changes

| Current Name | New Name | File Rename | Status |
|--------------|----------|-------------|--------|
| `HttpClientAdapter` | `SoliplexHttpClient` | `http_client_adapter.dart` → `soliplex_http_client.dart` | Pending |
| `AdapterResponse` | `HttpResponse` | `adapter_response.dart` → `http_response.dart` | Pending |
| `DartHttpAdapter` | `DartHttpClient` | `dart_http_adapter.dart` → `dart_http_client.dart` | Pending |
| `ObservableHttpAdapter` | `ObservableHttpClient` | `observable_http_adapter.dart` → `observable_http_client.dart` | Pending |
| `AdapterHttpClient` | `HttpClientAdapter` | `adapter_http_client.dart` → `http_client_adapter.dart` | Pending |
| `CupertinoHttpAdapter` | `CupertinoHttpClient` | `cupertino_http_adapter.dart` → `cupertino_http_client.dart` | Pending |
| `createPlatformAdapter` | `createPlatformClient` | (same file) | Pending |

**Parameter/variable renames:**

| Context | Old | New | Status |
|---------|-----|-----|--------|
| `HttpTransport({required ... adapter})` | `adapter` | `client` | Pending |
| `ObservableHttpClient({required ... adapter})` | `adapter` | `client` | Pending |
| `HttpClientAdapter({required ... adapter})` | `adapter` | `client` | Pending |
| `observableAdapterProvider` | - | `observableClientProvider` | Pending |
| `httpAdapterProvider` | - | `soliplexHttpClientProvider` | Pending |

## Architecture After Rename

```text
AgUiClient (external, needs http.Client)
    ↓
HttpClientAdapter (adapts SoliplexHttpClient TO http.Client)
    ↓
ObservableHttpClient (monitoring decorator)
    ↓
DartHttpClient / CupertinoHttpClient (platform implementations)
    ↓ implements
SoliplexHttpClient (interface)
```

```text
SoliplexApi
    ↓
HttpTransport (JSON + exceptions + cancellation)
    ↓
SoliplexHttpClient (interface)
```

## Commit Plan

| # | Description | Status |
|---|-------------|--------|
| 0 | Reset branch to new_frontend | Done |
| 1 | Rename HttpClientAdapter → SoliplexHttpClient | Pending |
| 2 | Rename AdapterResponse → HttpResponse | Pending |
| 3 | Rename DartHttpAdapter → DartHttpClient | Pending |
| 4 | Rename ObservableHttpAdapter → ObservableHttpClient | Pending |
| 5 | Rename AdapterHttpClient → HttpClientAdapter | Pending |
| 6 | Rename CupertinoHttpAdapter → CupertinoHttpClient + createPlatformClient | Pending |
| 7 | Finalize documentation | Pending |
