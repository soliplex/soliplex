import 'package:equatable/equatable.dart';
import 'package:soliplex/core/models/endpoint_models.dart';
import 'package:uuid/uuid.dart';

const _uuid = Uuid();

/// Full configuration for a saved endpoint.
///
/// This represents a complete endpoint entry in the user's saved endpoints,
/// including the base URL, type-specific configuration, and metadata.
class SavedEndpoint extends Equatable {
  const SavedEndpoint({
    required this.id,
    required this.createdAt,
    required this.updatedAt,
    required this.config,
    this.isEnabled = true,
    this.notes,
  });

  /// Create a new endpoint configuration.
  factory SavedEndpoint.create({
    required EndpointConfiguration config,
    String? notes,
  }) {
    final now = DateTime.now();
    return SavedEndpoint(
      id: _uuid.v4(),
      createdAt: now,
      updatedAt: now,
      notes: notes,
      config: config,
    );
  }

  /// Create from JSON.
  factory SavedEndpoint.fromJson(Map<String, dynamic> json) {
    return SavedEndpoint(
      id: json['id'] as String,
      isEnabled: json['is_enabled'] as bool? ?? true,
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: DateTime.parse(json['updated_at'] as String),
      notes: json['notes'] as String?,
      config: EndpointConfiguration.fromJson(
        json['config'] as Map<String, dynamic>,
      ),
    );
  }

  /// Unique identifier for this endpoint
  final String id;

  /// Whether this endpoint is enabled (can be disabled without deleting)
  final bool isEnabled;

  /// Timestamp when this endpoint was first created
  final DateTime createdAt;

  /// Timestamp when this endpoint was last modified
  final DateTime updatedAt;

  /// Optional notes about this endpoint
  final String? notes;

  /// The actual endpoint configuration (type, url, label).
  final EndpointConfiguration config;

  String get name => config.label;
  String get url => config.url;

  /// Convert to JSON.
  Map<String, dynamic> toJson() => {
    'id': id,
    'is_enabled': isEnabled,
    'created_at': createdAt.toIso8601String(),
    'updated_at': updatedAt.toIso8601String(),
    if (notes != null) 'notes': notes,
    'config': config.toJson(),
  };

  /// Create a copy with updated fields.
  SavedEndpoint copyWith({
    bool? isEnabled,
    DateTime? updatedAt,
    String? notes,
    EndpointConfiguration? config,
  }) {
    return SavedEndpoint(
      id: id,
      isEnabled: isEnabled ?? this.isEnabled,
      createdAt: createdAt,
      updatedAt: updatedAt ?? DateTime.now(),
      notes: notes ?? this.notes,
      config: config ?? this.config,
    );
  }

  /// Whether this is an AG-UI endpoint.
  bool get isAgUi => config is AgUiEndpoint;

  /// Whether this is a completions endpoint.
  bool get isCompletions => config is CompletionsEndpoint;

  @override
  List<Object?> get props => [
    id,
    isEnabled,
    createdAt,
    updatedAt,
    notes,
    config,
  ];

  @override
  String toString() =>
      'SavedEndpoint(id: $id, name: $name, url: $url, type: ${config.type})';
}
