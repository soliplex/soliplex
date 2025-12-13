import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:mocktail/mocktail.dart';

/// Mock AgUiClient using mocktail for testing Thread class.
class MockAgUiClient extends Mock implements ag_ui.AgUiClient {
  List<ag_ui.BaseEvent>? eventsToReturn;
  Exception? exceptionToThrow;

  /// Sets up the runAgent method stub based on eventsToReturn/exceptionToThrow
  void setupRunAgent() {
    when(() => runAgent(any(), any())).thenAnswer((_) {
      if (exceptionToThrow != null) {
        throw exceptionToThrow!;
      }
      return createEventStream(eventsToReturn ?? []);
    });
  }
}

/// Helper to create a stream of events for testing
Stream<ag_ui.BaseEvent> createEventStream(List<ag_ui.BaseEvent> events) async* {
  for (final event in events) {
    yield event;
  }
}
