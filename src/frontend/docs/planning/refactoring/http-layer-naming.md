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
| 1 | Rename HttpClientAdapter → SoliplexHttpClient | Done |
| 2 | Rename AdapterResponse → HttpResponse | Done |
| 3 | Rename DartHttpAdapter → DartHttpClient | Done |
| 4 | Rename ObservableHttpAdapter → ObservableHttpClient | Done |
| 5 | Rename AdapterHttpClient → HttpClientAdapter | Done |
| 6 | Rename CupertinoHttpAdapter → CupertinoHttpClient + createPlatformClient | Done |
| 7 | Finalize documentation | Done |
