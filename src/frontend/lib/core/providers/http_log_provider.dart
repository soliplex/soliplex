import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:soliplex_client/soliplex_client.dart';

/// Notifier that stores HTTP events and implements [HttpObserver].
///
/// Provides app-wide HTTP traffic logging for debugging and inspection.
/// Events are stored in chronological order as they occur. Oldest events
/// are dropped when [maxEvents] is exceeded to prevent unbounded memory growth.
///
/// **Timing**: Events are processed asynchronously via [scheduleMicrotask].
/// State updates may be delayed by one microtask tick after the HTTP event
/// occurs. This avoids Riverpod build-time mutation errors when HTTP requests
/// happen during provider initialization.
///
/// Example:
/// ```dart
/// // Access events
/// final events = ref.watch(httpLogProvider);
///
/// // Clear log
/// ref.read(httpLogProvider.notifier).clear();
/// ```
class HttpLogNotifier extends Notifier<List<HttpEvent>>
    implements HttpObserver {
  /// Maximum number of events to retain.
  static const maxEvents = 500;

  @override
  List<HttpEvent> build() => [];

  /// Headers that should have their values redacted for security.
  static const _sensitiveHeaders = {'authorization', 'cookie', 'set-cookie'};

  /// Query parameters that should have their values redacted for security.
  static const _sensitiveParams = {
    'token',
    'access_token',
    'refresh_token',
    'id_token',
    'code',
    'client_secret',
    'state',
    'code_verifier',
    'session_state',
  };

  void _addEvent(HttpEvent event) {
    // Defer state update to avoid Riverpod errors when called during
    // another provider's initialization (e.g., FutureProvider making HTTP
    // requests during build).
    scheduleMicrotask(() {
      final newState = [...state, event];
      state = newState.length > maxEvents
          ? newState.sublist(newState.length - maxEvents)
          : newState;
    });
  }

  /// Redacts sensitive header values to prevent token leakage in logs.
  Map<String, String> _redactHeaders(Map<String, String> headers) {
    return headers.map((key, value) {
      if (_sensitiveHeaders.contains(key.toLowerCase())) {
        return MapEntry(key, '[REDACTED]');
      }
      return MapEntry(key, value);
    });
  }

  /// Redacts sensitive query parameter values to prevent token leakage in logs.
  Uri _redactUri(Uri uri) {
    if (uri.queryParameters.isEmpty) return uri;

    final hasSenitiveParams = uri.queryParameters.keys
        .any((key) => _sensitiveParams.contains(key.toLowerCase()));
    if (!hasSenitiveParams) return uri;

    final redactedParams = uri.queryParameters.map((key, value) {
      if (_sensitiveParams.contains(key.toLowerCase())) {
        return MapEntry(key, '[REDACTED]');
      }
      return MapEntry(key, value);
    });

    return uri.replace(queryParameters: redactedParams);
  }

  @override
  void onRequest(HttpRequestEvent event) {
    final redacted = HttpRequestEvent(
      requestId: event.requestId,
      timestamp: event.timestamp,
      method: event.method,
      uri: _redactUri(event.uri),
      headers: _redactHeaders(event.headers),
    );
    _addEvent(redacted);
  }

  @override
  void onResponse(HttpResponseEvent event) => _addEvent(event);

  @override
  void onError(HttpErrorEvent event) {
    final redacted = HttpErrorEvent(
      requestId: event.requestId,
      timestamp: event.timestamp,
      method: event.method,
      uri: _redactUri(event.uri),
      exception: event.exception,
      duration: event.duration,
    );
    _addEvent(redacted);
  }

  @override
  void onStreamStart(HttpStreamStartEvent event) {
    final redacted = HttpStreamStartEvent(
      requestId: event.requestId,
      timestamp: event.timestamp,
      method: event.method,
      uri: _redactUri(event.uri),
    );
    _addEvent(redacted);
  }

  @override
  void onStreamEnd(HttpStreamEndEvent event) => _addEvent(event);

  /// Clears all stored HTTP events.
  void clear() {
    state = [];
  }
}

/// Provider for HTTP event logging.
///
/// The notifier implements [HttpObserver] and can be passed to
/// [ObservableHttpClient] to capture all HTTP traffic.
final httpLogProvider =
    NotifierProvider<HttpLogNotifier, List<HttpEvent>>(HttpLogNotifier.new);
