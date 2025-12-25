import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_group.dart';

/// Groups a flat list of HTTP events by requestId into [HttpEventGroup]s.
///
/// Events are correlated and sorted by timestamp (oldest first).
List<HttpEventGroup> groupHttpEvents(List<HttpEvent> events) {
  final groups = <String, HttpEventGroup>{};

  for (final event in events) {
    final id = event.requestId;
    final existing = groups[id] ?? HttpEventGroup(requestId: id);

    groups[id] = switch (event) {
      HttpRequestEvent() => existing.copyWith(request: event),
      HttpResponseEvent() => existing.copyWith(response: event),
      HttpErrorEvent() => existing.copyWith(error: event),
      HttpStreamStartEvent() => existing.copyWith(streamStart: event),
      HttpStreamEndEvent() => existing.copyWith(streamEnd: event),
      _ => existing,
    };
  }

  final sorted = groups.values.toList()
    ..sort((a, b) => a.timestamp.compareTo(b.timestamp));
  return sorted;
}
