import 'dart:async';

import 'package:soliplex_client/src/agui/tool_registry.dart';
import 'package:soliplex_client/src/models/chat_message.dart';
import 'package:test/test.dart';

void main() {
  group('ToolRegistry', () {
    late ToolRegistry registry;

    setUp(() {
      registry = ToolRegistry();
    });

    group('initial state', () {
      test('count is 0', () {
        expect(registry.count, equals(0));
      });

      test('registeredTools is empty', () {
        expect(registry.registeredTools, isEmpty);
      });
    });

    group('register', () {
      test('registers a tool', () {
        registry.register(
          name: 'test_tool',
          executor: (_) async => 'result',
        );

        expect(registry.count, equals(1));
        expect(registry.isRegistered('test_tool'), isTrue);
      });

      test('registers multiple tools', () {
        registry
          ..register(name: 'tool1', executor: (_) async => '1')
          ..register(name: 'tool2', executor: (_) async => '2')
          ..register(name: 'tool3', executor: (_) async => '3');

        expect(registry.count, equals(3));
        expect(
          registry.registeredTools,
          containsAll(['tool1', 'tool2', 'tool3']),
        );
      });

      test('registers with fireAndForget', () {
        registry.register(
          name: 'fire_tool',
          executor: (_) async => 'result',
          fireAndForget: true,
        );

        expect(registry.isFireAndForget('fire_tool'), isTrue);
      });

      test('registers with description', () {
        registry.register(
          name: 'described_tool',
          executor: (_) async => 'result',
          description: 'A test tool',
        );

        final info = registry.getToolInfo('described_tool');
        expect(info?.description, equals('A test tool'));
      });

      test('throws when tool already registered', () {
        registry.register(name: 'test_tool', executor: (_) async => 'result');

        expect(
          () => registry.register(
            name: 'test_tool',
            executor: (_) async => 'different',
          ),
          throwsArgumentError,
        );
      });
    });

    group('unregister', () {
      test('removes registered tool', () {
        registry.register(name: 'test_tool', executor: (_) async => 'result');

        final removed = registry.unregister('test_tool');

        expect(removed, isTrue);
        expect(registry.count, equals(0));
        expect(registry.isRegistered('test_tool'), isFalse);
      });

      test('returns false for unknown tool', () {
        final removed = registry.unregister('unknown');

        expect(removed, isFalse);
      });

      test('allows re-registration after unregister', () {
        registry
          ..register(name: 'test_tool', executor: (_) async => 'first')
          ..unregister('test_tool')
          // Should not throw
          ..register(name: 'test_tool', executor: (_) async => 'second');

        expect(registry.isRegistered('test_tool'), isTrue);
      });
    });

    group('isRegistered', () {
      test('returns true for registered tool', () {
        registry.register(name: 'test_tool', executor: (_) async => 'result');

        expect(registry.isRegistered('test_tool'), isTrue);
      });

      test('returns false for unknown tool', () {
        expect(registry.isRegistered('unknown'), isFalse);
      });
    });

    group('isFireAndForget', () {
      test('returns true for fire-and-forget tool', () {
        registry.register(
          name: 'fire_tool',
          executor: (_) async => 'result',
          fireAndForget: true,
        );

        expect(registry.isFireAndForget('fire_tool'), isTrue);
      });

      test('returns false for regular tool', () {
        registry.register(
          name: 'regular_tool',
          executor: (_) async => 'result',
        );

        expect(registry.isFireAndForget('regular_tool'), isFalse);
      });

      test('returns false for unknown tool', () {
        expect(registry.isFireAndForget('unknown'), isFalse);
      });
    });

    group('getToolInfo', () {
      test('returns tool info for registered tool', () {
        registry.register(
          name: 'test_tool',
          executor: (_) async => 'result',
          fireAndForget: true,
          description: 'A test tool',
        );

        final info = registry.getToolInfo('test_tool');

        expect(info, isNotNull);
        expect(info!.name, equals('test_tool'));
        expect(info.fireAndForget, isTrue);
        expect(info.description, equals('A test tool'));
      });

      test('returns null for unknown tool', () {
        final info = registry.getToolInfo('unknown');

        expect(info, isNull);
      });
    });

    group('execute', () {
      test('executes tool and returns result', () async {
        registry.register(
          name: 'calculator',
          executor: (call) async {
            expect(call.name, equals('calculator'));
            expect(call.arguments, equals('{"a": 1, "b": 2}'));
            return '3';
          },
        );

        const toolCall = ToolCallInfo(
          id: 'tc-1',
          name: 'calculator',
          arguments: '{"a": 1, "b": 2}',
        );

        final result = await registry.execute(toolCall);

        expect(result, equals('3'));
      });

      test('returns null for unknown tool', () async {
        const toolCall = ToolCallInfo(
          id: 'tc-1',
          name: 'unknown',
        );

        final result = await registry.execute(toolCall);

        expect(result, isNull);
      });

      test('returns null for fire-and-forget tool', () async {
        var executed = false;
        registry.register(
          name: 'fire_tool',
          executor: (_) async {
            executed = true;
            return 'result';
          },
          fireAndForget: true,
        );

        const toolCall = ToolCallInfo(id: 'tc-1', name: 'fire_tool');

        final result = await registry.execute(toolCall);

        expect(result, isNull);
        // Wait a bit for async execution
        await Future<void>.delayed(const Duration(milliseconds: 10));
        expect(executed, isTrue);
      });

      test('propagates executor exceptions', () async {
        registry.register(
          name: 'failing_tool',
          executor: (_) async => throw Exception('Tool failed'),
        );

        const toolCall = ToolCallInfo(id: 'tc-1', name: 'failing_tool');

        expect(
          () => registry.execute(toolCall),
          throwsException,
        );
      });

      test('passes tool call info to executor', () async {
        ToolCallInfo? receivedCall;
        registry.register(
          name: 'test_tool',
          executor: (call) async {
            receivedCall = call;
            return 'done';
          },
        );

        const toolCall = ToolCallInfo(
          id: 'tc-123',
          name: 'test_tool',
          arguments: '{"key": "value"}',
          status: ToolCallStatus.executing,
        );

        await registry.execute(toolCall);

        expect(receivedCall, isNotNull);
        expect(receivedCall!.id, equals('tc-123'));
        expect(receivedCall!.name, equals('test_tool'));
        expect(receivedCall!.arguments, equals('{"key": "value"}'));
      });
    });

    group('executeOrDefault', () {
      test('executes tool and returns result', () async {
        registry.register(
          name: 'test_tool',
          executor: (_) async => 'success',
        );

        const toolCall = ToolCallInfo(id: 'tc-1', name: 'test_tool');

        final result = await registry.executeOrDefault(toolCall);

        expect(result, equals('success'));
      });

      test('returns default for unknown tool', () async {
        const toolCall = ToolCallInfo(id: 'tc-1', name: 'unknown');

        final result = await registry.executeOrDefault(toolCall);

        expect(result, equals('Tool not found'));
      });

      test('returns custom default for unknown tool', () async {
        const toolCall = ToolCallInfo(id: 'tc-1', name: 'unknown');

        final result = await registry.executeOrDefault(
          toolCall,
          defaultResult: 'Custom error',
        );

        expect(result, equals('Custom error'));
      });

      test('returns null for fire-and-forget tool', () async {
        registry.register(
          name: 'fire_tool',
          executor: (_) async => 'result',
          fireAndForget: true,
        );

        const toolCall = ToolCallInfo(id: 'tc-1', name: 'fire_tool');

        final result = await registry.executeOrDefault(toolCall);

        expect(result, isNull);
      });
    });

    group('clear', () {
      test('removes all tools', () {
        registry
          ..register(name: 'tool1', executor: (_) async => '1')
          ..register(name: 'tool2', executor: (_) async => '2')
          ..clear();

        expect(registry.count, equals(0));
        expect(registry.registeredTools, isEmpty);
      });

      test('can be called when empty', () {
        registry.clear();

        expect(registry.count, equals(0));
      });
    });

    group('RegisteredTool', () {
      test('const constructor works', () {
        const tool = RegisteredTool(
          name: 'test',
          executor: _dummyExecutor,
          fireAndForget: true,
          description: 'A test',
        );

        expect(tool.name, equals('test'));
        expect(tool.fireAndForget, isTrue);
        expect(tool.description, equals('A test'));
      });
    });

    group('concurrent execution', () {
      test('handles multiple concurrent executions', () async {
        var callCount = 0;
        registry.register(
          name: 'slow_tool',
          executor: (_) async {
            callCount++;
            await Future<void>.delayed(const Duration(milliseconds: 10));
            return 'result-$callCount';
          },
        );

        const toolCall = ToolCallInfo(id: 'tc-1', name: 'slow_tool');

        // Execute concurrently
        final results = await Future.wait([
          registry.execute(toolCall),
          registry.execute(toolCall),
          registry.execute(toolCall),
        ]);

        expect(results, hasLength(3));
        expect(callCount, equals(3));
      });
    });
  });
}

Future<String> _dummyExecutor(ToolCallInfo call) async => 'dummy';
