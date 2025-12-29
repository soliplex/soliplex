import 'dart:convert';

import 'package:equatable/equatable.dart';

/// Request body for OpenAI-compatible chat completions API.
class CompletionRequest {
  const CompletionRequest({
    required this.model,
    required this.messages,
    this.stream = true,
    this.temperature,
    this.maxTokens,
    this.stop,
  });
  final String model;
  final List<CompletionMessage> messages;
  final bool stream;
  final double? temperature;
  final int? maxTokens;
  final List<String>? stop;

  Map<String, dynamic> toJson() => {
    'model': model,
    'messages': messages.map((m) => m.toJson()).toList(),
    'stream': stream,
    if (temperature != null) 'temperature': temperature,
    if (maxTokens != null) 'max_tokens': maxTokens,
    if (stop != null) 'stop': stop,
  };

  String toJsonString() => jsonEncode(toJson());
}

/// A message in the completions format.
class CompletionMessage extends Equatable {
  const CompletionMessage({required this.role, required this.content});

  /// Create a user message.
  const CompletionMessage.user(String content)
    : this(role: 'user', content: content);

  /// Create an assistant message.
  const CompletionMessage.assistant(String content)
    : this(role: 'assistant', content: content);

  /// Create a system message.
  const CompletionMessage.system(String content)
    : this(role: 'system', content: content);

  factory CompletionMessage.fromJson(Map<String, dynamic> json) {
    return CompletionMessage(
      role: json['role'] as String,
      content: json['content'] as String,
    );
  }
  final String role;
  final String content;

  Map<String, dynamic> toJson() => {'role': role, 'content': content};

  @override
  List<Object?> get props => [role, content];
}

/// Non-streaming response from completions API.
class CompletionResponse extends Equatable {
  const CompletionResponse({
    required this.id,
    required this.model,
    required this.choices,
    this.usage,
  });

  factory CompletionResponse.fromJson(Map<String, dynamic> json) {
    return CompletionResponse(
      id: json['id'] as String,
      model: json['model'] as String,
      choices: (json['choices'] as List)
          .map((c) => Choice.fromJson(c as Map<String, dynamic>))
          .toList(),
      usage: json['usage'] != null
          ? Usage.fromJson(json['usage'] as Map<String, dynamic>)
          : null,
    );
  }
  final String id;
  final String model;
  final List<Choice> choices;
  final Usage? usage;

  @override
  List<Object?> get props => [id, model, choices, usage];
}

/// A choice in the completions response.
class Choice extends Equatable {
  const Choice({required this.index, required this.message, this.finishReason});

  factory Choice.fromJson(Map<String, dynamic> json) {
    return Choice(
      index: json['index'] as int,
      message: CompletionMessage.fromJson(
        json['message'] as Map<String, dynamic>,
      ),
      finishReason: json['finish_reason'] as String?,
    );
  }
  final int index;
  final CompletionMessage message;
  final String? finishReason;

  @override
  List<Object?> get props => [index, message, finishReason];
}

/// Token usage information.
class Usage extends Equatable {
  const Usage({
    required this.promptTokens,
    required this.completionTokens,
    required this.totalTokens,
  });

  factory Usage.fromJson(Map<String, dynamic> json) {
    return Usage(
      promptTokens: json['prompt_tokens'] as int,
      completionTokens: json['completion_tokens'] as int,
      totalTokens: json['total_tokens'] as int,
    );
  }
  final int promptTokens;
  final int completionTokens;
  final int totalTokens;

  @override
  List<Object?> get props => [promptTokens, completionTokens, totalTokens];
}

/// A streaming chunk from the completions API.
class CompletionChunk extends Equatable {
  const CompletionChunk({required this.id, required this.choices, this.model});

  factory CompletionChunk.fromJson(Map<String, dynamic> json) {
    return CompletionChunk(
      id: json['id'] as String,
      model: json['model'] as String?,
      choices: (json['choices'] as List)
          .map((c) => ChunkChoice.fromJson(c as Map<String, dynamic>))
          .toList(),
    );
  }
  final String id;
  final String? model;
  final List<ChunkChoice> choices;

  @override
  List<Object?> get props => [id, model, choices];
}

/// A choice in a streaming chunk.
class ChunkChoice extends Equatable {
  const ChunkChoice({
    required this.index,
    required this.delta,
    this.finishReason,
  });

  factory ChunkChoice.fromJson(Map<String, dynamic> json) {
    final deltaJson = json['delta'];
    return ChunkChoice(
      index: json['index'] as int,
      delta: Delta.fromJson(
        deltaJson is Map<String, dynamic>
            ? deltaJson
            : Map<String, dynamic>.from(deltaJson as Map),
      ),
      finishReason: json['finish_reason'] as String?,
    );
  }
  final int index;
  final Delta delta;
  final String? finishReason;

  @override
  List<Object?> get props => [index, delta, finishReason];
}

/// Delta content in a streaming chunk.
class Delta extends Equatable {
  const Delta({this.role, this.content});

  factory Delta.fromJson(Map<String, dynamic> json) {
    return Delta(
      role: json['role'] as String?,
      content: json['content'] as String?,
    );
  }
  final String? role;
  final String? content;

  @override
  List<Object?> get props => [role, content];
}

/// Parser for SSE stream from completions API.
///
/// Parses lines like:
/// ```dart
/// data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"Hello"}}]}
///
/// data: DONE
/// ```
class CompletionsStreamParser {
  /// Parse a stream of SSE lines into CompletionChunk objects.
  ///
  /// Filters out empty lines and DONE markers.
  Stream<CompletionChunk> parse(Stream<String> sseLines) async* {
    await for (final line in sseLines) {
      final chunk = parseLine(line);
      if (chunk != null) {
        yield chunk;
      }
    }
  }

  /// Parse a single SSE line.
  ///
  /// Returns null for empty lines, DONE markers, or unparseable lines.
  CompletionChunk? parseLine(String line) {
    // Skip empty lines
    if (line.trim().isEmpty) return null;

    // Handle data: prefix
    if (!line.startsWith('data: ')) return null;

    final data = line.substring(6); // Remove "data: " prefix

    // Skip DONE marker
    if (data == '[DONE]') return null;

    try {
      final json = jsonDecode(data) as Map<String, dynamic>;
      return CompletionChunk.fromJson(json);
    } on Object {
      // Skip unparseable lines
      return null;
    }
  }
}
