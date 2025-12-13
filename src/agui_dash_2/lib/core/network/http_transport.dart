import 'dart:convert';

import 'package:http/http.dart' as http;

import '../utils/debug_log.dart';
import '../utils/url_builder.dart';
import 'network_inspector.dart';
import 'network_transport.dart';
import 'network_transport_layer.dart';

/// HTTP-based network transport for POST requests.
///
/// Web-compatible implementation using http.Client.
/// Supports 401 retry with header refresh for token expiration.
///
/// Can optionally use a [NetworkTransportLayer] for unified network management.
/// When a transport layer is provided, HTTP operations delegate to it.
class HttpTransport implements NetworkTransport {
  final String baseUrl;
  final UrlBuilder _urlBuilder;

  // Either use transport layer or direct http client
  final NetworkTransportLayer? _transportLayer;
  final http.Client? _ownHttpClient;
  Map<String, String>? _headers;
  final Future<Map<String, String>> Function()? _headerRefresher;
  final NetworkInspector? _inspector;

  /// Creates HttpTransport with optional [NetworkTransportLayer].
  ///
  /// If [transportLayer] is provided, HTTP operations delegate to it.
  /// Otherwise, creates its own http.Client (legacy behavior).
  HttpTransport({
    required this.baseUrl,
    NetworkTransportLayer? transportLayer,
    http.Client? httpClient,
    Map<String, String>? defaultHeaders,
    Future<Map<String, String>> Function()? headerRefresher,
    NetworkInspector? inspector,
  })  : _transportLayer = transportLayer,
        _ownHttpClient = transportLayer == null ? (httpClient ?? http.Client()) : null,
        _headers = defaultHeaders,
        _headerRefresher = headerRefresher,
        _urlBuilder = UrlBuilder(baseUrl),
        _inspector = transportLayer == null ? inspector : null; // Transport layer handles inspector

  /// Creates HttpTransport from a [NetworkTransportLayer].
  ///
  /// This is the preferred constructor for new code.
  factory HttpTransport.fromTransportLayer({
    required String baseUrl,
    required NetworkTransportLayer transportLayer,
  }) {
    return HttpTransport(
      baseUrl: baseUrl,
      transportLayer: transportLayer,
    );
  }

  /// Current headers for requests.
  Map<String, String>? get defaultHeaders => _transportLayer?.headers ?? _headers;

  /// The underlying transport layer, if using unified transport.
  NetworkTransportLayer? get transportLayer => _transportLayer;

  @override
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  }) async {
    // POST to cancel endpoint
    // Server may not support this - fail gracefully
    final uri = _urlBuilder.cancelRun(roomId, threadId, runId);

    try {
      http.Response response;

      if (_transportLayer != null) {
        // Use transport layer (handles inspector internally)
        response = await _transportLayer.post(uri, '{}');
      } else {
        // Legacy path: direct http client with inspector
        final requestHeaders = {
          'Content-Type': 'application/json',
          ...?_headers,
        };

        final requestId = _inspector?.recordRequest(
          method: 'POST',
          uri: uri,
          headers: requestHeaders,
          body: {},
        );

        try {
          response = await _ownHttpClient!.post(
            uri,
            headers: requestHeaders,
            body: '{}',
          );

          // 401 retry with header refresh
          if (response.statusCode == 401 && _headerRefresher != null) {
            DebugLog.network('HttpTransport: Cancel 401, refreshing headers...');
            _headers = await _headerRefresher();
            final retryHeaders = {
              'Content-Type': 'application/json',
              ...?_headers,
            };
            response = await _ownHttpClient.post(
              uri,
              headers: retryHeaders,
              body: '{}',
            );
          }

          // Record response for inspector
          if (requestId != null) {
            dynamic responseBody;
            try {
              responseBody = jsonDecode(response.body);
            } catch (_) {
              responseBody = response.body;
            }
            _inspector?.recordResponse(
              requestId: requestId,
              statusCode: response.statusCode,
              headers: response.headers,
              body: responseBody,
            );
          }
        } catch (e) {
          if (requestId != null) {
            _inspector?.recordError(requestId: requestId, error: e.toString());
          }
          rethrow;
        }
      }

      if (response.statusCode >= 400) {
        DebugLog.network('HttpTransport: Cancel request returned ${response.statusCode}');
      } else {
        DebugLog.network('HttpTransport: Cancel request successful');
      }
    } catch (e) {
      // Server cancel is optional - client-side cancel is the primary mechanism
      DebugLog.network('HttpTransport: Cancel request failed (non-critical): $e');
    }
  }

  @override
  Future<Map<String, dynamic>> post(
    Uri uri,
    Map<String, dynamic> body,
  ) async {
    final requestBody = jsonEncode(body);
    http.Response response;

    if (_transportLayer != null) {
      // Use transport layer (handles inspector and 401 retry internally)
      response = await _transportLayer.post(uri, requestBody);
    } else {
      // Legacy path: direct http client with inspector
      final requestHeaders = {
        'Content-Type': 'application/json',
        ...?_headers,
      };

      final requestId = _inspector?.recordRequest(
        method: 'POST',
        uri: uri,
        headers: requestHeaders,
        body: body,
      );

      try {
        response = await _ownHttpClient!.post(
          uri,
          headers: requestHeaders,
          body: requestBody,
        );

        // 401 retry with header refresh (single retry to avoid loops)
        if (response.statusCode == 401 && _headerRefresher != null) {
          DebugLog.network('HttpTransport: 401 received, refreshing headers...');
          _headers = await _headerRefresher();
          final retryHeaders = {
            'Content-Type': 'application/json',
            ...?_headers,
          };
          response = await _ownHttpClient.post(
            uri,
            headers: retryHeaders,
            body: requestBody,
          );
          DebugLog.network('HttpTransport: Retry after refresh returned ${response.statusCode}');
        }

        // Record response for inspector
        if (requestId != null) {
          dynamic responseBody;
          try {
            responseBody = jsonDecode(response.body);
          } catch (_) {
            responseBody = response.body;
          }
          _inspector?.recordResponse(
            requestId: requestId,
            statusCode: response.statusCode,
            headers: response.headers,
            body: responseBody,
          );
        }
      } catch (e) {
        if (requestId != null) {
          _inspector?.recordError(requestId: requestId, error: e.toString());
        }
        rethrow;
      }
    }

    if (response.statusCode >= 400) {
      throw HttpTransportException(
        'POST failed: ${response.statusCode} ${response.body}',
        response.statusCode,
      );
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  @override
  Future<void> close() async {
    // Only close own http client; transport layer is managed externally
    _ownHttpClient?.close();
  }
}

/// Exception for HTTP transport errors.
class HttpTransportException implements Exception {
  final String message;
  final int statusCode;

  HttpTransportException(this.message, this.statusCode);

  @override
  String toString() => 'HttpTransportException: $message (status: $statusCode)';
}
