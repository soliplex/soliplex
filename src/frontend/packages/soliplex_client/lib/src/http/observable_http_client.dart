import 'dart:async';

import 'package:soliplex_client/src/errors/exceptions.dart';
import 'package:soliplex_client/src/http/http_observer.dart';
import 'package:soliplex_client/src/http/http_response.dart';
import 'package:soliplex_client/src/http/soliplex_http_client.dart';

/// HTTP client decorator that notifies observers of all HTTP activity.
///
/// Wraps any [SoliplexHttpClient] implementation and notifies registered
/// [HttpObserver]s on requests, responses, errors, and streaming events.
///
/// Observers that throw exceptions are caught and ignored to prevent
/// disrupting the request flow.
///
/// Example:
/// ```dart
/// final baseClient = DartHttpClient();
/// final observable = ObservableHttpClient(
///   client: baseClient,
///   observers: [LoggingObserver(), MetricsObserver()],
/// );
///
/// final response = await observable.request('GET', uri);
/// // Observers notified at each step
///
/// observable.close();
/// ```
class ObservableHttpClient implements SoliplexHttpClient {
  /// Creates an observable client wrapping [client].
  ///
  /// Parameters:
  /// - [client]: The underlying client to wrap
  /// - [observers]: List of observers to notify (defaults to empty)
  /// - [generateRequestId]: Optional ID generator for correlation
  ///   (defaults to timestamp-based IDs)
  ObservableHttpClient({
    required SoliplexHttpClient client,
    List<HttpObserver> observers = const [],
    String Function()? generateRequestId,
  })  : _client = client,
        _observers = List.unmodifiable(observers),
        _generateRequestId = generateRequestId ?? _defaultRequestIdGenerator;

  final SoliplexHttpClient _client;
  final List<HttpObserver> _observers;
  final String Function() _generateRequestId;

  /// Counter for request ID generation.
  static int _requestCounter = 0;

  /// Default request ID generator using timestamp and counter.
  static String _defaultRequestIdGenerator() {
    return '${DateTime.now().millisecondsSinceEpoch}-${_requestCounter++}';
  }

  @override
  Future<HttpResponse> request(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
    Duration? timeout,
  }) async {
    final requestId = _generateRequestId();
    final startTime = DateTime.now();

    // Notify request start
    _notifyObservers((observer) {
      observer.onRequest(
        HttpRequestEvent(
          requestId: requestId,
          timestamp: startTime,
          method: method,
          uri: uri,
          headers: headers ?? const {},
        ),
      );
    });

    try {
      final response = await _client.request(
        method,
        uri,
        headers: headers,
        body: body,
        timeout: timeout,
      );

      final endTime = DateTime.now();
      final duration = endTime.difference(startTime);

      // Notify successful response
      _notifyObservers((observer) {
        observer.onResponse(
          HttpResponseEvent(
            requestId: requestId,
            timestamp: endTime,
            statusCode: response.statusCode,
            duration: duration,
            bodySize: response.bodyBytes.length,
            reasonPhrase: response.reasonPhrase,
          ),
        );
      });

      return response;
    } on SoliplexException catch (e) {
      final endTime = DateTime.now();
      final duration = endTime.difference(startTime);

      // Notify error
      _notifyObservers((observer) {
        observer.onError(
          HttpErrorEvent(
            requestId: requestId,
            timestamp: endTime,
            method: method,
            uri: uri,
            exception: e,
            duration: duration,
          ),
        );
      });

      rethrow;
    }
  }

  @override
  Stream<List<int>> requestStream(
    String method,
    Uri uri, {
    Map<String, String>? headers,
    Object? body,
  }) {
    final requestId = _generateRequestId();
    final startTime = DateTime.now();
    var bytesReceived = 0;

    // Notify stream start
    _notifyObservers((observer) {
      observer.onStreamStart(
        HttpStreamStartEvent(
          requestId: requestId,
          timestamp: startTime,
          method: method,
          uri: uri,
        ),
      );
    });

    // Get the source stream
    final sourceStream = _client.requestStream(
      method,
      uri,
      headers: headers,
      body: body,
    );

    // Transform stream to intercept data, errors, and completion
    return sourceStream.transform(
      StreamTransformer<List<int>, List<int>>.fromHandlers(
        handleData: (data, sink) {
          bytesReceived += data.length;
          sink.add(data);
        },
        handleError: (error, stackTrace, sink) {
          final endTime = DateTime.now();
          final duration = endTime.difference(startTime);

          // Only notify with SoliplexException errors
          final soliplexError = error is SoliplexException
              ? error
              : NetworkException(
                  message: error.toString(),
                  originalError: error,
                  stackTrace: stackTrace,
                );

          _notifyObservers((observer) {
            observer.onStreamEnd(
              HttpStreamEndEvent(
                requestId: requestId,
                timestamp: endTime,
                bytesReceived: bytesReceived,
                duration: duration,
                error: soliplexError,
              ),
            );
          });

          sink.addError(error, stackTrace);
        },
        handleDone: (sink) {
          final endTime = DateTime.now();
          final duration = endTime.difference(startTime);

          _notifyObservers((observer) {
            observer.onStreamEnd(
              HttpStreamEndEvent(
                requestId: requestId,
                timestamp: endTime,
                bytesReceived: bytesReceived,
                duration: duration,
              ),
            );
          });

          sink.close();
        },
      ),
    );
  }

  @override
  void close() {
    _client.close();
  }

  /// Safely notifies all observers, catching and ignoring any exceptions.
  ///
  /// Observer exceptions should never break the request flow.
  void _notifyObservers(void Function(HttpObserver observer) notify) {
    for (final observer in _observers) {
      try {
        notify(observer);
      } catch (e, stackTrace) {
        // Observer threw exception - log but don't break request flow.
        // Use assert pattern to only log in debug mode (assertions enabled).
        assert(
          () {
            // ignore: avoid_print
            print(
              'Warning: HttpObserver ${observer.runtimeType} '
              'threw exception: $e',
            );
            // ignore: avoid_print
            print(stackTrace);
            return true;
          }(),
          'Observer exception logged',
        );
      }
    }
  }
}
