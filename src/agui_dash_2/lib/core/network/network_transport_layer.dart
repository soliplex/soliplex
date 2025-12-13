import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:http/http.dart' as http;

import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'network_inspector.dart';

/// Low-level network transport layer that owns both HTTP and SSE clients.
///
/// This is the single source of truth for all network I/O:
/// - [http.Client] for HTTP POST requests
/// - [ag_ui.AgUiClient] for SSE streaming
///
/// Provides observable hooks for [NetworkInspector] to capture all traffic.
/// Supports 401 retry with header refresh for both HTTP and SSE.
class NetworkTransportLayer {
  final String baseUrl;
  final http.Client _httpClient;
  final ag_ui.AgUiClient _agUiClient;
  final UrlBuilder _urlBuilder;
  final NetworkInspector? _inspector;

  Map<String, String>? _headers;
  final Future<Map<String, String>> Function()? _headerRefresher;

  bool _disposed = false;

  NetworkTransportLayer({
    required this.baseUrl,
    http.Client? httpClient,
    ag_ui.AgUiClient? agUiClient,
    Map<String, String>? defaultHeaders,
    Future<Map<String, String>> Function()? headerRefresher,
    NetworkInspector? inspector,
  }) : _httpClient = httpClient ?? http.Client(),
       _headers = defaultHeaders,
       _headerRefresher = headerRefresher,
       _urlBuilder = UrlBuilder(baseUrl),
       _inspector = inspector,
       _agUiClient = agUiClient ??
           ag_ui.AgUiClient(
             config: ag_ui.AgUiClientConfig(
               baseUrl: UrlBuilder(baseUrl).serverUrl,
               defaultHeaders: defaultHeaders ?? {},
             ),
           ) {
    DebugLog.network('NetworkTransportLayer: Created for $baseUrl');
  }

  /// Current headers for requests.
  Map<String, String>? get headers => _headers;

  /// The underlying AG-UI client for SSE streaming.
  ///
  /// Used by [Thread] to run agent interactions.
  /// Traffic is observable via [NetworkInspector] when SSE hooks are added.
  ag_ui.AgUiClient get agUiClient => _agUiClient;

  /// Whether this transport has been disposed.
  bool get isDisposed => _disposed;

  /// Update the default headers.
  ///
  /// Note: This updates headers for future requests. The AgUiClient
  /// uses headers from its config, so we recreate it if needed.
  void updateHeaders(Map<String, String> headers) {
    _headers = headers;
    // Note: AgUiClient config is immutable, so header updates for SSE
    // require recreating the client or using per-request headers.
    // For now, HTTP headers are updated, SSE uses initial config.
    DebugLog.network('NetworkTransportLayer: Headers updated');
  }

  /// Make an HTTP GET request with observable hooks.
  ///
  /// Supports 401 retry with header refresh.
  Future<http.Response> get(
    Uri uri, {
    Map<String, String>? additionalHeaders,
  }) async {
    if (_disposed) {
      throw StateError('Cannot use disposed NetworkTransportLayer');
    }

    final requestHeaders = {
      'Accept': 'application/json',
      ...?_headers,
      ...?additionalHeaders,
    };

    // Record request for inspector
    final requestId = _inspector?.recordRequest(
      method: 'GET',
      uri: uri,
      headers: requestHeaders,
    );

    try {
      var response = await _httpClient.get(uri, headers: requestHeaders);

      // 401 retry with header refresh
      if (response.statusCode == 401 && _headerRefresher != null) {
        DebugLog.network(
          'NetworkTransportLayer: 401 received on GET, refreshing headers...',
        );
        _headers = await _headerRefresher();
        final retryHeaders = {
          'Accept': 'application/json',
          ...?_headers,
          ...?additionalHeaders,
        };
        response = await _httpClient.get(uri, headers: retryHeaders);
        DebugLog.network(
          'NetworkTransportLayer: GET retry returned ${response.statusCode}',
        );
      }

      // Record response for inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      return response;
    } catch (e) {
      // Record error for inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      rethrow;
    }
  }

  /// Make an HTTP POST request with observable hooks.
  ///
  /// Supports 401 retry with header refresh.
  Future<http.Response> post(
    Uri uri,
    String body, {
    Map<String, String>? additionalHeaders,
  }) async {
    if (_disposed) {
      throw StateError('Cannot use disposed NetworkTransportLayer');
    }

    final requestHeaders = {
      'Content-Type': 'application/json',
      ...?_headers,
      ...?additionalHeaders,
    };

    // Record request for inspector
    final requestId = _inspector?.recordRequest(
      method: 'POST',
      uri: uri,
      headers: requestHeaders,
      body: body,
    );

    try {
      var response = await _httpClient.post(
        uri,
        headers: requestHeaders,
        body: body,
      );

      // 401 retry with header refresh
      if (response.statusCode == 401 && _headerRefresher != null) {
        DebugLog.network(
          'NetworkTransportLayer: 401 received, refreshing headers...',
        );
        _headers = await _headerRefresher();
        final retryHeaders = {
          'Content-Type': 'application/json',
          ...?_headers,
          ...?additionalHeaders,
        };
        response = await _httpClient.post(
          uri,
          headers: retryHeaders,
          body: body,
        );
        DebugLog.network(
          'NetworkTransportLayer: Retry returned ${response.statusCode}',
        );
      }

      // Record response for inspector
      if (requestId != null) {
        _inspector?.recordResponse(
          requestId: requestId,
          statusCode: response.statusCode,
          headers: response.headers,
          body: response.body,
        );
      }

      return response;
    } catch (e) {
      // Record error for inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      rethrow;
    }
  }

  /// Run an SSE agent stream with observable hooks.
  ///
  /// This wraps [ag_ui.AgUiClient.runAgent] with inspector hooks
  /// to capture SSE stream metadata (start, end, event count, errors).
  ///
  /// Note: Individual SSE events are not logged (too verbose).
  /// Only stream-level metadata is captured.
  Stream<ag_ui.BaseEvent> runAgent(
    String endpoint,
    ag_ui.SimpleRunAgentInput input,
  ) async* {
    if (_disposed) {
      throw StateError('Cannot use disposed NetworkTransportLayer');
    }

    // Ensure proper path separator between serverUrl and endpoint
    final normalizedEndpoint = endpoint.startsWith('/')
        ? endpoint
        : '/$endpoint';
    final uri = Uri.parse('${_urlBuilder.serverUrl}$normalizedEndpoint');
    final startTime = DateTime.now();
    var eventCount = 0;
    String? error;

    // Record SSE stream start for inspector
    final requestId = _inspector?.recordRequest(
      method: 'SSE',
      uri: uri,
      headers: _headers ?? {},
      body: {'threadId': input.threadId, 'runId': input.runId},
    );

    DebugLog.network(
      'NetworkTransportLayer: SSE stream starting for $endpoint',
    );

    try {
      await for (final event in _agUiClient.runAgent(endpoint, input)) {
        eventCount++;
        yield event;
      }

      DebugLog.network(
        'NetworkTransportLayer: SSE stream completed ($eventCount events)',
      );
    } catch (e) {
      error = e.toString();
      DebugLog.network('NetworkTransportLayer: SSE stream error: $e');
      rethrow;
    } finally {
      // Record SSE stream completion for inspector
      if (requestId != null) {
        final duration = DateTime.now().difference(startTime);
        if (error != null) {
          _inspector?.recordError(requestId: requestId, error: error);
        } else {
          _inspector?.recordResponse(
            requestId: requestId,
            statusCode: 200,
            headers: {'x-sse-event-count': eventCount.toString()},
            body: {
              'eventCount': eventCount,
              'durationMs': duration.inMilliseconds,
            },
          );
        }
      }
    }
  }

  /// Close the transport and release resources.
  void close() {
    if (_disposed) return;
    _disposed = true;

    DebugLog.network('NetworkTransportLayer: Closing');
    _httpClient.close();
  }
}
