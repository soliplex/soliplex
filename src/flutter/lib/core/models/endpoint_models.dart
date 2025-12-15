import 'package:equatable/equatable.dart';
import 'package:flutter/material.dart'; // For IconData

enum EndpointType { agUi, completions }

extension EndpointTypeUI on EndpointType {
  String get displayName => switch (this) {
    EndpointType.agUi => 'AG-UI Server',
    EndpointType.completions => 'Completions API',
  };

  IconData get icon => switch (this) {
    EndpointType.agUi => Icons.smart_toy,
    EndpointType.completions => Icons.chat,
  };

  bool get requiresAuthByDefault => switch (this) {
    EndpointType.agUi => true,
    EndpointType.completions => true, // Usually API key
  };
}

/// Base class for endpoint configuration.
sealed class EndpointConfiguration extends Equatable {
  const EndpointConfiguration({
    required this.type,
    required this.url,
    required this.label,
  });
  final EndpointType type;
  final String url;
  final String label;

  Map<String, dynamic> toJson();

  static EndpointConfiguration fromJson(Map<String, dynamic> json) {
    final typeStr = json['type'] as String? ?? 'agUi';
    final type = EndpointType.values.firstWhere(
      (e) => e.name == typeStr,
      orElse: () => EndpointType.agUi,
    );

    switch (type) {
      case EndpointType.agUi:
        return AgUiEndpoint.fromJson(json);
      case EndpointType.completions:
        return CompletionsEndpoint.fromJson(json);
    }
  }
}

/// AG-UI Node endpoint (standard).
class AgUiEndpoint extends EndpointConfiguration {
  const AgUiEndpoint({
    required super.url,
    required super.label,
    this.requiresAuth = true,
  }) : super(type: EndpointType.agUi);

  factory AgUiEndpoint.fromJson(Map<String, dynamic> json) {
    return AgUiEndpoint(
      url: json['url'] as String,
      label: json['label'] as String? ?? 'AG-UI Server',
      requiresAuth: json['requiresAuth'] as bool? ?? true,
    );
  }
  final bool requiresAuth;

  @override
  List<Object?> get props => [type, url, label, requiresAuth];

  @override
  Map<String, dynamic> toJson() => {
    'type': type.name,
    'url': url,
    'label': label,
    'requiresAuth': requiresAuth,
  };
}

/// OpenAI-compatible Completions endpoint.
class CompletionsEndpoint extends EndpointConfiguration {
  // Note: API Keys are stored separately in SecureStorage, keyed by the server
  // ID.

  const CompletionsEndpoint({
    required super.url,
    required super.label,
    required this.model,
    this.availableModels,
    this.supportsModelDiscovery = true,
  }) : super(type: EndpointType.completions);

  factory CompletionsEndpoint.fromJson(Map<String, dynamic> json) {
    return CompletionsEndpoint(
      url: json['url'] as String,
      label: json['label'] as String? ?? 'LLM Endpoint',
      model: json['model'] as String? ?? 'gpt-3.5-turbo',
      availableModels: (json['available_models'] as List?)?.cast<String>(),
      supportsModelDiscovery: json['supports_model_discovery'] as bool? ?? true,
    );
  }
  final String model;
  final List<String>? availableModels;
  final bool supportsModelDiscovery;

  @override
  List<Object?> get props => [
    type,
    url,
    label,
    model,
    availableModels,
    supportsModelDiscovery,
  ];

  @override
  Map<String, dynamic> toJson() => {
    'type': type.name,
    'url': url,
    'label': label,
    'model': model,
    if (availableModels != null) 'available_models': availableModels,
    'supports_model_discovery': supportsModelDiscovery,
  };
}
