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
  /// Uses a [Completer] as a semaphore: multiple concurrent 401s share a
  /// single refresh attempt by awaiting the same Completer. After refresh
  /// completes (success or failure), the Completer reference is cleared so
  /// subsequent requests trigger fresh refresh attempts.
  ///
  /// The null-clearing is critical: a [Completer] can only complete once, and
  /// afterward `.future` returns the cached result forever. Without clearing,
  /// new 401s would receive stale results instead of refreshing.
  Future<bool> _tryRefreshOnce() async {
    // If refresh already in progress, wait for it.
    // Race condition safety: Dart's single-threaded event loop guarantees no
    // interleaving between the null check and assignment below. Code only
    // yields at `await` points, so this check-then-assign is atomic.
    if (_refreshInProgress != null) {
      return _refreshInProgress!.future;
    }

    final completer = Completer<bool>();
    _refreshInProgress = completer;
    try {
      final result = await _refresher.tryRefresh();
      completer.complete(result);
      // REQUIRED: Clear the Completer reference after completion.
      // A Completer can only complete once—after that, .future returns the
      // cached result forever. Without clearing, subsequent 401s would get
      // stale results instead of triggering fresh refresh attempts.
      _refreshInProgress = null;
      return result;
    } catch (e) {
      completer.completeError(e);
      _refreshInProgress = null; // Same reason: allow fresh attempts
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
