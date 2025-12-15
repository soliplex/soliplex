import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex/core/config/feature_flags.dart';

void main() {
  group('FeatureFlags', () {
    test('defaults has all features enabled', () {
      const flags = FeatureFlags.defaults;

      expect(flags.enableEndpointManagement, isTrue);
      expect(flags.enableCustomServers, isTrue);
      expect(flags.enableNetworkInspector, isTrue);
      expect(flags.enableCompletionsEndpoints, isTrue);
    });

    test('restricted has all features disabled', () {
      const flags = FeatureFlags.restricted;

      expect(flags.enableEndpointManagement, isFalse);
      expect(flags.enableCustomServers, isFalse);
      expect(flags.enableNetworkInspector, isFalse);
      expect(flags.enableCompletionsEndpoints, isFalse);
    });

    test('fromMap creates correct flags', () {
      final flags = FeatureFlags.fromMap({
        'enableEndpointManagement': false,
        'enableCustomServers': true,
        'enableNetworkInspector': false,
        'enableCompletionsEndpoints': true,
      });

      expect(flags.enableEndpointManagement, isFalse);
      expect(flags.enableCustomServers, isTrue);
      expect(flags.enableNetworkInspector, isFalse);
      expect(flags.enableCompletionsEndpoints, isTrue);
    });

    test('fromMap uses defaults for missing keys', () {
      final flags = FeatureFlags.fromMap({'enableEndpointManagement': false});

      expect(flags.enableEndpointManagement, isFalse);
      expect(flags.enableCustomServers, isTrue); // default
      expect(flags.enableNetworkInspector, isTrue); // default
      expect(flags.enableCompletionsEndpoints, isTrue); // default
    });

    test('toMap serializes correctly', () {
      const flags = FeatureFlags(
        enableEndpointManagement: false,
        enableNetworkInspector: false,
      );

      final map = flags.toMap();

      expect(map['enableEndpointManagement'], isFalse);
      expect(map['enableCustomServers'], isTrue);
      expect(map['enableNetworkInspector'], isFalse);
      expect(map['enableCompletionsEndpoints'], isTrue);
    });

    test('copyWith overrides specific flags', () {
      const original = FeatureFlags.defaults;
      final modified = original.copyWith(enableEndpointManagement: false);

      expect(modified.enableEndpointManagement, isFalse);
      expect(modified.enableCustomServers, isTrue); // unchanged
      expect(modified.enableNetworkInspector, isTrue); // unchanged
      expect(modified.enableCompletionsEndpoints, isTrue); // unchanged
    });

    test('equality works correctly', () {
      const flags1 = FeatureFlags(enableEndpointManagement: false);
      const flags2 = FeatureFlags(enableEndpointManagement: false);
      const flags3 = FeatureFlags();

      expect(flags1, equals(flags2));
      expect(flags1, isNot(equals(flags3)));
    });
  });

  group('FeatureFlags Providers', () {
    test('featureFlagsProvider returns defaults', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final flags = container.read(featureFlagsProvider);
      expect(flags, equals(FeatureFlags.defaults));
    });

    test('provider can be overridden', () {
      final container = ProviderContainer(
        overrides: [
          featureFlagsProvider.overrideWithValue(
            const FeatureFlags(enableEndpointManagement: false),
          ),
        ],
      );
      addTearDown(container.dispose);

      final flags = container.read(featureFlagsProvider);
      expect(flags.enableEndpointManagement, isFalse);
    });

    test('individual flag providers work correctly', () {
      final container = ProviderContainer(
        overrides: [
          featureFlagsProvider.overrideWithValue(
            const FeatureFlags(
              enableEndpointManagement: false,
              enableNetworkInspector: false,
            ),
          ),
        ],
      );
      addTearDown(container.dispose);

      expect(container.read(enableEndpointManagementProvider), isFalse);
      expect(container.read(enableCustomServersProvider), isTrue);
      expect(container.read(enableNetworkInspectorProvider), isFalse);
      expect(container.read(enableCompletionsEndpointsProvider), isTrue);
    });
  });
}
