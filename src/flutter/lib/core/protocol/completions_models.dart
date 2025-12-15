import 'package:equatable/equatable.dart';

/// Represents a single message in an OpenAI-compatible chat completion request.
class CompletionMessage extends Equatable {
  const CompletionMessage({required this.role, required this.content});

  factory CompletionMessage.user(String content) =>
      CompletionMessage(role: 'user', content: content);
  factory CompletionMessage.assistant(String content) =>
      CompletionMessage(role: 'assistant', content: content);
  factory CompletionMessage.system(String content) =>
      CompletionMessage(role: 'system', content: content);

  factory CompletionMessage.fromJson(Map<String, dynamic> json) {
    return CompletionMessage(
      role: json['role'] as String,
      content: json['content'] as String,
    );
  }
  final String role; // "system", "user", "assistant"
  final String content;

  Map<String, dynamic> toJson() => {'role': role, 'content': content};

  @override
  List<Object?> get props => [role, content];
}

/// Represents an OpenAI-compatible chat completion request.
class CompletionRequest extends Equatable {
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

  Map<String, dynamic> toJson() {
    final json = <String, dynamic>{
      'model': model,
      'messages': messages.map((m) => m.toJson()).toList(),
      'stream': stream,
    };
    if (temperature != null) json['temperature'] = temperature;
    if (maxTokens != null) json['max_tokens'] = maxTokens;
    if (stop != null) json['stop'] = stop;
    return json;
  }

  @override
  List<Object?> get props => [
    model,
    messages,
    stream,
    temperature,
    maxTokens,
    stop,
  ];
}

/// Represents a choice in an OpenAI-compatible chat completion response.
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

/// Represents usage statistics in an OpenAI-compatible chat completion
/// response.
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

/// Represents an OpenAI-compatible chat completion response (non-streaming).
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

/// Represents a delta (partial update) in a streaming OpenAI-compatible
/// response.
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

/// Represents a choice (partial update) in a streaming OpenAI-compatible
/// response chunk.
class ChunkChoice extends Equatable {
  const ChunkChoice({
    required this.index,
    required this.delta,
    this.finishReason,
  });

  factory ChunkChoice.fromJson(Map<String, dynamic> json) {
    return ChunkChoice(
      index: json['index'] as int,
      delta: Delta.fromJson(json['delta'] as Map<String, dynamic>),
      finishReason: json['finish_reason'] as String?,
    );
  }
  final int index;
  final Delta delta;
  final String? finishReason;

  @override
  List<Object?> get props => [index, delta, finishReason];
}

/// Represents an OpenAI-compatible streaming chat completion response chunk.
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
  final List<ChunkChoice> choices;
  final String? model;

  @override
  List<Object?> get props => [id, choices, model];
}

/// Represents information about an available model from the /v1/models
/// endpoint.
class ModelInfo extends Equatable {
  // Potentially add more fields like 'ownedBy', 'created' etc. if needed
  // For now, just the ID is sufficient.

  const ModelInfo({required this.id});

  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    return ModelInfo(id: json['id'] as String);
  }
  final String id;

  @override
  List<Object?> get props => [id];
}
