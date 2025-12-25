import 'package:soliplex_client/src/http/http_response.dart';

/// Abstract interface for Soliplex HTTP clients.
///
/// Implementations wrap platform-specific HTTP clients to provide a unified
/// interface for making HTTP requests. Use `DartHttpClient` for the default
/// pure-Dart implementation using `package:http`.
///
/// Example:
/// ```dart
/// final client = DartHttpClient();
/// final response = await client.request(
///   'GET',
///   Uri.parse('https://api.example.com/data'),
/// );
/// print(response.body);
/// client.close();
/// ```
abstract class SoliplexHttpClient {
  /// Performs an HTTP request and returns the complete response.
  ///
  /// Parameters:
  /// - [method]: HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
  /// - [uri]: The request URI
  /// - [headers]: Optional request headers
  /// - [body]: Optional request body. Supported types:
  ///   - `String`: Sent as-is with UTF-8 encoding
  ///   - `List<int>`: Sent as raw bytes
  ///   - `Map<String, dynamic>`: JSON encoded automatically
  /// - [timeout]: Request timeout. Uses client's default if not specified.
  ///
  /// Throws `NetworkException` on connection failures or timeouts.
  /// Throws `CancelledException` if the request was cancelled.
  Future<HttpResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  });

  /// Performs an HTTP request and returns a byte stream for streaming
  /// responses.
  ///
  /// Used for SSE (Server-Sent Events) and other streaming protocols.
  /// The returned stream emits byte chunks as they arrive from the server.
  ///
  /// Parameters:
  /// - [method]: HTTP method (typically GET or POST)
  /// - [uri]: The request URI
  /// - [headers]: Optional request headers
  /// - [body]: Optional request body (same types as [request])
  ///
  /// Throws `NetworkException` on connection failures.
  /// Throws `CancelledException` if the request was cancelled.
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  });

  /// Closes the client and releases any resources.
  ///
  /// After calling this method, no further requests should be made.
  /// Calling [close] multiple times is safe.
  void close();
}
