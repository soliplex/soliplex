import 'package:meta/meta.dart';

/// Represents a run within a thread.
@immutable
class RunInfo {
  /// Creates run info.
  const RunInfo({
    required this.id,
    required this.threadId,
    this.label,
    this.createdAt,
    this.completedAt,
    this.status = RunStatus.pending,
    this.metadata,
  });

  /// Creates run info from JSON.
  factory RunInfo.fromJson(Map<String, dynamic> json) {
    return RunInfo(
      id: json['id'] as String? ?? json['run_id'] as String,
      threadId: json['thread_id'] as String? ?? '',
      label: json['label'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
      completedAt: json['completed_at'] != null
          ? DateTime.tryParse(json['completed_at'] as String)
          : null,
      status: RunStatus.fromString(json['status'] as String?),
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  /// Unique identifier for the run.
  final String id;

  /// ID of the thread this run belongs to.
  final String threadId;

  /// Optional label for the run.
  final String? label;

  /// When the run was created.
  final DateTime? createdAt;

  /// When the run completed.
  final DateTime? completedAt;

  /// Current status of the run.
  final RunStatus status;

  /// Optional metadata for the run.
  final Map<String, dynamic>? metadata;

  /// Converts the run info to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'thread_id': threadId,
      if (label != null) 'label': label,
      if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
      if (completedAt != null) 'completed_at': completedAt!.toIso8601String(),
      'status': status.name,
      if (metadata != null) 'metadata': metadata,
    };
  }

  /// Creates a copy of this run info with the given fields replaced.
  RunInfo copyWith({
    String? id,
    String? threadId,
    String? label,
    DateTime? createdAt,
    DateTime? completedAt,
    RunStatus? status,
    Map<String, dynamic>? metadata,
  }) {
    return RunInfo(
      id: id ?? this.id,
      threadId: threadId ?? this.threadId,
      label: label ?? this.label,
      createdAt: createdAt ?? this.createdAt,
      completedAt: completedAt ?? this.completedAt,
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
