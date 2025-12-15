import 'package:fake_async/fake_async.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/services/tool_execution_service.dart';

void main() {
  group('ToolExecutionNotifier', () {
    late ToolExecutionNotifier notifier;

    setUp(() {
      notifier = ToolExecutionNotifier(
        serverId: 'test-server',
        roomId: 'test-room',
      );
    });

    tearDown(() {
      notifier.dispose();
    });

    group('startExecution', () {
      test('adds tool to active executions', () {
        notifier.startExecution('call-1', 'test_tool');

        expect(notifier.state.hasActiveExecutions, isTrue);
        expect(notifier.state.activeCount, equals(1));
        expect(notifier.state.activeToolNames, contains('test_tool'));
      });

      test('tracks multiple concurrent tool executions', () {
        notifier.startExecution('call-1', 'tool_a');
        notifier.startExecution('call-2', 'tool_b');
        notifier.startExecution('call-3', 'tool_c');

        expect(notifier.state.activeCount, equals(3));
        expect(
          notifier.state.activeToolNames,
          containsAll(['tool_a', 'tool_b', 'tool_c']),
        );
      });

      test('records execution start time', () {
        final before = DateTime.now();
        notifier.startExecution('call-1', 'test_tool');
        final after = DateTime.now();

        final execution = notifier.getExecution('call-1');
        expect(execution, isNotNull);
        expect(
          execution!.startedAt.isAfter(
            before.subtract(const Duration(seconds: 1)),
          ),
          isTrue,
        );
        expect(
          execution.startedAt.isBefore(after.add(const Duration(seconds: 1))),
          isTrue,
        );
      });

      test('stores tool arguments', () {
        notifier.startExecution(
          'call-1',
          'test_tool',
          args: {'key': 'value', 'count': 42},
        );

        final execution = notifier.getExecution('call-1');
        expect(execution?.args, equals({'key': 'value', 'count': 42}));
      });
    });

    group('endExecution', () {
      test('removes tool from active executions', () {
        notifier.startExecution('call-1', 'test_tool');
        expect(notifier.state.hasActiveExecutions, isTrue);

        notifier.endExecution('call-1');
        expect(notifier.state.hasActiveExecutions, isFalse);
      });

      test('only removes specified tool call', () {
        notifier.startExecution('call-1', 'tool_a');
        notifier.startExecution('call-2', 'tool_b');

        notifier.endExecution('call-1');

        expect(notifier.state.activeCount, equals(1));
        expect(notifier.state.activeToolNames, equals(['tool_b']));
      });

      test('handles non-existent tool call gracefully', () {
        notifier.endExecution('non-existent');
        expect(notifier.state.hasActiveExecutions, isFalse);
      });
    });

    group('clearAll', () {
      test('removes all active executions', () {
        notifier.startExecution('call-1', 'tool_a');
        notifier.startExecution('call-2', 'tool_b');
        notifier.startExecution('call-3', 'tool_c');

        notifier.clearAll();

        expect(notifier.state.hasActiveExecutions, isFalse);
        expect(notifier.state.activeCount, equals(0));
      });
    });

    group('isExecuting', () {
      test('returns true for active tool call', () {
        notifier.startExecution('call-1', 'test_tool');
        expect(notifier.isExecuting('call-1'), isTrue);
      });

      test('returns false for inactive tool call', () {
        expect(notifier.isExecuting('call-1'), isFalse);
      });

      test('returns false after tool completes', () {
        notifier.startExecution('call-1', 'test_tool');
        notifier.endExecution('call-1');
        expect(notifier.isExecuting('call-1'), isFalse);
      });
    });

    group('timeout behavior', () {
      test('auto-clears execution after 60 seconds', () {
        fakeAsync((async) {
          final notifier = ToolExecutionNotifier(
            serverId: 'test-server',
            roomId: 'test-room',
          );

          notifier.startExecution('call-1', 'test_tool');
          expect(notifier.state.hasActiveExecutions, isTrue);

          // Advance time by 59 seconds - should still be active
          async.elapse(const Duration(seconds: 59));
          expect(notifier.state.hasActiveExecutions, isTrue);

          // Advance by 2 more seconds (total 61s) - should be cleared
          async.elapse(const Duration(seconds: 2));
          expect(notifier.state.hasActiveExecutions, isFalse);

          notifier.dispose();
        });
      });

      test('cancels timeout when execution completes normally', () {
        fakeAsync((async) {
          final notifier = ToolExecutionNotifier(
            serverId: 'test-server',
            roomId: 'test-room',
          );

          notifier.startExecution('call-1', 'test_tool');
          notifier.endExecution('call-1');

          // Advance past timeout - should not throw or cause issues
          async.elapse(const Duration(seconds: 120));

          // State should still be empty (no phantom re-clearing)
          expect(notifier.state.hasActiveExecutions, isFalse);

          notifier.dispose();
        });
      });

      test('each tool call has independent timeout', () {
        fakeAsync((async) {
          final notifier = ToolExecutionNotifier(
            serverId: 'test-server',
            roomId: 'test-room',
          );

          notifier.startExecution('call-1', 'tool_a');
          async.elapse(const Duration(seconds: 30));
          notifier.startExecution('call-2', 'tool_b');

          // After 31 more seconds (61 total for call-1)
          async.elapse(const Duration(seconds: 31));
          expect(notifier.isExecuting('call-1'), isFalse);
          expect(notifier.isExecuting('call-2'), isTrue);

          // After 30 more seconds (61 total for call-2)
          async.elapse(const Duration(seconds: 30));
          expect(notifier.isExecuting('call-2'), isFalse);

          notifier.dispose();
        });
      });
    });
  });

  group('ToolExecutionState', () {
    test('hasActiveExecutions returns false when empty', () {
      const state = ToolExecutionState();
      expect(state.hasActiveExecutions, isFalse);
    });

    test('activeToolNames returns list of tool names', () {
      final state = ToolExecutionState(
        activeExecutions: {
          'call-1': ActiveToolExecution(
            toolCallId: 'call-1',
            toolName: 'tool_a',
            startedAt: DateTime.now(),
          ),
          'call-2': ActiveToolExecution(
            toolCallId: 'call-2',
            toolName: 'tool_b',
            startedAt: DateTime.now(),
          ),
        },
      );

      expect(state.activeToolNames, containsAll(['tool_a', 'tool_b']));
    });
  });

  group('ActiveToolExecution', () {
    test('elapsed returns duration since start', () async {
      final startTime = DateTime.now();
      final execution = ActiveToolExecution(
        toolCallId: 'call-1',
        toolName: 'test_tool',
        startedAt: startTime,
      );

      await Future<void>.delayed(const Duration(milliseconds: 50));

      expect(execution.elapsed.inMilliseconds, greaterThanOrEqualTo(40));
    });
  });
}
