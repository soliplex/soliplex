import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';

/// Provider for the HTTP transport layer.
///
/// Creates a singleton [HttpTransport] instance with [DartHttpAdapter]
/// for the app lifetime. The transport is shared across all API clients
/// to prevent resource leaks and unnecessary HTTP client creation.
///
/// **Lifecycle**: This is a non-autoDispose provider because the HTTP
/// transport should live for the entire app session. The transport will
/// be closed when the app is disposed (when ProviderContainer is disposed).
///
/// **Threading**: Safe to call from any isolate. The underlying
/// [DartHttpAdapter] uses dart:http which is isolate-safe.
final httpTransportProvider = Provider<HttpTransport>((ref) {
  final adapter = DartHttpAdapter();
  final transport = HttpTransport(adapter: adapter);

  // Register disposal callback to close transport and underlying HTTP client
  ref.onDispose(transport.close);

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
