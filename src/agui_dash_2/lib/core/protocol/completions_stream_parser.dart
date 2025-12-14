import 'dart:async';
import 'dart:convert';

import '../utils/debug_log.dart';
import 'completions_models.dart';

/// Parses an OpenAI-compatible Server-Sent Events (SSE) stream
/// into [CompletionChunk] objects.
class CompletionsStreamParser {
  /// Parses a single SSE line into a [CompletionChunk].
  /// Returns null for empty lines, [DONE] messages, or malformed data.
  CompletionChunk? parseLine(String line) {
    line = line.trim();
    if (line.isEmpty) return null;

    if (line == 'data: [DONE]') {
      return null; // Stream termination
    }

    if (line.startsWith('data: ')) {
      final jsonString = line.substring(6);
      try {
        final Map<String, dynamic> json = jsonDecode(jsonString);
        return CompletionChunk.fromJson(json);
      } catch (e) {
        DebugLog.warn('CompletionsStreamParser: Failed to parse JSON: $e');
        return null;
      }
    }
    // Ignore non-data lines (e.g., comments, event types)
    return null;
  }

  /// Parses a stream of SSE lines into a stream of [CompletionChunk] objects.
  Stream<CompletionChunk> parse(Stream<String> sseStream) {
    return sseStream.transform(
      StreamTransformer.fromHandlers(
        handleData: (line, sink) {
          if (line.trim() == 'data: [DONE]') {
            sink.close();
            return;
          }
          final chunk = parseLine(line);
          if (chunk != null) {
            sink.add(chunk);
          }
        },
        handleError: (error, stackTrace, sink) {
          DebugLog.error('CompletionsStreamParser: Stream error: $error');
          sink.addError(error, stackTrace);
        },
        handleDone: (sink) {
          DebugLog.service('CompletionsStreamParser: Stream done.');
          sink.close();
        },
      ),
    );
  }
}
