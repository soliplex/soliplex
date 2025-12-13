/// Represents a room from the backend.
class Room {
  const Room({
    required this.id,
    required this.name,
    this.description,
    this.metadata,
  });

  factory Room.fromJson(Map<String, dynamic> json) {
    return Room(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  final String id;
  final String name;
  final String? description;
  final Map<String, dynamic>? metadata;

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      if (description != null) 'description': description,
      if (metadata != null) 'metadata': metadata,
    };
  }

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
