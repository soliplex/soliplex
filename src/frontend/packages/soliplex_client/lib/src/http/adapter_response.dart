import 'dart:typed_data';

import 'package:meta/meta.dart';

/// Response from an HTTP adapter.
///
/// Contains the status code, headers, and body bytes from an HTTP response.
/// Use [body] getter to decode the response as a UTF-8 string.
@immutable
class AdapterResponse {
  /// Creates an adapter response.
  const AdapterResponse({
    required this.statusCode,
    required this.bodyBytes,
    this.headers = const {},
    this.reasonPhrase,
  });

  /// The HTTP status code (e.g., 200, 404, 500).
  final int statusCode;

  /// The raw response body as bytes.
  final Uint8List bodyBytes;

  /// Response headers with lowercase keys.
  final Map<String, String> headers;

  /// The reason phrase from the server (e.g., "OK", "Not Found").
  final String? reasonPhrase;

  /// The response body decoded as a UTF-8 string.
  String get body => String.fromCharCodes(bodyBytes);

  /// Whether this response indicates success (2xx status code).
  bool get isSuccess => statusCode >= 200 && statusCode < 300;

  /// Whether this response indicates a redirect (3xx status code).
  bool get isRedirect => statusCode >= 300 && statusCode < 400;

  /// Whether this response indicates a client error (4xx status code).
  bool get isClientError => statusCode >= 400 && statusCode < 500;

  /// Whether this response indicates a server error (5xx status code).
  bool get isServerError => statusCode >= 500;

  /// Content-Type header value, if present.
  String? get contentType => headers['content-type'];

  /// Content-Length header value parsed as int, if present and valid.
  int? get contentLength {
    final value = headers['content-length'];
    return value != null ? int.tryParse(value) : null;
  }

  @override
  String toString() {
    return 'AdapterResponse(statusCode: $statusCode, '
        'bodyLength: ${bodyBytes.length})';
  }
}
