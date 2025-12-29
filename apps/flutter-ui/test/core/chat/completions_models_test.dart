import 'package:flutter_test/flutter_test.dart';

import 'package:soliplex/core/chat/completions_models.dart';

void main() {
  group('CompletionMessage', () {
    test('creates user message', () {
      const msg = CompletionMessage.user('Hello');
      expect(msg.role, 'user');
      expect(msg.content, 'Hello');
    });

    test('creates assistant message', () {
      const msg = CompletionMessage.assistant('Hi there');
      expect(msg.role, 'assistant');
      expect(msg.content, 'Hi there');
    });

    test('creates system message', () {
      const msg = CompletionMessage.system('You are helpful');
      expect(msg.role, 'system');
      expect(msg.content, 'You are helpful');
    });

    test('serializes to JSON', () {
      const msg = CompletionMessage.user('Hello');
      expect(msg.toJson(), {'role': 'user', 'content': 'Hello'});
    });

    test('deserializes from JSON', () {
      final msg = CompletionMessage.fromJson(const {
        'role': 'assistant',
        'content': 'Response',
      });
      expect(msg.role, 'assistant');
      expect(msg.content, 'Response');
    });
  });

  group('CompletionRequest', () {
    test('creates minimal request', () {
      const request = CompletionRequest(
        model: 'gpt-4',
        messages: [CompletionMessage.user('Hello')],
      );

      expect(request.model, 'gpt-4');
      expect(request.messages.length, 1);
      expect(request.stream, isTrue);
    });

    test('serializes to JSON', () {
      const request = CompletionRequest(
        model: 'gpt-4',
        messages: [CompletionMessage.user('Hello')],
        temperature: 0.7,
        maxTokens: 100,
      );

      final json = request.toJson();
      expect(json['model'], 'gpt-4');
      expect(json['stream'], isTrue);
      expect(json['temperature'], 0.7);
      expect(json['max_tokens'], 100);
      expect(json['messages'], [
        {'role': 'user', 'content': 'Hello'},
      ]);
    });

    test('omits null optional fields', () {
      const request = CompletionRequest(
        model: 'gpt-4',
        messages: [CompletionMessage.user('Hello')],
      );

      final json = request.toJson();
      expect(json.containsKey('temperature'), isFalse);
      expect(json.containsKey('max_tokens'), isFalse);
      expect(json.containsKey('stop'), isFalse);
    });
  });

  group('CompletionResponse', () {
    test('deserializes from JSON', () {
      final response = CompletionResponse.fromJson(const {
        'id': 'chatcmpl-123',
        'model': 'gpt-4',
        'choices': [
          {
            'index': 0,
            'message': {'role': 'assistant', 'content': 'Hello!'},
            'finish_reason': 'stop',
          },
        ],
        'usage': {
          'prompt_tokens': 10,
          'completion_tokens': 5,
          'total_tokens': 15,
        },
      });

      expect(response.id, 'chatcmpl-123');
      expect(response.model, 'gpt-4');
      expect(response.choices.length, 1);
      expect(response.choices[0].message.content, 'Hello!');
      expect(response.usage?.totalTokens, 15);
    });
  });

  group('CompletionChunk', () {
    test('deserializes from JSON', () {
      final chunk = CompletionChunk.fromJson(const {
        'id': 'chatcmpl-123',
        'model': 'gpt-4',
        'choices': [
          {
            'index': 0,
            'delta': {'content': 'Hello'},
            'finish_reason': null,
          },
        ],
      });

      expect(chunk.id, 'chatcmpl-123');
      expect(chunk.choices.length, 1);
      expect(chunk.choices[0].delta.content, 'Hello');
      expect(chunk.choices[0].finishReason, isNull);
    });

    test('handles finish_reason', () {
      final chunk = CompletionChunk.fromJson(const {
        'id': 'chatcmpl-123',
        'choices': [
          {'index': 0, 'delta': {}, 'finish_reason': 'stop'},
        ],
      });

      expect(chunk.choices[0].finishReason, 'stop');
      expect(chunk.choices[0].delta.content, isNull);
    });
  });

  group('CompletionsStreamParser', () {
    final parser = CompletionsStreamParser();

    test('parses data line', () {
      final chunk = parser.parseLine(
        // ignore: lines_longer_than_80_chars (auto-documented)
        'data: {"id":"chatcmpl-123","choices":[{"index":0,"delta":{"content":"Hi"}}]}', // ignore: lines_longer_than_80_chars
      );

      expect(chunk, isNotNull);
      expect(chunk!.id, 'chatcmpl-123');
      expect(chunk.choices[0].delta.content, 'Hi');
    });

    test('returns null for empty line', () {
      expect(parser.parseLine(''), isNull);
      expect(parser.parseLine('   '), isNull);
    });

    test('returns null for [DONE] marker', () {
      expect(parser.parseLine('data: [DONE]'), isNull);
    });

    test('returns null for non-data lines', () {
      expect(parser.parseLine('event: message'), isNull);
      expect(parser.parseLine(': comment'), isNull);
    });

    test('returns null for invalid JSON', () {
      expect(parser.parseLine('data: {invalid json}'), isNull);
    });

    test('parses stream of lines', () async {
      final lines = Stream.fromIterable([
        'data: {"id":"1","choices":[{"index":0,"delta":{"content":"Hello"}}]}',
        '',
        'data: {"id":"1","choices":[{"index":0,"delta":{"content":" world"}}]}',
        'data: [DONE]',
      ]);

      final chunks = await parser.parse(lines).toList();

      expect(chunks.length, 2);
      expect(chunks[0].choices[0].delta.content, 'Hello');
      expect(chunks[1].choices[0].delta.content, ' world');
    });
  });

  group('Delta', () {
    test('deserializes with content', () {
      final delta = Delta.fromJson(const {'content': 'Hello'});
      expect(delta.content, 'Hello');
      expect(delta.role, isNull);
    });

    test('deserializes with role', () {
      final delta = Delta.fromJson(const {'role': 'assistant'});
      expect(delta.role, 'assistant');
      expect(delta.content, isNull);
    });

    test('deserializes empty', () {
      final delta = Delta.fromJson(const {});
      expect(delta.role, isNull);
      expect(delta.content, isNull);
    });
  });

  group('Usage', () {
    test('deserializes from JSON', () {
      final usage = Usage.fromJson(const {
        'prompt_tokens': 10,
        'completion_tokens': 20,
        'total_tokens': 30,
      });

      expect(usage.promptTokens, 10);
      expect(usage.completionTokens, 20);
      expect(usage.totalTokens, 30);
    });
  });
}
