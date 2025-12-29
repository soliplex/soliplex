import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/cancel_token.dart';
import 'package:soliplex/infrastructure/quick_agui/thread.dart';

/// Tests for the watchdog timer that detects server hangs.
void main() {
  group('Thread watchdog timer', () {
    test('Watchdog fires after timeout with no events', () async {
      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) async* {
          // Send one event, then hang forever
          yield const ag_ui.RunStartedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
          // Simulate server hang - never complete
          await Future<void>.delayed(const Duration(seconds: 10));
        },
      );

      // Use a very short timeout for testing
      await expectLater(
        thread.startRun(
          endpoint: '/agent',
          runId: 'run-1',
          streamTimeout: const Duration(milliseconds: 50),
        ),
        throwsA(isA<StreamTimeoutException>()),
      );

      thread.dispose();
    });

    test('Watchdog resets on each event - no false timeout', () async {
      final events = <ag_ui.BaseEvent>[];

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) async* {
          // Each event comes within timeout window
          yield const ag_ui.RunStartedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
          await Future<void>.delayed(const Duration(milliseconds: 30));

          yield const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          );
          await Future<void>.delayed(const Duration(milliseconds: 30));

          yield const ag_ui.TextMessageContentEvent(
            messageId: 'm1',
            delta: 'Hello',
          );
          await Future<void>.delayed(const Duration(milliseconds: 30));

          yield const ag_ui.TextMessageEndEvent(messageId: 'm1');
          yield const ag_ui.RunFinishedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
        },
      );

      thread.stepsStream.listen(events.add);

      // Timeout is 100ms, but events come every 30ms - should not timeout
      await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        streamTimeout: const Duration(milliseconds: 100),
      );

      // All events should be received (no timeout)
      expect(events.length, equals(5));
      expect(events.last, isA<ag_ui.RunFinishedEvent>());

      thread.dispose();
    });

    test('Timeout ignored after cancel if events still flowing', () async {
      // When user cancels (switches rooms), timeout errors are caught and
      // ignored
      // but only if the stream is still actively delivering events.
      // If the server truly hangs after cancel, the timeout will still fire.
      // This is acceptable - we're draining to get results, not waiting
      // forever.
      final events = <ag_ui.BaseEvent>[];
      final cancelToken = CancelToken();

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) async* {
          yield const ag_ui.RunStartedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );

          yield const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          );

          // Events continue within timeout window
          await Future<void>.delayed(const Duration(milliseconds: 20));

          yield const ag_ui.TextMessageContentEvent(
            messageId: 'm1',
            delta: 'Still coming',
          );

          await Future<void>.delayed(const Duration(milliseconds: 20));

          yield const ag_ui.TextMessageEndEvent(messageId: 'm1');
          yield const ag_ui.RunFinishedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
        },
      );

      thread.stepsStream.listen((event) {
        events.add(event);
        // Cancel after first event
        if (events.length == 1) {
          cancelToken.cancel('User switched');
        }
      });

      // Timeout is 50ms, events come every 20ms, so should complete
      await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        cancelToken: cancelToken,
        streamTimeout: const Duration(milliseconds: 50),
      );

      // All events should be received
      expect(events.length, equals(5));
      expect(events.last, isA<ag_ui.RunFinishedEvent>());

      thread.dispose();
    });

    test('Watchdog disabled when streamTimeout is null', () async {
      final events = <ag_ui.BaseEvent>[];

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) async* {
          yield const ag_ui.RunStartedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
          // Long delay that would timeout if watchdog was enabled
          await Future<void>.delayed(const Duration(milliseconds: 100));
          yield const ag_ui.RunFinishedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
        },
      );

      thread.stepsStream.listen(events.add);

      // No timeout (null) - should complete even with long delay
      await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        streamTimeout: null,
      );

      expect(events.length, equals(2));

      thread.dispose();
    });

    test('StreamTimeoutException contains timeout duration', () async {
      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) async* {
          yield const ag_ui.RunStartedEvent(
            threadId: 'test-thread',
            runId: 'run-1',
          );
          // Hang
          await Future<void>.delayed(const Duration(seconds: 10));
        },
      );

      try {
        await thread.startRun(
          endpoint: '/agent',
          runId: 'run-1',
          streamTimeout: const Duration(milliseconds: 50),
        );
        fail('Should have thrown');
      } on StreamTimeoutException catch (e) {
        expect(e.timeout, equals(const Duration(milliseconds: 50)));
        expect(e.message, contains('No SSE event received'));
      }

      thread.dispose();
    });
  });
}
