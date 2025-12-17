import 'package:soliplex_client/src/agui/tool_call_buffer.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:test/test.dart';

void main() {
  group('ToolCallBuffer', () {
    late ToolCallBuffer buffer;

    setUp(() {
      buffer = ToolCallBuffer();
    });

    group('initial state', () {
      test('activeCount is 0', () {
        expect(buffer.activeCount, equals(0));
      });

      test('hasActiveToolCalls is false', () {
        expect(buffer.hasActiveToolCalls, isFalse);
      });

      test('activeToolCallIds is empty', () {
        expect(buffer.activeToolCallIds, isEmpty);
      });

      test('allToolCalls is empty', () {
        expect(buffer.allToolCalls, isEmpty);
      });
    });

    group('startToolCall', () {
      test('tracks a new tool call', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        expect(buffer.activeCount, equals(1));
        expect(buffer.hasActiveToolCalls, isTrue);
        expect(buffer.activeToolCallIds, contains('tc-1'));
      });

      test('tracks multiple concurrent tool calls', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..startToolCall(callId: 'tc-2', name: 'calculate');

        expect(buffer.activeCount, equals(2));
        expect(buffer.activeToolCallIds, containsAll(['tc-1', 'tc-2']));
      });

      test('stores parentMessageId', () {
        buffer.startToolCall(
          callId: 'tc-1',
          name: 'search',
          parentMessageId: 'msg-123',
        );

        final toolCall = buffer.getToolCall('tc-1');
        expect(toolCall, isNotNull);
        // Note: parentMessageId is not exposed on ToolCallInfo
        // It's internal state for the buffer
      });

      test('throws when tool call already exists', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        expect(
          () => buffer.startToolCall(callId: 'tc-1', name: 'different'),
          throwsStateError,
        );
      });
    });

    group('appendArgs', () {
      test('appends arguments to tool call', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: '{"query":')
          ..appendArgs(callId: 'tc-1', delta: '"test"}');

        final toolCall = buffer.getToolCall('tc-1');
        expect(toolCall?.arguments, equals('{"query":"test"}'));
      });

      test('handles empty deltas', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: '')
          ..appendArgs(callId: 'tc-1', delta: 'content')
          ..appendArgs(callId: 'tc-1', delta: '');

        final toolCall = buffer.getToolCall('tc-1');
        expect(toolCall?.arguments, equals('content'));
      });

      test('appends to correct tool call when multiple active', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..startToolCall(callId: 'tc-2', name: 'calculate')
          ..appendArgs(callId: 'tc-1', delta: 'args-1')
          ..appendArgs(callId: 'tc-2', delta: 'args-2');

        expect(buffer.getToolCall('tc-1')?.arguments, equals('args-1'));
        expect(buffer.getToolCall('tc-2')?.arguments, equals('args-2'));
      });

      test('throws when tool call not found', () {
        expect(
          () => buffer.appendArgs(callId: 'tc-unknown', delta: 'args'),
          throwsStateError,
        );
      });

      test('throws when tool call already complete', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..completeToolCall(callId: 'tc-1');

        expect(
          () => buffer.appendArgs(callId: 'tc-1', delta: 'more'),
          throwsStateError,
        );
      });
    });

    group('completeToolCall', () {
      test('returns ToolCallInfo with accumulated arguments', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: '{"query": "test"}');

        final toolCall = buffer.completeToolCall(callId: 'tc-1');

        expect(toolCall.id, equals('tc-1'));
        expect(toolCall.name, equals('search'));
        expect(toolCall.arguments, equals('{"query": "test"}'));
        expect(toolCall.status, equals(ToolCallStatus.pending));
        expect(toolCall.startedAt, isNotNull);
        expect(toolCall.completedAt, isNotNull);
      });

      test('marks tool call as complete', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        expect(buffer.isComplete('tc-1'), isFalse);

        buffer.completeToolCall(callId: 'tc-1');

        expect(buffer.isComplete('tc-1'), isTrue);
      });

      test('keeps tool call in buffer after completion', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..completeToolCall(callId: 'tc-1');

        expect(buffer.isActive('tc-1'), isTrue);
        expect(buffer.activeCount, equals(1));
      });

      test('throws when tool call not found', () {
        expect(
          () => buffer.completeToolCall(callId: 'tc-unknown'),
          throwsStateError,
        );
      });
    });

    group('setResult', () {
      test('sets result and returns updated ToolCallInfo', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: '{"query": "test"}')
          ..completeToolCall(callId: 'tc-1');

        final toolCall = buffer.setResult(
          callId: 'tc-1',
          result: 'Search results here',
        );

        expect(toolCall.id, equals('tc-1'));
        expect(toolCall.result, equals('Search results here'));
        expect(toolCall.status, equals(ToolCallStatus.completed));
      });

      test('hasResult returns true after setting result', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..completeToolCall(callId: 'tc-1');

        expect(buffer.hasResult('tc-1'), isFalse);

        buffer.setResult(callId: 'tc-1', result: 'result');

        expect(buffer.hasResult('tc-1'), isTrue);
      });

      test('can set result before completeToolCall', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        // In some cases, result may arrive before TOOL_CALL_END
        final toolCall = buffer.setResult(
          callId: 'tc-1',
          result: 'Early result',
        );

        expect(toolCall.result, equals('Early result'));
      });

      test('throws when tool call not found', () {
        expect(
          () => buffer.setResult(callId: 'tc-unknown', result: 'result'),
          throwsStateError,
        );
      });
    });

    group('getToolCall', () {
      test('returns tool call info', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: 'args');

        final toolCall = buffer.getToolCall('tc-1');

        expect(toolCall, isNotNull);
        expect(toolCall!.id, equals('tc-1'));
        expect(toolCall.name, equals('search'));
        expect(toolCall.arguments, equals('args'));
      });

      test('returns null for unknown tool call', () {
        final toolCall = buffer.getToolCall('tc-unknown');

        expect(toolCall, isNull);
      });

      test('reflects current state', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        var toolCall = buffer.getToolCall('tc-1');
        expect(toolCall?.arguments, isEmpty);
        expect(toolCall?.result, isNull);

        buffer.appendArgs(callId: 'tc-1', delta: 'args');
        toolCall = buffer.getToolCall('tc-1');
        expect(toolCall?.arguments, equals('args'));

        buffer
          ..completeToolCall(callId: 'tc-1')
          ..setResult(callId: 'tc-1', result: 'done');
        toolCall = buffer.getToolCall('tc-1');
        expect(toolCall?.result, equals('done'));
      });
    });

    group('allToolCalls', () {
      test('returns all active tool calls', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..startToolCall(callId: 'tc-2', name: 'calculate');

        final toolCalls = buffer.allToolCalls;

        expect(toolCalls, hasLength(2));
        expect(toolCalls.map((t) => t.id), containsAll(['tc-1', 'tc-2']));
      });

      test('returns empty list when no tool calls', () {
        expect(buffer.allToolCalls, isEmpty);
      });
    });

    group('removeToolCall', () {
      test('removes and returns tool call', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..appendArgs(callId: 'tc-1', delta: 'args')
          ..completeToolCall(callId: 'tc-1')
          ..setResult(callId: 'tc-1', result: 'result');

        final removed = buffer.removeToolCall('tc-1');

        expect(removed, isNotNull);
        expect(removed!.id, equals('tc-1'));
        expect(removed.arguments, equals('args'));
        expect(removed.result, equals('result'));

        expect(buffer.activeCount, equals(0));
        expect(buffer.isActive('tc-1'), isFalse);
      });

      test('returns null for unknown tool call', () {
        final removed = buffer.removeToolCall('tc-unknown');

        expect(removed, isNull);
      });
    });

    group('isActive', () {
      test('returns true for active tool call', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        expect(buffer.isActive('tc-1'), isTrue);
      });

      test('returns false for unknown tool call', () {
        expect(buffer.isActive('tc-unknown'), isFalse);
      });

      test('returns false after removal', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..removeToolCall('tc-1');

        expect(buffer.isActive('tc-1'), isFalse);
      });
    });

    group('isComplete', () {
      test('returns false before completeToolCall', () {
        buffer.startToolCall(callId: 'tc-1', name: 'search');

        expect(buffer.isComplete('tc-1'), isFalse);
      });

      test('returns true after completeToolCall', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..completeToolCall(callId: 'tc-1');

        expect(buffer.isComplete('tc-1'), isTrue);
      });

      test('returns false for unknown tool call', () {
        expect(buffer.isComplete('tc-unknown'), isFalse);
      });
    });

    group('hasResult', () {
      test('returns false before setResult', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..completeToolCall(callId: 'tc-1');

        expect(buffer.hasResult('tc-1'), isFalse);
      });

      test('returns true after setResult', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..setResult(callId: 'tc-1', result: 'result');

        expect(buffer.hasResult('tc-1'), isTrue);
      });

      test('returns false for unknown tool call', () {
        expect(buffer.hasResult('tc-unknown'), isFalse);
      });
    });

    group('reset', () {
      test('clears all tool calls', () {
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..startToolCall(callId: 'tc-2', name: 'calculate')
          ..reset();

        expect(buffer.activeCount, equals(0));
        expect(buffer.hasActiveToolCalls, isFalse);
        expect(buffer.allToolCalls, isEmpty);
      });

      test('can be called when empty', () {
        buffer.reset();

        expect(buffer.activeCount, equals(0));
      });
    });

    group('full lifecycle', () {
      test('handles complete tool call lifecycle', () {
        // Start
        buffer.startToolCall(callId: 'tc-1', name: 'search');
        expect(buffer.activeCount, equals(1));
        expect(buffer.isComplete('tc-1'), isFalse);

        // Stream arguments
        buffer
          ..appendArgs(callId: 'tc-1', delta: '{"query": "')
          ..appendArgs(callId: 'tc-1', delta: 'test')
          ..appendArgs(callId: 'tc-1', delta: '"}');
        expect(buffer.getToolCall('tc-1')?.arguments, '{"query": "test"}');

        // Complete arguments
        final completed = buffer.completeToolCall(callId: 'tc-1');
        expect(completed.status, equals(ToolCallStatus.pending));
        expect(buffer.isComplete('tc-1'), isTrue);

        // Get result
        final withResult = buffer.setResult(
          callId: 'tc-1',
          result: 'Found 10 results',
        );
        expect(withResult.status, equals(ToolCallStatus.completed));
        expect(buffer.hasResult('tc-1'), isTrue);

        // Cleanup
        final removed = buffer.removeToolCall('tc-1');
        expect(removed?.result, equals('Found 10 results'));
        expect(buffer.activeCount, equals(0));
      });

      test('handles multiple concurrent tool calls', () {
        // Start multiple tool calls
        buffer
          ..startToolCall(callId: 'tc-1', name: 'search')
          ..startToolCall(callId: 'tc-2', name: 'calculate')
          ..startToolCall(callId: 'tc-3', name: 'fetch');

        expect(buffer.activeCount, equals(3));

        // Interleave argument streaming
        buffer
          ..appendArgs(callId: 'tc-1', delta: 'search-args')
          ..appendArgs(callId: 'tc-2', delta: 'calc-')
          ..appendArgs(callId: 'tc-2', delta: 'args')
          ..appendArgs(callId: 'tc-3', delta: 'fetch-args')
          // Complete in different order
          ..completeToolCall(callId: 'tc-2')
          ..completeToolCall(callId: 'tc-1')
          ..completeToolCall(callId: 'tc-3')
          // Results in different order
          ..setResult(callId: 'tc-3', result: 'fetch-result')
          ..setResult(callId: 'tc-1', result: 'search-result')
          ..setResult(callId: 'tc-2', result: 'calc-result');

        // Verify all results
        expect(buffer.getToolCall('tc-1')?.result, equals('search-result'));
        expect(buffer.getToolCall('tc-2')?.result, equals('calc-result'));
        expect(buffer.getToolCall('tc-3')?.result, equals('fetch-result'));
      });
    });
  });

  group('ToolCallBufferSnapshot', () {
    test('captures buffer state', () {
      final buffer = ToolCallBuffer()
        ..startToolCall(callId: 'tc-1', name: 'search')
        ..appendArgs(callId: 'tc-1', delta: 'args')
        ..startToolCall(callId: 'tc-2', name: 'calculate');

      final snapshot = ToolCallBufferSnapshot.fromBuffer(buffer);

      expect(snapshot.activeCount, equals(2));
      expect(snapshot.hasActiveToolCalls, isTrue);
      expect(snapshot.toolCalls, hasLength(2));
    });

    test('captures empty buffer state', () {
      final buffer = ToolCallBuffer();

      final snapshot = ToolCallBufferSnapshot.fromBuffer(buffer);

      expect(snapshot.activeCount, equals(0));
      expect(snapshot.hasActiveToolCalls, isFalse);
      expect(snapshot.toolCalls, isEmpty);
    });

    test('is independent of buffer changes', () {
      final buffer = ToolCallBuffer()
        ..startToolCall(callId: 'tc-1', name: 'search');

      final snapshot = ToolCallBufferSnapshot.fromBuffer(buffer);

      // Modify buffer
      buffer.startToolCall(callId: 'tc-2', name: 'calculate');

      // Snapshot should be unchanged
      expect(snapshot.activeCount, equals(1));
      expect(snapshot.toolCalls, hasLength(1));
    });

    test('const constructor works', () {
      const snapshot = ToolCallBufferSnapshot(
        activeCount: 2,
        toolCalls: [],
      );

      expect(snapshot.activeCount, equals(2));
      expect(snapshot.hasActiveToolCalls, isTrue);
    });
  });
}
