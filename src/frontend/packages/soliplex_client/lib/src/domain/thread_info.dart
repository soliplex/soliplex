import 'package:meta/meta.dart';

/// Represents a thread (conversation) in a room.
@immutable
class ThreadInfo {
  /// Creates thread info.
  const ThreadInfo({
    required this.id,
    required this.roomId,
    required this.createdAt,
    required this.updatedAt,
    this.initialRunId = '',
    this.name = '',
    this.description = '',
    this.metadata = const {},
  });

  /// Unique identifier for the thread.
  final String id;

  /// ID of the room this thread belongs to.
  final String roomId;

  /// ID of the initial run created with the thread (empty if none).
  final String initialRunId;

  /// Name of the thread (empty string if not provided).
  final String name;

  /// Description of the thread (empty string if not provided).
  final String description;

  /// When the thread was created.
  final DateTime createdAt;

  /// When the thread was last updated.
  final DateTime updatedAt;

  /// Metadata for the thread (empty map if not provided).
  final Map<String, dynamic> metadata;

  /// Whether the thread has an initial run.
  bool get hasInitialRun => initialRunId.isNotEmpty;

  /// Whether the thread has a name.
  bool get hasName => name.isNotEmpty;

  /// Whether the thread has a description.
  bool get hasDescription => description.isNotEmpty;

  /// Creates a copy of this thread info with the given fields replaced.
  ThreadInfo copyWith({
    String? id,
    String? roomId,
    String? initialRunId,
    String? name,
    String? description,
    DateTime? createdAt,
    DateTime? updatedAt,
    Map<String, dynamic>? metadata,
  }) {
    return ThreadInfo(
      id: id ?? this.id,
      roomId: roomId ?? this.roomId,
      initialRunId: initialRunId ?? this.initialRunId,
      name: name ?? this.name,
      description: description ?? this.description,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is ThreadInfo && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'ThreadInfo(id: $id, roomId: $roomId, name: $name)';
}
