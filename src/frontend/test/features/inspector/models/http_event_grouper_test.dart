import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_frontend/features/inspector/models/http_event_grouper.dart';

import '../../../helpers/test_helpers.dart';

void main() {
  group('groupHttpEvents', () {
    test('returns empty list for empty input', () {
      final groups = groupHttpEvents([]);
      expect(groups, isEmpty);
    });

    test('creates single group for single event', () {
      final events = [
        TestData.createRequestEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].requestId, 'req-1');
      expect(groups[0].request, isNotNull);
    });

    test('groups request and response by requestId', () {
      final events = [
        TestData.createRequestEvent(),
        TestData.createResponseEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].request, isNotNull);
      expect(groups[0].response, isNotNull);
    });

    test('groups events into separate groups by requestId', () {
      final events = [
        TestData.createRequestEvent(),
        TestData.createRequestEvent(requestId: 'req-2'),
        TestData.createResponseEvent(),
        TestData.createResponseEvent(requestId: 'req-2'),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 2);
      expect(groups[0].request, isNotNull);
      expect(groups[0].response, isNotNull);
      expect(groups[1].request, isNotNull);
      expect(groups[1].response, isNotNull);
    });

    test('sorts groups by timestamp', () {
      final now = DateTime.now();
      final events = [
        TestData.createRequestEvent(
          requestId: 'req-2',
          timestamp: now.add(const Duration(minutes: 1)),
        ),
        TestData.createRequestEvent(
          timestamp: now,
        ),
      ];

      final groups = groupHttpEvents(events);

      expect(groups[0].requestId, 'req-1');
      expect(groups[1].requestId, 'req-2');
    });

    test('handles events arriving out of order', () {
      final now = DateTime.now();
      final events = [
        TestData.createResponseEvent(
          timestamp: now.add(const Duration(milliseconds: 100)),
        ),
        TestData.createRequestEvent(
          timestamp: now,
        ),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].request, isNotNull);
      expect(groups[0].response, isNotNull);
    });

    test('groups error event with request', () {
      final events = [
        TestData.createRequestEvent(),
        TestData.createErrorEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].request, isNotNull);
      expect(groups[0].error, isNotNull);
    });

    test('groups streaming events together', () {
      final events = [
        TestData.createStreamStartEvent(),
        TestData.createStreamEndEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].streamStart, isNotNull);
      expect(groups[0].streamEnd, isNotNull);
      expect(groups[0].isStream, isTrue);
    });

    test('handles orphan response (response without request)', () {
      final events = [
        TestData.createResponseEvent(requestId: 'orphan'),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].requestId, 'orphan');
      expect(groups[0].request, isNull);
      expect(groups[0].response, isNotNull);
    });

    test('handles orphan error (error without request)', () {
      final events = [
        TestData.createErrorEvent(requestId: 'orphan'),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].request, isNull);
      expect(groups[0].error, isNotNull);
    });

    test('handles mixed regular and streaming requests', () {
      final now = DateTime.now();
      final events = [
        TestData.createRequestEvent(
          requestId: 'regular',
          timestamp: now,
        ),
        TestData.createStreamStartEvent(
          requestId: 'stream',
          timestamp: now.add(const Duration(milliseconds: 50)),
        ),
        TestData.createResponseEvent(
          requestId: 'regular',
          timestamp: now.add(const Duration(milliseconds: 100)),
        ),
        TestData.createStreamEndEvent(
          requestId: 'stream',
          timestamp: now.add(const Duration(seconds: 5)),
        ),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 2);
      expect(groups[0].requestId, 'regular');
      expect(groups[0].isStream, isFalse);
      expect(groups[0].response, isNotNull);
      expect(groups[1].requestId, 'stream');
      expect(groups[1].isStream, isTrue);
      expect(groups[1].streamEnd, isNotNull);
    });

    test('groups multiple events for same request', () {
      final events = [
        TestData.createRequestEvent(),
        TestData.createResponseEvent(),
        TestData.createErrorEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].request, isNotNull);
      expect(groups[0].response, isNotNull);
      expect(groups[0].error, isNotNull);
    });

    test('preserves all event types in group', () {
      final events = [
        TestData.createRequestEvent(),
        TestData.createResponseEvent(),
        TestData.createStreamStartEvent(),
        TestData.createStreamEndEvent(),
        TestData.createErrorEvent(),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      final group = groups[0];
      expect(group.request, isNotNull);
      expect(group.response, isNotNull);
      expect(group.streamStart, isNotNull);
      expect(group.streamEnd, isNotNull);
      expect(group.error, isNotNull);
    });

    test('later events of same type overwrite earlier ones', () {
      final events = [
        TestData.createResponseEvent(),
        TestData.createResponseEvent(statusCode: 404),
      ];

      final groups = groupHttpEvents(events);

      expect(groups.length, 1);
      expect(groups[0].response!.statusCode, 404);
    });
  });
}
