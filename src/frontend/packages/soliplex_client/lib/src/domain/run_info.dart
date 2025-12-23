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
      identical(this, other) ||
      other is NotCompleted && runtimeType == other.runtimeType;

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
      identical(this, other) ||
      other is CompletedAt &&
          runtimeType == other.runtimeType &&
          time == other.time;

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

  /// Creates run info from JSON.
  factory RunInfo.fromJson(Map<String, dynamic> json) {
    return RunInfo(
      id: json['id'] as String? ?? json['run_id'] as String,
      threadId: json['thread_id'] as String? ?? '',
      label: (json['label'] as String?) ?? '',
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
          : DateTime.now(),
      completion: json['completed_at'] != null
          ? CompletedAt(
              DateTime.tryParse(json['completed_at'] as String) ??
                  DateTime.now(),
            )
          : const NotCompleted(),
      status: RunStatus.fromString(json['status'] as String?),
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? const {},
    );
  }

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

  /// Converts the run info to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'thread_id': threadId,
      if (label.isNotEmpty) 'label': label,
      'created_at': createdAt.toIso8601String(),
      if (completion case CompletedAt(:final time))
        'completed_at': time.toIso8601String(),
      'status': status.name,
      if (metadata.isNotEmpty) 'metadata': metadata,
    };
  }

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
    return other is RunInfo && other.id == id && other.threadId == threadId;
  }

  @override
  int get hashCode => Object.hash(id, threadId);

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
  cancelled;

  /// Creates a RunStatus from a string value.
  static RunStatus fromString(String? value) {
    if (value == null) return RunStatus.pending;
    return RunStatus.values.firstWhere(
      (e) => e.name == value.toLowerCase(),
      orElse: () => RunStatus.pending,
    );
  }
}
