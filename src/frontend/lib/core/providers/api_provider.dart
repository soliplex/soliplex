import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/soliplex_client_native.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

/// Provider for the shared observable HTTP adapter.
///
/// Creates a single [ObservableHttpAdapter] that wraps the platform adapter
/// and notifies [HttpLogNotifier] of all HTTP activity. This adapter is shared
/// by both REST API ([httpTransportProvider]) and SSE streaming
/// ([httpAdapterProvider]) to provide unified HTTP logging.
///
/// **Lifecycle**: Lives for the entire app session. Closed when container
/// is disposed.
final observableAdapterProvider = Provider<HttpClientAdapter>((ref) {
  final baseAdapter = createPlatformAdapter();
  final observer = ref.watch(httpLogProvider.notifier);
  final observable = ObservableHttpAdapter(
    adapter: baseAdapter,
    observers: [observer],
  );
  ref.onDispose(() {
    try {
      observable.close();
    } catch (e, stack) {
      debugPrint('Error disposing observable adapter: $e\n$stack');
    }
  });
  return observable;
});

/// Provider for the HTTP transport layer.
///
/// Creates a singleton [HttpTransport] instance using the shared
/// [observableAdapterProvider]. All HTTP requests through this transport
/// are logged to [httpLogProvider].
///
/// **Lifecycle**: This is a non-autoDispose provider because the HTTP
/// transport should live for the entire app session.
///
/// **Threading**: Safe to call from any isolate. The underlying
/// adapter uses dart:http which is isolate-safe.
final httpTransportProvider = Provider<HttpTransport>((ref) {
  final adapter = ref.watch(observableAdapterProvider);
  final transport = HttpTransport(adapter: adapter);

  // Note: Don't dispose transport here - adapter is managed by
  // observableAdapterProvider
  return transport;
});

/// Provider for the URL builder.
///
/// Creates a [UrlBuilder] configured with the base URL from [configProvider].
/// Automatically reconstructs when the config changes (e.g., user changes
/// backend URL in settings).
///
/// The URL builder appends `/api/v1` to the base URL to construct
/// API endpoint URLs.
final urlBuilderProvider = Provider<UrlBuilder>((ref) {
  final config = ref.watch(configProvider);
  return UrlBuilder('${config.baseUrl}/api/v1');
});

/// Provider for the SoliplexApi instance.
///
/// Creates a single API client instance for the app lifetime.
/// The client is configured using dependencies from [httpTransportProvider]
/// and [urlBuilderProvider].
///
/// **Lifecycle**: This is a non-autoDispose provider because the API client
/// should live for the entire app session. The client shares the HTTP
/// transport with other potential API clients.
///
/// **Dependency Graph**:
/// ```text
/// configProvider
///     ↓
/// urlBuilderProvider → apiProvider
///                         ↑
/// httpTransportProvider ──┘
/// ```
///
/// **Usage Example**:
/// ```dart
/// final api = ref.watch(apiProvider);
/// final rooms = await api.getRooms();
/// ```
///
/// **Error Handling**:
/// Methods throw [SoliplexException] subtypes:
/// - [NetworkException]: Connection failures, timeouts
/// - [AuthException]: 401/403 authentication errors
/// - [NotFoundException]: 404 resource not found
/// - [ApiException]: Other 4xx/5xx server errors
/// - [CancelledException]: Request was cancelled
final apiProvider = Provider<SoliplexApi>((ref) {
  final transport = ref.watch(httpTransportProvider);
  final urlBuilder = ref.watch(urlBuilderProvider);

  final api = SoliplexApi(
    transport: transport,
    urlBuilder: urlBuilder,
  );

  // Register disposal callback
  // Note: We don't close the transport here as it's managed by
  // httpTransportProvider. We just clean up the API instance.
  ref.onDispose(api.close);

  return api;
});

/// Provider for the HTTP client adapter.
///
/// Returns the shared [observableAdapterProvider] to ensure all HTTP activity
/// (both REST and SSE) is logged through [httpLogProvider].
final httpAdapterProvider = Provider<HttpClientAdapter>((ref) {
  return ref.watch(observableAdapterProvider);
});

/// Provider for http.Client that uses our adapter stack.
///
/// This bridges our [HttpClientAdapter] to the standard [http.Client]
/// interface,
/// allowing libraries like AgUiClient to use our HTTP infrastructure.
final httpClientProvider = Provider<http.Client>((ref) {
  final adapter = ref.watch(httpAdapterProvider);
  final client = AdapterHttpClient(adapter: adapter);
  ref.onDispose(client.close);
  return client;
});

/// Provider for the AG-UI client.
///
/// Creates an [AgUiClient] that uses our HTTP stack via [httpClientProvider].
/// This ensures AG-UI requests go through our platform adapters and observers.
final agUiClientProvider = Provider<AgUiClient>((ref) {
  final httpClient = ref.watch(httpClientProvider);
  final config = ref.watch(configProvider);

  final client = AgUiClient(
    config: AgUiClientConfig(baseUrl: '${config.baseUrl}/api/v1'),
    httpClient: httpClient,
  );

  ref.onDispose(client.close);
  return client;
});
