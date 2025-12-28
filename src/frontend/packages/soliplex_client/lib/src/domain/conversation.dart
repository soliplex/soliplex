import 'package:meta/meta.dart';

import 'package:soliplex_client/src/domain/chat_message.dart';

/// Status of a conversation.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (status) {
///   case Idle():
///     // No active run
///   case Running(:final runId):
///     // Run is active
///   case Completed():
///     // Run finished successfully
///   case Failed(:final error):
///     // Run failed
///   case Cancelled(:final reason):
///     // Run was cancelled
/// }
/// ```
@immutable
sealed class ConversationStatus {
  const ConversationStatus();
}

/// No run is currently active.
@immutable
class Idle extends ConversationStatus {
  /// Creates an idle status.
  const Idle();

  @override
  bool operator ==(Object other) => identical(this, other) || other is Idle;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'Idle()';
}

/// A run is currently executing.
@immutable
class Running extends ConversationStatus {
  /// Creates a running status with the given [runId].
  const Running({required this.runId});

  /// The ID of the current run.
  final String runId;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Running && runId == other.runId;

  @override
  int get hashCode => Object.hash(runtimeType, runId);

  @override
  String toString() => 'Running(runId: $runId)';
}

/// The run completed successfully.
@immutable
class Completed extends ConversationStatus {
  /// Creates a completed status.
  const Completed();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Completed;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'Completed()';
}

/// The run failed with an error.
@immutable
class Failed extends ConversationStatus {
  /// Creates a failed status with the given [error] message.
  const Failed({required this.error});

  /// The error message.
  final String error;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Failed && error == other.error;

  @override
  int get hashCode => Object.hash(runtimeType, error);

  @override
  String toString() => 'Failed(error: $error)';
}

/// The run was cancelled.
@immutable
class Cancelled extends ConversationStatus {
  /// Creates a cancelled status with the given [reason].
  const Cancelled({required this.reason});

  /// The reason for cancellation.
  final String reason;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is Cancelled && reason == other.reason;

  @override
  int get hashCode => Object.hash(runtimeType, reason);

  @override
  String toString() => 'Cancelled(reason: $reason)';
}

/// Aggregate root for the live state of a conversation within a thread.
///
/// A Conversation is 1:1 with a Thread and contains:
/// - Messages displayed to the user
/// - Tool calls (history, not displayed)
/// - Run status
///
/// Streaming state is managed separately in the application layer.
/// All mutation methods return a new instance (immutable).
@immutable
class Conversation {
  /// Creates a conversation with the given properties.
  const Conversation({
    required this.threadId,
    this.messages = const [],
    this.toolCalls = const [],
    this.status = const Idle(),
  });

  /// Creates an empty conversation for the given thread.
  factory Conversation.empty({required String threadId}) {
    return Conversation(threadId: threadId);
  }

  /// The ID of the thread this conversation belongs to.
  final String threadId;

  /// Messages displayed to the user.
  final List<ChatMessage> messages;

  /// Tool calls history (not displayed to user).
  final List<ToolCallInfo> toolCalls;

  /// Current status of the conversation.
  final ConversationStatus status;

  /// Whether a run is currently active.
  bool get isRunning => status is Running;

  /// Returns a new conversation with the message appended.
  Conversation withAppendedMessage(ChatMessage message) {
    return copyWith(messages: [...messages, message]);
  }

  /// Returns a new conversation with the tool call added.
  Conversation withToolCall(ToolCallInfo toolCall) {
    return copyWith(toolCalls: [...toolCalls, toolCall]);
  }

  /// Returns a new conversation with the given status.
  Conversation withStatus(ConversationStatus newStatus) {
    return copyWith(status: newStatus);
  }

  /// Creates a copy with the given fields replaced.
  Conversation copyWith({
    String? threadId,
    List<ChatMessage>? messages,
    List<ToolCallInfo>? toolCalls,
    ConversationStatus? status,
  }) {
    return Conversation(
      threadId: threadId ?? this.threadId,
      messages: messages ?? this.messages,
      toolCalls: toolCalls ?? this.toolCalls,
      status: status ?? this.status,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Conversation && threadId == other.threadId;

  @override
  int get hashCode => threadId.hashCode;

  @override
  String toString() => 'Conversation(threadId: $threadId, '
      'messages: ${messages.length}, '
      'toolCalls: ${toolCalls.length}, '
      'status: $status)';
}
