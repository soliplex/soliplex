import 'dart:async';

import 'package:soliplex_client/src/http/http_response.dart';
import 'package:soliplex_client/src/http/soliplex_http_client.dart';
import 'package:soliplex_client/src/http/token_refresher.dart';

/// HTTP client decorator that handles token refresh.
///
/// Wraps an inner client to provide:
/// - Proactive refresh before requests when token is expiring soon
/// - Reactive refresh and retry on 401 responses (once only per request)
/// - Concurrent refresh deduplication via Completer
///
/// ## Concurrent Refresh Handling
///
/// When multiple requests receive 401 simultaneously, only one refresh
/// call is made. Other requests wait on the same Completer. The Completer
/// is cleared synchronously before completing to ensure subsequent requests
/// start fresh refresh attempts if needed.
///
/// Decorator order: `Refreshing -> Authenticated -> Observable -> Platform`
class RefreshingHttpClient implements SoliplexHttpClient {
  /// Creates a refreshing HTTP client.
  ///
  /// [inner] is the wrapped HTTP client (typically AuthenticatedHttpClient).
  /// [refresher] provides token refresh capabilities.
  RefreshingHttpClient({
    required SoliplexHttpClient inner,
    required TokenRefresher refresher,
  })  : _inner = inner,
        _refresher = refresher;

  final SoliplexHttpClient _inner;
  final TokenRefresher _refresher;

  /// Guards concurrent refresh attempts.
  Completer<bool>? _refreshInProgress;

  @override
  Future<HttpResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  }) async {
    // Proactive refresh if token is expiring soon
    await _refresher.refreshIfExpiringSoon();

    return _executeWithRetry(
      method,
      uri,
      headers: headers,
      body: body,
      timeout: timeout,
      retried: false,
    );
  }

  Future<HttpResponse> _executeWithRetry(
    String method,
    Uri uri, {
    required bool retried,
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  }) async {
    final response = await _inner.request(
      method,
      uri,
      headers: headers,
      body: body,
      timeout: timeout,
    );

    // On 401, attempt refresh and retry ONCE (CWE-834 prevention)
    if (response.statusCode == 401 && !retried) {
      final refreshed = await _tryRefreshOnce();
      if (refreshed) {
        return _executeWithRetry(
          method,
          uri,
          headers: headers,
          body: body,
          timeout: timeout,
          retried: true,
        );
      }
    }

    return response;
  }

  /// Attempt refresh with concurrent call deduplication.
  ///
  /// Multiple concurrent 401s will share a single refresh attempt.
  /// The Completer is cleared before completing so new requests after
  /// refresh finishes will start a fresh refresh if needed.
  Future<bool> _tryRefreshOnce() async {
    // If refresh already in progress, wait for it
    if (_refreshInProgress != null) {
      return _refreshInProgress!.future;
    }

    final completer = Completer<bool>();
    _refreshInProgress = completer;
    try {
      final result = await _refresher.tryRefresh();
      // Clear before completing so new requests after refresh finishes start
      // fresh. Waiters already hold the Completer reference. Safe because Dart
      // runs on a single event loop—no await between clear and complete.
      _refreshInProgress = null;
      completer.complete(result);
      return result;
    } catch (e) {
      // Same pattern for error path
      _refreshInProgress = null;
      completer.completeError(e);
      rethrow;
    }
  }

  @override
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  }) async* {
    // Proactive refresh only - can't retry mid-stream on 401
    await _refresher.refreshIfExpiringSoon();

    yield* _inner.requestStream(
      method,
      uri,
      headers: headers,
      body: body,
    );
  }

  @override
  void close() => _inner.close();
}
