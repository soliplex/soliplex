import 'package:ag_ui/ag_ui.dart' as ag_ui;
import 'package:soliplex_flutter/client/agui/tool_call_registry.dart';
import 'package:test/test.dart';

void main() {
  group('ToolCallRegistry', () {
    late ToolCallRegistry registry;

    setUp(() {
      registry = ToolCallRegistry();
    });

    ag_ui.ToolCall createToolCall(String id, String name) {
      return ag_ui.ToolCall(
        id: id,
        function: ag_ui.FunctionCall(name: name, arguments: '{}'),
      );
    }

    test('starts empty', () {
      expect(registry.pendingCalls, isEmpty);
      expect(registry.executingCalls, isEmpty);
      expect(registry.completedResults, isEmpty);
    });

    test('register adds to pending', () {
      final call = createToolCall('tc-1', 'test_tool');

      registry.register(call);

      expect(registry.isPending('tc-1'), isTrue);
      expect(registry.pendingCalls.length, 1);
    });

    test('tryStartExecution moves from pending to executing', () {
      final call = createToolCall('tc-1', 'test_tool');
      registry.register(call);

      final result = registry.tryStartExecution('tc-1');

      expect(result, isNotNull);
      expect(result!.id, 'tc-1');
      expect(registry.isPending('tc-1'), isFalse);
      expect(registry.isExecuting('tc-1'), isTrue);
    });

    test('tryStartExecution returns null if not pending', () {
      final result = registry.tryStartExecution('tc-1');

      expect(result, isNull);
    });

    test('tryStartExecution returns null if already executing', () {
      final call = createToolCall('tc-1', 'test_tool');
      registry.register(call);
      registry.tryStartExecution('tc-1');

      final result = registry.tryStartExecution('tc-1');

      expect(result, isNull);
    });

    test('markCompleted moves from executing to completed', () {
      final call = createToolCall('tc-1', 'test_tool');
      registry.register(call);
      registry.tryStartExecution('tc-1');

      const message = ag_ui.ToolMessage(
        id: 'msg-tc-1',
        toolCallId: 'tc-1',
        content: 'result',
      );
      registry.markCompleted('tc-1', message);

      expect(registry.isExecuting('tc-1'), isFalse);
      expect(registry.isCompleted('tc-1'), isTrue);
      expect(registry.completedResults.length, 1);
    });

    test('markFailed moves from executing to failed', () {
      final call = createToolCall('tc-1', 'test_tool');
      registry.register(call);
      registry.tryStartExecution('tc-1');

      registry.markFailed('tc-1', 'error message');

      expect(registry.isExecuting('tc-1'), isFalse);
      expect(registry.isFailed('tc-1'), isTrue);
    });

    test('clear resets all state', () {
      final call = createToolCall('tc-1', 'test_tool');
      registry.register(call);

      registry.clear();

      expect(registry.pendingCalls, isEmpty);
      expect(registry.isPending('tc-1'), isFalse);
    });
  });
}
