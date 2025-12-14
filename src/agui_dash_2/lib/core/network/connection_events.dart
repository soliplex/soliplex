/// Events emitted by the connection manager for observability.
library;

/// Base class for all connection events.
sealed class ConnectionEvent {
  /// Server ID this event belongs to (for multi-server routing).
  final String? serverId;

  final String roomId;
  final DateTime timestamp;

  ConnectionEvent({this.serverId, required this.roomId, DateTime? timestamp})
    : timestamp = timestamp ?? DateTime.now();
}

/// Session was created for a room.
class SessionCreatedEvent extends ConnectionEvent {
  final String threadId;

  SessionCreatedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    super.timestamp,
  });

  @override
  String toString() =>
      'SessionCreated(server: $serverId, room: $roomId, thread: $threadId)';
}

/// Active room was switched.
class RoomSwitchedEvent extends ConnectionEvent {
  final String? previousRoomId;

  RoomSwitchedEvent({
    super.serverId,
    required super.roomId,
    this.previousRoomId,
    super.timestamp,
  });

  @override
  String toString() =>
      'RoomSwitched(server: $serverId, from: $previousRoomId, to: $roomId)';
}

/// A run was started.
class RunStartedEvent extends ConnectionEvent {
  final String threadId;
  final String runId;

  RunStartedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    required this.runId,
    super.timestamp,
  });

  @override
  String toString() =>
      'RunStarted(server: $serverId, room: $roomId, run: $runId)';
}

/// A run was completed successfully.
class RunCompletedEvent extends ConnectionEvent {
  final String threadId;
  final String runId;

  RunCompletedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    required this.runId,
    super.timestamp,
  });

  @override
  String toString() =>
      'RunCompleted(server: $serverId, room: $roomId, run: $runId)';
}

/// A run was cancelled.
class RunCancelledEvent extends ConnectionEvent {
  final String threadId;
  final String runId;
  final String? reason;

  RunCancelledEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    required this.runId,
    this.reason,
    super.timestamp,
  });

  @override
  String toString() =>
      'RunCancelled(server: $serverId, room: $roomId, run: $runId, reason: $reason)';
}

/// A run failed with an error.
class RunFailedEvent extends ConnectionEvent {
  final String threadId;
  final String runId;
  final String error;

  RunFailedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    required this.runId,
    required this.error,
    super.timestamp,
  });

  @override
  String toString() =>
      'RunFailed(server: $serverId, room: $roomId, run: $runId, error: $error)';
}

/// Session was suspended (room switched away).
class SessionSuspendedEvent extends ConnectionEvent {
  final String threadId;

  SessionSuspendedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    super.timestamp,
  });

  @override
  String toString() => 'SessionSuspended(room: $roomId, thread: $threadId)';
}

/// Session was resumed (room switched back).
class SessionResumedEvent extends ConnectionEvent {
  final String threadId;

  SessionResumedEvent({
    super.serverId,
    required super.roomId,
    required this.threadId,
    super.timestamp,
  });

  @override
  String toString() => 'SessionResumed(room: $roomId, thread: $threadId)';
}

/// Session was disposed (cleanup).
class SessionDisposedEvent extends ConnectionEvent {
  final String? threadId;

  SessionDisposedEvent({
    super.serverId,
    required super.roomId,
    this.threadId,
    super.timestamp,
  });

  @override
  String toString() => 'SessionDisposed(room: $roomId, thread: $threadId)';
}

// =============================================================================
// TOOL EXECUTION EVENTS
// =============================================================================

/// A tool started executing.
class ToolExecutionStartedEvent extends ConnectionEvent {
  final String toolCallId;
  final String toolName;
  final Map<String, dynamic>? args;

  ToolExecutionStartedEvent({
    super.serverId,
    required super.roomId,
    required this.toolCallId,
    required this.toolName,
    this.args,
    super.timestamp,
  });

  @override
  String toString() =>
      'ToolExecutionStarted(server: $serverId, room: $roomId, tool: $toolName, callId: $toolCallId)';
}

/// A tool completed execution successfully.
class ToolExecutionCompletedEvent extends ConnectionEvent {
  final String toolCallId;
  final String? result;

  ToolExecutionCompletedEvent({
    super.serverId,
    required super.roomId,
    required this.toolCallId,
    this.result,
    super.timestamp,
  });

  @override
  String toString() =>
      'ToolExecutionCompleted(server: $serverId, room: $roomId, callId: $toolCallId)';
}

/// A tool execution failed with an error.
class ToolExecutionErrorEvent extends ConnectionEvent {
  final String toolCallId;
  final String errorMessage;

  ToolExecutionErrorEvent({
    super.serverId,
    required super.roomId,
    required this.toolCallId,
    required this.errorMessage,
    super.timestamp,
  });

  @override
  String toString() =>
      'ToolExecutionError(server: $serverId, room: $roomId, callId: $toolCallId, error: $errorMessage)';
}

/// State of a session.
enum SessionState {
  /// Session is active and processing or ready.
  active,

  /// Session is streaming a response.
  streaming,

  /// Session is backgrounded (switched away but preserved).
  backgrounded,

  /// Session is suspended (hibernated, resources released).
  suspended,

  /// Session is disposed and cannot be used.
  disposed,
}

/// Information about a connection for observer/UI.
class ConnectionInfo {
  /// Server ID this connection belongs to (for multi-server routing).
  final String? serverId;
  final String roomId;
  final String? threadId;
  final String? activeRunId;
  final SessionState state;
  final DateTime? lastActivity;

  const ConnectionInfo({
    this.serverId,
    required this.roomId,
    this.threadId,
    this.activeRunId,
    required this.state,
    this.lastActivity,
  });

  bool get isActive =>
      state == SessionState.active || state == SessionState.streaming;
  bool get isStreaming => state == SessionState.streaming;

  @override
  String toString() =>
      'ConnectionInfo(server: $serverId, room: $roomId, thread: $threadId, run: $activeRunId, state: $state)';
}
