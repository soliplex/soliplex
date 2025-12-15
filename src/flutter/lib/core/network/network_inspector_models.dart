/// Data models for the network traffic inspector.
///
/// These models capture HTTP request/response cycles for debugging
/// and diagnostics purposes.
library;

import 'dart:convert';

/// A single HTTP request/response entry.
///
/// Captures the full lifecycle of an HTTP request including:
/// - Request details (method, URL, headers, body)
/// - Response details (status, headers, body)
/// - Timing information for latency calculation
/// - Error information if the request failed
class NetworkEntry {
  const NetworkEntry({
    required this.id,
    required this.method,
    required this.uri,
    required this.requestHeaders,
    required this.startTime,
    this.requestBody,
    this.statusCode,
    this.responseHeaders,
    this.responseBody,
    this.endTime,
    this.error,
  });

  /// Create an entry for a new request (response not yet received).
  factory NetworkEntry.request({
    required String id,
    required String method,
    required Uri uri,
    required Map<String, String> headers,
    dynamic body,
  }) {
    return NetworkEntry(
      id: id,
      method: method,
      uri: uri,
      requestHeaders: Map.unmodifiable(headers),
      requestBody: body,
      startTime: DateTime.now(),
    );
  }

  /// Unique identifier for this entry.
  final String id;

  /// HTTP method (GET, POST, PUT, DELETE, etc.).
  final String method;

  /// Full request URI.
  final Uri uri;

  /// Request headers.
  final Map<String, String> requestHeaders;

  /// Request body (JSON object, string, or null).
  final dynamic requestBody;

  /// Timestamp when request was initiated.
  final DateTime startTime;

  /// HTTP status code (null while in-flight or on network error).
  final int? statusCode;

  /// Response headers (null while in-flight).
  final Map<String, String>? responseHeaders;

  /// Response body (JSON object, string, or null).
  final dynamic responseBody;

  /// Timestamp when response was received.
  final DateTime? endTime;

  /// Error message if request failed.
  final String? error;

  /// Create a copy with response data.
  NetworkEntry withResponse({
    required int statusCode,
    required Map<String, String> headers,
    dynamic body,
  }) {
    return NetworkEntry(
      id: id,
      method: method,
      uri: uri,
      requestHeaders: requestHeaders,
      requestBody: requestBody,
      startTime: startTime,
      statusCode: statusCode,
      responseHeaders: Map.unmodifiable(headers),
      responseBody: body,
      endTime: DateTime.now(),
    );
  }

  /// Create a copy with error information.
  NetworkEntry withError(String errorMessage) {
    return NetworkEntry(
      id: id,
      method: method,
      uri: uri,
      requestHeaders: requestHeaders,
      requestBody: requestBody,
      startTime: startTime,
      error: errorMessage,
      endTime: DateTime.now(),
    );
  }

  // ===========================================================================
  // Computed Properties
  // ===========================================================================

  /// Request/response latency.
  Duration? get latency => endTime?.difference(startTime);

  /// Latency in milliseconds (for display).
  int? get latencyMs => latency?.inMilliseconds;

  /// Whether the request has completed (success or error).
  bool get isComplete => statusCode != null || error != null;

  /// Whether the request is still in-flight.
  bool get isInFlight => !isComplete;

  /// Whether the request completed successfully (2xx status).
  bool get isSuccess =>
      statusCode != null && statusCode! >= 200 && statusCode! < 300;

  /// Whether the request resulted in an error (4xx, 5xx, or network error).
  bool get isError =>
      error != null || (statusCode != null && statusCode! >= 400);

  /// Short path for display (without query params).
  String get shortPath {
    final path = uri.path;
    return path.length > 50 ? '${path.substring(0, 47)}...' : path;
  }

  /// Full URL as string.
  String get fullUrl => uri.toString();

  // ===========================================================================
  // Content Type Detection
  // ===========================================================================

  /// Request content type header.
  String? get requestContentType =>
      requestHeaders['content-type'] ?? requestHeaders['Content-Type'];

  /// Response content type header.
  String? get responseContentType =>
      responseHeaders?['content-type'] ?? responseHeaders?['Content-Type'];

  /// Whether request body is JSON.
  bool get isJsonRequest =>
      requestContentType?.contains('application/json') ??
      (requestBody is Map) || requestBody is List;

  /// Whether response body is JSON.
  bool get isJsonResponse =>
      responseContentType?.contains('application/json') ??
      (responseBody is Map) || responseBody is List;

  /// Whether response body is likely binary.
  bool get isBinaryResponse {
    final ct = responseContentType?.toLowerCase();
    if (ct == null) return false;
    return ct.contains('image/') ||
        ct.contains('audio/') ||
        ct.contains('video/') ||
        ct.contains('application/octet-stream') ||
        ct.contains('application/pdf');
  }

  /// Whether response body is HTML.
  bool get isHtmlResponse =>
      responseContentType?.contains('text/html') ?? false;

  // ===========================================================================
  // Formatting Helpers
  // ===========================================================================

  /// Format request body for display.
  String formatRequestBody() {
    if (requestBody == null) return '';
    if (requestBody is String) return requestBody as String;
    if (requestBody is Map || requestBody is List) {
      return const JsonEncoder.withIndent('  ').convert(requestBody);
    }
    return requestBody.toString();
  }

  /// Format response body for display.
  String formatResponseBody() {
    if (responseBody == null) return '';
    if (isBinaryResponse) {
      final size = _estimateSize(responseBody);
      return '[Binary data: ${responseContentType ?? "unknown"}, ~$size]';
    }
    if (responseBody is String) {
      // Try to parse and pretty-print JSON strings
      if (isJsonResponse) {
        try {
          final parsed = jsonDecode(responseBody as String);
          return const JsonEncoder.withIndent('  ').convert(parsed);
        } on Object catch (_) {
          return responseBody as String;
        }
      }
      return responseBody as String;
    }
    if (responseBody is Map || responseBody is List) {
      return const JsonEncoder.withIndent('  ').convert(responseBody);
    }
    return responseBody.toString();
  }

  /// Estimate size of body for display.
  String _estimateSize(dynamic body) {
    if (body == null) return '0 B';
    int bytes;
    if (body is String) {
      bytes = body.length;
    } else if (body is List<int>) {
      bytes = body.length;
    } else {
      bytes = body.toString().length;
    }
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }

  /// Generate a curl command for this request.
  String toCurl() {
    final buffer = StringBuffer('curl');

    // Method (skip if GET)
    if (method != 'GET') {
      buffer.write(" -X '$method'");
    }

    // Headers
    for (final entry in requestHeaders.entries) {
      // Skip content-length as curl calculates it
      if (entry.key.toLowerCase() == 'content-length') continue;
      buffer.write(" \\\n  -H '${entry.key}: ${entry.value}'");
    }

    // Body
    if (requestBody != null) {
      final bodyStr = requestBody is String
          ? requestBody as String
          : jsonEncode(requestBody);
      // Escape single quotes in body
      final escaped = bodyStr.replaceAll("'", r"'\''");
      buffer.write(" \\\n  -d '$escaped'");
    }

    // URL (must be last)
    buffer.write(" \\\n  '$uri'");

    return buffer.toString();
  }

  @override
  String toString() {
    final status = statusCode?.toString() ?? (error != null ? 'ERR' : '...');
    final time = latencyMs != null ? '${latencyMs}ms' : '-';
    return 'NetworkEntry($method $shortPath → $status [$time])';
  }
}
