import 'package:meta/meta.dart';

/// User type for messages.
enum ChatUser {
  /// Human user.
  user,

  /// AI assistant.
  assistant,

  /// System-generated message.
  system,
}

/// A chat message in a conversation.
@immutable
sealed class ChatMessage {
  /// Creates a chat message with the given properties.
  const ChatMessage({
    required this.id,
    required this.user,
    required this.createdAt,
  });

  /// Unique identifier for this message.
  final String id;

  /// The user who sent this message.
  final ChatUser user;

  /// When this message was created.
  final DateTime createdAt;

  /// Generates a unique message ID.
  static String generateId() => 'msg_${DateTime.now().millisecondsSinceEpoch}';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ChatMessage &&
          runtimeType == other.runtimeType &&
          id == other.id;

  @override
  int get hashCode => id.hashCode;
}

/// A text message.
@immutable
class TextMessage extends ChatMessage {
  /// Creates a text message with all properties.
  const TextMessage({
    required super.id,
    required super.user,
    required super.createdAt,
    required this.text,
    this.isStreaming = false,
    this.thinkingText = '',
    this.isThinkingStreaming = false,
  });

  /// Creates a text message with auto-generated ID and timestamp.
  factory TextMessage.create({
    required ChatUser user,
    required String text,
    String? id,
    bool isStreaming = false,
  }) {
    return TextMessage(
      id: id ?? ChatMessage.generateId(),
      user: user,
      text: text,
      isStreaming: isStreaming,
      createdAt: DateTime.now(),
    );
  }

  /// The message text content.
  final String text;

  /// Whether this message is currently streaming.
  final bool isStreaming;

  /// The thinking/reasoning text if available.
  final String thinkingText;

  /// Whether thinking text is currently streaming.
  final bool isThinkingStreaming;

  /// Creates a copy with modified properties.
  TextMessage copyWith({
    String? id,
    ChatUser? user,
    DateTime? createdAt,
    String? text,
    bool? isStreaming,
    String? thinkingText,
    bool? isThinkingStreaming,
  }) {
    return TextMessage(
      id: id ?? this.id,
      user: user ?? this.user,
      createdAt: createdAt ?? this.createdAt,
      text: text ?? this.text,
      isStreaming: isStreaming ?? this.isStreaming,
      thinkingText: thinkingText ?? this.thinkingText,
      isThinkingStreaming: isThinkingStreaming ?? this.isThinkingStreaming,
    );
  }

  @override
  String toString() => 'TextMessage(id: $id, user: $user)';
}

/// An error message.
@immutable
class ErrorMessage extends ChatMessage {
  /// Creates an error message with all properties.
  const ErrorMessage({
    required super.id,
    required super.createdAt,
    required this.errorText,
  }) : super(user: ChatUser.system);

  /// Creates an error message with auto-generated ID and timestamp.
  factory ErrorMessage.create({required String message, String? id}) {
    return ErrorMessage(
      id: id ?? ChatMessage.generateId(),
      errorText: message,
      createdAt: DateTime.now(),
    );
  }

  /// The error message text.
  final String errorText;

  @override
  String toString() => 'ErrorMessage(id: $id, error: $errorText)';
}

/// A tool call message.
@immutable
class ToolCallMessage extends ChatMessage {
  /// Creates a tool call message with all properties.
  const ToolCallMessage({
    required super.id,
    required super.createdAt,
    required this.toolCalls,
  }) : super(user: ChatUser.assistant);

  /// Creates a tool call message with auto-generated ID and timestamp.
  factory ToolCallMessage.create({
    required List<ToolCallInfo> toolCalls,
    String? id,
  }) {
    return ToolCallMessage(
      id: id ?? ChatMessage.generateId(),
      toolCalls: toolCalls,
      createdAt: DateTime.now(),
    );
  }

  /// List of tool calls in this message.
  final List<ToolCallInfo> toolCalls;

  @override
  String toString() => 'ToolCallMessage(id: $id, calls: ${toolCalls.length})';
}

/// A generated UI message.
@immutable
class GenUiMessage extends ChatMessage {
  /// Creates a genUI message with all properties.
  const GenUiMessage({
    required super.id,
    required super.createdAt,
    required this.widgetName,
    required this.data,
  }) : super(user: ChatUser.assistant);

  /// Creates a genUI message with auto-generated ID and timestamp.
  factory GenUiMessage.create({
    required String widgetName,
    required Map<String, dynamic> data,
    String? id,
  }) {
    return GenUiMessage(
      id: id ?? ChatMessage.generateId(),
      widgetName: widgetName,
      data: data,
      createdAt: DateTime.now(),
    );
  }

  /// Name of the widget to render.
  final String widgetName;

  /// Data for the widget.
  final Map<String, dynamic> data;

  @override
  String toString() => 'GenUiMessage(id: $id, widget: $widgetName)';
}

/// A loading indicator message.
@immutable
class LoadingMessage extends ChatMessage {
  /// Creates a loading message with all properties.
  const LoadingMessage({
    required super.id,
    required super.createdAt,
  }) : super(user: ChatUser.assistant);

  /// Creates a loading message with auto-generated ID and timestamp.
  factory LoadingMessage.create({String? id}) {
    return LoadingMessage(
      id: id ?? ChatMessage.generateId(),
      createdAt: DateTime.now(),
    );
  }

  @override
  String toString() => 'LoadingMessage(id: $id)';
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

/// Information about a tool call.
@immutable
class ToolCallInfo {
  /// Creates tool call info with the given properties.
  const ToolCallInfo({
    required this.id,
    required this.name,
    this.arguments = '',
    this.status = ToolCallStatus.pending,
    this.result = '',
  });

  /// Unique identifier for this tool call.
  final String id;

  /// Name of the tool being called.
  final String name;

  /// JSON-encoded arguments for the tool.
  final String arguments;

  /// Current status of the tool call.
  final ToolCallStatus status;

  /// Result from the tool execution.
  final String result;

  /// Creates a copy with modified properties.
  ToolCallInfo copyWith({
    String? id,
    String? name,
    String? arguments,
    ToolCallStatus? status,
    String? result,
  }) {
    return ToolCallInfo(
      id: id ?? this.id,
      name: name ?? this.name,
      arguments: arguments ?? this.arguments,
      status: status ?? this.status,
      result: result ?? this.result,
    );
  }

  @override
  String toString() => 'ToolCallInfo(id: $id, name: $name, status: $status)';
}
