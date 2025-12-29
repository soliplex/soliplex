import 'dart:async';
import 'dart:convert';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:http/http.dart' as http;
import 'package:soliplex/core/network/network_inspector.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// Low-level network transport layer that owns both HTTP and SSE clients.
///
/// This is the single source of truth for all network I/O:
/// - [http.Client] for HTTP POST requests
/// - [ag_ui.AgUiClient] for SSE streaming
///
/// Provides observable hooks for NetworkInspector to capture all traffic.
/// Supports 401 retry with header refresh for both HTTP and SSE.
class NetworkTransportLayer {
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
       _agUiClient =
           agUiClient ??
           ag_ui.AgUiClient(
             config: ag_ui.AgUiClientConfig(
               baseUrl: UrlBuilder(baseUrl).serverUrl,
               defaultHeaders: defaultHeaders ?? {},
             ),
           ) {
    DebugLog.network('NetworkTransportLayer: Created for $baseUrl');
  }
  final String baseUrl;
  final http.Client _httpClient;
  final UrlBuilder _urlBuilder;
  final NetworkInspector? _inspector;

  ag_ui.AgUiClient _agUiClient;
  Map<String, String>? _headers;
  final Future<Map<String, String>> Function()? _headerRefresher;

  bool _disposed = false;

  /// The underlying HTTP client.
  ///
  /// Exposed for cases where raw HTTP access is needed (e.g.
  /// CompletionsClient).
  http.Client get httpClient => _httpClient;

  /// Current headers for requests.
  Map<String, String>? get headers => _headers;

  /// The underlying AG-UI client for SSE streaming.
  ///
  /// Used by Thread to run agent interactions.
  /// Traffic is observable via NetworkInspector when SSE hooks are added.
  ag_ui.AgUiClient get agUiClient => _agUiClient;

  /// Whether this transport has been disposed.
  bool get isDisposed => _disposed;

  Future<void>? _refreshFuture;

  /// Handles 401 Unauthorized by refreshing headers.
  /// Uses a cached future to ensure only one refresh happens at a time.
  /// All concurrent callers await the same future.
  Future<void> _handle401() async {
    if (_headerRefresher == null) {
      DebugLog.network(
        'NetworkTransportLayer: 401 received but no refresher configured.',
      );
      return;
    }

    // If already refreshing, wait for the existing operation
    if (_refreshFuture != null) {
      DebugLog.network(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'NetworkTransportLayer: 401 received. Refresh already in progress. Waiting...',
      );
      await _refreshFuture;
      DebugLog.network(
        'NetworkTransportLayer: Waited for existing refresh. Resuming request.',
      );
      return;
    }

    DebugLog.network(
      'NetworkTransportLayer: 401 received. Initiating token refresh lock.',
    );

    // Store the refresh operation as a future that all callers can await.
    // This avoids orphaned completer errors.
    _refreshFuture = _doRefresh();

    try {
      await _refreshFuture;
    } finally {
      _refreshFuture = null;
      DebugLog.network('NetworkTransportLayer: Refresh lock released.');
    }
  }

  /// Performs the actual token refresh.
  Future<void> _doRefresh() async {
    DebugLog.network('NetworkTransportLayer: Calling header refresher...');
    final newHeaders = await _headerRefresher!();
    DebugLog.network(
      'NetworkTransportLayer: Header refresher returned. Updating headers.',
    );
    updateHeaders(newHeaders);
    DebugLog.network(
      'NetworkTransportLayer: Token refresh completed successfully.',
    );
  }

  /// Update the default headers.
  ///
  /// Recreates the AgUiClient to ensure new headers are used for SSE.
  void updateHeaders(Map<String, String> headers) {
    _headers = headers;

    // Recreate SSE client with new headers
    _agUiClient = ag_ui.AgUiClient(
      config: ag_ui.AgUiClientConfig(
        baseUrl: _urlBuilder.serverUrl,
        defaultHeaders: _headers ?? {},
      ),
    );

    DebugLog.network(
      'NetworkTransportLayer: Headers updated and SSE client recreated',
    );
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
        await _handle401();

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
    } on Object catch (e) {
      // Record error for inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      rethrow;
    }
  }

  /// Make an HTTP HEAD request with observable hooks.
  ///
  /// Supports 401 retry with header refresh.
  Future<http.Response> head(
    Uri uri, {
    Map<String, String>? additionalHeaders,
  }) async {
    if (_disposed) {
      throw StateError('Cannot use disposed NetworkTransportLayer');
    }

    final requestHeaders = {
      ...?_headers,
      ...?additionalHeaders,
    };

    // Record request for inspector
    final requestId = _inspector?.recordRequest(
      method: 'HEAD',
      uri: uri,
      headers: requestHeaders,
    );

    try {
      var response = await _httpClient.head(uri, headers: requestHeaders);

      // 401 retry with header refresh
      if (response.statusCode == 401 && _headerRefresher != null) {
        await _handle401();

        final retryHeaders = {
          ...?_headers,
          ...?additionalHeaders,
        };
        response = await _httpClient.head(uri, headers: retryHeaders);
        DebugLog.network(
          'NetworkTransportLayer: HEAD retry returned ${response.statusCode}',
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
    } on Object catch (e) {
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
        await _handle401();

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
    } on Object catch (e) {
      // Record error for inspector
      if (requestId != null) {
        _inspector?.recordError(requestId: requestId, error: e.toString());
      }
      rethrow;
    }
  }

  /// Make an HTTP DELETE request with observable hooks.
  ///
  /// Supports 401 retry with header refresh.
  Future<http.Response> delete(
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
      method: 'DELETE',
      uri: uri,
      headers: requestHeaders,
    );

    try {
      var response = await _httpClient.delete(uri, headers: requestHeaders);

      // 401 retry with header refresh
      if (response.statusCode == 401 && _headerRefresher != null) {
        await _handle401();

        final retryHeaders = {
          'Accept': 'application/json',
          ...?_headers,
          ...?additionalHeaders,
        };
        response = await _httpClient.delete(uri, headers: retryHeaders);
        DebugLog.network(
          'NetworkTransportLayer: DELETE retry returned ${response.statusCode}',
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
    } on Object catch (e) {
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

    var retryCount = 0;
    const maxRetries = 3;

    try {
      while (true) {
        try {
          await for (final event in _agUiClient.runAgent(endpoint, input)) {
            eventCount++;
            DebugLog.network(
              // ignore: lines_longer_than_80_chars (auto-documented)
              'NetworkTransportLayer: SSE event #$eventCount: ${event.runtimeType}',
            );
            // DEBUG: Log raw StateSnapshotEvent data
            if (event is ag_ui.StateSnapshotEvent) {
              DebugLog.network(
                'NetworkTransportLayer: StateSnapshot.snapshot = '
                '${event.snapshot}',
              );
            }
            yield event;
          }

          DebugLog.network(
            'NetworkTransportLayer: SSE stream completed ($eventCount events)',
          );
          break; // Stream completed successfully
        } on Object catch (e) {
          // Handle 401 Refresh for SSE
          // We check for "401" in the string as a generic catch-all since
          // exceptions might wrap http exceptions
          if (e.toString().contains('401') && _headerRefresher != null) {
            DebugLog.network(
              'NetworkTransportLayer: SSE 401 detected. Refreshing token.',
            );
            await _handle401();
            // Reset retry count to allow full set of retries with new token?
            // Or just continue and let it count against retries?
            // Let's continue without incrementing retryCount for this specific
            // auth recovery.
            continue;
          }

          // Only retry if we haven't yielded any events yet and haven't hit the
          // limit
          if (eventCount > 0 || retryCount >= maxRetries) {
            rethrow;
          }

          retryCount++;
          DebugLog.network(
            'NetworkTransportLayer: SSE stream failed (attempt $retryCount/$maxRetries). Retrying... Error: $e',
          );

          // Exponential backoff: 500ms, 1000ms, 1500ms...
          await Future.delayed(Duration(milliseconds: 500 * retryCount));
        }
      }
    } on Object catch (e) {
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

  /// Make a streaming HTTP POST request for SSE responses.
  ///
  /// Used for OpenAI-compatible completions endpoints that return
  /// Server-Sent Events. Returns a stream of SSE data lines.
  ///
  /// Supports 401 retry with header refresh.
  Stream<String> streamPost(
    Uri uri,
    String body, {
    Map<String, String>? additionalHeaders,
  }) async* {
    if (_disposed) {
      throw StateError('Cannot use disposed NetworkTransportLayer');
    }

    final requestHeaders = {
      'Content-Type': 'application/json',
      'Accept': 'text/event-stream',
      ...?_headers,
      ...?additionalHeaders,
    };

    final startTime = DateTime.now();
    var lineCount = 0;
    String? error;

    // Record request for inspector
    final requestId = _inspector?.recordRequest(
      method: 'SSE-POST',
      uri: uri,
      headers: requestHeaders,
      body: body,
    );

    DebugLog.network('NetworkTransportLayer: SSE POST starting for $uri');

    try {
      final request = http.Request('POST', uri);
      request.headers.addAll(requestHeaders);
      request.body = body;

      final streamedResponse = await _httpClient.send(request);

      // Handle non-success status codes
      if (streamedResponse.statusCode != 200) {
        // For 401, try refresh and retry
        if (streamedResponse.statusCode == 401 && _headerRefresher != null) {
          await _handle401();

          // Retry with new headers
          final retryHeaders = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            ...?_headers,
            ...?additionalHeaders,
          };
          final retryRequest = http.Request('POST', uri);
          retryRequest.headers.addAll(retryHeaders);
          retryRequest.body = body;

          final retryResponse = await _httpClient.send(retryRequest);
          if (retryResponse.statusCode != 200) {
            throw http.ClientException(
              'SSE POST failed with status ${retryResponse.statusCode}',
              uri,
            );
          }

          // Stream retry response
          await for (final chunk
              in retryResponse.stream
                  .transform(const Utf8Decoder())
                  .transform(const LineSplitter())) {
            lineCount++;
            yield chunk;
          }
        } else {
          throw http.ClientException(
            'SSE POST failed with status ${streamedResponse.statusCode}',
            uri,
          );
        }
      } else {
        // Stream successful response
        await for (final chunk
            in streamedResponse.stream
                .transform(const Utf8Decoder())
                .transform(const LineSplitter())) {
          lineCount++;
          yield chunk;
        }
      }

      DebugLog.network(
        'NetworkTransportLayer: SSE POST completed ($lineCount lines)',
      );
    } on Object catch (e) {
      error = e.toString();
      DebugLog.network('NetworkTransportLayer: SSE POST error: $e');
      rethrow;
    } finally {
      // Record completion for inspector
      if (requestId != null) {
        final duration = DateTime.now().difference(startTime);
        if (error != null) {
          _inspector?.recordError(requestId: requestId, error: error);
        } else {
          _inspector?.recordResponse(
            requestId: requestId,
            statusCode: 200,
            headers: {'x-sse-line-count': lineCount.toString()},
            body: {
              'lineCount': lineCount,
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
