/// Events emitted by the connection manager for observability.
library;

/// Base class for all connection events.
sealed class ConnectionEvent {
  ConnectionEvent({required this.roomId, this.serverId, DateTime? timestamp})
    : timestamp = timestamp ?? DateTime.now();

  /// Server ID this event belongs to (for multi-server routing).
  final String? serverId;

  final String roomId;
  final DateTime timestamp;
}

/// Session was created for a room.
class SessionCreatedEvent extends ConnectionEvent {
  SessionCreatedEvent({
    required super.roomId,
    required this.threadId,
    super.serverId,
    super.timestamp,
  });
  final String threadId;

  @override
  String toString() =>
      'SessionCreated(server: $serverId, room: $roomId, thread: $threadId)';
}

/// Active room was switched.
class RoomSwitchedEvent extends ConnectionEvent {
  RoomSwitchedEvent({
    required super.roomId,
    super.serverId,
    this.previousRoomId,
    super.timestamp,
  });
  final String? previousRoomId;

  @override
  String toString() =>
      'RoomSwitched(server: $serverId, from: $previousRoomId, to: $roomId)';
}

/// A run was started.
class RunStartedEvent extends ConnectionEvent {
  RunStartedEvent({
    required super.roomId,
    required this.threadId,
    required this.runId,
    super.serverId,
    super.timestamp,
  });
  final String threadId;
  final String runId;

  @override
  String toString() =>
      'RunStarted(server: $serverId, room: $roomId, run: $runId)';
}

/// A run was completed successfully.
class RunCompletedEvent extends ConnectionEvent {
  RunCompletedEvent({
    required super.roomId,
    required this.threadId,
    required this.runId,
    super.serverId,
    super.timestamp,
  });
  final String threadId;
  final String runId;

  @override
  String toString() =>
      'RunCompleted(server: $serverId, room: $roomId, run: $runId)';
}

/// A run was cancelled.
class RunCancelledEvent extends ConnectionEvent {
  RunCancelledEvent({
    required super.roomId,
    required this.threadId,
    required this.runId,
    super.serverId,
    this.reason,
    super.timestamp,
  });
  final String threadId;
  final String runId;
  final String? reason;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'RunCancelled(server: $serverId, room: $roomId, run: $runId, reason: $reason)';
}

/// A run failed with an error.
class RunFailedEvent extends ConnectionEvent {
  RunFailedEvent({
    required super.roomId,
    required this.threadId,
    required this.runId,
    required this.error,
    super.serverId,
    super.timestamp,
  });
  final String threadId;
  final String runId;
  final String error;

  @override
  String toString() =>
      'RunFailed(server: $serverId, room: $roomId, run: $runId, error: $error)';
}

/// Session was suspended (room switched away).
class SessionSuspendedEvent extends ConnectionEvent {
  SessionSuspendedEvent({
    required super.roomId,
    required this.threadId,
    super.serverId,
    super.timestamp,
  });
  final String threadId;

  @override
  String toString() => 'SessionSuspended(room: $roomId, thread: $threadId)';
}

/// Session was resumed (room switched back).
class SessionResumedEvent extends ConnectionEvent {
  SessionResumedEvent({
    required super.roomId,
    required this.threadId,
    super.serverId,
    super.timestamp,
  });
  final String threadId;

  @override
  String toString() => 'SessionResumed(room: $roomId, thread: $threadId)';
}

/// Session was disposed (cleanup).
class SessionDisposedEvent extends ConnectionEvent {
  SessionDisposedEvent({
    required super.roomId,
    super.serverId,
    this.threadId,
    super.timestamp,
  });
  final String? threadId;

  @override
  String toString() => 'SessionDisposed(room: $roomId, thread: $threadId)';
}

// =============================================================================
// TOOL EXECUTION EVENTS
// =============================================================================

/// A tool started executing.
class ToolExecutionStartedEvent extends ConnectionEvent {
  ToolExecutionStartedEvent({
    required super.roomId,
    required this.toolCallId,
    required this.toolName,
    super.serverId,
    this.args,
    super.timestamp,
  });
  final String toolCallId;
  final String toolName;
  final Map<String, dynamic>? args;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'ToolExecutionStarted(server: $serverId, room: $roomId, tool: $toolName, callId: $toolCallId)';
}

/// A tool completed execution successfully.
class ToolExecutionCompletedEvent extends ConnectionEvent {
  ToolExecutionCompletedEvent({
    required super.roomId,
    required this.toolCallId,
    super.serverId,
    this.result,
    super.timestamp,
  });
  final String toolCallId;
  final String? result;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'ToolExecutionCompleted(server: $serverId, room: $roomId, callId: $toolCallId)';
}

/// A tool execution failed with an error.
class ToolExecutionErrorEvent extends ConnectionEvent {
  ToolExecutionErrorEvent({
    required super.roomId,
    required this.toolCallId,
    required this.errorMessage,
    super.serverId,
    super.timestamp,
  });
  final String toolCallId;
  final String errorMessage;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
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
  const ConnectionInfo({
    required this.roomId,
    required this.state,
    this.serverId,
    this.threadId,
    this.activeRunId,
    this.lastActivity,
  });

  /// Server ID this connection belongs to (for multi-server routing).
  final String? serverId;
  final String roomId;
  final String? threadId;
  final String? activeRunId;
  final SessionState state;
  final DateTime? lastActivity;

  bool get isActive =>
      state == SessionState.active || state == SessionState.streaming;
  bool get isStreaming => state == SessionState.streaming;

  @override
  String toString() =>
      // ignore: lines_longer_than_80_chars (auto-documented)
      'ConnectionInfo(server: $serverId, room: $roomId, thread: $threadId, run: $activeRunId, state: $state)';
}
