import 'package:meta/meta.dart';

/// Represents a chat message in a conversation.
@immutable
class ChatMessage {
  /// Creates a chat message.
  const ChatMessage({
    required this.id,
    required this.user,
    required this.type,
    required this.createdAt,
    this.text,
    this.data,
    this.isStreaming = false,
    this.thinkingText,
    this.isThinkingStreaming = false,
    this.toolCalls,
    this.errorMessage,
  });

  /// Create a text message.
  factory ChatMessage.text({
    required ChatUser user,
    required String text,
    String? id,
    bool isStreaming = false,
  }) {
    return ChatMessage(
      id: id ?? _generateId(),
      user: user,
      type: MessageType.text,
      text: text,
      isStreaming: isStreaming,
      createdAt: DateTime.now(),
    );
  }

  /// Create an error message.
  factory ChatMessage.error({required String message, String? id}) {
    return ChatMessage(
      id: id ?? _generateId(),
      user: ChatUser.system,
      type: MessageType.error,
      errorMessage: message,
      createdAt: DateTime.now(),
    );
  }

  /// Create a tool call message.
  factory ChatMessage.toolCall({
    required List<ToolCallInfo> toolCalls,
    String? id,
  }) {
    return ChatMessage(
      id: id ?? _generateId(),
      user: ChatUser.assistant,
      type: MessageType.toolCall,
      toolCalls: toolCalls,
      createdAt: DateTime.now(),
    );
  }

  /// Create a GenUI message.
  factory ChatMessage.genUi({
    required String widgetName,
    required Map<String, dynamic> data,
    String? id,
  }) {
    return ChatMessage(
      id: id ?? _generateId(),
      user: ChatUser.assistant,
      type: MessageType.genUi,
      data: {'widget_name': widgetName, ...data},
      createdAt: DateTime.now(),
    );
  }

  /// Unique identifier for the message.
  final String id;

  /// The user who sent the message.
  final ChatUser user;

  /// The type of message.
  final MessageType type;

  /// The text content of the message.
  final String? text;

  /// Additional data for the message.
  final Map<String, dynamic>? data;

  /// Whether the message is currently streaming.
  final bool isStreaming;

  /// The thinking/reasoning text from the AI.
  final String? thinkingText;

  /// Whether the thinking text is currently streaming.
  final bool isThinkingStreaming;

  /// Tool calls associated with the message.
  final List<ToolCallInfo>? toolCalls;

  /// Error message if the message type is error.
  final String? errorMessage;

  /// When the message was created.
  final DateTime createdAt;

  static String _generateId() {
    return 'msg_${DateTime.now().millisecondsSinceEpoch}';
  }

  /// Creates a copy of this message with the given fields replaced.
  ChatMessage copyWith({
    String? id,
    ChatUser? user,
    MessageType? type,
    String? text,
    Map<String, dynamic>? data,
    bool? isStreaming,
    String? thinkingText,
    bool? isThinkingStreaming,
    List<ToolCallInfo>? toolCalls,
    String? errorMessage,
    DateTime? createdAt,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      user: user ?? this.user,
      type: type ?? this.type,
      text: text ?? this.text,
      data: data ?? this.data,
      isStreaming: isStreaming ?? this.isStreaming,
      thinkingText: thinkingText ?? this.thinkingText,
      isThinkingStreaming: isThinkingStreaming ?? this.isThinkingStreaming,
      toolCalls: toolCalls ?? this.toolCalls,
      errorMessage: errorMessage ?? this.errorMessage,
      createdAt: createdAt ?? this.createdAt,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is ChatMessage && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'ChatMessage(id: $id, type: $type, user: $user)';
}

/// User type for messages.
enum ChatUser {
  /// Message from the user.
  user,

  /// Message from the AI assistant.
  assistant,

  /// System message.
  system,
}

/// Type of message.
enum MessageType {
  /// Text message.
  text,

  /// Error message.
  error,

  /// Tool call message.
  toolCall,

  /// Generated UI message.
  genUi,

  /// Loading indicator message.
  loading,
}

/// Information about a tool call.
@immutable
class ToolCallInfo {
  /// Creates tool call info.
  const ToolCallInfo({
    required this.id,
    required this.name,
    this.arguments,
    this.status = ToolCallStatus.pending,
    this.result,
    this.startedAt,
    this.completedAt,
  });

  /// Unique identifier for the tool call.
  final String id;

  /// Name of the tool being called.
  final String name;

  /// Arguments passed to the tool.
  final String? arguments;

  /// Current status of the tool call.
  final ToolCallStatus status;

  /// Result of the tool call.
  final String? result;

  /// When the tool call started.
  final DateTime? startedAt;

  /// When the tool call completed.
  final DateTime? completedAt;

  /// Creates a copy of this tool call info with the given fields replaced.
  ToolCallInfo copyWith({
    String? id,
    String? name,
    String? arguments,
    ToolCallStatus? status,
    String? result,
    DateTime? startedAt,
    DateTime? completedAt,
  }) {
    return ToolCallInfo(
      id: id ?? this.id,
      name: name ?? this.name,
      arguments: arguments ?? this.arguments,
      status: status ?? this.status,
      result: result ?? this.result,
      startedAt: startedAt ?? this.startedAt,
      completedAt: completedAt ?? this.completedAt,
    );
  }

  @override
  String toString() => 'ToolCallInfo(id: $id, name: $name, status: $status)';
}

/// Status of a tool call.
enum ToolCallStatus {
  /// Tool call is pending execution.
  pending,

  /// Tool call is currently executing.
  executing,

  /// Tool call completed successfully.
  completed,

  /// Tool call failed.
  failed,
}
