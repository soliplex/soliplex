// reason: mutable data class pattern
// ignore_for_file: avoid_equals_and_hash_code_on_mutable_classes
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Feature flags for the application.
///
/// These can be configured via:
/// - Compile-time constants (default values)
/// - Runtime overrides (for MDM/enterprise deployment)
/// - Provider overrides (for testing)
///
/// MDM Integration:
/// Enterprise deployments can override these flags via managed app
/// configuration.
/// On iOS: Use AppConfig/MDM profile
/// On Android: Use managed configurations
/// On macOS: Use managed preferences
///
/// Example MDM config (iOS plist):
/// ```xml
/// <key>com.soliplex.featureFlags</key>
/// <dict>
///   <key>enableEndpointManagement</key>
///   <false/>
/// </dict>
/// ```
class FeatureFlags {
  const FeatureFlags({
    this.enableEndpointManagement = true,
    this.enableCustomServers = true,
    this.enableNetworkInspector = true,
    this.enableCompletionsEndpoints = true,
  });

  /// Create from a map (e.g., from MDM configuration).
  factory FeatureFlags.fromMap(Map<String, dynamic> map) {
    return FeatureFlags(
      enableEndpointManagement:
          map['enableEndpointManagement'] as bool? ?? true,
      enableCustomServers: map['enableCustomServers'] as bool? ?? true,
      enableNetworkInspector: map['enableNetworkInspector'] as bool? ?? true,
      enableCompletionsEndpoints:
          map['enableCompletionsEndpoints'] as bool? ?? true,
    );
  }

  /// Whether users can add/edit/delete custom endpoints.
  ///
  /// When disabled (e.g., via MDM), users can only use pre-configured
  /// endpoints.
  /// This is useful for enterprise deployments where IT wants to control
  /// which AI services employees can connect to.
  final bool enableEndpointManagement;

  /// Whether users can connect to arbitrary AG-UI servers.
  ///
  /// When disabled, users can only connect to pre-approved servers.
  final bool enableCustomServers;

  /// Whether to show the network inspector (useful for debugging).
  ///
  /// May be disabled in production/enterprise deployments.
  final bool enableNetworkInspector;

  /// Whether to enable completions (OpenAI-compatible) endpoints.
  ///
  /// When disabled, only AG-UI servers are available.
  final bool enableCompletionsEndpoints;

  /// Default flags - all features enabled.
  static const FeatureFlags defaults = FeatureFlags();

  /// Restricted flags - for locked-down enterprise deployments.
  static const FeatureFlags restricted = FeatureFlags(
    enableEndpointManagement: false,
    enableCustomServers: false,
    enableNetworkInspector: false,
    enableCompletionsEndpoints: false,
  );

  /// Convert to map (for serialization).
  Map<String, dynamic> toMap() => {
    'enableEndpointManagement': enableEndpointManagement,
    'enableCustomServers': enableCustomServers,
    'enableNetworkInspector': enableNetworkInspector,
    'enableCompletionsEndpoints': enableCompletionsEndpoints,
  };

  /// Create a copy with some flags overridden.
  FeatureFlags copyWith({
    bool? enableEndpointManagement,
    bool? enableCustomServers,
    bool? enableNetworkInspector,
    bool? enableCompletionsEndpoints,
  }) {
    return FeatureFlags(
      enableEndpointManagement:
          enableEndpointManagement ?? this.enableEndpointManagement,
      enableCustomServers: enableCustomServers ?? this.enableCustomServers,
      enableNetworkInspector:
          enableNetworkInspector ?? this.enableNetworkInspector,
      enableCompletionsEndpoints:
          enableCompletionsEndpoints ?? this.enableCompletionsEndpoints,
    );
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is FeatureFlags &&
          runtimeType == other.runtimeType &&
          enableEndpointManagement == other.enableEndpointManagement &&
          enableCustomServers == other.enableCustomServers &&
          enableNetworkInspector == other.enableNetworkInspector &&
          enableCompletionsEndpoints == other.enableCompletionsEndpoints;

  @override
  int get hashCode => Object.hash(
    enableEndpointManagement,
    enableCustomServers,
    enableNetworkInspector,
    enableCompletionsEndpoints,
  );

  @override
  String toString() =>
      'FeatureFlags('
      'endpointMgmt: $enableEndpointManagement, '
      'customServers: $enableCustomServers, '
      'networkInspector: $enableNetworkInspector, '
      'completions: $enableCompletionsEndpoints)';
}

// =============================================================================
// Provider
// =============================================================================

/// Provider for feature flags.
///
/// Override this provider to apply MDM-managed configuration:
/// ```dart
/// ProviderScope(
///   overrides: [
///     featureFlagsProvider.overrideWithValue(
///       FeatureFlags(enableEndpointManagement: false),
///     ),
///   ],
///   child: MyApp(),
/// )
/// ```
///
/// For MDM integration, load flags from platform-specific managed config
/// before creating the ProviderScope.
final featureFlagsProvider = Provider<FeatureFlags>((ref) {
  // Default: all features enabled
  // In production, this would be overridden with MDM-loaded values
  return FeatureFlags.defaults;
});

/// Convenience providers for individual flags.

final enableEndpointManagementProvider = Provider<bool>((ref) {
  return ref.watch(featureFlagsProvider).enableEndpointManagement;
});

final enableCustomServersProvider = Provider<bool>((ref) {
  return ref.watch(featureFlagsProvider).enableCustomServers;
});

final enableNetworkInspectorProvider = Provider<bool>((ref) {
  return ref.watch(featureFlagsProvider).enableNetworkInspector;
});

final enableCompletionsEndpointsProvider = Provider<bool>((ref) {
  return ref.watch(featureFlagsProvider).enableCompletionsEndpoints;
});
