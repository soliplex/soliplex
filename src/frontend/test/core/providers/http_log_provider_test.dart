import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

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
      test('stores HttpRequestEvent', () {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
        );

        notifier.onRequest(event);

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onResponse', () {
      test('stores HttpResponseEvent', () {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpResponseEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          statusCode: 200,
          duration: const Duration(milliseconds: 45),
          bodySize: 1024,
        );

        notifier.onResponse(event);

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onError', () {
      test('stores HttpErrorEvent', () {
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

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onStreamStart', () {
      test('stores HttpStreamStartEvent', () {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpStreamStartEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/runs/stream'),
        );

        notifier.onStreamStart(event);

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('onStreamEnd', () {
      test('stores HttpStreamEndEvent', () {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpStreamEndEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          bytesReceived: 5120,
          duration: const Duration(seconds: 30),
        );

        notifier.onStreamEnd(event);

        final events = container.read(httpLogProvider);
        expect(events, hasLength(1));
        expect(events.first, event);
      });
    });

    group('event ordering', () {
      test('stores events in chronological order', () {
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

        notifier.onRequest(requestEvent);
        notifier.onResponse(responseEvent);

        final events = container.read(httpLogProvider);
        expect(events, hasLength(2));
        expect(events[0], requestEvent);
        expect(events[1], responseEvent);
      });
    });

    group('clear', () {
      test('removes all events', () {
        final notifier = container.read(httpLogProvider.notifier);
        final event = HttpRequestEvent(
          requestId: 'req-1',
          timestamp: DateTime.now(),
          method: 'GET',
          uri: Uri.parse('http://localhost/api/rooms'),
        );

        notifier.onRequest(event);
        expect(container.read(httpLogProvider), hasLength(1));

        notifier.clear();

        expect(container.read(httpLogProvider), isEmpty);
      });
    });

    group('event cap', () {
      test('limits events to maxEvents', () {
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

        final events = container.read(httpLogProvider);
        expect(events, hasLength(HttpLogNotifier.maxEvents));
      });

      test('drops oldest events when cap exceeded', () {
        final notifier = container.read(httpLogProvider.notifier);
        final totalEvents = HttpLogNotifier.maxEvents + 50;

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

        final events = container.read(httpLogProvider);
        // First event should be req-50 (oldest 50 were dropped)
        final firstEvent = events.first as HttpRequestEvent;
        expect(firstEvent.requestId, 'req-50');
        // Last event should be req-(totalEvents-1)
        final lastEvent = events.last as HttpRequestEvent;
        expect(lastEvent.requestId, 'req-${totalEvents - 1}');
      });

      test('maintains order with rapid events from multiple methods', () {
        final notifier = container.read(httpLogProvider.notifier);

        for (var i = 0; i < 100; i++) {
          notifier.onRequest(
            HttpRequestEvent(
              requestId: 'req-$i',
              timestamp: DateTime.now(),
              method: 'GET',
              uri: Uri.parse('http://localhost/api/test'),
            ),
          );
          notifier.onResponse(
            HttpResponseEvent(
              requestId: 'req-$i',
              timestamp: DateTime.now(),
              statusCode: 200,
              duration: const Duration(milliseconds: 10),
              bodySize: 100,
            ),
          );
        }

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
