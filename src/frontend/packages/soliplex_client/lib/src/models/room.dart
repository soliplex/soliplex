import 'package:meta/meta.dart';

/// Represents a room from the backend.
@immutable
class Room {
  /// Creates a room.
  const Room({
    required this.id,
    required this.name,
    this.description,
    this.metadata,
  });

  /// Creates a room from JSON.
  factory Room.fromJson(Map<String, dynamic> json) {
    return Room(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  /// Unique identifier for the room.
  final String id;

  /// Display name of the room.
  final String name;

  /// Optional description of the room.
  final String? description;

  /// Optional metadata for the room.
  final Map<String, dynamic>? metadata;

  /// Converts the room to JSON.
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      if (description != null) 'description': description,
      if (metadata != null) 'metadata': metadata,
    };
  }

  /// Creates a copy of this room with the given fields replaced.
  Room copyWith({
    String? id,
    String? name,
    String? description,
    Map<String, dynamic>? metadata,
  }) {
    return Room(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      metadata: metadata ?? this.metadata,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is Room && other.id == id;
  }

  @override
  int get hashCode => id.hashCode;

  @override
  String toString() => 'Room(id: $id, name: $name)';
}
