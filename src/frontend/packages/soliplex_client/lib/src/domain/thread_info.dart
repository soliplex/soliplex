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

  /// Creates thread info from JSON.
  factory ThreadInfo.fromJson(Map<String, dynamic> json) {
    final createdAt = json['created_at'] != null
        ? DateTime.tryParse(json['created_at'] as String) ?? DateTime.now()
        : DateTime.now();
    return ThreadInfo(
      id: json['id'] as String? ?? json['thread_id'] as String,
      roomId: json['room_id'] as String? ?? '',
      initialRunId: (json['initial_run_id'] as String?) ?? '',
      name: (json['name'] as String?) ?? '',
      description: (json['description'] as String?) ?? '',
      createdAt: createdAt,
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'] as String) ?? createdAt
          : createdAt,
      metadata: (json['metadata'] as Map<String, dynamic>?) ?? const {},
    );
  }

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

  /// Converts the thread info to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'room_id': roomId,
      if (initialRunId.isNotEmpty) 'initial_run_id': initialRunId,
      if (name.isNotEmpty) 'name': name,
      if (description.isNotEmpty) 'description': description,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
      if (metadata.isNotEmpty) 'metadata': metadata,
    };
  }

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
    return other is ThreadInfo && other.id == id && other.roomId == roomId;
  }

  @override
  int get hashCode => Object.hash(id, roomId);

  @override
  String toString() => 'ThreadInfo(id: $id, roomId: $roomId, name: $name)';
}
