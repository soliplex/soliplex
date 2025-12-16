import 'dart:async';
import 'dart:convert';

import 'package:soliplex_client/src/errors/exceptions.dart';
import 'package:soliplex_client/src/http/adapter_response.dart';
import 'package:soliplex_client/src/http/http_client_adapter.dart';
import 'package:soliplex_client/src/utils/cancel_token.dart';

/// HTTP transport layer with JSON serialization and exception mapping.
///
/// Wraps an [HttpClientAdapter] and provides:
/// - Automatic JSON encoding/decoding for request and response bodies
/// - HTTP status code to exception mapping
/// - Request cancellation via [CancelToken]
/// - Configurable timeout with per-request override
///
/// Example:
/// ```dart
/// final transport = HttpTransport(adapter: DartHttpAdapter());
///
/// // Simple GET request
/// final data = await transport.request<Map<String, dynamic>>(
///   'GET',
///   Uri.parse('https://api.example.com/rooms'),
/// );
///
/// // POST with JSON body
/// final response = await transport.request(
///   'POST',
///   Uri.parse('https://api.example.com/rooms'),
///   body: {'name': 'New Room'},
/// );
///
/// // With cancellation
/// final token = CancelToken();
/// final future = transport.request('GET', uri, cancelToken: token);
/// token.cancel();  // Throws CancelledException
///
/// transport.close();
/// ```
class HttpTransport {
  /// Creates an HTTP transport with the given [adapter].
  ///
  /// Parameters:
  /// - [adapter]: The underlying HTTP adapter to use for requests
  /// - [defaultTimeout]: Default timeout for requests (defaults to 30 seconds)
  HttpTransport({
    required HttpClientAdapter adapter,
    this.defaultTimeout = const Duration(seconds: 30),
  }) : _adapter = adapter;

  final HttpClientAdapter _adapter;

  /// Default timeout applied to requests when no per-request timeout is given.
  final Duration defaultTimeout;

  /// Performs an HTTP request and returns the decoded response.
  ///
  /// Parameters:
  /// - [method]: HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
  /// - [uri]: The request URI
  /// - [body]: Optional request body. Maps are JSON encoded automatically.
  /// - [headers]: Optional request headers. Content-Type is set to JSON
  ///   when body is a Map.
  /// - [timeout]: Request timeout. Uses [defaultTimeout] if not specified.
  /// - [cancelToken]: Optional token for cancelling the request.
  /// - [fromJson]: Optional function to convert the JSON response to type [T].
  ///   If null and response is JSON, returns the decoded Map.
  ///
  /// Returns:
  /// - The decoded response body. If [fromJson] is provided, returns [T].
  /// - If response body is empty, returns null cast to [T].
  /// - If response is not JSON, returns the raw string cast to [T].
  ///
  /// Throws:
  /// - [CancelledException] if the request was cancelled via [cancelToken]
  /// - [AuthException] for 401 and 403 responses
  /// - [NotFoundException] for 404 responses
  /// - [ApiException] for other 4xx and 5xx responses
  /// - [NetworkException] for connection failures (from adapter)
  Future<T> request<T>(
    String method,
    Uri uri, {
    Object? body,
    Map<String, String>? headers,
    Duration? timeout,
    CancelToken? cancelToken,
    T Function(Map<String, dynamic>)? fromJson,
  }) async {
    // Check cancellation before starting
    cancelToken?.throwIfCancelled();

    // Prepare headers and body
    final requestHeaders = <String, String>{...?headers};
    var requestBody = body;

    // JSON encode Map bodies
    if (body is Map<String, dynamic>) {
      requestBody = jsonEncode(body);
      requestHeaders['content-type'] ??= 'application/json';
    }

    // Make the request
    final response = await _adapter.request(
      method,
      uri,
      headers: requestHeaders,
      body: requestBody,
      timeout: timeout ?? defaultTimeout,
    );

    // Check cancellation after request completes
    cancelToken?.throwIfCancelled();

    // Map status codes to exceptions
    _throwForStatusCode(response, uri);

    // Decode response
    return _decodeResponse<T>(response, fromJson);
  }

  /// Performs a streaming HTTP request and returns a byte stream.
  ///
  /// Used for SSE (Server-Sent Events) and other streaming protocols.
  ///
  /// Parameters:
  /// - [method]: HTTP method (typically GET or POST)
  /// - [uri]: The request URI
  /// - [body]: Optional request body. Maps are JSON encoded automatically.
  /// - [headers]: Optional request headers
  /// - [cancelToken]: Optional token for cancelling the stream
  ///
  /// Returns a stream of byte chunks as they arrive from the server.
  /// The stream can be cancelled by calling [CancelToken.cancel], which
  /// will cause the stream to emit a [CancelledException] error.
  ///
  /// Throws:
  /// - [CancelledException] if cancelled before the stream starts
  /// - [NetworkException] for connection failures (from adapter)
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Object? body,
    Map<String, String>? headers,
    CancelToken? cancelToken,
  }) {
    // Check cancellation before starting
    cancelToken?.throwIfCancelled();

    // Prepare headers and body
    final requestHeaders = <String, String>{...?headers};
    var requestBody = body;

    // JSON encode Map bodies
    if (body is Map<String, dynamic>) {
      requestBody = jsonEncode(body);
      requestHeaders['content-type'] ??= 'application/json';
    }

    // Get the source stream
    final sourceStream = _adapter.requestStream(
      method,
      uri,
      headers: requestHeaders,
      body: requestBody,
    );

    // If no cancel token, return stream as-is
    if (cancelToken == null) {
      return sourceStream;
    }

    // Wrap stream with cancellation support
    return _wrapStreamWithCancellation(sourceStream, cancelToken);
  }

  /// Closes the transport and releases resources.
  ///
  /// After calling this method, no further requests should be made.
  void close() {
    _adapter.close();
  }

  /// Wraps a stream with cancellation support from a [CancelToken].
  Stream<List<int>> _wrapStreamWithCancellation(
    Stream<List<int>> source,
    CancelToken cancelToken,
  ) {
    late StreamController<List<int>> controller;
    StreamSubscription<List<int>>? subscription;

    controller = StreamController<List<int>>(
      onListen: () {
        // Listen to cancellation
        cancelToken.whenCancelled.then((_) {
          if (!controller.isClosed) {
            controller
              ..addError(CancelledException(reason: cancelToken.reason))
              ..close();
            subscription?.cancel();
          }
        });

        // Forward stream data
        subscription = source.listen(
          controller.add,
          onError: controller.addError,
          onDone: controller.close,
        );
      },
      onPause: () => subscription?.pause(),
      onResume: () => subscription?.resume(),
      onCancel: () => subscription?.cancel(),
    );

    return controller.stream;
  }

  /// Throws appropriate exception for HTTP error status codes.
  void _throwForStatusCode(AdapterResponse response, Uri uri) {
    final statusCode = response.statusCode;

    if (statusCode >= 200 && statusCode < 300) {
      return; // Success
    }

    final body = response.body;
    final message = _extractErrorMessage(body) ?? 'HTTP $statusCode';

    if (statusCode == 401 || statusCode == 403) {
      throw AuthException(
        message: message,
        statusCode: statusCode,
      );
    }

    if (statusCode == 404) {
      throw NotFoundException(
        message: message,
        resource: uri.path,
      );
    }

    // All other 4xx and 5xx errors
    throw ApiException(
      message: message,
      statusCode: statusCode,
      body: body.isNotEmpty ? body : null,
    );
  }

  /// Attempts to extract an error message from a JSON response body.
  String? _extractErrorMessage(String body) {
    if (body.isEmpty) return null;

    try {
      final json = jsonDecode(body);
      if (json is Map<String, dynamic>) {
        // Common error message fields
        return json['message'] as String? ??
            json['error'] as String? ??
            json['detail'] as String?;
      }
    } catch (_) {
      // Not JSON, return null
    }
    return null;
  }

  /// Decodes the response body, optionally using a [fromJson] converter.
  T _decodeResponse<T>(
    AdapterResponse response,
    T Function(Map<String, dynamic>)? fromJson,
  ) {
    final body = response.body;

    // Handle empty body
    if (body.isEmpty) {
      return null as T;
    }

    // Check if response is JSON
    final contentType = response.contentType ?? '';
    final isJson = contentType.contains('application/json') ||
        body.trimLeft().startsWith('{') ||
        body.trimLeft().startsWith('[');

    if (!isJson) {
      // Return raw string
      return body as T;
    }

    // Decode JSON
    final decoded = jsonDecode(body);

    // If fromJson is provided and response is a Map, use it
    if (fromJson != null && decoded is Map<String, dynamic>) {
      return fromJson(decoded);
    }

    // Return decoded JSON as-is
    return decoded as T;
  }
}
