import 'package:meta/meta.dart';

/// Completion status of a run.
///
/// Use pattern matching for exhaustive handling:
/// ```dart
/// switch (completion) {
///   case NotCompleted():
///     // Run has not completed yet
///   case CompletedAt(:final time):
///     // Run completed at the given time
/// }
/// ```
@immutable
sealed class CompletionTime {
  const CompletionTime();
}

/// The run has not completed yet.
@immutable
class NotCompleted extends CompletionTime {
  /// Creates a not-completed status.
  const NotCompleted();

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is NotCompleted;

  @override
  int get hashCode => runtimeType.hashCode;

  @override
  String toString() => 'NotCompleted()';
}

/// The run completed at the given time.
@immutable
class CompletedAt extends CompletionTime {
  /// Creates a completed status with the given [time].
  const CompletedAt(this.time);

  /// When the run completed.
  final DateTime time;

  @override
  bool operator ==(Object other) =>
      identical(this, other) || other is CompletedAt && time == other.time;

  @override
  int get hashCode => Object.hash(runtimeType, time);

  @override
  String toString() => 'CompletedAt($time)';
}

/// Represents a run within a thread.
@immutable
class RunInfo {
  /// Creates run info.
  const RunInfo({
    required this.id,
    required this.threadId,
    required this.createdAt,
    this.label = '',
    this.completion = const NotCompleted(),
    this.status = RunStatus.pending,
    this.metadata = const {},
  });

  /// Unique identifier for the run.
  final String id;

  /// ID of the thread this run belongs to.
  final String threadId;

  /// Label for the run (empty string if not provided).
  final String label;

  /// When the run was created.
  final DateTime createdAt;

  /// Completion status of the run.
  final CompletionTime completion;

  /// Current status of the run.
  final RunStatus status;

  /// Metadata for the run (empty map if not provided).
  final Map<String, dynamic> metadata;

  /// Whether the run has a label.
  bool get hasLabel => label.isNotEmpty;

  /// Whether the run has completed.
  bool get isCompleted => completion is CompletedAt;

  /// Creates a copy of this run info with the given fields replaced.
  RunInfo copyWith({
    String? id,
    String? threadId,
    String? label,
    DateTime? createdAt,
    CompletionTime? completion,
    RunStatus? status,
    Map<String, dynamic>? metadata,
  }) {
    return RunInfo(
      id: id ?? this.id,
      threadId: threadId ?? this.threadId,
      label: label ?? this.label,
      createdAt: createdAt ?? this.createdAt,
      completion: completion ?? this.completion,
      status: status ?? this.status,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is RunInfo && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'RunInfo(id: $id, threadId: $threadId, status: $status)';
}

/// Status of a run.
enum RunStatus {
  /// Run is pending.
  pending,

  /// Run is currently running.
  running,

  /// Run completed successfully.
  completed,

  /// Run failed.
  failed,

  /// Run was cancelled.
  cancelled,
}
