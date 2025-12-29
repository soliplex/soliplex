import 'dart:convert';

import 'package:soliplex/core/network/network_transport.dart';
import 'package:soliplex/core/network/network_transport_layer.dart';
import 'package:soliplex/core/utils/debug_log.dart';
import 'package:soliplex/core/utils/url_builder.dart';

/// HTTP-based network transport adapter.
///
/// This is a thin adapter that wraps NetworkTransportLayer to provide
/// the NetworkTransport interface with JSON encoding/decoding.
///
/// All network operations (HTTP POST, 401 retry, inspector hooks) are
/// delegated to NetworkTransportLayer - this class only handles:
/// - JSON encoding of request bodies (Map → String)
/// - JSON decoding of response bodies (String → Map)
/// - Error wrapping via HttpTransportException
class HttpTransport implements NetworkTransport {
  /// Creates HttpTransport wrapping a NetworkTransportLayer.
  HttpTransport({
    required this.baseUrl,
    required NetworkTransportLayer transportLayer,
  }) : _transportLayer = transportLayer,
       _urlBuilder = UrlBuilder(baseUrl);

  /// Creates HttpTransport from a NetworkTransportLayer.
  ///
  /// Alias for the default constructor for API compatibility.
  factory HttpTransport.fromTransportLayer({
    required String baseUrl,
    required NetworkTransportLayer transportLayer,
  }) {
    return HttpTransport(baseUrl: baseUrl, transportLayer: transportLayer);
  }
  final String baseUrl;
  final NetworkTransportLayer _transportLayer;
  final UrlBuilder _urlBuilder;

  /// Current headers for requests (from transport layer).
  Map<String, String>? get defaultHeaders => _transportLayer.headers;

  /// The underlying transport layer.
  NetworkTransportLayer get transportLayer => _transportLayer;

  @override
  Future<void> cancelRun({
    required String roomId,
    required String threadId,
    required String runId,
  }) async {
    final uri = _urlBuilder.cancelRun(roomId, threadId, runId);

    try {
      final response = await _transportLayer.post(uri, '{}');

      if (response.statusCode >= 400) {
        DebugLog.network(
          'HttpTransport: Cancel request returned ${response.statusCode}',
        );
      } else {
        DebugLog.network('HttpTransport: Cancel request successful');
      }
    } on Object catch (e) {
      // Server cancel is optional - client-side cancel is the primary mechanism
      DebugLog.network(
        'HttpTransport: Cancel request failed (non-critical): $e',
      );
    }
  }

  @override
  Future<Map<String, dynamic>> post(Uri uri, Map<String, dynamic> body) async {
    final requestBody = jsonEncode(body);

    // Delegate to transport layer (handles 401 retry, inspector hooks)
    final response = await _transportLayer.post(uri, requestBody);

    if (response.statusCode >= 400) {
      throw HttpTransportException(
        'POST failed: ${response.statusCode} ${response.body}',
        response.statusCode,
      );
    }

    if (response.body.isEmpty) {
      return {};
    }

    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  @override
  Future<void> close() async {
    // Transport layer is managed externally - don't close it here
    // This is a no-op to satisfy the interface
  }
}

/// Exception for HTTP transport errors.
class HttpTransportException implements Exception {
  HttpTransportException(this.message, this.statusCode);
  final String message;
  final int statusCode;

  @override
  String toString() => 'HttpTransportException: $message (status: $statusCode)';
}
