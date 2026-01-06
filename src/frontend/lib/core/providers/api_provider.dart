import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_client_native/soliplex_client_native.dart';
import 'package:soliplex_frontend/core/auth/auth_provider.dart';
import 'package:soliplex_frontend/core/providers/config_provider.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

/// Provider for the base observable HTTP client (without auth).
///
/// Creates a single [ObservableHttpClient] that wraps the platform client
/// and notifies [HttpLogNotifier] of all HTTP activity.
///
/// **Note**: Use [authenticatedClientProvider] for API requests; this provider
/// is the base client without authentication. Use this provider for:
/// - Token refresh calls (must not use authenticated client to avoid loops)
/// - Backend health checks (don't require authentication)
/// - Any other calls that should be observable but not authenticated
final baseHttpClientProvider = Provider<SoliplexHttpClient>((ref) {
  final baseClient = createPlatformClient();
  final observer = ref.watch(httpLogProvider.notifier);
  final observable = ObservableHttpClient(
    client: baseClient,
    observers: [observer],
  );
  ref.onDispose(() {
    try {
      observable.close();
    } catch (e, stack) {
      debugPrint('Error disposing observable client: $e\n$stack');
    }
  });
  return observable;
});

/// Provider for the shared HTTP client with auth token injection and refresh.
///
/// Wraps the observable client to automatically add Authorization header
/// when a token is available, and handles token refresh on expiry or 401.
///
/// This client is shared by both REST API ([httpTransportProvider]) and
/// SSE streaming ([soliplexHttpClientProvider]) to provide unified HTTP
/// logging, authentication, and token refresh.
///
/// **Decorator order**: `Refreshing(Authenticated(Observable(Platform)))`
/// - Refreshing handles proactive refresh and 401 retry (once only)
/// - Authenticated adds Authorization header
/// - Observer sees requests WITH auth headers (accurate logging)
/// - Observer sees all responses including 401s
///
/// **Lifecycle**: Lives for the entire app session. Closed when container
/// is disposed.
final authenticatedClientProvider = Provider<SoliplexHttpClient>((ref) {
  final observableClient = ref.watch(baseHttpClientProvider);
  final authNotifier = ref.watch(authProvider.notifier);

  // Inner client: adds Authorization header
  final authClient = AuthenticatedHttpClient(
    observableClient,
    () => ref.read(accessTokenProvider),
  );

  // Outer client: handles proactive refresh + 401 retry
  return RefreshingHttpClient(
    inner: authClient,
    refresher: authNotifier,
  );
});

/// Provider for the HTTP transport layer.
///
/// Creates a singleton [HttpTransport] instance using the shared
/// [authenticatedClientProvider]. All HTTP requests through this transport
/// are logged to [httpLogProvider].
///
/// **Lifecycle**: This is a non-autoDispose provider because the HTTP
/// transport should live for the entire app session.
///
/// **Threading**: Safe to call from any isolate. The underlying
/// adapter uses dart:http which is isolate-safe.
final httpTransportProvider = Provider<HttpTransport>((ref) {
  final client = ref.watch(authenticatedClientProvider);
  final transport = HttpTransport(client: client);

  // Note: Don't dispose transport here - client is managed by
  // authenticatedClientProvider
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

/// Provider for the Soliplex HTTP client.
///
/// Returns the shared [authenticatedClientProvider] to ensure all HTTP activity
/// (both REST and SSE) is logged through [httpLogProvider].
final soliplexHttpClientProvider = Provider<SoliplexHttpClient>((ref) {
  return ref.watch(authenticatedClientProvider);
});

/// Provider for http.Client that uses our HTTP client stack.
///
/// This bridges our [SoliplexHttpClient] to the standard [http.Client]
/// interface, allowing libraries like AgUiClient to use our HTTP
/// infrastructure.
final httpClientProvider = Provider<http.Client>((ref) {
  final soliplexClient = ref.watch(soliplexHttpClientProvider);
  final client = HttpClientAdapter(client: soliplexClient);
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
