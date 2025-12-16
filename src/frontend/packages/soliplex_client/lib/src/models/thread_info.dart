import 'package:meta/meta.dart';

/// Represents a thread (conversation) in a room.
@immutable
class ThreadInfo {
  /// Creates thread info.
  const ThreadInfo({
    required this.id,
    required this.roomId,
    this.name,
    this.description,
    this.createdAt,
    this.updatedAt,
    this.metadata,
  });

  /// Creates thread info from JSON.
  factory ThreadInfo.fromJson(Map<String, dynamic> json) {
    return ThreadInfo(
      id: json['id'] as String? ?? json['thread_id'] as String,
      roomId: json['room_id'] as String? ?? '',
      name: json['name'] as String?,
      description: json['description'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.tryParse(json['created_at'] as String)
          : null,
      updatedAt: json['updated_at'] != null
          ? DateTime.tryParse(json['updated_at'] as String)
          : null,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  /// Unique identifier for the thread.
  final String id;

  /// ID of the room this thread belongs to.
  final String roomId;

  /// Optional name of the thread.
  final String? name;

  /// Optional description of the thread.
  final String? description;

  /// When the thread was created.
  final DateTime? createdAt;

  /// When the thread was last updated.
  final DateTime? updatedAt;

  /// Optional metadata for the thread.
  final Map<String, dynamic>? metadata;

  /// Converts the thread info to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'room_id': roomId,
      if (name != null) 'name': name,
      if (description != null) 'description': description,
      if (createdAt != null) 'created_at': createdAt!.toIso8601String(),
      if (updatedAt != null) 'updated_at': updatedAt!.toIso8601String(),
      if (metadata != null) 'metadata': metadata,
    };
  }

  /// Creates a copy of this thread info with the given fields replaced.
  ThreadInfo copyWith({
    String? id,
    String? roomId,
    String? name,
    String? description,
    DateTime? createdAt,
    DateTime? updatedAt,
    Map<String, dynamic>? metadata,
  }) {
    return ThreadInfo(
      id: id ?? this.id,
      roomId: roomId ?? this.roomId,
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
