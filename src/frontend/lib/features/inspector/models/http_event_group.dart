import 'package:soliplex_client/soliplex_client.dart';

/// Status of an HTTP event group.
enum HttpEventStatus {
  pending,
  success,
  clientError,
  serverError,
  networkError,
  streaming,
  streamComplete,
  streamError,
}

/// Groups related HTTP events by requestId.
///
/// Correlates request/response pairs and streaming events into a single
/// logical unit for display and analysis.
class HttpEventGroup {
  HttpEventGroup({
    required this.requestId,
    this.request,
    this.response,
    this.error,
    this.streamStart,
    this.streamEnd,
  });

  final String requestId;
  final HttpRequestEvent? request;
  final HttpResponseEvent? response;
  final HttpErrorEvent? error;
  final HttpStreamStartEvent? streamStart;
  final HttpStreamEndEvent? streamEnd;

  HttpEventGroup copyWith({
    HttpRequestEvent? request,
    HttpResponseEvent? response,
    HttpErrorEvent? error,
    HttpStreamStartEvent? streamStart,
    HttpStreamEndEvent? streamEnd,
  }) =>
      HttpEventGroup(
        requestId: requestId,
        request: request ?? this.request,
        response: response ?? this.response,
        error: error ?? this.error,
        streamStart: streamStart ?? this.streamStart,
        streamEnd: streamEnd ?? this.streamEnd,
      );

  bool get isStream => streamStart != null;

  /// UI label for the request method.
  ///
  /// Returns 'SSE' for streams, HTTP method otherwise.
  String get methodLabel => isStream ? 'SSE' : method;

  /// Returns the HTTP method from the first available event.
  ///
  /// Throws [StateError] if no event contains method information.
  /// Check [hasEvents] before accessing if the group may be incomplete.
  String get method {
    if (request != null) return request!.method;
    if (error != null) return error!.method;
    if (streamStart != null) return streamStart!.method;
    throw StateError('HttpEventGroup $requestId has no event with method');
  }

  /// Returns the URI from the first available event.
  ///
  /// Throws [StateError] if no event contains URI information.
  /// Check [hasEvents] before accessing if the group may be incomplete.
  Uri get uri {
    if (request != null) return request!.uri;
    if (error != null) return error!.uri;
    if (streamStart != null) return streamStart!.uri;
    throw StateError('HttpEventGroup $requestId has no event with uri');
  }

  String get pathWithQuery {
    final u = uri;
    final path = u.path.isEmpty ? '/' : u.path;
    if (u.hasQuery) {
      return '$path?${u.query}';
    }
    return path;
  }

  /// Returns the timestamp from the first available event.
  ///
  /// Throws [StateError] if no event contains timestamp information.
  /// Check [hasEvents] before accessing if the group may be incomplete.
  DateTime get timestamp {
    if (request != null) return request!.timestamp;
    if (streamStart != null) return streamStart!.timestamp;
    if (error != null) return error!.timestamp;
    throw StateError('HttpEventGroup $requestId has no event with timestamp');
  }

  /// Whether this group contains at least one event.
  ///
  /// An incomplete group (no events) will throw [StateError] when accessing
  /// [method], [uri], or [timestamp]. Check this property first if the group
  /// may be incomplete.
  bool get hasEvents =>
      request != null ||
      response != null ||
      error != null ||
      streamStart != null ||
      streamEnd != null;

  /// Determines the aggregate status of this event group.
  ///
  /// Precedence: stream state > error > response status code.
  /// Streams check completion and error state first. For non-streams,
  /// network errors take precedence over missing responses (pending).
  HttpEventStatus get status {
    if (isStream) {
      if (streamEnd == null) return HttpEventStatus.streaming;
      if (streamEnd!.error != null) return HttpEventStatus.streamError;
      return HttpEventStatus.streamComplete;
    }

    if (error != null) return HttpEventStatus.networkError;
    if (response == null) return HttpEventStatus.pending;

    final code = response!.statusCode;
    if (code >= 200 && code < 300) return HttpEventStatus.success;
    if (code >= 400 && code < 500) return HttpEventStatus.clientError;
    if (code >= 500) return HttpEventStatus.serverError;
    return HttpEventStatus.success;
  }

  /// Whether this status should display a spinner.
  bool get hasSpinner =>
      status == HttpEventStatus.pending || status == HttpEventStatus.streaming;

  /// Human-readable description of the current status for accessibility.
  String get statusDescription {
    return switch (status) {
      HttpEventStatus.pending => 'pending',
      HttpEventStatus.success => 'success, status ${response!.statusCode}',
      HttpEventStatus.clientError =>
        'client error, status ${response!.statusCode}',
      HttpEventStatus.serverError =>
        'server error, status ${response!.statusCode}',
      HttpEventStatus.networkError =>
        'network error, ${error!.exception.runtimeType}',
      HttpEventStatus.streaming => 'streaming',
      HttpEventStatus.streamComplete => 'stream complete',
      HttpEventStatus.streamError => 'stream error',
    };
  }

  /// Semantic label describing this request for accessibility.
  String get semanticLabel {
    final methodText = isStream ? 'SSE stream' : '$method request';
    return '$methodText to $pathWithQuery, $statusDescription';
  }
}
