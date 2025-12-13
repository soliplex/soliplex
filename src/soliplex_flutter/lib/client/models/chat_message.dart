/// Represents a chat message in a conversation.
class ChatMessage {
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

  final String id;
  final ChatUser user;
  final MessageType type;
  final String? text;
  final Map<String, dynamic>? data;
  final bool isStreaming;
  final String? thinkingText;
  final bool isThinkingStreaming;
  final List<ToolCallInfo>? toolCalls;
  final String? errorMessage;
  final DateTime createdAt;

  static String _generateId() {
    return 'msg_${DateTime.now().millisecondsSinceEpoch}';
  }

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
enum ChatUser { user, assistant, system }

/// Type of message.
enum MessageType { text, error, toolCall, genUi, loading }

/// Information about a tool call.
class ToolCallInfo {
  const ToolCallInfo({
    required this.id,
    required this.name,
    this.arguments,
    this.status = ToolCallStatus.pending,
    this.result,
    this.startedAt,
    this.completedAt,
  });

  final String id;
  final String name;
  final String? arguments;
  final ToolCallStatus status;
  final String? result;
  final DateTime? startedAt;
  final DateTime? completedAt;

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
enum ToolCallStatus { pending, executing, completed, failed }
