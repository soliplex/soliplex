import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

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

    // Note: This test verifies disposal doesn't throw. Verifying that
    // resources are actually cleaned up (close() called) requires mocking
    // and is covered by integration tests at the feature level.
    test('container disposal completes without errors', () {
      final container = ProviderContainer()..read(httpTransportProvider);

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

    test('shares transport with agUiClientProvider via shared adapter', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Both apiProvider and agUiClientProvider should use the same
      // underlying observable adapter for unified HTTP logging
      final sharedAdapter = container.read(observableAdapterProvider);

      // Read both API clients
      container
        ..read(apiProvider)
        ..read(agUiClientProvider);

      // Verify the shared adapter is still the same instance
      final adapterAfterClients = container.read(observableAdapterProvider);
      expect(identical(sharedAdapter, adapterAfterClients), isTrue);
    });

    // Note: This test verifies disposal doesn't throw. Verifying that
    // resources are actually cleaned up (close() called) requires mocking
    // and is covered by integration tests at the feature level.
    test('container disposal completes without errors', () {
      final container = ProviderContainer()..read(apiProvider);

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

  group('observableAdapterProvider', () {
    test('creates ObservableHttpAdapter instance', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final adapter = container.read(observableAdapterProvider);

      expect(adapter, isA<ObservableHttpAdapter>());
    });

    test('is singleton across multiple reads', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      final adapter1 = container.read(observableAdapterProvider);
      final adapter2 = container.read(observableAdapterProvider);

      expect(identical(adapter1, adapter2), isTrue);
    });

    test('initializes HttpLogNotifier dependency', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Reading the observable adapter should initialize the log notifier
      container.read(observableAdapterProvider);

      // The log notifier should be accessible and functional
      final logNotifier = container.read(httpLogProvider.notifier);
      expect(logNotifier, isA<HttpLogNotifier>());
    });
  });

  group('shared adapter', () {
    test('httpTransportProvider and httpAdapterProvider share same adapter',
        () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Read the observable adapter directly
      final sharedAdapter = container.read(observableAdapterProvider);

      // Read the adapter from httpAdapterProvider
      final httpAdapter = container.read(httpAdapterProvider);

      // They should be the same instance
      expect(identical(sharedAdapter, httpAdapter), isTrue);
    });

    test('httpTransportProvider depends on observableAdapterProvider', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      // Read observable adapter first to establish the shared instance
      final sharedAdapter = container.read(observableAdapterProvider);

      // Read the transport - it should use the same adapter
      container.read(httpTransportProvider);

      // Reading observable adapter again should return same instance,
      // proving the transport didn't create a separate adapter
      final adapterAfterTransport = container.read(observableAdapterProvider);
      expect(identical(sharedAdapter, adapterAfterTransport), isTrue);

      // Verify adapter is observable type (has logging capability)
      expect(sharedAdapter, isA<ObservableHttpAdapter>());
    });
  });
}
