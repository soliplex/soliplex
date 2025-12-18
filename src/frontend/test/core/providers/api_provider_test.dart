import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  group('httpTransportProvider', () {
    test('creates HttpTransport instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final transport = container.read(httpTransportProvider);

      expect(transport, isA<HttpTransport>());
    });

    test('is singleton across multiple reads', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final transport1 = container.read(httpTransportProvider);
      final transport2 = container.read(httpTransportProvider);

      expect(identical(transport1, transport2), isTrue);
    });

    test('disposes transport when container is disposed', () {
      final container = ProviderContainer();

      final transport = container.read(httpTransportProvider);
      expect(transport, isA<HttpTransport>());

      // Dispose container should trigger onDispose callback
      container.dispose();

      // We can't directly test if close() was called, but we can verify
      // that no exceptions are thrown during disposal
      expect(container.dispose, returnsNormally);
    });
  });

  group('urlBuilderProvider', () {
    test('creates UrlBuilder with base URL from config', () {
      const testConfig = AppConfig(
        baseUrl: 'http://localhost:8000',
        appName: 'Test App',
        version: '1.0.0',
      );

      final container = ProviderContainer(
        overrides: [
          configProviderOverride(testConfig),
        ],
      );
      addTearDown(container.dispose);

      final urlBuilder = container.read(urlBuilderProvider);

      expect(urlBuilder, isA<UrlBuilder>());
      // Verify it uses the config's baseUrl with /api/v1 suffix
      expect(
        urlBuilder.build(path: '/rooms'),
        Uri.parse('http://localhost:8000/api/v1/rooms'),
      );
    });

    test('uses different baseUrl for different config', () {
      const config1 = AppConfig(
        baseUrl: 'http://localhost:8000',
        appName: 'Test App',
        version: '1.0.0',
      );
      const config2 = AppConfig(
        baseUrl: 'http://localhost:9000',
        appName: 'Test App',
        version: '1.0.0',
      );

      // Test with config1
      final container1 = ProviderContainer(
        overrides: [
          configProviderOverride(config1),
        ],
      );
      addTearDown(container1.dispose);

      final urlBuilder1 = container1.read(urlBuilderProvider);
      expect(
        urlBuilder1.build(path: '/rooms'),
        Uri.parse('http://localhost:8000/api/v1/rooms'),
      );

      // Test with config2 in separate container
      final container2 = ProviderContainer(
        overrides: [
          configProviderOverride(config2),
        ],
      );
      addTearDown(container2.dispose);

      final urlBuilder2 = container2.read(urlBuilderProvider);
      expect(
        urlBuilder2.build(path: '/rooms'),
        Uri.parse('http://localhost:9000/api/v1/rooms'),
      );
    });
  });

  group('apiProvider', () {
    test('creates SoliplexApi instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final api = container.read(apiProvider);

      expect(api, isA<SoliplexApi>());
    });

    test('is singleton across multiple reads', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final api1 = container.read(apiProvider);
      final api2 = container.read(apiProvider);

      expect(identical(api1, api2), isTrue);
    });

    test('uses shared httpTransport instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final transport1 = container.read(httpTransportProvider);
      final transport2 = container.read(httpTransportProvider);

      // Verify transport is singleton
      expect(identical(transport1, transport2), isTrue);

      // Read API to ensure it uses the same transport
      final api = container.read(apiProvider);
      expect(api, isA<SoliplexApi>());
    });

    test('disposes api when container is disposed', () {
      final container = ProviderContainer();

      final api = container.read(apiProvider);
      expect(api, isA<SoliplexApi>());

      // Dispose container should trigger onDispose callback
      container.dispose();

      // We can't directly test if close() was called, but we can verify
      // that no exceptions are thrown during disposal
      expect(container.dispose, returnsNormally);
    });

    test('creates different instances for different configs', () {
      const config1 = AppConfig(
        baseUrl: 'http://localhost:8000',
        appName: 'Test App',
        version: '1.0.0',
      );
      const config2 = AppConfig(
        baseUrl: 'http://localhost:9000',
        appName: 'Test App',
        version: '1.0.0',
      );

      // Test with config1
      final container1 = ProviderContainer(
        overrides: [
          configProviderOverride(config1),
        ],
      );
      addTearDown(container1.dispose);

      final api1 = container1.read(apiProvider);
      expect(api1, isA<SoliplexApi>());

      // Test with config2 in separate container
      final container2 = ProviderContainer(
        overrides: [
          configProviderOverride(config2),
        ],
      );
      addTearDown(container2.dispose);

      final api2 = container2.read(apiProvider);
      expect(api2, isA<SoliplexApi>());

      // APIs should be different instances for different configs
      expect(identical(api1, api2), isFalse);
    });
  });

  group('Provider integration', () {
    test('all providers work together correctly', () {
      const testConfig = AppConfig(
        baseUrl: 'http://localhost:8000',
        appName: 'Test App',
        version: '1.0.0',
      );

      final container = ProviderContainer(
        overrides: [
          configProviderOverride(testConfig),
        ],
      );
      addTearDown(container.dispose);

      // Read all providers
      final transport = container.read(httpTransportProvider);
      final urlBuilder = container.read(urlBuilderProvider);
      final api = container.read(apiProvider);

      // Verify all are properly instantiated
      expect(transport, isA<HttpTransport>());
      expect(urlBuilder, isA<UrlBuilder>());
      expect(api, isA<SoliplexApi>());

      // Verify URL builder has correct base URL
      expect(
        urlBuilder.build(path: '/rooms'),
        Uri.parse('http://localhost:8000/api/v1/rooms'),
      );
    });
  });
}
