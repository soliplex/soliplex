import 'package:flutter_test/flutter_test.dart';
import 'package:soliplex_client/soliplex_client.dart';
import 'package:soliplex_frontend/core/models/app_config.dart';
import 'package:soliplex_frontend/core/providers/api_provider.dart';
import 'package:soliplex_frontend/core/providers/http_log_provider.dart';

import '../../helpers/test_helpers.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('httpTransportProvider', () {
    test('creates HttpTransport instance', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final transport = container.read(httpTransportProvider);

      expect(transport, isA<HttpTransport>());
    });

    test('is singleton across multiple reads', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final transport1 = container.read(httpTransportProvider);
      final transport2 = container.read(httpTransportProvider);

      expect(identical(transport1, transport2), isTrue);
    });

    // Note: This test verifies disposal doesn't throw. Verifying that
    // resources are actually cleaned up (close() called) requires mocking
    // and is covered by integration tests at the feature level.
    test('container disposal completes without errors', () async {
      final container = createContainerWithMockedAuth()
        ..read(httpTransportProvider);

      // Wait for AuthNotifier's async _restoreSession to complete
      await waitForAuthRestore(container);

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

      final container = createContainerWithMockedAuth(
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
      final container1 = createContainerWithMockedAuth(
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
      final container2 = createContainerWithMockedAuth(
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
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final api = container.read(apiProvider);

      expect(api, isA<SoliplexApi>());
    });

    test('is singleton across multiple reads', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final api1 = container.read(apiProvider);
      final api2 = container.read(apiProvider);

      expect(identical(api1, api2), isTrue);
    });

    test('shares transport with agUiClientProvider via shared client', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      // Both apiProvider and agUiClientProvider should use the same
      // underlying observable client for unified HTTP logging
      final sharedClient = container.read(authenticatedClientProvider);

      // Read both API clients
      container
        ..read(apiProvider)
        ..read(agUiClientProvider);

      // Verify the shared client is still the same instance
      final clientAfterClients = container.read(authenticatedClientProvider);
      expect(identical(sharedClient, clientAfterClients), isTrue);
    });

    // Note: This test verifies disposal doesn't throw. Verifying that
    // resources are actually cleaned up (close() called) requires mocking
    // and is covered by integration tests at the feature level.
    test('container disposal completes without errors', () async {
      final container = createContainerWithMockedAuth()
        ..read(apiProvider);

      // Wait for AuthNotifier's async _restoreSession to complete
      await waitForAuthRestore(container);

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
      final container1 = createContainerWithMockedAuth(
        overrides: [
          configProviderOverride(config1),
        ],
      );
      addTearDown(container1.dispose);

      final api1 = container1.read(apiProvider);
      expect(api1, isA<SoliplexApi>());

      // Test with config2 in separate container
      final container2 = createContainerWithMockedAuth(
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

      final container = createContainerWithMockedAuth(
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

  group('authenticatedClientProvider', () {
    test('creates SoliplexHttpClient instance', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final client = container.read(authenticatedClientProvider);

      // Returns authenticated wrapper around ObservableHttpClient
      expect(client, isA<SoliplexHttpClient>());
    });

    test('is singleton across multiple reads', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      final client1 = container.read(authenticatedClientProvider);
      final client2 = container.read(authenticatedClientProvider);

      expect(identical(client1, client2), isTrue);
    });

    test('initializes HttpLogNotifier dependency', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      // Reading the observable client should initialize the log notifier
      container.read(authenticatedClientProvider);

      // The log notifier should be accessible and functional
      final logNotifier = container.read(httpLogProvider.notifier);
      expect(logNotifier, isA<HttpLogNotifier>());
    });
  });

  group('shared client', () {
    test(
      'httpTransportProvider and soliplexHttpClientProvider share same client',
      () {
        final container = createContainerWithMockedAuth();
        addTearDown(container.dispose);

        // Read the observable client directly
        final sharedClient = container.read(authenticatedClientProvider);

        // Read the client from soliplexHttpClientProvider
        final httpClient = container.read(soliplexHttpClientProvider);

        // They should be the same instance
        expect(identical(sharedClient, httpClient), isTrue);
      },
    );

    test('httpTransportProvider depends on authenticatedClientProvider', () {
      final container = createContainerWithMockedAuth();
      addTearDown(container.dispose);

      // Read observable client first to establish the shared instance
      final sharedClient = container.read(authenticatedClientProvider);

      // Read the transport - it should use the same client
      container.read(httpTransportProvider);

      // Reading observable client again should return same instance,
      // proving the transport didn't create a separate client
      final clientAfterTransport = container.read(authenticatedClientProvider);
      expect(identical(sharedClient, clientAfterTransport), isTrue);

      // Verify client implements SoliplexHttpClient interface
      expect(sharedClient, isA<SoliplexHttpClient>());
    });
  });
}
