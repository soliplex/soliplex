import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/protocol/completions_stream_parser.dart';

void main() {
  group('CompletionsStreamParser', () {
    late CompletionsStreamParser parser;

    setUp(() {
      parser = CompletionsStreamParser();
    });

    group('parseLine', () {
      test('parses a valid data line into CompletionChunk', () {
        const line =
            // ignore: lines_longer_than_80_chars (auto-documented)
            'data: {"id":"chatcmpl-123","choices":[{"index":0,"delta":{"content":"Hello"}}]}'; // ignore: lines_longer_than_80_chars
        final chunk = parser.parseLine(line);

        expect(chunk, isNotNull);
        expect(chunk!.id, 'chatcmpl-123');
        expect(chunk.choices.length, 1);
        expect(chunk.choices[0].delta.content, 'Hello');
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
        expect(parser.parseLine('some random text'), isNull);
      });

      test('returns null for malformed JSON', () {
        expect(parser.parseLine('data: {invalid json}'), isNull);
      });
    });

    group('parse stream', () {
      test('parses a stream of valid data lines', () async {
        final sseStream = Stream.fromIterable([
          // ignore: lines_longer_than_80_chars (auto-documented)
          'data: {"id":"1","choices":[{"index":0,"delta":{"content":"Hello"}}]}', // ignore: lines_longer_than_80_chars
          '', // Empty line should be ignored
          // ignore: lines_longer_than_80_chars (auto-documented)
          'data: {"id":"1","choices":[{"index":0,"delta":{"content":" world"}}]}', // ignore: lines_longer_than_80_chars
          'event: custom', // Non-data line ignored
          'data: [DONE]', // Termination marker
        ]);

        final chunks = await parser.parse(sseStream).toList();

        expect(chunks.length, 2);
        expect(chunks[0].id, '1');
        expect(chunks[0].choices[0].delta.content, 'Hello');
        expect(chunks[1].id, '1');
        expect(chunks[1].choices[0].delta.content, ' world');
      });

      test('handles errors in the upstream stream', () async {
        final sseStream = Stream<String>.error(Exception('Network error'));

        await expectLater(
          parser.parse(sseStream),
          emitsError(
            isA<Exception>().having(
              (e) => e.toString(),
              'toString',
              contains('Network error'),
            ),
          ),
        );
      });
    });
  });
}
