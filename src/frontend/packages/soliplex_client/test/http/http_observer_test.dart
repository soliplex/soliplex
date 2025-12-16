import 'package:soliplex_client/soliplex_client.dart';
import 'package:test/test.dart';

void main() {
  group('HttpRequestEvent', () {
    test('creates event with required fields', () {
      final timestamp = DateTime(2024, 1, 15, 10, 30);
      final uri = Uri.parse('https://example.com/api');

      final event = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: timestamp,
        method: 'GET',
        uri: uri,
      );

      expect(event.requestId, equals('req-123'));
      expect(event.timestamp, equals(timestamp));
      expect(event.method, equals('GET'));
      expect(event.uri, equals(uri));
      expect(event.headers, isEmpty);
    });

    test('creates event with headers', () {
      final event = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'POST',
        uri: Uri.parse('https://example.com/api'),
        headers: const {
          'Authorization': 'Bearer token',
          'Content-Type': 'json',
        },
      );

      expect(event.headers, hasLength(2));
      expect(event.headers['Authorization'], equals('Bearer token'));
    });

    test('equality is based on requestId', () {
      final event1 = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 15),
        method: 'GET',
        uri: Uri.parse('https://example.com/a'),
      );

      final event2 = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 16),
        method: 'POST',
        uri: Uri.parse('https://example.com/b'),
      );

      final event3 = HttpRequestEvent(
        requestId: 'req-456',
        timestamp: DateTime(2024, 1, 15),
        method: 'GET',
        uri: Uri.parse('https://example.com/a'),
      );

      expect(event1, equals(event2));
      expect(event1, isNot(equals(event3)));
      expect(event1.hashCode, equals(event2.hashCode));
    });

    test('identical returns true for same instance', () {
      final event = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
      );

      expect(event == event, isTrue);
    });

    test('returns false for non-HttpRequestEvent', () {
      final event = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
      );

      // ignore: unrelated_type_equality_checks
      expect(event == 'not an event', isFalse);
    });

    test('toString includes key information', () {
      final event = HttpRequestEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com/api'),
      );

      final str = event.toString();
      expect(str, contains('HttpRequestEvent'));
      expect(str, contains('req-123'));
      expect(str, contains('GET'));
      expect(str, contains('https://example.com/api'));
    });
  });

  group('HttpResponseEvent', () {
    test('creates event with required fields', () {
      final timestamp = DateTime(2024, 1, 15, 10, 30);
      const duration = Duration(milliseconds: 150);

      final event = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: timestamp,
        statusCode: 200,
        duration: duration,
        bodySize: 1024,
      );

      expect(event.requestId, equals('req-123'));
      expect(event.timestamp, equals(timestamp));
      expect(event.statusCode, equals(200));
      expect(event.duration, equals(duration));
      expect(event.bodySize, equals(1024));
      expect(event.reasonPhrase, isNull);
    });

    test('creates event with reasonPhrase', () {
      final event = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        statusCode: 201,
        duration: const Duration(milliseconds: 100),
        bodySize: 512,
        reasonPhrase: 'Created',
      );

      expect(event.reasonPhrase, equals('Created'));
    });

    test('isSuccess returns true for 2xx status codes', () {
      for (final statusCode in [200, 201, 204, 299]) {
        final event = HttpResponseEvent(
          requestId: 'req-123',
          timestamp: DateTime.now(),
          statusCode: statusCode,
          duration: Duration.zero,
          bodySize: 0,
        );

        expect(event.isSuccess, isTrue, reason: 'Status $statusCode');
      }
    });

    test('isSuccess returns false for non-2xx status codes', () {
      for (final statusCode in [100, 199, 300, 400, 404, 500]) {
        final event = HttpResponseEvent(
          requestId: 'req-123',
          timestamp: DateTime.now(),
          statusCode: statusCode,
          duration: Duration.zero,
          bodySize: 0,
        );

        expect(event.isSuccess, isFalse, reason: 'Status $statusCode');
      }
    });

    test('equality is based on requestId', () {
      final event1 = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 15),
        statusCode: 200,
        duration: const Duration(milliseconds: 100),
        bodySize: 100,
      );

      final event2 = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 16),
        statusCode: 404,
        duration: const Duration(milliseconds: 200),
        bodySize: 200,
      );

      expect(event1, equals(event2));
      expect(event1.hashCode, equals(event2.hashCode));
    });

    test('identical returns true for same instance', () {
      final event = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        statusCode: 200,
        duration: Duration.zero,
        bodySize: 0,
      );

      expect(event == event, isTrue);
    });

    test('returns false for non-HttpResponseEvent', () {
      final event = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        statusCode: 200,
        duration: Duration.zero,
        bodySize: 0,
      );

      // ignore: unrelated_type_equality_checks
      expect(event == 'not an event', isFalse);
    });

    test('toString includes key information', () {
      final event = HttpResponseEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        statusCode: 200,
        duration: const Duration(milliseconds: 150),
        bodySize: 1024,
      );

      final str = event.toString();
      expect(str, contains('HttpResponseEvent'));
      expect(str, contains('req-123'));
      expect(str, contains('200'));
      expect(str, contains('150ms'));
      expect(str, contains('1024B'));
    });
  });

  group('HttpErrorEvent', () {
    test('creates event with required fields', () {
      final timestamp = DateTime(2024, 1, 15, 10, 30);
      final uri = Uri.parse('https://example.com/api');
      const exception = NetworkException(message: 'Connection failed');
      const duration = Duration(milliseconds: 50);

      final event = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: timestamp,
        method: 'GET',
        uri: uri,
        exception: exception,
        duration: duration,
      );

      expect(event.requestId, equals('req-123'));
      expect(event.timestamp, equals(timestamp));
      expect(event.method, equals('GET'));
      expect(event.uri, equals(uri));
      expect(event.exception, equals(exception));
      expect(event.duration, equals(duration));
    });

    test('equality is based on requestId', () {
      final event1 = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 15),
        method: 'GET',
        uri: Uri.parse('https://example.com/a'),
        exception: const NetworkException(message: 'Error 1'),
        duration: const Duration(milliseconds: 100),
      );

      final event2 = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 16),
        method: 'POST',
        uri: Uri.parse('https://example.com/b'),
        exception: const NetworkException(message: 'Error 2'),
        duration: const Duration(milliseconds: 200),
      );

      expect(event1, equals(event2));
      expect(event1.hashCode, equals(event2.hashCode));
    });

    test('identical returns true for same instance', () {
      final event = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
        exception: const NetworkException(message: 'Error'),
        duration: Duration.zero,
      );

      expect(event == event, isTrue);
    });

    test('returns false for non-HttpErrorEvent', () {
      final event = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
        exception: const NetworkException(message: 'Error'),
        duration: Duration.zero,
      );

      // ignore: unrelated_type_equality_checks
      expect(event == 'not an event', isFalse);
    });

    test('toString includes key information', () {
      final event = HttpErrorEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'POST',
        uri: Uri.parse('https://example.com/api'),
        exception: const NetworkException(message: 'Timeout', isTimeout: true),
        duration: const Duration(milliseconds: 5000),
      );

      final str = event.toString();
      expect(str, contains('HttpErrorEvent'));
      expect(str, contains('req-123'));
      expect(str, contains('POST'));
      expect(str, contains('https://example.com/api'));
      expect(str, contains('NetworkException'));
    });
  });

  group('HttpStreamStartEvent', () {
    test('creates event with required fields', () {
      final timestamp = DateTime(2024, 1, 15, 10, 30);
      final uri = Uri.parse('https://example.com/stream');

      final event = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: timestamp,
        method: 'GET',
        uri: uri,
      );

      expect(event.requestId, equals('req-123'));
      expect(event.timestamp, equals(timestamp));
      expect(event.method, equals('GET'));
      expect(event.uri, equals(uri));
    });

    test('equality is based on requestId', () {
      final event1 = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 15),
        method: 'GET',
        uri: Uri.parse('https://example.com/a'),
      );

      final event2 = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 16),
        method: 'POST',
        uri: Uri.parse('https://example.com/b'),
      );

      expect(event1, equals(event2));
      expect(event1.hashCode, equals(event2.hashCode));
    });

    test('identical returns true for same instance', () {
      final event = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
      );

      expect(event == event, isTrue);
    });

    test('returns false for non-HttpStreamStartEvent', () {
      final event = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'GET',
        uri: Uri.parse('https://example.com'),
      );

      // ignore: unrelated_type_equality_checks
      expect(event == 'not an event', isFalse);
    });

    test('toString includes key information', () {
      final event = HttpStreamStartEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        method: 'POST',
        uri: Uri.parse('https://example.com/stream'),
      );

      final str = event.toString();
      expect(str, contains('HttpStreamStartEvent'));
      expect(str, contains('req-123'));
      expect(str, contains('POST'));
      expect(str, contains('https://example.com/stream'));
    });
  });

  group('HttpStreamEndEvent', () {
    test('creates event with required fields for success', () {
      final timestamp = DateTime(2024, 1, 15, 10, 30);
      const duration = Duration(seconds: 5);

      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: timestamp,
        bytesReceived: 10240,
        duration: duration,
      );

      expect(event.requestId, equals('req-123'));
      expect(event.timestamp, equals(timestamp));
      expect(event.bytesReceived, equals(10240));
      expect(event.duration, equals(duration));
      expect(event.error, isNull);
      expect(event.isSuccess, isTrue);
    });

    test('creates event with error', () {
      const error = NetworkException(message: 'Connection lost');

      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 5000,
        duration: const Duration(seconds: 2),
        error: error,
      );

      expect(event.error, equals(error));
      expect(event.isSuccess, isFalse);
    });

    test('isSuccess returns true when error is null', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 1000,
        duration: const Duration(milliseconds: 500),
      );

      expect(event.isSuccess, isTrue);
    });

    test('isSuccess returns false when error is present', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 1000,
        duration: const Duration(milliseconds: 500),
        error: const CancelledException(),
      );

      expect(event.isSuccess, isFalse);
    });

    test('equality is based on requestId', () {
      final event1 = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 15),
        bytesReceived: 100,
        duration: const Duration(seconds: 1),
      );

      final event2 = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime(2024, 1, 16),
        bytesReceived: 200,
        duration: const Duration(seconds: 2),
        error: const NetworkException(message: 'Error'),
      );

      expect(event1, equals(event2));
      expect(event1.hashCode, equals(event2.hashCode));
    });

    test('identical returns true for same instance', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 0,
        duration: Duration.zero,
      );

      expect(event == event, isTrue);
    });

    test('returns false for non-HttpStreamEndEvent', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 0,
        duration: Duration.zero,
      );

      // ignore: unrelated_type_equality_checks
      expect(event == 'not an event', isFalse);
    });

    test('toString includes key information for success', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 2048,
        duration: const Duration(milliseconds: 1500),
      );

      final str = event.toString();
      expect(str, contains('HttpStreamEndEvent'));
      expect(str, contains('req-123'));
      expect(str, contains('2048B'));
      expect(str, contains('1500ms'));
      expect(str, isNot(contains('error')));
    });

    test('toString includes error indicator when error present', () {
      final event = HttpStreamEndEvent(
        requestId: 'req-123',
        timestamp: DateTime.now(),
        bytesReceived: 500,
        duration: const Duration(milliseconds: 300),
        error: const NetworkException(message: 'Failed'),
      );

      final str = event.toString();
      expect(str, contains('error'));
    });
  });
}
