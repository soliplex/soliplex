import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/chat/unified_message.dart';

void main() {
  group('MessageRole', () {
    test('has all expected values', () {
      expect(
        MessageRole.values,
        containsAll([
          MessageRole.user,
          MessageRole.assistant,
          MessageRole.system,
          MessageRole.tool,
        ]),
      );
    });
  });

  group('ToolCallStatus', () {
    test('has all expected values', () {
      expect(
        ToolCallStatus.values,
        containsAll([
          ToolCallStatus.pending,
          ToolCallStatus.running,
          ToolCallStatus.completed,
          ToolCallStatus.failed,
        ]),
      );
    });
  });

  group('TextMessage', () {
    test('creates with required fields', () {
      final msg = TextMessage(
        id: 'msg-1',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      expect(msg.id, 'msg-1');
      expect(msg.role, MessageRole.user);
      expect(msg.content, 'Hello');
      expect(msg.isComplete, isTrue);
      expect(msg.isStreaming, isFalse);
    });

    test('appendContent creates new message with appended text', () {
      final msg = TextMessage(
        id: 'msg-1',
        role: MessageRole.assistant,
        timestamp: DateTime(2025),
        content: 'Hello',
        isStreaming: true,
      );

      final updated = msg.appendContent(' world');

      expect(updated.content, 'Hello world');
      expect(updated.id, msg.id);
      expect(updated.isStreaming, isTrue);
    });

    test('finalize marks message as complete', () {
      final msg = TextMessage(
        id: 'msg-1',
        role: MessageRole.assistant,
        timestamp: DateTime(2025),
        content: 'Hello',
        isComplete: false,
        isStreaming: true,
      );

      final finalized = msg.finalize();

      expect(finalized.isComplete, isTrue);
      expect(finalized.isStreaming, isFalse);
    });

    test('equality works correctly', () {
      final msg1 = TextMessage(
        id: 'msg-1',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      final msg2 = TextMessage(
        id: 'msg-1',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      final msg3 = TextMessage(
        id: 'msg-2',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      expect(msg1, equals(msg2));
      expect(msg1, isNot(equals(msg3)));
    });
  });

  group('ThinkingMessage', () {
    test('creates with assistant role', () {
      final msg = ThinkingMessage(
        id: 'think-1',
        timestamp: DateTime(2025),
        content: 'Let me think...',
      );

      expect(msg.role, MessageRole.assistant);
      expect(msg.isFinalized, isFalse);
    });

    test('appendContent works correctly', () {
      final msg = ThinkingMessage(
        id: 'think-1',
        timestamp: DateTime(2025),
        content: 'Step 1',
      );

      final updated = msg.appendContent(', Step 2');

      expect(updated.content, 'Step 1, Step 2');
    });

    test('finalize marks as finalized', () {
      final msg = ThinkingMessage(
        id: 'think-1',
        timestamp: DateTime(2025),
        content: 'Done thinking',
        isStreaming: true,
      );

      final finalized = msg.finalize();

      expect(finalized.isFinalized, isTrue);
      expect(finalized.isStreaming, isFalse);
    });
  });

  group('ToolCallMessage', () {
    test('creates with tool role', () {
      final msg = ToolCallMessage(
        id: 'tool-1',
        timestamp: DateTime(2025),
        toolName: 'search',
        arguments: const {'query': 'flutter'},
      );

      expect(msg.role, MessageRole.tool);
      expect(msg.status, ToolCallStatus.pending);
      expect(msg.result, isNull);
    });

    test('copyWith updates status', () {
      final msg = ToolCallMessage(
        id: 'tool-1',
        timestamp: DateTime(2025),
        toolName: 'search',
        arguments: const {'query': 'flutter'},
      );

      final running = msg.copyWith(status: ToolCallStatus.running);
      expect(running.status, ToolCallStatus.running);

      final completed = running.copyWith(
        status: ToolCallStatus.completed,
        result: 'Found 10 results',
      );
      expect(completed.status, ToolCallStatus.completed);
      expect(completed.result, 'Found 10 results');
    });

    test('copyWith preserves other fields', () {
      final msg = ToolCallMessage(
        id: 'tool-1',
        timestamp: DateTime(2025),
        toolName: 'search',
        arguments: const {'query': 'flutter'},
      );

      final updated = msg.copyWith(status: ToolCallStatus.running);

      expect(updated.id, msg.id);
      expect(updated.toolName, msg.toolName);
      expect(updated.arguments, msg.arguments);
    });
  });

  group('ToolResultMessage', () {
    test('creates with tool role', () {
      final msg = ToolResultMessage(
        id: 'result-1',
        timestamp: DateTime(2025),
        toolCallId: 'tool-1',
        resultData: const {'count': 10},
      );

      expect(msg.role, MessageRole.tool);
      expect(msg.isSuccess, isTrue);
    });

    test('can represent failure', () {
      final msg = ToolResultMessage(
        id: 'result-1',
        timestamp: DateTime(2025),
        toolCallId: 'tool-1',
        resultData: null,
        isSuccess: false,
        error: 'Tool not found',
      );

      expect(msg.isSuccess, isFalse);
      expect(msg.error, 'Tool not found');
    });
  });

  group('SystemMessage', () {
    test('creates with system role', () {
      final msg = SystemMessage(
        id: 'sys-1',
        timestamp: DateTime(2025),
        content: 'You are a helpful assistant.',
      );

      expect(msg.role, MessageRole.system);
      expect(msg.content, 'You are a helpful assistant.');
    });
  });

  group('RichContentMessage', () {
    test('creates with content type and payload', () {
      final msg = RichContentMessage(
        id: 'rich-1',
        role: MessageRole.assistant,
        timestamp: DateTime(2025),
        contentType: 'canvas',
        payload: const {'width': 800, 'height': 600},
      );

      expect(msg.contentType, 'canvas');
      expect(msg.payload['width'], 800);
    });
  });

  group('UnifiedMessage pattern matching', () {
    test('can pattern match on message types', () {
      final messages = <UnifiedMessage>[
        TextMessage(
          id: '1',
          role: MessageRole.user,
          timestamp: DateTime(2025),
          content: 'Hello',
        ),
        ThinkingMessage(
          id: '2',
          timestamp: DateTime(2025),
          content: 'Thinking...',
        ),
        ToolCallMessage(
          id: '3',
          timestamp: DateTime(2025),
          toolName: 'search',
          arguments: const {},
        ),
      ];

      final types = messages.map((msg) {
        return switch (msg) {
          TextMessage _ => 'text',
          ThinkingMessage _ => 'thinking',
          ToolCallMessage _ => 'tool_call',
          ToolResultMessage _ => 'tool_result',
          SystemMessage _ => 'system',
          RichContentMessage _ => 'rich',
        };
      }).toList();

      expect(types, ['text', 'thinking', 'tool_call']);
    });

    test('can access type-specific fields in switch', () {
      final UnifiedMessage msg = TextMessage(
        id: '1',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      final content = switch (msg) {
        final TextMessage m => m.content,
        final ThinkingMessage m => m.content,
        final SystemMessage m => m.content,
        final ToolCallMessage m => m.toolName,
        ToolResultMessage _ => 'result',
        RichContentMessage _ => 'rich',
      };

      expect(content, 'Hello');
    });
  });

  group('copyWithStreaming', () {
    test('TextMessage copyWithStreaming', () {
      final msg = TextMessage(
        id: '1',
        role: MessageRole.user,
        timestamp: DateTime(2025),
        content: 'Hello',
      );

      final streaming = msg.copyWithStreaming(streaming: true);
      expect(streaming.isStreaming, isTrue);
      expect(streaming.content, 'Hello');
    });

    test('ThinkingMessage copyWithStreaming', () {
      final msg = ThinkingMessage(
        id: '1',
        timestamp: DateTime(2025),
        content: 'Thinking',
      );

      final streaming = msg.copyWithStreaming(streaming: true);
      expect(streaming.isStreaming, isTrue);
    });

    test('ToolCallMessage copyWithStreaming', () {
      final msg = ToolCallMessage(
        id: '1',
        timestamp: DateTime(2025),
        toolName: 'test',
        arguments: const {},
      );

      final streaming = msg.copyWithStreaming(streaming: true);
      expect(streaming.isStreaming, isTrue);
    });
  });
}
