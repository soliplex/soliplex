import 'dart:async';

import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/network/cancel_token.dart';
import 'package:soliplex/infrastructure/quick_agui/thread.dart';

/// Critical regression tests for cancel behavior.
///
/// These tests ensure that when a user switches rooms/servers mid-stream,
/// events continue flowing to RoomSession so they can be collected later.
/// This is the "background result collection" feature.
void main() {
  group('Thread cancel behavior - background result collection', () {
    test(
      'Thread continues consuming events after cancel token fires',
      () async {
        final events = <ag_ui.BaseEvent>[];
        final cancelToken = CancelToken();

        // Stream that sends events with a delay, allowing cancel mid-stream
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

            // Cancel happens here (simulating user switch)
            yield const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'Hello ',
            );

            // These events should STILL be consumed after cancel
            yield const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'world!',
            );

            yield const ag_ui.TextMessageEndEvent(messageId: 'm1');

            yield const ag_ui.RunFinishedEvent(
              threadId: 'test-thread',
              runId: 'run-1',
            );
          },
        );

        thread.stepsStream.listen((event) {
          events.add(event);
          // Cancel after first few events (simulating user switch mid-stream)
          if (events.length == 3) {
            cancelToken.cancel('User switched rooms');
          }
        });

        await thread.startRun(
          endpoint: '/agent',
          runId: 'run-1',
          cancelToken: cancelToken,
          streamTimeout: null, // Disable watchdog for this test
        );

        // All events should have been consumed, even after cancel
        expect(events.length, equals(6));
        expect(events[0], isA<ag_ui.RunStartedEvent>());
        expect(events[5], isA<ag_ui.RunFinishedEvent>());

        thread.dispose();
      },
    );

    test('Events forwarded to stepsController even when cancelled', () async {
      final stepsEvents = <ag_ui.BaseEvent>[];
      final cancelToken = CancelToken();

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.RunStartedEvent(threadId: 'test-thread', runId: 'run-1'),
          const ag_ui.TextMessageStartEvent(
            messageId: 'm1',
          ),
          const ag_ui.TextMessageContentEvent(messageId: 'm1', delta: 'Result'),
          const ag_ui.TextMessageEndEvent(messageId: 'm1'),
          const ag_ui.RunFinishedEvent(threadId: 'test-thread', runId: 'run-1'),
        ]),
      );

      // Cancel before starting
      cancelToken.cancel('Pre-cancelled');

      thread.stepsStream.listen(stepsEvents.add);

      await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        cancelToken: cancelToken,
        streamTimeout: null,
      );

      // All events should still be forwarded to stepsStream
      // This is critical for RoomSession.processEvent() to receive them
      expect(stepsEvents.length, equals(5));
      expect(stepsEvents.whereType<ag_ui.RunFinishedEvent>().length, equals(1));

      thread.dispose();
    });

    test('Tool execution skipped when cancelled', () async {
      var toolExecuted = false;
      final cancelToken = CancelToken();

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.ToolCallStartEvent(
            toolCallId: 'tc1',
            toolCallName: 'test_tool',
          ),
          const ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          const ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
          const ag_ui.RunFinishedEvent(threadId: 'test-thread', runId: 'run-1'),
        ]),
        tools: [
          const ag_ui.Tool(
            name: 'test_tool',
            description: 'Test tool',
            parameters: {'type': 'object'},
          ),
        ],
        toolExecutors: {
          'test_tool': (call) async {
            toolExecuted = true;
            return 'executed';
          },
        },
      );

      // Cancel before starting
      cancelToken.cancel('Session suspended');

      await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        cancelToken: cancelToken,
        streamTimeout: null,
      );

      // Tool should NOT have been executed (cancelled)
      expect(toolExecuted, isFalse);

      thread.dispose();
    });

    test('Returns empty tool list when cancelled', () async {
      final cancelToken = CancelToken();

      final thread = Thread(
        id: 'test-thread',
        runAgent: (endpoint, input) => Stream.fromIterable([
          const ag_ui.ToolCallStartEvent(
            toolCallId: 'tc1',
            toolCallName: 'test_tool',
          ),
          const ag_ui.ToolCallArgsEvent(toolCallId: 'tc1', delta: '{}'),
          const ag_ui.ToolCallEndEvent(toolCallId: 'tc1'),
          const ag_ui.RunFinishedEvent(threadId: 'test-thread', runId: 'run-1'),
        ]),
        tools: [
          const ag_ui.Tool(
            name: 'test_tool',
            description: 'Test tool',
            parameters: {'type': 'object'},
          ),
        ],
        toolExecutors: {'test_tool': (call) async => 'result'},
      );

      // Cancel mid-stream
      cancelToken.cancel('Session suspended');

      final result = await thread.startRun(
        endpoint: '/agent',
        runId: 'run-1',
        cancelToken: cancelToken,
        streamTimeout: null,
      );

      // Should return empty list (no server round-trip)
      expect(result, isEmpty);

      thread.dispose();
    });

    test(
      'Stream completes normally after cancel - server closes stream',
      () async {
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
            yield const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'Processing...',
            );

            // Simulate delay while server processes
            await Future<void>.delayed(const Duration(milliseconds: 10));

            yield const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: ' Done!',
            );
            yield const ag_ui.TextMessageEndEvent(messageId: 'm1');
            yield const ag_ui.RunFinishedEvent(
              threadId: 'test-thread',
              runId: 'run-1',
            );
          },
        );

        thread.stepsStream.listen(events.add);

        // Cancel almost immediately
        Future<void>.delayed(const Duration(milliseconds: 5), () {
          cancelToken.cancel('User switched rooms');
        });

        // Start run and wait for completion
        await thread.startRun(
          endpoint: '/agent',
          runId: 'run-1',
          cancelToken: cancelToken,
          streamTimeout: null,
        );

        // Stream should complete normally (all events received)
        expect(events.whereType<ag_ui.RunFinishedEvent>().length, equals(1));

        thread.dispose();
      },
    );

    test(
      'Cancel mid-stream preserves events received before and after cancel',
      () async {
        final events = <ag_ui.BaseEvent>[];
        final cancelToken = CancelToken();
        var cancelledAt = 0;

        final thread = Thread(
          id: 'test-thread',
          runAgent: (endpoint, input) => Stream.fromIterable([
            const ag_ui.TextMessageStartEvent(
              messageId: 'm1',
            ),
            const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'Part 1',
            ),
            const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'Part 2',
            ),
            const ag_ui.TextMessageContentEvent(
              messageId: 'm1',
              delta: 'Part 3',
            ),
            const ag_ui.TextMessageEndEvent(messageId: 'm1'),
          ]),
        );

        thread.stepsStream.listen((event) {
          events.add(event);
          // Cancel after 2 events
          if (events.length == 2 && cancelledAt == 0) {
            cancelToken.cancel('Session suspended');
            cancelledAt = events.length;
          }
        });

        await thread.startRun(
          endpoint: '/agent',
          runId: 'run-1',
          cancelToken: cancelToken,
          streamTimeout: null,
        );

        // All 5 events should be received (before and after cancel)
        expect(events.length, equals(5));
        expect(cancelledAt, equals(2));

        // Verify event types
        expect(events[0], isA<ag_ui.TextMessageStartEvent>());
        expect(events[1], isA<ag_ui.TextMessageContentEvent>());
        expect(events[2], isA<ag_ui.TextMessageContentEvent>());
        expect(events[3], isA<ag_ui.TextMessageContentEvent>());
        expect(events[4], isA<ag_ui.TextMessageEndEvent>());

        thread.dispose();
      },
    );
  });
}
