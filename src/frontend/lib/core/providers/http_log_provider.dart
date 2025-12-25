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

  @override
  void onRequest(HttpRequestEvent event) => _addEvent(event);

  @override
  void onResponse(HttpResponseEvent event) => _addEvent(event);

  @override
  void onError(HttpErrorEvent event) => _addEvent(event);

  @override
  void onStreamStart(HttpStreamStartEvent event) => _addEvent(event);

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
/// [ObservableHttpAdapter] to capture all HTTP traffic.
final httpLogProvider =
    NotifierProvider<HttpLogNotifier, List<HttpEvent>>(HttpLogNotifier.new);
