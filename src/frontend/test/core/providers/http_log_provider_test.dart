import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

/// Pumps the microtask queue multiple times to allow scheduled microtasks
/// to execute, including any microtasks scheduled by other microtasks.
Future<void> pumpMicrotasks() async {
  for (var i = 0; i < 10; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

void main() {
  group('HttpLogNotifier', () {
    late ProviderContainer container;

    setUp(() {
      container = ProviderContainer();
    });

    tearDown(() {
      container.dispose();
    });

    test('starts with empty event list', () {
      final events = container.read(httpLogProvider);

      expect(events, isEmpty);
    });

    test('implements HttpObserver', () {
      final notifier = container.read(httpLogProvider.notifier);

      expect(notifier, isA<HttpObserver>());
    });

    group('onRequest', () {
      test('stores HttpRequestEvent', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
        );

        notifier.onRequest(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onResponse', () {
      test('stores HttpResponseEvent', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpResponseEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          statusCode: 200,
          duration: const Duration(milliseconds: 45),
          bodySize: 1024,
        );

        notifier.onResponse(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onError', () {
      test('stores HttpErrorEvent', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpErrorEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'POST',
          uri: Uri.parse('http://localhost/api/threads'),
          exception: const NetworkException(message: 'Timeout'),
          duration: const Duration(seconds: 2),
        );

        notifier.onError(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onStreamStart', () {
      test('stores HttpStreamStartEvent', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpStreamStartEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/runs/stream'),
        );

        notifier.onStreamStart(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onStreamEnd', () {
      test('stores HttpStreamEndEvent', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpStreamEndEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          bytesReceived: 5120,
          duration: const Duration(seconds: 30),
        );

        notifier.onStreamEnd(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('event ordering', () {
      test('stores events in chronological order', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final now = DateTime.now();

        final requestEvent = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: now,
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
        );
        final responseEvent = HttpResponseEvent(
          requestId: 'req-1',
          timestamp: now.add(const Duration(milliseconds: 50)),
          statusCode: 200,
          duration: const Duration(milliseconds: 50),
          bodySize: 512,
        );

        notifier
          ..onRequest(requestEvent)
          ..onResponse(responseEvent);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(2));
        expect(events[0], requestEvent);
        expect(events[1], responseEvent);
      });
    });

    group('clear', () {
      test('removes all events', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
        );

        notifier.onRequest(event);
        await pumpMicrotasks();
        expect(container.read(httpLogProvider), hasLength(1));

        notifier.clear();

        expect(container.read(httpLogProvider), isEmpty);
      });
    });

    group('sensitive data redaction', () {
      test('redacts authorization header in request', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
          headers: const {'Authorization': 'Bearer secret-token-123'},
        );

        notifier.onRequest(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        final stored = events.first as HttpRequestEvent;
        expect(stored.headers['Authorization'], '[REDACTED]');
      });

      test('redacts sensitive query params in request URI', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse(
            'http://localhost/callback?code=auth-code-123&state=state-456',
          ),
        );

        notifier.onRequest(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        final stored = events.first as HttpRequestEvent;
        expect(stored.uri.queryParameters['code'], '[REDACTED]');
        expect(stored.uri.queryParameters['state'], '[REDACTED]');
      });

      test('preserves non-sensitive query params', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api?page=1&limit=10'),
        );

        notifier.onRequest(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        final stored = events.first as HttpRequestEvent;
        expect(stored.uri.queryParameters['page'], '1');
        expect(stored.uri.queryParameters['limit'], '10');
      });

      test('redacts sensitive query params in error event URI', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpErrorEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/token?access_token=secret'),
          exception: const NetworkException(message: 'Timeout'),
          duration: const Duration(seconds: 2),
        );

        notifier.onError(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        final stored = events.first as HttpErrorEvent;
        expect(stored.uri.queryParameters['access_token'], '[REDACTED]');
      });

      test('redacts sensitive query params in stream start event', () async {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpStreamStartEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/stream?refresh_token=secret'),
        );

        notifier.onStreamStart(event);
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        final stored = events.first as HttpStreamStartEvent;
        expect(stored.uri.queryParameters['refresh_token'], '[REDACTED]');
      });
    });

    group('event cap', () {
      test('limits events to maxEvents', () async {
        final notifier = container.read(httpLogProvider.notifier);

        // Add more events than the cap allows
        for (var i = 0; i < HttpLogNotifier.maxEvents + 100; i++) {
          notifier.onRequest(
            HttpRequestEvent(
              requestId: 'req-$i',
              timestamp: DateTime.now(),
              method: 'GET',
              uri: Uri.parse('http://localhost/api/test'),
            ),
          );
        }
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(HttpLogNotifier.maxEvents));
      });

      test('drops oldest events when cap exceeded', () async {
        final notifier = container.read(httpLogProvider.notifier);
        const overflowCount = 50;
        const totalEvents = HttpLogNotifier.maxEvents + overflowCount;

        for (var i = 0; i < totalEvents; i++) {
          notifier.onRequest(
            HttpRequestEvent(
              requestId: 'req-$i',
              timestamp: DateTime.now(),
              method: 'GET',
              uri: Uri.parse('http://localhost/api/test'),
            ),
          );
        }
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        // First event should be req-{overflowCount} (oldest were dropped)
        final firstEvent = events.first as HttpRequestEvent;
        expect(firstEvent.requestId, 'req-$overflowCount');
        // Last event should be req-(totalEvents-1)
        final lastEvent = events.last as HttpRequestEvent;
        expect(lastEvent.requestId, 'req-${totalEvents - 1}');
      });

      test('maintains order with rapid events from multiple methods', () async {
        final notifier = container.read(httpLogProvider.notifier);

        for (var i = 0; i < 100; i++) {
          notifier
            ..onRequest(
              HttpRequestEvent(
                requestId: 'req-$i',
                timestamp: DateTime.now(),
                method: 'GET',
                uri: Uri.parse('http://localhost/api/test'),
              ),
            )
            ..onResponse(
              HttpResponseEvent(
                requestId: 'req-$i',
                timestamp: DateTime.now(),
                statusCode: 200,
                duration: const Duration(milliseconds: 10),
                bodySize: 100,
              ),
            );
        }
        await pumpMicrotasks();

        final events = container.read(httpLogProvider);
        expect(events, hasLength(200));

        // Verify alternating pattern preserved
        for (var i = 0; i < 100; i++) {
          expect(events[i * 2], isA<HttpRequestEvent>());
          expect(events[i * 2 + 1], isA<HttpResponseEvent>());
          expect((events[i * 2] as HttpRequestEvent).requestId, 'req-$i');
          expect((events[i * 2 + 1] as HttpResponseEvent).requestId, 'req-$i');
        }
      });
    });
  });
}
