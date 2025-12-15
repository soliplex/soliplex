import 'package:equatable/equatable.dart';

/// Role of a message in the conversation
enum MessageRole { user, assistant, system, tool }

/// Status of a tool call
enum ToolCallStatus { pending, running, completed, failed }

/// Base class for all message types across different protocols.
///
/// This sealed class provides a common interface for messages from AG-UI,
/// completions APIs, and other future protocols. The UI can render messages
/// without knowing the underlying protocol.
sealed class UnifiedMessage extends Equatable {
  const UnifiedMessage({
    required this.id,
    required this.role,
    required this.timestamp,
    this.isStreaming = false,
  });

  /// Unique identifier for this message
  final String id;

  /// Role of the message sender
  final MessageRole role;

  /// When the message was created/received
  final DateTime timestamp;

  /// Whether the message is still being streamed
  final bool isStreaming;

  /// Create a copy with updated streaming status
  UnifiedMessage copyWithStreaming({bool streaming = false});
}

/// A text message from user or assistant
class TextMessage extends UnifiedMessage {
  const TextMessage({
    required super.id,
    required super.role,
    required super.timestamp,
    required this.content,
    this.isComplete = true,
    super.isStreaming = false,
  });

  /// The text content of the message
  final String content;

  /// Whether the message content is complete
  final bool isComplete;

  /// Create a new TextMessage with appended content
  TextMessage appendContent(String additionalContent) {
    return TextMessage(
      id: id,
      role: role,
      timestamp: timestamp,
      content: content + additionalContent,
      isComplete: isComplete,
      isStreaming: isStreaming,
    );
  }

  /// Create a finalized version of this message
  TextMessage finalize() {
    return TextMessage(
      id: id,
      role: role,
      timestamp: timestamp,
      content: content,
    );
  }

  @override
  TextMessage copyWithStreaming({bool streaming = false}) {
    return TextMessage(
      id: id,
      role: role,
      timestamp: timestamp,
      content: content,
      isComplete: isComplete,
      isStreaming: streaming,
    );
  }

  @override
  List<Object?> get props => [
    id,
    role,
    timestamp,
    content,
    isComplete,
    isStreaming,
  ];
}

/// A thinking/reasoning message from the assistant (AG-UI specific)
class ThinkingMessage extends UnifiedMessage {
  const ThinkingMessage({
    required super.id,
    required super.timestamp,
    required this.content,
    this.isFinalized = false,
    super.isStreaming = false,
  }) : super(role: MessageRole.assistant);

  /// The thinking content
  final String content;

  /// Whether the thinking is finalized
  final bool isFinalized;

  /// Create a new ThinkingMessage with appended content
  ThinkingMessage appendContent(String additionalContent) {
    return ThinkingMessage(
      id: id,
      timestamp: timestamp,
      content: content + additionalContent,
      isFinalized: isFinalized,
      isStreaming: isStreaming,
    );
  }

  /// Create a finalized version of this message
  ThinkingMessage finalize() {
    return ThinkingMessage(
      id: id,
      timestamp: timestamp,
      content: content,
      isFinalized: true,
    );
  }

  @override
  ThinkingMessage copyWithStreaming({bool streaming = false}) {
    return ThinkingMessage(
      id: id,
      timestamp: timestamp,
      content: content,
      isFinalized: isFinalized,
      isStreaming: streaming,
    );
  }

  @override
  List<Object?> get props => [
    id,
    role,
    timestamp,
    content,
    isFinalized,
    isStreaming,
  ];
}

/// A tool call made by the assistant
class ToolCallMessage extends UnifiedMessage {
  const ToolCallMessage({
    required super.id,
    required super.timestamp,
    required this.toolName,
    required this.arguments,
    this.result,
    this.status = ToolCallStatus.pending,
    this.error,
    super.isStreaming = false,
  }) : super(role: MessageRole.tool);

  /// Name of the tool being called
  final String toolName;

  /// Arguments passed to the tool
  final Map<String, dynamic> arguments;

  /// Result from the tool execution (if completed)
  final String? result;

  /// Current status of the tool call
  final ToolCallStatus status;

  /// Error message if the tool call failed
  final String? error;

  /// Update the tool call status
  ToolCallMessage copyWith({
    String? result,
    ToolCallStatus? status,
    String? error,
    bool? isStreaming,
  }) {
    return ToolCallMessage(
      id: id,
      timestamp: timestamp,
      toolName: toolName,
      arguments: arguments,
      result: result ?? this.result,
      status: status ?? this.status,
      error: error ?? this.error,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }

  @override
  ToolCallMessage copyWithStreaming({bool streaming = false}) {
    return copyWith(isStreaming: streaming);
  }

  @override
  List<Object?> get props => [
    id,
    role,
    timestamp,
    toolName,
    arguments,
    result,
    status,
    error,
    isStreaming,
  ];
}

/// A result from a tool execution
class ToolResultMessage extends UnifiedMessage {
  const ToolResultMessage({
    required super.id,
    required super.timestamp,
    required this.toolCallId,
    required this.resultData,
    this.isSuccess = true,
    this.error,
    super.isStreaming = false,
  }) : super(role: MessageRole.tool);

  /// ID of the tool call this result is for
  final String toolCallId;

  /// The result data
  final dynamic resultData;

  /// Whether the tool execution was successful
  final bool isSuccess;

  /// Error message if failed
  final String? error;

  @override
  ToolResultMessage copyWithStreaming({bool streaming = false}) {
    return ToolResultMessage(
      id: id,
      timestamp: timestamp,
      toolCallId: toolCallId,
      resultData: resultData,
      isSuccess: isSuccess,
      error: error,
      isStreaming: streaming,
    );
  }

  @override
  List<Object?> get props => [
    id,
    role,
    timestamp,
    toolCallId,
    resultData,
    isSuccess,
    error,
    isStreaming,
  ];
}

/// A system message (instructions, context)
class SystemMessage extends UnifiedMessage {
  const SystemMessage({
    required super.id,
    required super.timestamp,
    required this.content,
    super.isStreaming = false,
  }) : super(role: MessageRole.system);

  /// The system message content
  final String content;

  @override
  SystemMessage copyWithStreaming({bool streaming = false}) {
    return SystemMessage(
      id: id,
      timestamp: timestamp,
      content: content,
      isStreaming: streaming,
    );
  }

  @override
  List<Object?> get props => [id, role, timestamp, content, isStreaming];
}

/// Rich content message for AG-UI specific features (canvas, genui, etc.)
class RichContentMessage extends UnifiedMessage {
  const RichContentMessage({
    required super.id,
    required super.role,
    required super.timestamp,
    required this.contentType,
    required this.payload,
    super.isStreaming = false,
  });

  /// Type of rich content (e.g., 'canvas', 'genui', 'state')
  final String contentType;

  /// The rich content payload
  final Map<String, dynamic> payload;

  @override
  RichContentMessage copyWithStreaming({bool streaming = false}) {
    return RichContentMessage(
      id: id,
      role: role,
      timestamp: timestamp,
      contentType: contentType,
      payload: payload,
      isStreaming: streaming,
    );
  }

  @override
  List<Object?> get props => [
    id,
    role,
    timestamp,
    contentType,
    payload,
    isStreaming,
  ];
}
