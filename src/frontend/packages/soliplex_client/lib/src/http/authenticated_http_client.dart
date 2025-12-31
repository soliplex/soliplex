import 'package:soliplex_client/src/http/http_response.dart';
import 'package:soliplex_client/src/http/soliplex_http_client.dart';

/// HTTP client decorator that injects Bearer token authentication.
///
/// Wraps a [SoliplexHttpClient] and adds an `Authorization: Bearer` header
/// to all requests when a token is available.
///
/// This decorator has a single responsibility: add tokens. It does NOT:
/// - Handle 401 responses (that's the application layer's job)
/// - Refresh tokens (orchestration belongs in the frontend)
/// - Store tokens (frontend provides token via callback)
///
/// Example:
/// ```dart
/// final client = AuthenticatedHttpClient(
///   innerClient,
///   () => authState.accessToken,
/// );
/// ```
class AuthenticatedHttpClient implements SoliplexHttpClient {
  /// Creates an authenticated HTTP client.
  ///
  /// The `inner` client is delegated to for all requests.
  /// The `getToken` callback is invoked per request to get the current token.
  AuthenticatedHttpClient(this._inner, this._getToken);

  final SoliplexHttpClient _inner;
  final String? Function() _getToken;

  Map<String, String> _injectAuth(Map<String, String>? headers) {
    final token = _getToken();
    if (token == null) return headers ?? {};
    return <String, String>{...?headers, 'Authorization': 'Bearer $token'};
  }

  @override
  Future<HttpResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  }) {
    return _inner.request(
      method,
      uri,
      headers: _injectAuth(headers),
      body: body,
      timeout: timeout,
    );
  }

  @override
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  }) {
    return _inner.requestStream(
      method,
      uri,
      headers: _injectAuth(headers),
      body: body,
    );
  }

  @override
  void close() => _inner.close();
}
